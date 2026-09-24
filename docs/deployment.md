# GitHub Pages

The static build runs the existing Python engine and bots through Pyodide in a
Web Worker. Game actions and replay construction run on the visitor's device.
No Python server, OpenAI API key, account, or hosted database is required for
visitors. Astra example games are recorded separately before publishing.

## Build and preview

```sh
make test
python3 scripts/build_site.py
python3 -m http.server 8872 --bind 127.0.0.1 --directory dist
```

Open <http://127.0.0.1:8872/site/>. Serve the directory over HTTP; opening the
HTML file directly will not work. The `/site/` prefix also checks the relative
asset paths required by GitHub project Pages.

The build downloads a pinned Pyodide runtime, verifies its SHA-256 checksums,
and includes it in `dist/site/runtime/`. The browser downloads the runtime on
first use, so initial loading is larger than an ordinary static page. Later
visits can use the browser's HTTP cache. This is not an offline/PWA install.

To build without downloading again, pass `--runtime-dir PATH` containing the
files listed in `scripts/pyodide-runtime.json`; checksums are still verified.

## Saves

Saves persist in IndexedDB, scoped to this site's URL path. A command is only
acknowledged after its save has been flushed. Tabs share a Web Lock and reload
the persisted files before acting, so stale decisions cannot overwrite newer
ones. This needs a current browser with IndexedDB, Web Workers, and Web Locks.
Storage failures are shown to the player instead of reporting a successful save.

Saves belong to that browser profile and origin/path. Clearing site data,
private browsing cleanup, or browser storage eviction can remove them. Moving
the site to a new domain/path does not transfer local games. Browser code and
saves can be inspected by the visitor; this is practice against bots, not a
trusted competitive service. The UI still keeps hidden cards private during play.

## Featured replays

Add the final Astra saves through [`examples/manifest.json`](../examples/manifest.json).
See [`examples/README.md`](../examples/README.md). The builder explicitly packages
the game modules, configuration, player guide, and selected replay saves. It
never publishes `runs/`, API logs, or the repository root as the website.

## First deployment

1. In the GitHub repository, open **Settings → Pages → Build and deployment**
   and select **GitHub Actions** as the source.
2. Commit the application changes, `scripts/`, `examples/`, and
   `.github/workflows/pages.yml`. Generated `dist/` stays ignored.
3. Push to `main`. The workflow runs the focused checks, builds the site, and
   deploys it to Pages. Its deployment summary supplies the live URL.

For this repository, the expected address is
<https://ephemeraldisle.github.io/social-deduction-game-test/>.
The workflow also builds pull requests but does not deploy them. Later pushes
to `main` update the site automatically. A custom domain is optional.

The original local command, `python3 -m mission_game.cli web`, remains available
and continues to save files under `runs/`.

## Optional browser check

With the static preview server running and Playwright available in your Node
environment, run `node scripts/check_site.cjs`. It uses an isolated headless
Chrome profile, creates a local game and one sample replay, and checks reloads,
concurrent tabs, stale actions, replay rankings, rewind, mobile width, and that
no requests go to a game API or an external host. Screenshots go to a temporary
directory printed by the script. This is a focused deployment check, not part
of routine `make test`.
