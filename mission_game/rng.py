"""Domain-separated reproducible streams; never expose seeds to players."""

import hashlib
import random


def stream(seed: int, label: str) -> random.Random:
    digest = hashlib.sha256(f"mission-game-dev.1:{seed}:{label}".encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


def tuple_tree(value):
    """Restore random.Random's tuple-based state after a JSON round trip."""
    return tuple(tuple_tree(item) for item in value) if isinstance(value, list) else value
