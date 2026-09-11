"""Authoritative mission and hidden-ability state machine. No input/output or policy calls."""

from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4

from .config import GameConfig
from . import abilities, objectives
from .rng import stream, tuple_tree
from .types import COLORS, MAX_QUANTITY, Mission, ObjectiveCard, Phase, Player, Tokens, mission_winner

SCHEMA_VERSION = 3
DEFAULT_NAMES = ("Abby", "Ben", "Casey", "Drew", "Ellis", "Fran", "Gray", "Harper")


class ActionError(ValueError):
    """A stable actor-facing validation failure; submission has no effects."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class Game:
    def __init__(self, seed=0, config=None, names=DEFAULT_NAMES, game_id=None):
        self.config = config or GameConfig()
        if len(names) != 8 or any(not isinstance(n, str) or not n.strip() for n in names):
            raise ValueError("Exactly eight nonempty player names are required")
        setup_rng = stream(seed, "setup")
        blue_count = self.config.blue_players
        teams = ["blue"] * blue_count + ["red"] * (8 - blue_count)
        setup_rng.shuffle(teams)
        self.players = [Player(f"p{i}", name, teams[i]) for i, name in enumerate(names)]
        cards = (objectives.deal(self.config.objective_deck, stream(seed, "objectives"), teams)
                 if self.config.objective_mode == "deck" else
                 [ObjectiveCard(f"loyalist-p{i}", "loyalist") for i in range(8)])
        for player, card in zip(self.players, cards):
            player.objective = card
        if self.config.abilities_enabled:
            ability_rng = stream(seed, "abilities")
            for player in self.players:
                player.ability = ability_rng.choice(abilities.KINDS)
        self.private_receipts = {p.id: [] for p in self.players}
        self.game_id = game_id or str(uuid4())  # Independent of the private seed.
        self.mission_rng = stream(seed, "missions")
        self.chairman = setup_rng.randrange(8)
        self.phase = Phase.PREPARE_SWAP if self.config.abilities_enabled else Phase.SELECT_CREW
        self.revision = 0  # Observable boundary, not sealed submission count.
        self.attempt = 1
        self.rejections = 0
        self.score = {"blue": 0, "red": 0}
        self.crew = []
        self.pledges = {}
        self.votes = []
        self.pending = {}
        self.action_log = []
        self._accepted = {}
        self.events = []
        self.resolutions = []  # Designer-only original paid contribution records.
        self.completed_missions = []
        self.last_contributions = {}
        self.frozen_result = None
        self.accounting = {"initial": 40, "income": 0, "penalty": 0, "removed": 0}
        if self.config.abilities_enabled:
            self.accounting["bonus"] = 0
        self._event("game_started", mode=self.config.mode,
                    seats=[{"id": p.id, "name": p.name} for p in self.players])
        self.mission = self._draw_mission(1)
        self.assert_invariants()

    @property
    def schema_version(self):
        return 3 if self.config.abilities_enabled else 2 if self.config.objective_mode == "deck" else 1

    @property
    def status(self):
        if self.phase == Phase.GAME_OVER:
            return "FINISHED" if self.frozen_result["winner"] else "UNRESOLVED"
        return "CLOSING" if self.frozen_result else "ACTIVE"

    def _event(self, kind, **payload):
        self.events.append({"id": len(self.events) + 1, "type": kind,
                            "attempt": self.attempt, **deepcopy(payload)})

    def _draw_mission(self, number):
        mission = Mission(number, self.mission_rng.randint(self.config.threshold_min,
                                                         self.config.threshold_max),
                          self.mission_rng.randint(self.config.crew_min, self.config.crew_max))
        self._event("mission_drawn", mission=mission.to_dict())
        return mission

    def _player(self, player_id):
        for player in self.players:
            if player.id == player_id:
                return player
        raise ActionError("unknown_seat", "Unknown player seat")

    def _eligible(self):
        # Fixed cover slots prevent participation/phase timing from announcing
        # which hidden abilities are present or still usable.
        if self.config.abilities_enabled and self.phase in (
                Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT, Phase.CONTRIBUTE, Phase.AUDIT):
            return [p.id for p in self.players]
        if self.phase == Phase.SELECT_CREW:
            return [self.players[self.chairman].id]
        if self.phase in (Phase.PLEDGE, Phase.CONTRIBUTE, Phase.REPORT):
            return list(self.crew)
        if self.phase == Phase.VOTE:
            return [self.players[(self.chairman + len(self.votes)) % 8].id]
        return []

    def _request_id(self, player_id):
        return f"{self.game_id}:{self.revision}:{player_id}"

    def pending_requests(self):
        """Trusted runner only. Do not expose batch participation to players."""
        return {pid: self._request_id(pid) for pid in self._eligible() if pid not in self.pending}

    def _action_type(self):
        return "prepare" if self.phase in (Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT) else self.phase.value

    def automatic_action(self, player_id):
        """Runner may fill a cover slot only when the seat has no decision."""
        player = self._player(player_id)
        if player_id not in self.pending_requests() or abilities.choice_spec(self, player):
            return None
        if self.phase in (Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT, Phase.AUDIT):
            return {"type": self._action_type(), "ability": None}
        if self.config.abilities_enabled and self.phase == Phase.CONTRIBUTE and player_id not in self.crew:
            return {"type": "contribute", "tokens": Tokens().to_dict(), "ability": None}
        return None

    def observe(self, player_id):
        """Build an allowlisted, detached seat view; never redact a snapshot."""
        player = self._player(player_id)
        ready = player_id in self._eligible() and player_id not in self.pending
        request_id = self._request_id(player_id) if ready else None
        spec = None
        if ready:
            spec = {"type": self._action_type()}
            if self.phase == Phase.SELECT_CREW:
                spec.update(crew_size=self.mission.crew_size, players=[p.id for p in self.players])
            elif self.phase in (Phase.PLEDGE, Phase.CONTRIBUTE):
                spec.update(colors=list(COLORS), max_total=player.wallet if player_id in self.crew else 0)
                if self.config.abilities_enabled and self.phase == Phase.CONTRIBUTE:
                    spec["on_crew"] = player_id in self.crew
            elif self.phase == Phase.VOTE:
                spec.update(max_complaints=1, complaint_required_on_no=True)
            elif self.phase == Phase.REPORT:
                spec.update(min_statements=1, max_statements=3,
                            max_quantity=MAX_QUANTITY)
            if self.config.abilities_enabled:
                spec["ability"] = abilities.choice_spec(self, player)
        private = {
            "team": player.team,
            "objective": (objectives.private_card(player, self.score, self.resolutions, self.config.missions_to_win)
                          if self.schema_version >= 2 else
                          {"id": "loyalist", "text": f"Win if {player.team.title()} wins three missions."}),
            "ability": abilities.private_card(player),
            "last_contribution": self.last_contributions.get(player_id),
            "submissions": [record for record in self.action_log if record["player_id"] == player_id],
        }
        if self.config.abilities_enabled:
            private["receipts"] = self.private_receipts[player_id]
        if self.phase == Phase.GAME_OVER:
            private["result"] = self.frozen_result["players"][player_id]
        return deepcopy({
            "schema_version": self.schema_version, "game_id": self.game_id,
            "rules_version": self.config.rules_version, "mode": self.config.mode,
            "viewer": player_id, "phase": "preparation" if self._action_type() == "prepare" else self.phase.value, "status": self.status,
            "request_id": request_id, "revision": self.revision,
            "action_spec": spec, "own_submission_received": player_id in self.pending,
            "public": {
                "players": [{"id": p.id, "name": p.name, "wallet": p.wallet} for p in self.players],
                "chairman": self.players[self.chairman].id,
                "attempt": self.attempt, "rejections": self.rejections,
                "mission": self.mission.to_dict(), "score": self.score,
                "crew": self.crew, "pledges": self.pledges, "votes": self.votes,
                "completed_missions": self.completed_missions,
                "public_badges": {p.id: p.team for p in self.players if p.ability == "standard_bearer"},
                "rules": {
                    "team_counts": {"blue": self.config.blue_players, "red": self.config.players - self.config.blue_players},
                    "contrarian_team": "blue",
                    "contrarian_enabled": "contrarian" in self.config.objective_deck and self.config.objective_mode == "deck",
                    "abilities_enabled": self.config.abilities_enabled,
                    "initiative": "Clockwise from the final proposer; preparation starts with its chairman.",
                    "threshold_range": [self.config.threshold_min, self.config.threshold_max],
                    "crew_range": [self.config.crew_min, self.config.crew_max],
                    "approval_votes": 5, "rejection_limit": 8,
                    "rejection_red_tokens": 5, "income": 1,
                    "missions_to_win": self.config.missions_to_win, "development_attempt_limit": self.config.max_attempts,
                    **({"vote_income": self.config.vote_income} if self.config.vote_income else {}),
                },
                "result": ({"winner": self.frozen_result["winner"],
                            "reason": self.frozen_result["reason"]}
                           if self.phase == Phase.GAME_OVER else None),
            },
            "private": private, "history": self.events,
        })

    def _keys(self, value, required, optional=()):
        if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
            raise ActionError("invalid_shape", f"Expected fields: {', '.join(required)}"
                              + (f"; optional: {', '.join(optional)}" if optional else ""))

    def _normalize_action(self, player_id, action):
        if not isinstance(action, dict) or action.get("type") != self._action_type():
            raise ActionError("wrong_action", f"Expected action type {self._action_type()}")
        if self.phase in (Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT, Phase.AUDIT):
            self._keys(action, ("type",), ("ability",))
            abilities.validate(self, self._player(player_id), action.get("ability"))
        elif self.phase == Phase.SELECT_CREW:
            self._keys(action, ("type", "crew"))
            crew = action["crew"]
            ids = [p.id for p in self.players]
            if (not isinstance(crew, list) or len(crew) != self.mission.crew_size
                    or any(not isinstance(pid, str) or pid not in ids for pid in crew)
                    or len(set(crew)) != len(crew)):
                raise ActionError("invalid_crew", f"Select exactly {self.mission.crew_size} distinct player IDs")
        elif self.phase in (Phase.PLEDGE, Phase.CONTRIBUTE):
            optional = ("ability",) if self.config.abilities_enabled and self.phase == Phase.CONTRIBUTE else ()
            self._keys(action, ("type", "tokens"), optional)
            try:
                tokens = Tokens.from_dict(action["tokens"])
            except ValueError as exc:
                raise ActionError("invalid_tokens", str(exc)) from exc
            if player_id not in self.crew and tokens.total:
                raise ActionError("not_on_crew", "Only crew members make ordinary deposits")
            if optional:
                abilities.validate(self, self._player(player_id), action.get("ability"))
            if tokens.total > self._player(player_id).wallet:
                raise ActionError("unaffordable", "The total exceeds your current wallet")
        elif self.phase == Phase.VOTE:
            self._keys(action, ("type", "approve"), ("complaints",))
            if type(action["approve"]) is not bool:
                raise ActionError("invalid_vote", "approve must be a boolean")
            complaints = action.get("complaints", [])
            if not isinstance(complaints, list) or len(complaints) != (0 if action["approve"] else 1):
                raise ActionError("invalid_complaints", "A No vote requires exactly one complaint; a Yes vote cannot have a complaint")
            for claim in complaints:
                self._keys(claim, (), ("modifier", "player_id", "color"))
                modifier, target, color = (claim.get(k) for k in ("modifier", "player_id", "color"))
                if (modifier not in (None, "more", "less", "exact")
                        or color not in (None, *COLORS)
                        or target not in (None, *(p.id for p in self.players))
                        or (target is None and color is None)):
                    raise ActionError("invalid_complaint", "A complaint needs a player or color and an optional modifier")
        elif self.phase == Phase.REPORT:
            self._keys(action, ("type", "statements"))
            statements = action["statements"]
            if not isinstance(statements, list) or not 1 <= len(statements) <= 3:
                raise ActionError("invalid_reports", "Submit 1 to 3 report statements")
            for claim in statements:
                self._keys(claim, ("player_id", "verb", "quantity", "color"))
                if (claim["player_id"] not in [p.id for p in self.players]
                        or claim["verb"] not in ("gave", "took") or claim["color"] not in COLORS
                        or type(claim["quantity"]) is not int or not 0 <= claim["quantity"] <= MAX_QUANTITY):
                    raise ActionError("invalid_report", "Reports need a player, gave/took, a nonnegative integer, and a color")
        return deepcopy(action)

    def submit(self, player_id, request_id, revision, action):
        """Accept once or reject without mutation. Identical retries are safe."""
        self._player(player_id)
        if not isinstance(request_id, str) or type(revision) is not int:
            raise ActionError("stale_request", "Use your current request ID and integer revision")
        # Check ownership before the receipt lookup: otherwise probing another
        # seat's request could reveal whether its sealed action has arrived.
        if request_id != f"{self.game_id}:{revision}:{player_id}":
            raise ActionError("stale_request", "There is no matching current request for your seat")
        previous = self._accepted.get(request_id)
        if previous:
            # Compare JSON types too: True must not be an identical retry of 1.
            import json
            same_action = json.dumps(previous["action"], sort_keys=True) == json.dumps(action, sort_keys=True)
            if (previous["player_id"] == player_id and previous["revision"] == revision and same_action):
                return {"accepted": True, "request_id": request_id}
            raise ActionError("conflicting_retry", "This request already has an accepted response")
        if (revision != self.revision or request_id != self._request_id(player_id)
                or player_id not in self._eligible() or player_id in self.pending):
            raise ActionError("stale_request", "There is no matching current request for your seat")
        normalized = self._normalize_action(player_id, action)
        record = {"player_id": player_id, "request_id": request_id,
                  "revision": revision, "action": normalized}
        self.action_log.append(record)
        self._accepted[request_id] = record
        if self.phase == Phase.SELECT_CREW:
            self.crew = normalized["crew"]
            self._event("crew_selected", chairman=player_id, crew=self.crew)
            self._advance(Phase.PLEDGE)
        elif self.phase == Phase.VOTE:
            vote = {"player_id": player_id, "approve": normalized["approve"],
                    "complaints": normalized.get("complaints", [])}
            self.votes.append(vote)
            self._event("vote", **vote)
            if len(self.votes) == self.config.players and self.config.vote_income:
                for player in self.players:
                    player.wallet += self.config.vote_income
                self.accounting["income"] += self.config.vote_income * self.config.players
                self._event("vote_income", amount_each=self.config.vote_income,
                            wallets={p.id: p.wallet for p in self.players})
            if len(self.votes) < 8:
                self._advance(Phase.VOTE)
            elif sum(v["approve"] for v in self.votes) >= self.config.approval_votes:
                self._event("proposal_approved", yes_votes=sum(v["approve"] for v in self.votes))
                self._advance(Phase.CONTRIBUTE)
            else:
                self.rejections += 1
                self._event("proposal_rejected", rejections=self.rejections)
                if self.rejections == self.config.rejection_limit:
                    self.crew, self.pledges = [], {}
                    if self.config.abilities_enabled:
                        self._advance(Phase.CONTRIBUTE)
                    else:
                        self._resolve(penalty=True)
                else:
                    self.chairman = (self.chairman + 1) % 8
                    self.crew, self.pledges, self.votes = [], {}, []
                    self._begin_preparation()
        else:
            self.pending[player_id] = normalized
            if len(self.pending) == len(self._eligible()):
                if self.phase in (Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT):
                    abilities.prepare(self)
                    self._advance(Phase.PREPARE_SCOUT if self.phase == Phase.PREPARE_SWAP else Phase.SELECT_CREW)
                elif self.phase == Phase.AUDIT:
                    abilities.audit(self)
                    self._advance(Phase.REPORT)
                elif self.phase == Phase.PLEDGE:
                    self.pledges = {pid: self.pending[pid]["tokens"] for pid in self.crew}
                    self._event("pledges_revealed", pledges=self.pledges)
                    self._advance(Phase.VOTE)
                elif self.phase == Phase.CONTRIBUTE:
                    self._resolve(penalty=not self.crew)
                elif self.phase == Phase.REPORT:
                    self._event("reports_revealed", reports={pid: self.pending[pid]["statements"] for pid in self.crew})
                    self._finish_attempt()
        self.assert_invariants()
        return {"accepted": True, "request_id": request_id}

    def _advance(self, phase):
        self.phase = phase
        self.pending = {}
        self.revision += 1

    def _begin_preparation(self):
        self._advance(Phase.PREPARE_SWAP if self.config.abilities_enabled else Phase.SELECT_CREW)

    def _resolve(self, penalty):
        original = {}
        if penalty:
            self.mission.pot += Tokens(red=self.config.rejection_red_tokens)
            self.accounting["penalty"] += self.config.rejection_red_tokens
        else:
            for pid in self.crew:
                tokens = Tokens(**self.pending[pid]["tokens"])
                self._player(pid).wallet -= tokens.total
                self.mission.pot += tokens
                original[pid] = tokens.to_dict()
        effects = abilities.modify(self, original, penalty) if self.config.abilities_enabled else []
        self.last_contributions = {pid: {"attempt": self.attempt, "tokens": tokens}
                                   for pid, tokens in original.items()}
        winner = mission_winner(self.mission.pot, self.mission.threshold)
        self.mission.winner = winner
        if winner:
            self.score[winner] += 1
            self.accounting["removed"] += self.mission.pot.total
            self.completed_missions.append(self.mission.to_dict())
        wallets = {p.id: p.wallet for p in self.players}
        self.resolutions.append(deepcopy({
            "attempt": self.attempt, "mission": self.mission.to_dict(),
            "penalty": penalty, "crew": self.crew, "pledges": self.pledges,
            "original_contributions": original, "wallets_before_income": wallets,
            "rejections": self.rejections,
        }))
        if self.config.abilities_enabled:
            self.resolutions[-1]["effects"] = effects
        if winner and self.score[winner] == self.config.missions_to_win:
            self._freeze(winner, "four_missions" if self.config.missions_to_win == 4 else "three_missions")
        self._event("attempt_resolved", mission=self.mission.to_dict(),
                    penalty=penalty, wallets=wallets, score=self.score)
        if self.crew:
            self._advance(Phase.AUDIT if self.config.abilities_enabled else Phase.REPORT)
        else:
            self._finish_attempt()

    def _freeze(self, winner, reason):
        results = {}
        for player in self.players:
            won = objectives.wins(player, self.score, self.resolutions, winner, self.config.missions_to_win)
            results[player.id] = {"objective": player.objective.kind, "wallet": player.wallet, "won": won}
            if self.schema_version >= 2:
                results[player.id]["text"] = objectives.result_text(player, winner, won)
        self.frozen_result = {
            "winner": winner, "reason": reason, "score": dict(self.score),
            "players": results,
        }

    def _finish_attempt(self):
        if not self.frozen_result and self.attempt >= self.config.max_attempts:
            self._freeze(None, "attempt_limit")
        if self.frozen_result:
            self._event("game_over", winner=self.frozen_result["winner"], reason=self.frozen_result["reason"])
            self._advance(Phase.GAME_OVER)
            return
        for player in self.players:
            player.wallet += self.config.income
        self.accounting["income"] += self.config.income * 8
        self._event("income", amount_each=self.config.income, wallets={p.id: p.wallet for p in self.players})
        self.chairman = (self.chairman + 1) % 8
        self.attempt += 1
        if self.mission.winner:
            self.mission = self._draw_mission(self.mission.number + 1)
        else:
            self.mission.attempts += 1
        self.crew, self.pledges, self.votes = [], {}, []
        self.rejections = 0
        self._begin_preparation()

    def assert_invariants(self):
        assert len(self.players) == self.config.players
        assert sum(p.team == "blue" for p in self.players) == self.config.blue_players
        assert sum(p.team == "red" for p in self.players) == self.config.players - self.config.blue_players
        assert len({p.objective.instance_id for p in self.players}) == 8
        assert sum(p.objective.kind == "contrarian" for p in self.players) <= 1
        assert all(p.team == "blue" for p in self.players if p.objective.kind == "contrarian")
        assert all(p.ability in (*abilities.KINDS, "disabled") and type(p.ability_used) is bool for p in self.players)
        if self.config.abilities_enabled:
            assert all(p.objective.kind != "contrarian" and p.ability != "disabled" for p in self.players)
        else:
            assert all(p.ability == "disabled" and not p.ability_used for p in self.players)
        assert all(type(p.wallet) is int and p.wallet >= 0 for p in self.players)
        assert all(getattr(self.mission.pot, c) >= 0 for c in COLORS)
        active_pot = self.mission.pot.total if not self.mission.winner else 0
        actual = sum(p.wallet for p in self.players) + active_pot + self.accounting["removed"]
        assert actual == self.accounting["initial"] + self.accounting["income"] + self.accounting["penalty"] + self.accounting.get("bonus", 0)
        assert sum(self.score.values()) == len(self.completed_missions)
        assert all(0 <= score <= self.config.missions_to_win for score in self.score.values())
        assert len(self.resolutions) == self.attempt - (self.phase not in (Phase.AUDIT, Phase.REPORT, Phase.GAME_OVER))

    def snapshot(self):
        """Trusted-only JSON state, including sealed commitments and RNG state."""
        players = [asdict(p) for p in self.players]
        for player in players:
            if self.schema_version < 3:
                player.pop("ability")
                player.pop("ability_used")
            if self.schema_version == 1:
                player.pop("objective")
        return deepcopy({
            "schema_version": self.schema_version, "config": self.config.to_dict(),
            **({"private_receipts": self.private_receipts} if self.config.abilities_enabled else {}),
            "game_id": self.game_id, "players": players,
            "mission_rng": self.mission_rng.getstate(), "mission": self.mission.to_dict(),
            "phase": self.phase.value, "revision": self.revision,
            **{name: getattr(self, name) for name in (
                "chairman", "attempt", "rejections", "score", "crew", "pledges", "votes",
                "pending", "action_log", "events", "resolutions", "completed_missions",
                "last_contributions", "frozen_result", "accounting")},
        })

    @classmethod
    def from_snapshot(cls, data):
        if data["schema_version"] not in (1, 2, SCHEMA_VERSION):
            raise ValueError("Unsupported snapshot schema version")
        game = cls.__new__(cls)
        data = deepcopy(data)
        game.config = GameConfig(**data.pop("config"))
        if data["schema_version"] != game.schema_version:
            raise ValueError("Snapshot schema does not match its rules profile")
        game.players = []
        for player in data.pop("players"):
            card = (ObjectiveCard(**player.pop("objective")) if game.schema_version >= 2
                    else ObjectiveCard(f"loyalist-{player['id']}", "loyalist"))
            game.players.append(Player(**player, objective=card))
        game.private_receipts = {p.id: [] for p in game.players}
        game.mission = Mission.from_dict(data.pop("mission"))
        game.mission_rng = stream(0, "restored")
        game.mission_rng.setstate(tuple_tree(data.pop("mission_rng")))
        game.phase = Phase(data.pop("phase"))
        data.pop("schema_version")
        for key, value in data.items():
            setattr(game, key, value)
        game._accepted = {r["request_id"]: r for r in game.action_log}
        game.assert_invariants()
        return game
