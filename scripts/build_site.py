"""Build the self-contained GitHub Pages artifact; never publish the runs folder."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mission_game.session import Session
from mission_game.types import Phase


def bundle_runtime(destination, runtime_dir=None):
    runtime_spec = json.loads((ROOT / "scripts/pyodide-runtime.json").read_text())
    target = destination / "runtime" / runtime_spec["version"]
    target.mkdir(parents=True)
    for name, expected in runtime_spec["files"].items():
        if runtime_dir:
            data = (Path(runtime_dir) / name).read_bytes()
        else:
            with urlopen(runtime_spec["base_url"] + name, timeout=60) as response:
                data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Runtime checksum mismatch: {name}")
        (target / name).write_bytes(data)

    for name in ("PYODIDE-LICENSE.txt", "PYTHON-LICENSE.txt", "runtime-notices.txt"):
        shutil.copyfile(ROOT / "scripts" / name, target / name)


def build(destination, runtime_dir=None, examples_dir=None):
    destination = Path(destination).resolve()
    # A build may clear only a child of the ignored output directory.
    if destination == ROOT / "dist" or not destination.is_relative_to(ROOT / "dist"):
        raise ValueError("Build output must be a subdirectory of dist/")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    bundle_runtime(destination, runtime_dir)

    examples_dir = Path(examples_dir or ROOT / "examples").resolve()
    entries = json.loads((examples_dir / "manifest.json").read_text())
    if not isinstance(entries, list):
        raise ValueError("Example manifest must be a list")
    manifest, examples, ids = [], [], set()
    for entry in entries:
        path = (examples_dir / entry["file"]).resolve()
        if not path.is_relative_to(examples_dir) or path.suffix != ".json":
            raise ValueError("Each example must be a JSON save inside examples/")
        if not isinstance(entry["title"], str) or not entry["title"].strip():
            raise ValueError("Each example needs a title")
        session = Session.load(path)
        if session.game.phase != Phase.GAME_OVER:
            raise ValueError(f"Only completed games can be published: {path.name}")
        session.replay()
        game_id = session.game.game_id
        if game_id in ids:
            raise ValueError("Duplicate featured game ID")
        ids.add(game_id)
        # Use generated archive paths, not user-supplied game IDs or filenames.
        archive_path = f"examples/{len(examples)}/session.json"
        examples.append((path, archive_path))
        manifest.append({"id": game_id, "title": entry["title"], "description": entry.get("description", "")})

    with ZipFile(destination / "game.zip", "w", ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "mission_game").glob("*.py")):
            if path.name not in {"blind_runner.py", "server.py", "cli.py", "terminal.py"}:
                archive.write(path, path.relative_to(ROOT))
        for name in ("mission_game/public_player_guide.md", "configs/development_abilities.json"):
            archive.write(ROOT / name, name)
        archive.writestr("examples/manifest.json", json.dumps(manifest))
        for path, archive_path in examples:
            archive.write(path, archive_path)
    web = ROOT / "mission_game/web"
    names = ("app.js", "style.css", "browser-client.js", "browser-worker.js")
    digest = hashlib.sha256((destination / "game.zip").read_bytes())
    for name in names:
        data = (web / name).read_bytes()
        digest.update(data)
        (destination / name).write_bytes(data)
    version = digest.hexdigest()[:16]
    html = (web / "index.html").read_text()
    html = html.replace('<script src="./app.js" defer>', '<script src="./browser-client.js" defer></script>\n  <script src="./app.js" defer>')
    for name in ("app.js", "style.css", "browser-client.js"):
        html = html.replace(f'./{name}"', f'./{name}?v={version}"')
    html = html.replace('A local table for Hidden Rules Mission Game.', 'Hidden Rules Mission Game, played and saved in your browser.')
    html = html.replace('<i></i> Local table', '<i></i> Saved on this device')
    html = html.replace('This local table needs JavaScript. The terminal interface remains available with python3 -m mission_game.cli play.', 'Enable JavaScript to play this game in your browser.')
    (destination / "index.html").write_text(html)
    (destination / ".nojekyll").touch()
    print(f"Built {destination}: {len(manifest)} featured replays, runtime bundled locally")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist/site")
    parser.add_argument("--runtime-dir", type=Path, help="Use previously downloaded, checksum-verified runtime files")
    args = parser.parse_args()
    build(args.out, args.runtime_dir)
