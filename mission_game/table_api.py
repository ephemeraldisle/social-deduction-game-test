"""Transport-independent commands shared by the HTTP server and browser."""

from importlib.resources import files
from urllib.parse import parse_qs, unquote, urlsplit

from .table_store import WebError


def table_request(store, path, mutate=False, payload=None):
    parsed = urlsplit(path)
    if not mutate and parsed.path == "/api/bootstrap":
        return {"token": None, "games": store.catalog(),
                "guide": files("mission_game").joinpath("public_player_guide.md").read_text()}
    if parsed.path == "/api/games":
        if not mutate:
            return {"games": store.catalog()}
        if not isinstance(payload, dict) or set(payload) - {"human_seat", "demo", "paced"}:
            raise WebError(400, "Supply a seat and optional sample-game flag")
        if type(payload.get("demo", False)) is not bool or type(payload.get("paced", False)) is not bool:
            raise WebError(400, "The sample-game flag must be a boolean")
        return {"game": store.create(payload.get("human_seat", 0), payload.get("demo", False), payload.get("paced", False))}
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "games"]:
        raise WebError(404, "This page could not be found")
    game_id, operation = unquote(parts[2]), parts[3]
    if mutate and operation == "actions":
        return store.submit(game_id, payload)
    if mutate and operation == "resume":
        if not isinstance(payload, dict) or set(payload) - {"paced"} or type(payload.get("paced", False)) is not bool:
            raise WebError(400, "Supply an optional pacing preference")
        return store.resume(game_id, payload.get("paced", False))
    if mutate and operation == "advance":
        return store.step(game_id, payload)
    if not mutate and operation == "state":
        return store.state(game_id)
    if not mutate and operation == "replay":
        query = parse_qs(parsed.query)
        if set(query) - {"step", "seat", "designer", "position"}:
            raise WebError(400, "Unknown replay option")
        designer = query.get("designer", ["false"])[0]
        if designer not in ("true", "false"):
            raise WebError(400, "Choose a player or designer view")
        return store.replay(game_id, int(query.get("step", [0])[0]), query.get("seat", [None])[0],
                            designer == "true", int(query["position"][0]) if "position" in query else None)
    raise WebError(404, "This operation could not be found")
