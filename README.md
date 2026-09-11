# Hidden Rules Mission Game

A working game with private objectives, all eight hidden abilities, a web table,
and verified replay, built from [the design plan](hidden-rules-mission-game-plan.md).

**New web, terminal, agent, and simulation games enable abilities. Contrarian is
removed from new default deals** while balance is revisited. Eight objectives
remain active. Social computer opponents use their own cards and visible evidence;
they plan abilities and payments together, using heuristic outcome estimates.
Existing supported saves retain their original rules and cards.

New tables pay **every player 1 token after each full vote**, pass or fail,
in addition to continuing-attempt income. The first team to **four missions**
wins; Close Race requires a **4–3** finish. These rules use `0.1-abilities-dev.2`.
Start a new table to play with them.

## Run it

Python 3.11 or newer is required; this slice uses only the standard library.
From the repository root, no installation or API key is needed:

```bash
python3 -m mission_game.cli web
```

Open **http://127.0.0.1:8765**. No JavaScript build step, npm install, or external
services are needed. Leave the Python server running while using the page.

- **Take a seat** creates a game against seven Social computer players.
- Enter your preferred **Seconds / step** (decimals allowed; zero for manual),
  or use **Pause** and **Next step**.
  Public votes and phase transitions advance individually; play waits for your
  decision. The last-step panel names the latest voter and reason or shows the
  revealed pledges. Speed is remembered in this browser.
- Click a player for their public actions, votes, and reports. Each vote includes
  the chairman and full proposed crew.
  Your own private decisions are shown only in your history. Use the separate
  **Add to crew / Remove from crew** buttons to select a crew.
- Expand **Compare mission tokens** to see an earlier pot beside the current one, with
  exact color and total changes. Wallet cards show a compact mission-resolution
  change; hover it for before/after balances. Income updates balances quietly.
- Mission funding, scores, wallets, pledges, votes, and No-vote complaints remain
  visible together. Previous-proposal complaints stay visible until voting begins again.
  Your private objective and ability show short reminders above your controls.
  Expand either caret for full rules and objective progress; private results
  also start collapsed.
  Personal results explain whether you fulfilled your card, independently of
  the team result. Opposition Patron’s global counter stays hidden.
- **What happened** groups public history by attempt. Filter official results
  or player claims; expand a result to inspect wallets at resolution.
- Every accepted decision saves automatically. Close the page whenever you
  like, then use **Resume table** from the game library.
- **Review so far** opens a read-only replay without advancing the live game.
  Step backward/forward, scrub to a point, click a decision, or play the timeline.
  Left/Right arrow keys also step when a form control isn't focused.
- Finished games allow switching viewing seats. **Designer view**, explicitly
  enabled, reveals teams, objectives, personal outcomes, sealed actions, and
  original deposits. New games also show **Why this bot acted**, with the saved
  personality, beliefs, evidence, forecast, and policy limitations at that replay step. Those controls are hidden for unfinished games, and the
  server rejects attempts to request that information.
- **Watch a sample game** generates a complete bot game for immediate review.
  Existing `session.json` and `example-replay.json` files anywhere under `runs/`
  using the current rules are discovered automatically.

Use a different port or saved-game directory if needed:

```bash
python3 -m mission_game.cli web --port 8767 --runs-dir runs
```

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
python3 -m unittest discover -s tests -v

# Optional client-logic tests, if Node.js is installed:
node --test tests/test_web_ui.cjs

python3 -m mission_game.cli simulate \
  --config configs/development_objectives.json \
  --policy social --games 100 --seed 20260910 --out runs/social-smoke

python3 -m mission_game.cli analyze runs/social-smoke
python3 -m mission_game.cli replay runs/social-smoke/example-replay.json --seat 0
```

Simulation writes the exact configuration, per-game metrics in `games.jsonl`,
the selected policy/version and settings in `policies.json`, an aggregate `summary.json`,
and a replay of the first game. `--policy random` retains the original diagnostic
controller; `--policy straightforward` retains the previous baseline. `--policy social`
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
- Eight active objective types: Loyalist, Saver, Spendthrift, Exact Change,
  Opposition Patron, Close Race, Reliable Partner, and Passenger. Eight cards are
  drawn from six Loyalists and one of each other active type (13 cards total).
  Contrarian remains supported in older saves and explicit abilities-off scenarios.
- All eight abilities: Thief, Stowaway, Auditor, Switcher, Standard Bearer, Scout,
  Recolorer, and Echo. Independently seeded assignments allow duplicates. Private
  preparation, sealed hidden actions, ordered resolution, closing audits, use
  counters, truthful receipts, and objective swaps work in play and replay.
- Crew selection, affordable sealed pledges, all eight clockwise votes,
  complaints, rejection rotation, and the five-Red penalty after eight rejections.
- Sealed deposits, persistent mission pots, funding checks, Green's special
  role, Blue ties, surplus retirement, and first-to-four victory.
- Reports with syntax validation and legal false statements; official results
  remain separate from player claims. Reports close before income or game end.
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

Social bots analyze promises, outcomes, votes, crew choices, and attributed
reports. They track Blue preference, pledge reliability, report credibility,
and inclusion demands separately. A highly selfish bot may reject an early
crew with **More me**; other bots learn that preference without treating the
protest itself as evidence of Red allegiance. Their forecasts influence crew
choices, pledges, votes, and objective-aware spending.

Each proposed crew is evaluated with an actual plan for the bot's objective.
Saver protects ten tokens; Spendthrift seeks spending opportunities; Exact
Change accounts for the difference between a continuing attempt's income and
the final wallet. Passenger seeks a free ride on a completing crew, and Reliable
Partner actively pursues its two qualifying pledges. These inclusion demands
can also produce **More me**, independent of personality.

Bots compare possible integer payments, including broken promises and Blue ties,
instead of treating an average pot as a certain win. Equally valuable plans favor
the stronger tactical color margin. Holding tokens has no generic scoring bonus;
saving incentives come from the objective. Designer review shows estimated
mission and personal outcome chances alongside the average pot.

Bots seeking Red, including temporary objective goals such as Blue Close Race,
use Blue cover pledges and plan their actual spending separately. Both sides use
the same situational complaints: inclusion, funding, or objections to a player's
pledge/history. Accusations influence later trust and choices: trusted speakers
carry more weight, while unsupported blame can make an unproven accuser suspect.
Designer review shows the private plan alongside the public-promise forecast.

Each controller saves isolated evidence, beliefs, personality, settings, and
randomness. Designer review makes the estimates and their evidence inspectable.
See [the bot implementation notes](docs/bots.md) for exact behavior and tuning.
These are uncalibrated heuristics with short-horizon objective scoring; they
do not establish human-level difficulty. Both earlier policies remain available.

The objective and ability mechanics in **milestone 2** are implemented. The default
`social.10` bots plan their own modifying abilities alongside deposits, crew choices,
and votes, including final wallets and original-payment objective credit. They
choose useful inspection targets and retain badge/scouting/audit evidence.
Repeated effects after independently verified crew payments can become tentative
forecast scenarios. Public pot/wallet discrepancies alone cannot certify spending
or lies. Arbitrary rule discovery and balance need further playtesting.
Existing saves retain their original controllers; start a new table for the
updated policy. Random and Straightforward remain simpler comparison policies.
See [the ability implementation notes](docs/abilities.md) for timing and limits.

Current persistence uses atomic JSON snapshots. The web server
binds only to `127.0.0.1`; it is a trusted local tool, not a hosted multiplayer or
benchmark-isolation service. It checks request origins and uses a per-server
token for mutations. Designer mode intentionally exposes finished-game secrets.

Objective predicates and private progress live in `mission_game/objectives.py`.
The default session/CLI profile is `configs/development_abilities.json`.
Use `--config configs/development_objectives.json` for an abilities-off comparison,
or `--config configs/development_common_rules.json` for all-Loyalist practice.
The low-level `GameConfig()` retains the objectives-only profile; use
`GameConfig.abilities()` to construct the full rules explicitly.
Simulation summaries include per-objective holders, personal conditions, and
individual wins; these files contain designer information.

The engine is in `mission_game/engine.py`; value objects and configuration are
separate from controllers, session persistence, adapters, and CLI tools. Static
browser assets live in `mission_game/web/`; `server.py` binds requests to the
saved human seat, and `replay.py` constructs observable replay steps. The UI
prevents incomplete input; the Python engine authoritatively validates every
action and resolves the game. The root design document remains the
source of truth for the full prototype.
