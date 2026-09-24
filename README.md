# Hidden Rules Mission Game

A working game with private objectives, nine abilities, a web table,
and verified replay, built from [the design plan](hidden-rules-mission-game-plan.md).

**New web, terminal, agent, and simulation games enable abilities. Contrarian is
removed from new default deals** while balance is revisited. Nine objectives
remain active. Social computer opponents use their own cards and visible evidence;
they use private funds and uncertain public evidence.
Outdated saves are incompatible with these rules; start a fresh table.

New tables pay **every player 1 token when a crew is selected, before pledging**,
in addition to continuing-attempt income. The first team to **four missions**
wins; Close Race requires a **4–3** finish. New deals use `0.1-abilities-dev.5`
and deal eight different abilities from a pool of nine, leaving one out at random.
Wallets are private. Pledges are single quantities, assumed Blue. Vote spending
is immediate: pooled tokens give each side one extra vote per 10, with remainder
tokens breaking ties; a complete tie rejects. Ten percent of spending becomes
Green reserve, with fractional credit carried forward. Reserves join the pot
when an attempt resolves, including rejection penalties.
Green Thumb adds five free influence to every vote, without spending wallet
tokens or creating reserves. Green Machine wins with its team if at least
20 Green tokens were added to missions across the whole table, including
deposits, reserves, bonuses, and recoloring into Green.

## Run it

For the browser-only build and GitHub Pages setup, see
[deployment instructions](docs/deployment.md). It saves games on the visitor's
device and can include selected [featured replays](examples/README.md).

Python 3.11 or newer is required; this slice uses only the standard library.
From the repository root, no installation or API key is needed:

```bash
python3 -m mission_game.cli web
```

To restart the main server, including one started in an assistant-managed
terminal, open your IDE's terminal at the repository root and run:

```bash
./restart-server.sh
```

This replaces the game server on port 8765 and keeps its output in your terminal.
Press **Ctrl+C** there to stop it. Run the same command again after code changes,
then refresh the browser.

Open **http://127.0.0.1:8765**. No JavaScript build step, npm install, or external
services are needed. Leave the Python server running while using the page.

New tables read `configs/development_abilities.json` when created. It currently
sets mission thresholds to **15–30** and crew sizes to **2–5**. Edit those ranges
and create a new table; no server restart is needed. Existing tables keep their
saved settings. Use `web --config path/to/settings.json` to select another file.

- **Take a seat** creates a game against seven Social computer players.
- Each new table draws eight distinct first names from a friendly pool of 48.
  Names stay with the saved game when you resume or watch its replay.
- The eight players sit around the mission pot. Each seat shows its latest public
  action or report, crew membership, and current pledge. Only your own wallet is visible. The next
  voter or chairman is highlighted. Older statements carry their attempt or
  proposal number; reports remain labeled as claims.
- Selected players move toward the table with a **✓ Crew** badge and a strong
  outline. Their quantity-only pledges sit between their seat and the table. An unrevealed pledge is distinct from zero.
  The proposed crew is also named in the center, separately from team colors.
- **Scout** changes the revealed player's card, avatar, and badge to their team
  color and adds **Scouted**. This knowledge is visible only to your seat. Replay
  shows it only after the inspection occurred. Public badges are labeled separately.
- Click a player for their full action history, grouped by Mission and Attempt
  with the result, token changes, and a link to the full record. Use **Add to crew / Remove from
  crew** beneath their seat when you are chairman. Once the crew is full, remove
  someone before adding another player.
- Click an unknown player's **avatar** to mark them as possibly **Blue** or
  **Red**, or clear the mark. A **?** and **Your guess** keep these separate
  from confirmed allegiance. Marks are private to this browser, saved per game
  and seat, and hidden in replay. Scouting and public badges take precedence.
- **Pause**, **Next step**, and **Seconds / step** sit below the table. Zero means
  manual play; speed is remembered in this browser. Play waits for your decision.
- Attempt resolution pauses on an animated pot reveal. Completed missions get a
  winner announcement, score award, and brief celebration. A second pause keeps
  the resolved crew, pledges, and revealed contribution claims at the table until
  you continue. Replay stops at these moments too; reduced motion is respected.
- Your decision controls and private cards sit beside the table. Expand a card
  for its full rules and objective progress; opening details pauses playback.
  Other private receipts remain under
  **Private results**. Personal results explain your card independently of the
  team result. Opposition Patron and Green Machine show table-wide progress
  counters and bars even while their cards are collapsed. Each attempt's history
  result records the cumulative paid-color and Green-addition totals.
- **History** opens the complete public record and pauses playback. Filter results,
  votes and crews, or player claims; expand or collapse attempts together.
  Attempt outcomes remain accurate in every filter.
- **Compare mission tokens**, below the table, shows earlier pots and exact changes.
  Attempt and mission results show each color’s before/after amount and change.
- Every accepted decision saves automatically. Close the page whenever you
  like, then use **Resume table** from the game library.
- **Replay** opens a read-only replay without advancing the live game.
  Step backward/forward, scrub to a point, click a decision, or play the timeline.
  In completed games, changing perspective or Reveal all keeps the same
  recorded moment even when the views have different frame numbers.
  Left/Right arrow keys also step when a form control isn't focused.
- Finished games allow switching viewing seats. **Reveal all**, explicitly
  enabled, reveals teams, objectives, personal outcomes, sealed actions, and
  original deposits. New games also show **Why this bot acted**, with the saved
  personality, beliefs, evidence, forecast, and policy limitations at that replay step. Those controls are hidden for unfinished games, and the
  server rejects attempts to request that information.
- With **Reveal all** enabled, click any player to inspect their perspective and
  latest recorded rankings of the other seven players. Rankings are sorted by
  Blue preference and include pledge reliability, report credibility, and the
  evidence behind each estimate. They stay at that player's most recent recorded
  assessment until another is available; **View that decision** jumps to its
  source. Rewinding never shows assessments from later in the game.
- **Watch a sample game** generates a complete bot game for immediate review.
  Existing `session.json` and `example-replay.json` files anywhere under `runs/`
  using the current rules are discovered automatically.

Use a different port or saved-game directory if needed:

```bash
python3 -m mission_game.cli web --port 8767 --runs-dir runs
```

Local saves, simulations, and model logs under `runs/`, along with historical
notes under `docs/reviews/`, are ignored by Git. The three curated Astra replays
and their [provenance](examples/provenance.md) live in `examples/` and are
included in the public site through its manifest.

New web games are stored under `runs/web/<game-id>/session.json`. Replay never
changes a save. Saves from older development rules are not migrated;
incompatible or malformed files are omitted from the library. Refresh after a
server restart, then choose **Take a seat** to play with the current objectives and bots.

The terminal interface is still available:

```bash
python3 -m mission_game.cli play --human-seat 0 --session runs/my-game
python3 -m mission_game.cli resume runs/my-game
```

In the terminal, use `/history` for the public record and `/quit` to save and
leave. Both interfaces use the same engine and session format.

Read the [player guide](mission_game/public_player_guide.md), also available with:

```bash
python3 -m mission_game.cli guide
```

An optional isolated Python environment works without installing dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m mission_game.cli web
```

The package also supports `python3 -m pip install -e .` and the `mission-game`
console command if you prefer an installed entry point. Build tooling may need
to be downloaded for that optional installation.

## Test, simulate, and replay

```bash
make test
# Or run just the relevant part:
python3 -m unittest tests.test_game_smoke -q
node --test tests/test_current_ui.cjs

python3 -m mission_game.cli simulate \
  --config configs/development_objectives.json \
  --policy social --games 1 --seed 20260910 --out runs/social-smoke

python3 -m mission_game.cli analyze runs/social-smoke
python3 -m mission_game.cli replay runs/social-smoke/example-replay.json --seat 0
```

The default check is a small set of focused smoke checks (roughly two seconds locally):
core vote/reserve rules, privacy, affordable actions, current save/resume, complete
bot games, and the changed UI. Historical replay and detailed bot-regression tests
are not part of current validation. Do not run full historical test discovery for
routine edits. Larger simulations below are optional balance tools.

Simulation writes the exact configuration, per-game metrics in `games.jsonl`,
the selected policy/version and settings in `policies.json`, an aggregate `summary.json`,
and a replay of the first game. `--policy random` is a legal-action diagnostic;
`--policy straightforward` uses simple objective-aware heuristics. `--policy social`
is the default for new web, play, agent, and simulation sessions. Use
`--policy-config configs/policy_social.json` to tune new Social games.
Resuming never replaces saved controllers. Failures get a
saved diagnostic session and a nonzero exit status. Unresolved runs are counted
separately; they have no team or individual winner. Every simulated game also
replays its actions to check equality with its saved engine state.

Verification results are recorded in [docs/validation.md](docs/validation.md).
The HTTP integration tests open a temporary loopback port; environments with
socket restrictions must permit that local bind. Node is used only by the
optional client tests and is not required to run the game.

Replay verifies the entire recorded action sequence without invoking bots.
`--seat 0` prints only that seat's permitted public and private history. To
inspect all hidden state, explicitly use the **designer-only** command:

```bash
python3 -m mission_game.cli replay runs/social-smoke/example-replay.json --omniscient
```

Seeds, authoritative snapshots, and designer replay files contain or reproduce
private information. They stay with the trusted local runner. Live web, terminal,
and JSON adapters restrict their output to one seat, but this local development tool
does not isolate participants from files they can read on the same computer.

## JSON participant

For a source-blind AI playtest with saved team predictions, use the tool-free
model runner (requires an OpenAI API key in `OPENAI_API_KEY`):

```bash
python3 -m mission_game.blind_runner --out runs/blind-ai
```

It plays one seat through the CLI against seven Social bots. Model requests
contain only public participant documentation, that seat's observations, and
its own notes; tools are disabled and no repository, seed, saved state, or
previous conversation is sent. `--model` selects the model (default
`gpt-6-astra`); `--human-seat` selects the seat. For an existing JSON credential
file containing `OPENAI_API_KEY`, use `--api-key-file path/to/auth.json`.
An optional `--seed` fixes the deal through the trusted CLI; the seed is never
included in model requests.
The output directory must be new.

After each completed mission's reports and inspections (skipped when the game ends), the model
records all eight team probabilities before receiving subsequent play.
The completed replay's **Reveal all → AI team predictions** shows these
checkpoints and their evidence; click a mission to seek to that moment. Earlier
replay frames do not show later predictions. The run also saves `review.md`,
`team-predictions.json`, model input/output logs, and the original CLI save.
The original action log is verified before designer metadata is attached.

```bash
python3 -m mission_game.cli agent --human-seat 0 --session runs/agent-game
```

This emits JSON Lines on stdout: public instructions, then the external seat's
observation and pending action request. Send one JSON object per line on stdin:

```json
{"request_id":"<copy from observation>","revision":12,"action":{"type":"vote","approve":true,"complaints":[]}}
```

The same command resumes an existing agent session. The saved session binds the
seat; clients cannot select another actor in their payload. EOF leaves a saved
game. See the [protocol](docs/protocol.md) for every action shape and retry rules.

## Implemented behavior

- Eight secret team assignments: always five Blue and three Red;
  independently seeded setup, objective, mission, and per-controller random streams.
- Nine active objective types: Loyalist, Saver, Spendthrift, Exact Change,
  Opposition Patron, Green Machine, Close Race, Reliable Partner, and Passenger. Eight cards are
  drawn from six Loyalists and one of each other active type (14 cards total).
  Contrarian remains supported in older saves and explicit abilities-off scenarios.
- Nine abilities: Thief, Stowaway, Auditor, Switcher, Standard Bearer, Scout,
  Recolorer, Echo, and Green Thumb. A separately seeded shuffle deals eight without replacement. Private
  preparation, sealed hidden actions, ordered resolution, between-attempt audits, use
  counters, truthful receipts, and objective swaps work in play and replay.
- Crew selection, affordable sealed pledges, all eight clockwise votes,
  complaints, rejection rotation, and the five-Red penalty after eight rejections.
- Sealed deposits, persistent mission pots, funding checks, Green's special
  role, Blue ties, surplus retirement, and first-to-four victory.
- Reports with syntax validation and legal false statements; official results
  remain separate from player claims. Continuing attempts report before audits and income;
  the final attempt skips audits and reports and shows every player's win/loss result.
- Terminal wallets frozen before income; a development attempt guard that
  cannot award a victory.
- Allowlisted seat observations, isolated controller inputs, atomic snapshots,
  persisted partial batches, idempotent actions, and deterministic action replay.
- Guided terminal play, a JSON-line participant adapter, simulation metrics,
  and rule, privacy, persistence, and adapter tests.
- A responsive local web table, guided action builders, automatic save/resume,
  a saved-game library, filtered history, and verified replay with optional
  designer inspection for completed games.

## Boundaries and next work

Current Social bots (`social.16`) use the holder’s own wallet, objective, public
badges, private scouting/audits, attributed reports and accusations, public pledges,
aggregate outcomes, and inclusion requests. Confirmed teams remain certain;
receipts expose false claims and repeated accusations cannot manufacture proof.
Aggregate results offer weak shared evidence, never exact individual
payments. Pledges do not reveal actual spending or allegiance. Bots compare a
small set of affordable secret deposits. Vote bids weigh improved odds against
token cost while preserving planned contributions. Bots use the income already
received before pledging, check plausible payments above pledges near match point, and support
crews that can recover a persistent pot in stages.

Wallet-related objectives influence saving and spending; Passenger and Reliable
Partner can request crew inclusion. Reliable Partner requires paying the pledged
quantity entirely in Blue, with at least two tokens, on two approved attempts.
Red deposits may be concealed in reports. Abilities use private instructions and
simple heuristics. These are deliberately small, uncalibrated strategies; they
do not preserve previous bot behavior or promise optimal play. The older exact
wallet/payment forecasting modules remain historical code and are bypassed by
current game decisions. See [bot notes](docs/bots.md).

Old snapshots and replays are rejected rather than migrated. The saved-game
library skips incompatible files; they are not deleted from disk. Current games
still save and resume normally. See [ability notes](docs/abilities.md) for the
unchanged abilities and resolution order.

Current persistence uses atomic JSON snapshots. The web server
binds only to `127.0.0.1`; it is a trusted local tool, not a hosted multiplayer or
benchmark-isolation service. It checks request origins and uses a per-server
token for mutations. Reveal all intentionally exposes finished-game secrets.

Objective predicates and private progress live in `mission_game/objectives.py`.
New web and CLI games load `configs/development_abilities.json` by default.
Use `--config configs/development_objectives.json` for an abilities-off comparison,
or `--config configs/development_common_rules.json` for all-Loyalist practice.
The low-level `GameConfig()` retains the objectives-only profile; use
`GameConfig.abilities()` to construct the full rules explicitly. Direct Python
`Session()` calls use those built-in settings; pass `GameConfig.load(path)` to
use an editable file there too.
Simulation summaries include per-objective holders, personal conditions, and
individual wins; these files contain designer information.

The engine is in `mission_game/engine.py`; value objects and configuration are
separate from controllers, session persistence, adapters, and CLI tools. Static
browser assets live in `mission_game/web/`; `server.py` binds requests to the
saved human seat, and `replay.py` constructs observable replay steps. The UI
prevents incomplete input; the Python engine authoritatively validates every
action and resolves the game. The root design document remains the
source of truth for the full prototype.
