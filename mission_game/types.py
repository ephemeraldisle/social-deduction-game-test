"""Core value objects, free of UI and controller logic."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum

COLORS = ("blue", "red", "green")
MAX_QUANTITY = 2**31 - 1


def vote_tally(votes):
    """Pool spent and bonus influence; whole tens add votes, leftovers break ties."""
    result = {}
    for side, approve in (("yes", True), ("no", False)):
        ballots = [v for v in votes if v["approve"] == approve]
        spent = sum(v.get("influence", 0) for v in ballots)
        bonus = sum(v.get("bonus", 0) for v in ballots)
        extra, remainder = divmod(spent + bonus, 10)
        result[side] = {"ballots": len(ballots), "votes": len(ballots) + extra,
                        "tokens": remainder, "spent": spent, "bonus": bonus}
    result["approved"] = ((result["yes"]["votes"], result["yes"]["tokens"])
                          > (result["no"]["votes"], result["no"]["tokens"]))
    return result


class Phase(StrEnum):
    PREPARE_SWAP = "prepare_swap"
    PREPARE_SCOUT = "prepare_scout"
    SELECT_CREW = "select_crew"
    PLEDGE = "pledge"
    VOTE = "vote"
    CONTRIBUTE = "contribute"
    AUDIT = "audit"
    REPORT = "report"
    GAME_OVER = "game_over"


class Objective(StrEnum):
    LOYALIST = "loyalist"
    SAVER = "saver"
    SPENDTHRIFT = "spendthrift"
    EXACT_CHANGE = "exact_change"
    OPPOSITION_PATRON = "opposition_patron"
    GREEN_MACHINE = "green_machine"
    CLOSE_RACE = "close_race"
    RELIABLE_PARTNER = "reliable_partner"
    PASSENGER = "passenger"
    CONTRARIAN = "contrarian"


@dataclass(frozen=True)
class ObjectiveCard:
    instance_id: str
    kind: str

    def __post_init__(self):
        if not isinstance(self.instance_id, str) or not self.instance_id:
            raise ValueError("Objective cards need a stable instance ID")
        if self.kind not in tuple(Objective):
            raise ValueError("Unknown objective type")


@dataclass(frozen=True)
class Tokens:
    blue: int = 0
    red: int = 0
    green: int = 0

    def __post_init__(self):
        if any(type(n) is not int or n < 0 for n in (self.blue, self.red, self.green)):
            raise ValueError("Token quantities must be nonnegative integers")

    @property
    def total(self):
        return self.blue + self.red + self.green

    def __add__(self, other):
        return Tokens(*(getattr(self, c) + getattr(other, c) for c in COLORS))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != set(COLORS):
            raise ValueError("A token vector needs exactly blue, red, and green")
        vector = cls(**data)
        if any(getattr(vector, c) > MAX_QUANTITY for c in COLORS):
            raise ValueError(f"Action quantities may not exceed {MAX_QUANTITY}")
        return vector


def mission_winner(pot: Tokens, threshold: int) -> str | None:
    if pot.total < threshold or pot.blue + pot.red == 0:
        return None
    return "blue" if pot.blue >= pot.red else "red"


@dataclass
class Player:
    id: str
    name: str
    team: str
    wallet: int = 5
    objective: ObjectiveCard | None = None
    ability: str = "disabled"
    ability_used: bool = False


@dataclass
class Mission:
    number: int
    threshold: int
    crew_size: int
    pot: Tokens = field(default_factory=Tokens)
    attempts: int = 1
    winner: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**{**data, "pot": Tokens(**data["pot"])})
