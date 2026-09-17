"""Versioned development profiles, including supported abilities-off saves."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .types import Objective

COMMON_VERSION = "0.1-common-rules-dev.3"
OBJECTIVES_VERSION = "0.1-objectives-dev.4"
LEGACY_ABILITIES_VERSION = "0.1-abilities-dev.1"
REVENUE_ABILITIES_VERSION = "0.1-abilities-dev.2"
ABILITIES_VERSION = "0.1-abilities-dev.3"
REVENUE_VERSIONS = (REVENUE_ABILITIES_VERSION, ABILITIES_VERSION)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "development_abilities.json"
DEFAULT_OBJECTIVE_DECK = ("loyalist",) * 6 + tuple(
    o.value for o in Objective if o not in (Objective.LOYALIST, Objective.CONTRARIAN))


@dataclass(frozen=True)
class GameConfig:
    rules_version: str = OBJECTIVES_VERSION
    mode: str = "development_objectives"
    players: int = 8
    starting_wallet: int = 5
    income: int = 1
    vote_income: int = 0
    blue_players: int = 5
    threshold_min: int = 8
    threshold_max: int = 12
    crew_min: int = 2
    crew_max: int = 4
    approval_votes: int = 5
    rejection_limit: int = 8
    rejection_red_tokens: int = 5
    missions_to_win: int = 3
    max_attempts: int = 100
    objective_mode: str = "deck"
    abilities_enabled: bool = False
    objective_deck: tuple[str, ...] = DEFAULT_OBJECTIVE_DECK

    def __post_init__(self):
        fixed = {
            "players": 8,
            "blue_players": 5,
            "starting_wallet": 5, "income": 1, "approval_votes": 5,
            "rejection_limit": 8, "rejection_red_tokens": 5,
            "missions_to_win": 4 if self.rules_version in REVENUE_VERSIONS else 3,
            "vote_income": 1 if self.rules_version in REVENUE_VERSIONS else 0,
        }
        for key, expected in fixed.items():
            actual = getattr(self, key)
            if type(actual) is not type(expected) or actual != expected:
                raise ValueError(f"{key} must be {expected!r} in this development rules version")
        profiles = {COMMON_VERSION: ("development_common_rules", "all_loyalist", False),
                    "0.1-objectives-dev.3": ("development_objectives", "deck", False),
                    OBJECTIVES_VERSION: ("development_objectives", "deck", False),
                    LEGACY_ABILITIES_VERSION: ("development_abilities", "deck", True),
                    REVENUE_ABILITIES_VERSION: ("development_abilities", "deck", True),
                    ABILITIES_VERSION: ("development_abilities", "deck", True)}
        if (type(self.abilities_enabled) is not bool or self.rules_version not in profiles
                or (self.mode, self.objective_mode, self.abilities_enabled) != profiles[self.rules_version]):
            raise ValueError("Rules version, mode, and objective mode must identify a supported profile")
        if (not isinstance(self.objective_deck, (list, tuple)) or len(self.objective_deck) < 8
                or any(not isinstance(kind, str) or kind not in tuple(Objective) for kind in self.objective_deck)
                or self.objective_deck.count("contrarian") > 1):
            raise ValueError("The objective deck needs at least eight valid cards and at most one Contrarian")
        object.__setattr__(self, "objective_deck", tuple(self.objective_deck))
        if self.abilities_enabled and "contrarian" in self.objective_deck:
            raise ValueError("Contrarian is disabled in the abilities profile")
        for key in ("threshold_min", "threshold_max", "crew_min", "crew_max", "max_attempts"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"{key} must be a positive integer")
        if self.rules_version == ABILITIES_VERSION:
            if self.threshold_min > self.threshold_max:
                raise ValueError("threshold_min must not exceed threshold_max")
            if not 2 <= self.crew_min <= self.crew_max <= self.players:
                raise ValueError("Crew sizes must be within 2..8")
        else:
            if not 8 <= self.threshold_min <= self.threshold_max <= 12:
                raise ValueError("Mission thresholds must be within 8..12")
            if not 2 <= self.crew_min <= self.crew_max <= 4:
                raise ValueError("Crew sizes must be within 2..4")

    def to_dict(self):
        data = asdict(self)
        if self.rules_version not in REVENUE_VERSIONS:
            data.pop("vote_income")  # Preserve historical snapshot representation.
        if self.objective_mode == "all_loyalist":
            data.pop("objective_deck")  # Preserve version-1 snapshot representation.
        else:
            data["objective_deck"] = list(self.objective_deck)
        return data

    @classmethod
    def abilities(cls, **kwargs):
        return cls(rules_version=ABILITIES_VERSION, mode="development_abilities",
                   abilities_enabled=True, **{"missions_to_win": 4, "vote_income": 1, **kwargs})

    @classmethod
    def common_rules(cls, **kwargs):
        return cls(rules_version=COMMON_VERSION, mode="development_common_rules",
                   objective_mode="all_loyalist", **kwargs)

    @classmethod
    def load(cls, path: str | Path):
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a JSON object")
        return cls(**data)
