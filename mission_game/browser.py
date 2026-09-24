"""JSON bridge for the browser worker; the same rules and saves as local play."""

import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .engine import ActionError
from .table_api import table_request
from .table_store import TableStore, WebError


class BrowserTableStore(TableStore):
    @staticmethod
    def advance(session, path):
        # The worker flushes to IndexedDB after a command completes. Rewriting
        # the growing JSON after every invisible bot turn adds no durability.
        session.run()
        session.save(path)


class BrowserApp:
    def __init__(self, root, examples_root):
        self.store = BrowserTableStore(root)
        self.examples = TableStore(examples_root)
        manifest = json.loads((Path(examples_root) / "manifest.json").read_text())
        self.featured = {entry["id"]: entry for entry in manifest}

    def catalog(self):
        featured = []
        for game in self.examples.catalog():
            entry = self.featured.get(game["id"])
            if entry:
                featured.append({**game, "title": entry["title"], "description": entry.get("description", ""),
                                 "bundled": True, "can_resume": False})
        return featured + self.store.catalog()

    def request(self, path, mutate=False, payload=None):
        parts = urlsplit(path).path.strip("/").split("/")
        store = self.examples if len(parts) == 4 and unquote(parts[2]) in self.featured else self.store
        if mutate and store is self.examples:
            raise WebError(403, "Featured replays are read-only")
        result = table_request(store, path, mutate, payload)
        if not mutate and path in ("/api/bootstrap", "/api/games"):
            result["games"] = self.catalog()
        if store is self.examples and "game" in result:
            entry = self.featured[result["game"]["id"]]
            result["game"].update(title=entry["title"], bundled=True, can_resume=False)
        return result

    def request_json(self, path, payload_json):
        try:
            payload = json.loads(payload_json) if payload_json else None
            return json.dumps({"status": 200, "data": self.request(path, bool(payload_json), payload)}, allow_nan=False)
        except ActionError as exc:
            status = 409 if exc.code in ("stale_request", "conflicting_retry") else 400
            error = {"code": exc.code, "message": str(exc)}
        except WebError as exc:
            status, error = exc.status, {"code": "web_error", "message": str(exc)}
        except (ValueError, TypeError, KeyError, AssertionError) as exc:
            status, error = 400, {"code": "invalid_request", "message": str(exc) or "Invalid saved game or request"}
        except OSError:
            status, error = 500, {"code": "storage_error", "message": "The game could not be saved in this browser."}
        return json.dumps({"status": status, "data": {"error": error}})
