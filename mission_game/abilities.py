"""Private ability cards, legal choices, and ordered hidden effects.

Only the engine calls the mutating functions. Choice validation depends on the
actor's card and public state, never on another player's hidden assignment.
"""

from copy import deepcopy

from .types import COLORS, Phase, Tokens

KINDS = ("thief", "stowaway", "auditor", "switcher", "standard_bearer", "scout", "recolorer", "echo")
ONCE = ("thief", "switcher", "scout")
TEXT = {
    "disabled": "Abilities are disabled at this table.",
    "thief": "Once per game, before an attempt resolves, request 1–3 tokens from another wallet or a Blue/Red/Green vector totaling 1–3 from the mission. Act on or off crew, including penalties. After deposits and bonuses, transfer only what remains (each mission color clips separately) to your wallet. You privately learn the actual transfer. A valid attempt consumes your use even if nothing remains. Stolen tokens cannot fund a deposit committed this attempt.",
    "stowaway": "Each attempt when off crew, optionally pay 1 wallet token to deposit 1 Blue, Red, or Green token. You need the token when committing. Available on penalty attempts, when nobody is on crew. This is an original paid deposit; it grants no report or crew credit.",
    "auditor": "After each approved attempt's public result and before reports, optionally inspect any crew member (including yourself). Privately learn their exact original paid Blue/Red/Green deposit, excluding bonuses, theft, and recoloring. You may inspect while off crew. No audit on penalty attempts.",
    "switcher": "Once per game, before a proposal, optionally exchange objectives with another player without consent. Swaps resolve clockwise from the chairman. Each affected player privately learns their final objective, without an automatic identification of the initiator. Teams, abilities, wallets, uses, and seat histories stay put. Receiving the same type still spends your use; all prior history counts for the new card.",
    "standard_bearer": "Your true Blue or Red allegiance has an official public badge throughout the game. Your objective and ability card remain private. This gives no extra tokens, immunity, or guarantee of cooperative intent. No action is needed.",
    "scout": "Once per game, before a proposal and after objective swaps, optionally inspect another player's true team. Only you receive the truthful result; the target is not notified. Objectives and abilities are not revealed. Inspecting a public badge still spends your use.",
    "recolorer": "Each attempt, optionally choose a source color and a different destination color. After theft, change 1 mission token between those colors, at no wallet cost. Act on or off crew, including penalties. Any mission token may be affected, including older deposits or bonuses. If the source color is absent when your action resolves, nothing happens. Commit before seeing results.",
    "echo": "Automatically, on an approved crew, an original paid deposit of at least 2 tokens in exactly one color adds 1 free mission token of that color. Mixed colors and deposits below 2 do not qualify. The bonus costs no wallet tokens and does not count toward paid history or pledge matching. No bonus on penalties.",
}


def private_card(player):
    return {"id": player.ability, "name": player.ability.replace("_", " ").title(),
            "text": TEXT[player.ability],
            "uses_remaining": int(not player.ability_used) if player.ability in ONCE else None}


def choice_spec(game, player):
    kind, phase = player.ability, game.phase
    if kind in ONCE and player.ability_used:
        return None
    others = [p.id for p in game.players if p.id != player.id]
    if (phase == Phase.PREPARE_SWAP and kind == "switcher"
            or phase == Phase.PREPARE_SCOUT and kind == "scout"):
        return {"id": kind, "targets": others}
    if phase == Phase.AUDIT and kind == "auditor":
        return {"id": kind, "targets": list(game.crew)}
    if phase == Phase.CONTRIBUTE:
        if kind == "stowaway" and player.id not in game.crew and player.wallet >= 1:
            return {"id": kind, "colors": list(COLORS)}
        if kind == "thief":
            return {"id": kind, "targets": others, "max_total": 3, "colors": list(COLORS)}
        if kind == "recolorer":
            return {"id": kind, "colors": list(COLORS)}
    return None


def validate(game, player, choice):
    if choice is None:
        return
    from .engine import ActionError
    spec = choice_spec(game, player)
    if spec is None:
        raise ActionError("ability_unavailable", "No ability action is available in this window")
    kind = spec["id"]
    if kind in ("switcher", "scout", "auditor"):
        game._keys(choice, ("target",))
        if choice["target"] not in spec["targets"]:
            raise ActionError("invalid_target", "Choose one of your listed targets")
    elif kind == "stowaway":
        game._keys(choice, ("color",))
        if choice["color"] not in COLORS:
            raise ActionError("invalid_color", "Choose Blue, Red, or Green")
    elif kind == "recolorer":
        game._keys(choice, ("from", "to"))
        if choice["from"] not in COLORS or choice["to"] not in COLORS or choice["from"] == choice["to"]:
            raise ActionError("invalid_color", "Choose two different colors")
    elif kind == "thief":
        if not isinstance(choice, dict):
            raise ActionError("invalid_shape", "Choose a mission or wallet source")
        if choice.get("source") == "wallet":
            game._keys(choice, ("source", "target", "amount"))
            if choice["target"] not in spec["targets"] or type(choice["amount"]) is not int or not 1 <= choice["amount"] <= 3:
                raise ActionError("invalid_theft", "Request 1–3 tokens from another wallet")
        elif choice.get("source") == "mission":
            game._keys(choice, ("source", "tokens"))
            try:
                tokens = Tokens.from_dict(choice["tokens"])
                if not 1 <= tokens.total <= 3:
                    raise ValueError("Request 1–3 mission tokens in total")
            except ValueError as exc:
                raise ActionError("invalid_theft", str(exc)) from exc
        else:
            raise ActionError("invalid_theft", "Choose a mission or wallet source")


def initiative(game):
    return [game.players[(game.chairman + i) % 8] for i in range(8)]


def receipt(game, pid, kind, **data):
    game.private_receipts[pid].append(deepcopy({"type": kind, "attempt": game.attempt,
                                               "revision": game.revision, **data}))


def prepare(game):
    affected = set()
    for player in initiative(game):
        choice = game.pending[player.id].get("ability")
        if choice is None:
            continue
        target = game._player(choice["target"])
        player.ability_used = True
        if game.phase == Phase.PREPARE_SWAP:
            player.objective, target.objective = target.objective, player.objective
            affected.update((player.id, target.id))
        else:
            receipt(game, player.id, "scout", target=target.id, team=target.team)
    for player in game.players:
        if player.id in affected:
            from .objectives import private_card as objective_card
            receipt(game, player.id, "objective_changed",
                    objective=objective_card(player, game.score, game.resolutions, game.config.missions_to_win))


def modify(game, original, penalty):
    """Deposit off-crew payments, create bonuses, transfer, then recolor."""
    actors = initiative(game)
    effects = []
    for player in actors:
        choice = game.pending[player.id].get("ability")
        if player.ability == "stowaway" and choice is not None:
            tokens = Tokens(**{choice["color"]: 1})
            player.wallet -= 1
            game.mission.pot += tokens
            original[player.id] = tokens.to_dict()
    if not penalty:
        for player in actors:
            paid = original.get(player.id, {})
            if player.ability == "echo" and player.id in game.crew and sum(paid.values()) >= 2 and sum(n > 0 for n in paid.values()) == 1:
                color = next(c for c, n in paid.items() if n)
                game.mission.pot += Tokens(**{color: 1})
                game.accounting["bonus"] += 1
                receipt(game, player.id, "echo", color=color, amount=1)
                effects.append({"player_id": player.id, "type": "echo", "color": color})
    for player in actors:
        choice = game.pending[player.id].get("ability")
        if player.ability != "thief" or choice is None:
            continue
        player.ability_used = True
        if choice["source"] == "wallet":
            target = game._player(choice["target"])
            amount = min(choice["amount"], target.wallet)
            target.wallet -= amount
            actual = {"source": "wallet", "target": target.id, "amount": amount}
        else:
            pot = game.mission.pot.to_dict()
            taken = {c: min(choice["tokens"][c], pot[c]) for c in COLORS}
            game.mission.pot = Tokens(**{c: pot[c] - taken[c] for c in COLORS})
            amount = sum(taken.values())
            actual = {"source": "mission", "tokens": taken, "amount": amount}
        player.wallet += amount
        receipt(game, player.id, "thief", **actual)
        effects.append({"player_id": player.id, "type": "thief", **actual})
    for player in actors:
        choice = game.pending[player.id].get("ability")
        if player.ability != "recolorer" or choice is None:
            continue
        pot = game.mission.pot.to_dict()
        changed = pot[choice["from"]] > 0
        if changed:
            pot[choice["from"]] -= 1
            pot[choice["to"]] += 1
            game.mission.pot = Tokens(**pot)
        # Only the user's committed choice is private knowledge; no extra
        # recoloring-result receipt is promised by this card.
        effects.append({"player_id": player.id, "type": "recolorer", **choice, "changed": changed})
    return effects


def audit(game):
    for player in initiative(game):
        choice = game.pending[player.id].get("ability")
        if choice is not None:
            receipt(game, player.id, "audit", target=choice["target"],
                    tokens=game.resolutions[-1]["original_contributions"][choice["target"]])
