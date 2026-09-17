# Development protocol

New web/CLI/session games use engine/observation schema `3`, rules
`0.1-abilities-dev.3`, mode `development_abilities`. Contrarian is disabled and
new deals contain exactly one of each ability. Both earlier abilities versions
remain readable with their original settings and assignments.
The optional objectives-only profile uses schema `2`, rules `0.1-objectives-dev.4`;
the all-Loyalist profile uses schema `1`, rules `0.1-common-rules-dev.3`.
Existing `0.1-objectives-dev.3` snapshots remain readable with their original decks.
The same action contract is used by the local JSON-line adapter and web table.
Neither adapter is an authenticated multi-user or hosted evaluation service.

## Local web transport

Run `python3 -m mission_game.cli web` and open `http://127.0.0.1:8765`.
The server binds to IPv4 loopback only. Static routes serve three allowlisted
assets; filesystem paths, authoritative snapshots, and seeds have no HTTP route.
Requests are serialized by the local store, so concurrent tabs cannot apply
conflicting actions at the same revision. Engine idempotency still applies.

New tables load `configs/development_abilities.json` at creation, or the file
selected with `web --config`. Changes apply to subsequent tables without a
restart. Every saved session embeds its resolved config; loading or replaying a
session never replaces it with the current file. Invalid configs reject creation.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/bootstrap` | Public guide, local game catalog, and this server's mutation token |
| `GET /api/games` | Public saved-game summaries, with opaque game IDs |
| `POST /api/games` | Create with `{"human_seat":0}`; optional `"demo":true` generates a completed bot game |
| `GET /api/games/{id}/state` | Observation bound to the saved human seat; recorded bot games default to p0 |
| `POST /api/games/{id}/resume` | Resume bot decisions until the human's next request; body `{}` |
| `POST /api/games/{id}/actions` | Submit the same `request_id`, `revision`, `action` object used below |
| `GET /api/games/{id}/replay?step=0` | One verified historical observation and its visible timeline |

POSTs require JSON and the `X-Table-Token` returned by bootstrap. Host and Origin
checks reject requests from other sites. No cross-origin permission is granted.
The token is a local request-integrity measure, not authentication or participant
isolation. Restarting the server requires refreshing open pages for a new token.

Replay accepts `step=-1` for the latest saved point. For completed games only,
`seat=p3` selects another perspective and `designer=true` explicitly requests
inspection data. These controls are hidden in unfinished-game replays. Both are rejected on unfinished games when they would expose
another seat's hidden information. Designer inspection returns teams, objectives, available frozen personal results, currently
sealed submissions, the most recent action, and the last resolved original
contributions. New sessions also return `designer.bot_decision` for the selected
recorded bot action: its policy version, reason, inputs/forecast, and limitations.
It is null for human actions and older actions without explanations. These are
saved diagnostics, not regenerated policy decisions or certified forecasts.
Ordinary replay responses contain `designer: null`.

Player replay steps are emitted only when that seat's observation changes.
Another player's unrevealed commitment adds no step, label, or count. The
replay includes only actions already in the saved game; it cannot advance play.
Completed-game responses include a shared `position` in the recorded action
sequence. Switching perspective or toggling designer inspection requests that
same `position` rather than a seat-specific `step`. The new view selects its
latest visible frame at or before that moment and retains the requested position
for subsequent switches. Frame numbers may differ between seats. The URL keeps
the shared position so refresh restores the same moment. Position requests take
precedence over `step`; they are rejected for unfinished games, whose responses
never expose positions or hidden-action counts.

The server verifies recorded actions against the saved final snapshot before
serving a timeline. Replays are cached by file modification, size, seat, and
inspection mode. Seeking does not call controllers, change their random streams,
or modify the saved file. All new games and accepted decisions are persisted
before their responses are returned.

## JSON-line transport

Optional `agent --mission-checkpoints` adds
`{"type":"mission_checkpoint","mission":1,"observation":{...}}` envelopes.
They contain the same allowlisted seat observation as ordinary requests,
captured after a completed mission's inspections/reports and before subsequent
preparation decisions, including the terminal mission. No response is required
for these notification envelopes; only ordinary `observation` requests accept
actions. A runner can pause consuming later observations while recording a
prediction. No seed or hidden action position is included. A resumed session
does not synthesize missing checkpoints for earlier missions.

Completed source-blind runs can attach optional `agent_predictions` to session
schema 2. These are designer metadata, separate from engine events, containing
mission, observer, model, observation revision/digest, recorded action position,
per-player `p_blue` estimates/evidence, and a summary. Ordinary observations and
replays do not expose them. Designer replay includes only checkpoints at or
before the requested position. Replay verifies game actions/results; it does
not certify the agent's probability estimates.

Start `python3 -m mission_game.cli agent --human-seat 0 --session runs/agent-game`.
The trusted runner creates or restores the session. Its `human_id` binds the
external participant; input cannot override that binding.

Output envelopes are:

```json
{"type":"instructions","text":"<complete public player guide>"}
{"type":"observation","observation":{"...":"..."}}
{"type":"acceptance","accepted":true,"request_id":"..."}
{"type":"error","code":"unaffordable","message":"The total exceeds your current wallet"}
```

After instructions, the runner fills bot decisions until the external seat has
a request, then emits its observation. After a valid response it emits acceptance
and the next observation (possibly the final result). An invalid response leaves
the state and current request unchanged; send a corrected response. EOF leaves
the session saved. Run the same command to resume. stdout contains only JSON
Lines; command startup errors go to stderr.

Input has exactly three fields:

```json
{
  "request_id": "<copy the current request_id>",
  "revision": 12,
  "action": {"type":"vote","approve":true,"complaints":[]}
}
```

Both identifiers come from the observation. `revision` is an integer identifying
an observable phase boundary; it does not count sealed responses. All requests
in a sealed batch use the same revision. Request IDs include a random game ID,
revision, and seat. Neither identifiers nor observations include the dealing seed.

An identical previously accepted request is acknowledged without executing again,
including after restore. A conflicting retry is rejected. Other seats' request
IDs return the same error before and after their hidden submissions.

## Observations

`Game.observe(player_id)` constructs a detached, allowlisted object containing:

| Field | Meaning |
| --- | --- |
| `schema_version`, `rules_version`, `mode` | Contract and rules identity |
| `game_id`, `viewer` | Game and the bound viewing seat |
| `phase`, `status` | Current decision phase and ACTIVE/CLOSING/FINISHED/UNRESOLVED |
| `request_id`, `revision` | The viewer's next request; ID is null if none |
| `action_spec` | Own action type and public/own budget limits; null if no request |
| `own_submission_received` | Whether this viewer has submitted to this sealed batch |
| `public` | Names, wallets, chairman, attempt/rejections, mission/pot, score, crew, revealed pledges, votes, completed missions, public rules and final team result |
| `private` | Own team/card text and permitted objective progress, own most recent contribution, own action history, and own final result once the game closes |
| `history` | Complete public event sequence, including all previous pledges, votes, reports and official results |

In schemas 2 and 3, `private.objective` contains `id` (type), `name`, complete truthful
`text`, `desired_winner`, and `progress`. Progress carries a label/text, visibility,
nullable value/target, and nullable `condition_met`. This is personal-condition
progress, not a prediction of overall victory. Wallets are evaluated after the
terminal spending and before income. Reliable Partner and Passenger derive
counts from the holder’s entire original history, including before receiving a
card. Reports are never input to these predicates.

Opposition Patron uses `visibility: "hidden_global"`, null `value` and
`condition_met`, and a private `own_paid` count. The global count is never
exposed by ordinary observations, even at game end. Only the final personal
win/loss is returned. No observation contains a deck list or card instance ID.
Other players’ objective assignments are absent from public events and fields.

Rules `0.1-objectives-dev.3` and `0.1-common-rules-dev.3` always assign five Blue
and three Red players. `public.rules.team_counts` is `{"blue":5,"red":3}` and
`public.rules.contrarian_team` is `"blue"`; the former probability field is gone.
These are public setup rules, not role reveals. Contrarian's presence and holder
are private. A drawn Contrarian is assigned only to a Blue seat, without changing
the eight drawn cards or the probability of drawing it. Invalid team counts or
a Red Contrarian violate snapshot invariants. Older development rules are not
migrated.

`private.result` in schemas 2 and 3 adds an explanatory `text` to `objective`, `wallet`,
and `won`. A Contrarian wins when their unchanged allegiance loses, and no
objective wins an unresolved game. Personal outcomes remain private until
closing reports finish. Schema 1 keeps its original card/result field shapes.

`public.mission.winner` is null for an open mission. When awarded, the finished
mission and its final pot remain visible through the closing report phase. Its
tokens have been retired from active accounting and cannot be spent again. A new
mission replaces it after nonterminal reports and income.

There is no pre-modification contribution total or individual color breakdown in
official public results. Public final wallets intentionally reveal spending
quantities in this ability-disabled development mode. A player's own original
contribution is private and persists in their action history.

During sealed pledges, contributions, and reports, another seat's response changes
neither your observation nor its revision until the batch closes. Revealed maps
use canonical crew/seat order and do not expose response arrival order. Votes
are public immediately and run clockwise, with all eight recorded.

`Game.pending_requests()`, `snapshot()`, `from_snapshot()`, the full action log,
and session files are trusted-runner APIs. They must never be sent to a participant.
The Python API does not provide process isolation; a future hosted runner must
keep these objects and files outside the participant's accessible environment.

## Action shapes

All token vectors have **exactly** `blue`, `red`, and `green`. All quantities are
integers from 0 through 2,147,483,647; booleans and floating-point numbers are
rejected. Actual token spending and pledges must also be affordable. Unknown
fields are rejected. Player IDs are `p0` through `p7`.

### Crew selection

Chairman only; select exactly the printed crew size. Seats must be distinct;
self-selection and empty wallets are allowed.

```json
{"type":"select_crew","crew":["p0","p2","p5"]}
```

### Pledge

Selected crew only; sealed until all crew members respond. Costs nothing and
does not constrain the later deposit.

```json
{"type":"pledge","tokens":{"blue":2,"red":0,"green":1}}
```

### Vote

Current clockwise voter only. A No vote requires exactly one entry in
`complaints`; a Yes vote requires none (omit the field or use `[]`). The action
spec provides `max_complaints: 1` and `complaint_required_on_no: true`. Each
complaint has at least a player or color; a modifier alone is invalid. Optional
fields may be omitted or null. Complaints remain player claims.

```json
{"type":"vote","approve":false,"complaints":[
  {"modifier":"less","player_id":"p2"}
]}
```

### Actual contribution

Approved crew only. Each actor's budget is checked before any batch spending.
All contributions resolve together; zero and differing from the pledge are legal.

```json
{"type":"contribute","tokens":{"blue":0,"red":3,"green":0}}
```

### Report

Only the approved crew receives report requests; each must supply 1–3 statements.
Off-crew submissions are rejected, including empty passes. After eight rejections
there is no crew: resolve the penalty and immediately finish the attempt, paying
income only if play continues. No report requests or report event are emitted.

```json
{"type":"report","statements":[
  {"player_id":"p0","verb":"gave","quantity":2,"color":"blue"},
  {"player_id":"p5","verb":"took","quantity":99,"color":"red"}
]}
```

Reports may name anyone and lie about amounts or actions. Validation checks
syntax, not hidden truth. `gave` means an original paid deposit during this
attempt; `took` means removal from the mission. The latter can be claimed even
though abilities are disabled in this mode. There is no source-wallet field.

## State and replay

The development state machine is:

```text
select_crew -> pledge -> vote (8 sequential seats)
  rejected 1..7 -> next chairman -> select_crew
  rejected 8 -> resolve penalty -> report
  approved -> contribute -> resolve deposits -> report
report -> income and next attempt, or game_over
```

Mission completion and terminal wallets freeze during resolution. Reports cannot
alter that result. The attempt guard applies after reports; reaching three
missions on the final permitted attempt takes precedence. No income is paid
after victory or after hitting the guard.

New sessions use session schema `2`; schema `1` remains supported and is written
back unchanged when resumed. Sessions store the initial/current engine snapshots,
accepted action log, sealed batch, versioned per-seat controllers, and external
seat binding. Session schema 2 adds the trusted `bot_decisions` array, separate
from all engine events and observations. Its nested engine snapshots use schema 1, 2, or 3 according to the
saved rules profile. Schemas 2 and 3 store each held objective as `{instance_id, kind}`;
legacy restores synthesize Loyalist cards internally without rewriting the
version-1 representation. The saved profile is never upgraded silently.
Files are replaced atomically and written owner-only. The complete
snapshot is the checkpoint; restoring it does not redraw any randomness.

Replay restores the initial engine snapshot, re-submits the recorded accepted
actions, and checks the resulting full snapshot against the saved one. This
also checks the public and private action streams. It does not sample policies
again. Runtime upgrades should be validated before comparing saved runs; no
cross-Python-version replay guarantee is made by this development release.


## Scripted controllers

New sessions default to `social.12`; the CLI also supports `--policy straightforward`
(`straightforward.3`) and `--policy random` (`random-legal.3`). The saved controller version selects the
implementation on restore within a supported development rules version.
Saved `social.7`, `social.8`, `social.9`, `social.10`, and `social.11` controllers use their previous algorithm within
supported rules profiles; other unknown rules versions are rejected.
Unknown controller versions are rejected. Engine/observation schema numbers
are 1 and 2 for abilities-off profiles and 3 for the abilities profile.
All publish fixed team counts; new defaults disable Contrarian. Policy selection and designer explanations
are not added to ordinary player observations or public game summaries.

A Straightforward snapshot contains `version`, `rng`, and `memory`. Memory binds
to one game/seat, deduplicates public evidence using an event-ID cursor, stores
only its own original deposit receipts, and recomputes its desired winning side
from the current own card. Public reports remain attributed claims. No inferred
trust or other-player allegiance is present in this baseline. Memory reflects
observations received through that controller's most recent decision.

A Social snapshot adds `traits`, `settings`, and `beliefs` to those fields;
`social.9` also adds `effects` containing observation-derived attempt contexts,
independently known payments, and residual evidence.
Traits are independently seeded; the resolved settings and inferred per-player
estimates are serialized and restored exactly. Beliefs have their own public
event cursor and retain only observation-derived evidence and deductions.
They distinguish desired side, pledge reliability, report credibility, and
inclusion demand; none is a hidden role lookup. Exact public contribution accounting
is restricted to the two ability-free development profiles. In abilities games,
private receipts verify payments and repeated fully observed crew residuals can
support tentative effect scenarios. `--policy-config`
accepts a JSON object of Social settings for new sessions; resuming ignores new
policy arguments and restores saved controllers. See [bots.md](bots.md).

Each successful scripted action records its action index, actor, request ID,
policy version, concise reason, decision details, and limitations in
`bot_decisions`. Nothing is added to the engine action payload. Ordinary replay
never receives these records; completed-game designer replay joins an explanation
to its exact recorded request. Action replay checks the engine snapshot without
running controllers again; explanations are saved metadata, not independently
verified strategic conclusions. `replay --omniscient` also prints this metadata.

Per-game simulation metrics and aggregate summaries identify actual policy
versions. Historical metrics without that field imply the original random
policy. Mixed versions are labeled `mixed`, with their versions listed.


## Ability-enabled action contract (schema 3)

`public.rules.abilities_enabled` and `contrarian_enabled` identify the table's
rules, not its deal. `public.public_badges` maps publicly revealed seat IDs to
true teams. No other ability assignments or use counters are public.
`private.ability` includes the holder's `id`, `name`, exact `text`, and
`uses_remaining` (0/1 for limited abilities, null otherwise).

`action_spec.ability` is null or the holder's currently available ability choice,
with allowed `targets`, `colors`, or `max_total` as appropriate. Passing uses
`"ability": null` (omitting it also passes). Only the holder sees these controls.
The engine uses fixed all-seat cover slots for both preparation windows, hidden
commitments, and approved-attempt audits. The trusted session fills slots with no
available decision automatically. Partial arrivals and uses stay hidden.

Both swap and scout windows have public `phase: "preparation"` and action
`{"type":"prepare","ability":{"target":"p2"}}`. Swaps resolve together in
chairman initiative order, notify all affected seats of their final current
objectives, then scouting choices are collected. The two internal snapshot phases
are `prepare_swap` and `prepare_scout`; they are not public role announcements.

On an approved or penalty attempt, every seat's hidden action has type
`contribute` and a `tokens` vector. `action_spec.on_crew` specifies whether an
ordinary deposit is permitted; off-crew `max_total` is zero. An optional `ability`
is committed in the same action, using these shapes when its own card permits:

```json
{"color":"green"}
{"source":"wallet","target":"p2","amount":3}
{"source":"mission","tokens":{"blue":0,"red":2,"green":1}}
{"from":"blue","to":"red"}
```

These are respectively an off-crew deposit, wallet transfer, mission transfer,
and color change. A valid limited transfer attempt consumes its use even if
nothing is available at resolution. Public wallets and the pot remain unchanged
until all commitments arrive. The engine orders paid deposits/penalty, bonuses,
transfers, color changes, and scoring. There is no mid-resolution action request.

Approved attempts then enter `audit`, even when the outcome is frozen. An
available inspection uses `{"type":"audit","ability":{"target":"p2"}}`;
only crew members may be targets. Results arrive before reports. Penalties skip
audits and reports. Income follows reports only when play continues.

`private.receipts` stores only this seat's truthful private results: `scout`
(target/team), `audit` (target/original tokens), `thief` (actual source/transfer),
`echo` (created color/amount), and `objective_changed` (final current objective
and permitted progress at that window). Each has an attempt and revision. Swap
notifications do not identify the initiator. Recoloring gives no extra oracle
about success. Own paid off-crew deposits also appear in `last_contribution`.
Snapshots persist uses, receipts, sealed actions, and bonus accounting; designer
resolution records include effects. Ordinary results reveal only final totals.


## Paced live web play and vote revenue

The current abilities profile publishes `public.rules.vote_income: 1` and
`missions_to_win: 4`. After the eighth ballot, a public `vote_income` event
contains `amount_each` and the resulting `wallets`, before the approval/rejection
branch. This awards all eight players revenue on both outcomes, including the
eighth rejection. End-of-attempt `income` remains a separate event. Terminal
reason is `four_missions`; Close Race uses the target-minus-one opponent score.
Earlier profiles and their snapshot representations remain supported unchanged.

The browser creates tables with `{"human_seat":0,"paced":true}`, resumes with
`{"paced":true}`, and adds `"paced":true` to action payloads. These operations
save the current boundary without running through subsequent bot decisions.
Existing API callers that omit `paced` retain the original advance-until-human
behavior; sample games still run to completion.

Live state responses add `can_advance`, `step_key`, and an optional `transition`
label. `POST /api/games/{id}/advance` with `{"step_key":"<current key>"}` advances
to the next seat-visible action or phase boundary and saves once. It skips other
seats’ sealed arrivals and automatically handles the viewer’s ineligible cover
slots, without publishing hidden participation. It stops when human input is
needed. Stale step keys return 409, preventing two tabs or repeated clicks from
advancing from the same visible state. Keys depend only on the viewer’s visible
revision, history length, and own submission count.

The browser accepts a custom number of seconds between completed steps, with
zero for manual advancement and a default of 1.8 seconds. It remembers the delay
locally, suspends the timer while the field is being edited, and preserves an
existing pause when the value changes. Pause stops scheduling; an already submitted step may finish. Automatic
progress waits for human decisions, pauses while hidden or viewing help, and
stops on navigation. Opening a player history pauses live play. History and pot
comparisons derive only from the currently visible observation, including in
replay; no extra hidden-state endpoint is used.

The browser derives its last-step explanation from visible events and the
viewer's own sealed choices. Votes include the voter, complaint, and proposed
crew; pledge quantities appear when the batch is revealed. Player histories
retain each proposal's chairman and crew. Income events remain in the protocol
and replay records but are omitted from UI histories and step descriptions.
The mission comparison starts collapsed and retains its expanded state across
steps and reference changes. Wallet deltas show only mission-resolution changes, using all wallet events to
calculate the correct before/after balances.
