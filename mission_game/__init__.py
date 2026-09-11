"""Hidden Rules Mission Game: common-rules development slice.

Authoritative Game objects belong to trusted runners. Controllers receive only
the dictionaries returned by Game.observe for their bound seat.
"""

from .config import GameConfig
from .engine import ActionError, Game

__all__ = ["ActionError", "Game", "GameConfig"]
