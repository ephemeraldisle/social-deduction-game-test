# Milestone 1 verification

Verified September 10, 2026 with Python 3.14.0, using only the standard library.

## Automated checks

```bash
python3 -m unittest discover -s tests -v
```

**42 tests passed.** Coverage includes scoring examples, accumulation, all-Green
missions, surplus removal, clockwise voting through all eight seats, rejected
proposal accounting, eight-rejection penalties and rotation, income timing,
terminal snapshots, and the unresolved guard.

Action tests cover affordability, strict integer types, complaint/report syntax,
legal false claims, wrong actors, stale requests, and idempotent retries.
Privacy checks compare complete observations around sealed submissions, mutate
unobserved team assignments, verify detached views, and ensure request error
messages do not disclose another seat's response arrival.

Persistence tests restore each implemented phase, including partly committed
pledges, contributions, and reports; compare final engine and controller state
with uninterrupted play; and replay recorded actions without invoking policies.
An end-to-end JSON adapter test reproduces the same complete recorded game.

## Seeded diagnostic

```bash
python3 -m mission_game.cli simulate \
  --config configs/development_common_rules.json \
  --games 100 --seed 20260910 --out runs/smoke
```

Rules: `0.1-common-rules-dev.1`. Policy: `random-legal.1`.
Seeds: 20260910 through 20261009 inclusive. All eight seats use independent
random legal-action controllers, all objectives are Loyalist, and abilities are
disabled. All 100 games replayed to their exact final engine snapshots.

| Metric | Result |
| --- | ---: |
| Games attempted | 100 |
| Completed games | 100 |
| Unresolved runs | 0 |
| Engine or replay failures | 0 |
| Blue / Red team wins | 62 / 38 |
| Attempts per game, mean | 7.83 |
| Attempts per game, min–max | 4–13 |
| Attempts per completed mission, mean | 1.91 |
| Rejected proposals | 189 |
| Eight-rejection penalty attempts in this random sample | 0 |
| Individual winners across 800 seats | 432 |
| Games with five Blue / six Blue seats | 68 / 32 |

The random sample did not exercise the eight-rejection limit; dedicated rule
tests exercise both an incomplete penalty pot and a penalty that awards Blue.
The unresolved guard and terminal victory taking precedence over it are also
tested directly rather than relying on their occurrence in random play.

This is a transition and accounting diagnostic. The policy ignores allegiance
and does not reason about winning, so these rates are not evidence of game
balance, strategic quality, human performance, or hidden-rule acquisition.

Generated local artifacts (ignored by Git): `runs/smoke/config.json`,
`games.jsonl`, `summary.json`, and `example-replay.json`. The latter is a trusted
designer artifact containing private state; use the seat replay command to
obtain a participant view.

## Adapter checks

Manually exercised terminal crew pledging, sequential voting with a complaint,
saving at the contribution prompt, and resuming to the same request and public
history. Verified that `/quit` saves and exits. The `analyze` command reproduced
the simulation summary, and `replay --seat 0` verified and rendered the example.

That initial verification covered milestone 1 mechanics only. The objective
implementation is verified below. Abilities, responsive opponents, and hosted
participant isolation still require later implementation and verification.

## Web table and replay follow-up

The web interface was added after the common-rules slice, ahead of the remaining
mechanics. Verified with Python 3.14.0 and Node's built-in test runner:

```bash
python3 -m unittest discover -s tests -v
node --test tests/test_web_ui.cjs
node --check mission_game/web/app.js
```

**56 Python tests and 7 client-logic tests pass.** The Python total includes the
original 42 tests, nine web-store/replay tests, and five HTTP integration tests.
The HTTP tests use a temporary loopback port and require local socket permission
in sandboxed environments. Node is not a runtime dependency of the application.

Additional checks cover:

- Completing a game through web actions, restoring from disk, and matching its
  final replay observation to live state.
- Saved-seat binding, idempotent HTTP-adapter submissions, and rejection of
  unfinished-game seat switching or designer inspection.
- Identical player timelines before and after another seat's sealed submission.
- Explicit finished-game inspection, tampered replay detection, and unchanged
  session bytes after repeated replay seeks.
- Serving only intended assets; rejecting invalid origins, hosts, mutation
  tokens, media types, and seat values.
- Client spending limits, deliberate crew/vote choices, mandatory crew reports,
  legal false claims, escaping player names, private replay receipts, and draft
  reset behavior at a new decision boundary.

Inspected the live desktop Chrome table and replay views, the help guide, and
crew-selection feedback. Browser rendering uses no external fonts, scripts, or
assets. Responsive styles and a mobile action shortcut are implemented; mobile
and cross-browser visual QA remain follow-up work. The automated client tests
exercise logic and HTML generation, not a browser rendering engine.

The original simulation figures above still describe the same unchanged game
mechanics and random policy. They are not a new strategic evaluation of the UI.

## Private objectives follow-up

New defaults use `0.1-objectives-dev.1`, engine/observation schema 2. The
version-1 common-rules profile remains supported without migrating old saves.
Abilities remain disabled and policies remain `random-legal.1`.

**74 Python tests and 9 client-logic tests passed.** The 18 new Python tests
cover all nine predicates, both allegiances, wallet boundaries, Contrarian's
reversed win condition, unresolved results, default deck counts, unique stable
card identities, deterministic dealing, and independent random streams.

History and integration checks include:

- Reliable Partner's exact original colors, minimum spend, and two qualifying
  attempts on one mission; progress remains with the seat when cards move.
- Passenger's zero deposit on the completing attempt itself, including the
  terminal attempt and missions completed by the opposing side.
- Opposition Patron's original paid deposits across all seats, a final deposit
  reaching 20, and exclusion of penalty, bonus, recoloring, and removal records.
  Synthetic future-ability records verify off-crew deposits and redeposits;
  no ability actions are implemented by these fixtures.
- Actual terminal spending and closing reports, 3–2 finishes, and private
  explanations for team wins without personal wins and Contrarian victories.
- Full-observation equality after changing another player's objective or hidden
  global paid deposits; progress cannot disclose the global count. Other seats'
  sealed commitments still create no observable changes.
- Objective card persistence, every visible replay step, explicit designer
  objectives/results, and original version-1 save and result shapes.

The existing phase-resume, JSON adapter, and web integration tests now also
exercise the new default objective profile. Five existing local version-1 saves
were loaded, compared to their original JSON representation, and replayed
without altering their files.

Client tests verify that unfinished replay omits the designer toggle and seat
selector, completed replay offers inspection, hidden progress is not rendered
as failed progress, and final text correctly explains Contrarian. Desktop Chrome
inspection confirmed the long Opposition Patron card fits, its global progress
is hidden, and **Review so far** shows a fixed viewing seat with no designer
control. UI fixtures were isolated under `/private/tmp/hidden-rules-web-check`.

```bash
python3 -m mission_game.cli simulate \
  --config configs/development_objectives.json \
  --games 100 --seed 20260910 --out runs/objectives-smoke
```

All 100 games completed and replayed exactly, with zero unresolved runs or
failures. Blue won 62 and Red 38; mean attempts remained 7.83. Objectives do not
change this random policy's actions, so those team results match the original
common-rules diagnostic. Personal wins fell from 432 to 243 across 800 seats.

| Objective | Holders | Personal wins |
| --- | ---: | ---: |
| Loyalist | 327 | 185 |
| Saver | 62 | 3 |
| Spendthrift | 60 | 1 |
| Exact Change | 64 | 0 |
| Opposition Patron | 58 | 11 |
| Close Race | 65 | 6 |
| Reliable Partner | 52 | 0 |
| Passenger | 50 | 5 |
| Contrarian | 62 | 32 |

These are execution diagnostics, not objective balance measurements: the bots
ignore every objective. Exact Change and Reliable Partner successes are covered
by authored tests despite having no personal winners in this random sample.
The generated config, summary, per-game objective metrics, and example replay
are in `runs/objectives-smoke/` (ignored by Git, designer-only data).

## Straightforward opponents follow-up

New sessions now use `straightforward.1`, implementing the exact ability-free
baseline from design-plan section 12.4. Game rules and observation schemas are
unchanged. Session schema 2 stores versioned controllers, per-seat evidence
memory, and separate designer-only decision explanations. Schema-1 sessions
retain their original random controllers and serialization.

**94 Python tests and 10 client-logic tests passed.** Twenty new Python tests
check richest-wallet crews, seeded tie-breaking, affordable ceiling shares,
funded all-Green pots, Blue-tie forecasts, incomplete funding decisions,
Contrarian preferences after card changes, exact pledge fulfillment, and own
truthful reports. They also check:

- Independent, detached memory, with event deduplication and reports retained
  as claims; a controller cannot reuse memory for another game or seat.
- Identical choices and memory when unobserved state changes or another seat
  seals a deposit; no privileged original-contribution records in memory.
- Version dispatch, saved randomness, restored memory, and old random-policy
  sessions continuing identically. Six existing local session-1 files were also
  loaded, compared against their JSON, and replayed without modifying them.
- Exact correspondence between accepted bot actions and saved explanations;
  no policy invocation during replay and no explanations in ordinary views.
- Actual policy versions in metrics, explicit mixed-policy labeling, and CLI
  selection of the original random controller.

Existing resume tests now exercise the Straightforward default at every phase
and partial batch, comparing engine state, controller memory/randomness, and the
complete saved explanation sequence. Existing web and JSON adapter tests also
run with the new default. A new client test verifies designer explanation
rendering, escaping of diagnostic text, and the older-game fallback.

Desktop Chrome inspection on an isolated completed game confirmed that selecting
a pledge or No vote updates **Why this bot acted**, and **Forecast and policy
limits** expands to show the recorded inputs and limitations. The panel remains
inside finished-game designer inspection. No broader UI redesign was made.

```bash
python3 -m mission_game.cli simulate --policy straightforward \
  --games 1000 --seed 20260910 --out runs/straightforward-smoke
```

Seeds 20260910 through 20261909 inclusive used the default objective deck and
unchanged `0.1-objectives-dev.1` rules. All 1,000 games completed and replayed
exactly, with zero unresolved runs or engine/replay failures.

| Metric | Result |
| --- | ---: |
| Blue / Red team wins | 696 / 304 |
| Attempts per game, mean | 4.554 |
| Attempts per game, min–max | 3–11 |
| Rejected proposals | 18,385 |
| Eight-rejection penalty attempts | 2,250 |
| Individual winners across 8,000 seats | 2,705 |

The repeated rejections expose a known weakness: this exact baseline ignores
rejection pressure, and opposing desired sides can repeatedly reject each
other's forecasts until the penalty resolves the dispute. Passenger had no
personal winners in this batch; the policy does not deliberately seek a free
ride. These results support treating Straightforward as a reference baseline,
not a completed objective-aware or belief-tracking opponent. The next policies
should be checked for evidence-sensitive behavior as well as termination.

Artifacts in `runs/straightforward-smoke/` include `config.json`, `policies.json`,
`games.jsonl`, `summary.json`, and `example-replay.json`. These contain designer
information and are ignored by Git. The `analyze` command reproduced the saved
summary, including its actual policy version.

## Social opponents follow-up

New sessions use `social.1`. Rules remain `0.1-objectives-dev.1`; session and
observation schemas are unchanged. Random and Straightforward controllers remain
available and saved sessions retain their original versions. Resolved Social
settings, personality, per-seat beliefs, memory, and RNG are persisted.

**114 Python tests and 11 client-logic tests passed.** The complete Python suite
includes the 94 existing tests and 20 new Social tests. The existing phase-resume,
web, and JSON adapter tests now also exercise the Social default. JavaScript
syntax checking passed. New behavioral coverage includes:

- Paired votes with identical proposals but different public histories: repeated
  Blue promises followed by deducible Red deposits change Yes to No and alter
  predicted approval; crew selection avoids those members at equal wallets.
- Identical observations with different self-interest produce Yes versus No
  with **More me**. Protests relax under rejection pressure and forecast terminal
  outcomes. Observed protests lower predicted approval while excluded without
  adding a Red preference signal.
- Public votes already cast fix the corresponding forecast probabilities.
- Conditional Blue priors, uncertainty about individual responsibility, own
  receipts that disambiguate other contributions, and matching aggregate colors
  that cannot certify individual honesty.
- Persistent pots, income timing, penalty exclusion, event deduplication,
  recovery after truthful behavior, bounded nonrecursive association, and
  report influence weighted by independently established credibility.
- Actual objective-sensitive spending for Saver, Spendthrift, Exact Change,
  Reliable Partner, and Passenger; Contrarian and Close Race preferences;
  exclusion of rejection penalties from Opposition Patron's inferred progress.
- Seeded personality independent of cards, exact controller restoration, custom
  settings persistence/validation, and identical decisions after unobservable
  changes to another role or a sealed contribution.

Seven preexisting local saves (six Random and one Straightforward) were loaded,
compared to their original JSON, and replayed without changing file contents.

Desktop Chrome inspection used a separate completed diagnostic under
`/private/tmp/hidden-rules-web-check/social-policy-check/`. A recorded exclusion
protest displayed **More me**, stable personality traits, expected pot, approval
estimate, and the seven-player belief table. The evidence disclosure expanded
to attributed event explanations. The layout fit the desktop board column.
These diagnostics remain within completed-game designer inspection; existing
server privacy tests still reject designer access during unfinished games.
Mobile and cross-browser visual checks remain follow-up work.

```bash
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 100 --seed 20260910 --out runs/social-smoke
```

Seeds 20260910 through 20261009 inclusive used the default objective deck and
resolved settings recorded in `policies.json`. All 100 games completed and
replayed to identical final engine snapshots, with no failures or unresolved
runs.

| Metric | Result |
| --- | ---: |
| Blue / Red team wins | 80 / 20 |
| Attempts per game, mean | 7.23 |
| Attempts per game, min–max | 3–12 |
| Rejected proposals | 2,262 |
| Eight-rejection penalty attempts | 135 |
| Individual winners across 800 seats | 400 |

| Objective | Holders | Personal wins |
| --- | ---: | ---: |
| Loyalist | 327 | 202 |
| Saver | 62 | 25 |
| Spendthrift | 60 | 20 |
| Exact Change | 64 | 21 |
| Opposition Patron | 58 | 23 |
| Close Race | 65 | 24 |
| Reliable Partner | 52 | 31 |
| Passenger | 50 | 20 |
| Contrarian | 62 | 34 |

Every objective type produced personal winners. These numbers are execution
and behavior diagnostics, not evidence of balanced teams or difficult human
opponents. Rejections remain frequent. Vote forecasts are uncalibrated and
assume independent choices; private objectives of other players are unknown.
Public accounting deductions apply only while abilities are disabled. Paired
scenarios establish that evidence influences behavior; human play and mixed
opponent comparisons are still needed to tune the strategy.

Artifacts are in `runs/social-smoke/` and include config, policy settings,
per-game metrics, summary, and an example replay with designer diagnostics.

## Required No-vote complaints and crew-only reports

Current profiles are `0.1-objectives-dev.2` and `0.1-common-rules-dev.2`.
Policies are `social.2`, `straightforward.2`, and `random-legal.2`. This rapid
iteration intentionally invalidates earlier development saves and replays;
no compatibility migration was implemented.

**116 Python tests and 13 client tests passed.** The engine now requires exactly
one syntactically valid complaint on a No vote, rejects complaints on Yes votes,
and only requests reports from the approved crew. Off-crew requests are rejected
even with a forged current request ID. Reports still form one sealed batch.
Penalty attempts have no reporters and proceed directly to income or game end.
Tests cover continuing penalties, terminal victories, attempt-limit endings,
correct income timing, and exactly the crew appearing in revealed reports.

Client checks cover the mandatory single complaint, disabled incomplete No vote,
clearing the complaint when switching to Yes, absence of add/remove complaint
controls, escaping, voter-card display in play and replay, and the labeled
previous-proposal summary after votes clear. Off-crew observations render no
report controls. The terminal prompts for a complaint only on No.

Desktop Chrome inspection on an isolated fixture confirmed visible **More me**
complaints on player cards, the required No complaint form, disabled submission
until a target is chosen, and removal of the form when changing to Yes.

The 100-game `runs/communication-smoke/` diagnostic completed with zero failures
or unresolved games and exact engine replay. Team/personal results matched the
previous Social diagnostic (80 Blue wins, 20 Red wins, 400 personal wins).
Separate completed and replayed games checked legal complaints from all three
policy families. These runs validate the revised action contract, not balance.

## Red concealment and accusation feedback

The default controller is now `social.3`; engine rules remain
`0.1-objectives-dev.2`. Straightforward remains the honest comparison policy.

**125 Python tests and 13 client tests passed.** Nine new authored behavior
checks cover Blue cover pledges versus private Red plans, actual Red spending,
approving a Blue-looking crew when the private plan wins Red, rejecting and
blaming the most Blue-looking crewmate, Contrarian exceptions, empty wallets,
and false Blue reports exposed by another crewmate's original receipt.

Accusation checks compare fresh and corroborated speakers: trusted accusations
have more influence on the target without a generic suspicion penalty on the
speaker. Other accusations also make the accuser more suspect. Tests verify
changes to later crew selection and to the influence of a subsequent accusation,
repeat deduplication, capped hearsay, preserved known contribution facts, and
exact belief restoration. A bot's own accusation cannot reinforce its private
beliefs. Existing complete-game resume and observation-isolation tests passed.

Designer-only client rendering now distinguishes the private forecast, forecast
with the public promise, and planned deposit. Desktop Chrome inspection on an
isolated replay confirmed a 5 Blue pledge accompanied by a 5 Red private plan,
with both forecast lines fitting the panel. Player views still receive only
ordinary public claims and their own permitted private information.

```bash
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 100 --seed 20260910 --out runs/deception-smoke
```

All 100 games completed and replayed exactly, with zero failures or unresolved
runs. Blue won 69 and Red 31; mean attempts were 7.33 (range 4–11), with 1,187
rejected proposals and 52 penalty attempts. There were 392 personal winners.
These are execution diagnostics, not a controlled estimate of human difficulty
or a claim of balance. Public-promise forecasts approximate other players'
responses; the policy does not maintain a separate belief model for each voter.
Cover reports can become implausible or directly contradicted by public evidence.

## Shared complaints and temporary Red goals

The default controller is now `social.4`; engine rules remain unchanged.
**131 Python tests and 13 client tests passed.** New paired checks cover both
sides making an exclusion protest and accusing a player with an objectionable
pledge; a Red bot no longer automatically accuses a cooperative Blue-looking
crewmate. Blue now rejects observed Red support even when those players kept
their promises, with that risk objection relaxing before the rejection penalty.
An unproven accuser's grounded objection adds no automatic speaker suspicion.
Existing trust weighting, rumor caps, private observation isolation, exact
save/resume, and replay checks still pass.

A Close Race regression checks Blue cover pledges, actual Red spending,
non-revealing complaints, and cover reports after the mission has satisfied the
temporary Red goal. A matrix of both teams, all nine objectives, and midgame /
near-ending scores checks that Social bots never pledge Red or request More Red.

The completed human game that prompted this change had a Blue Close Race Fran.
Feeding her recorded observations and saved personality to the new controller
changed all seven Red pledges to Blue cover promises while retaining private Red
plans. Her two More Red complaints became player objections. This checks the
recorded decision points, not a prediction of how that game would have unfolded
with every player using the new policy. The original recording was left intact.

```bash
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 100 --seed 20260910 --out runs/shared-complaints-smoke
```

All 100 games completed and replayed exactly: zero failures or unresolved runs.
Blue won 62 and Red 38; mean attempts were 7.16 (range 4–12), with 1,359 rejected
proposals, 67 penalty attempts, and 384 personal winners. An additional tally
of all simulated actions is saved in `complaint-audit.json` beside the summary:

| No-vote complaint | Blue team | Red team |
| --- | ---: | ---: |
| Less player | 2,074 | 3,002 |
| More me | 1,124 | 547 |
| More Blue | 306 | 903 |
| Less Blue | 108 | 84 |

All four complaint types occurred on both teams. The audit also groups by
desired winner to account for Contrarian: Blue-seeking bots used Less player
1,491 times and Red-seeking bots 3,585 times. There were zero public Red pledges,
Red complaints, or self-reports admitting positive Red deposits. These checks
establish overlap and remove the previous categorical complaint tell; they do
not establish that all behavioral tells are gone or that the game is balanced.

## Objective planning across crew, pledge, vote, and contribution

The default controller is now `social.5`; the objective cards, deck, and engine
rules are unchanged. **145 Python tests and 13 client tests passed.** Fourteen
new behavioral scenarios check:

- Saver protecting ten tokens in both pledges and deposits, while spending surplus.
- Saver and Passenger selecting affordable crews with a zero-paying self plan.
- Spendthrift demanding inclusion without a selfish personality and spending early.
- Exact Change saving below seven and distinguishing terminal spending from
  spending before continuing income, including a one-token payment at seven.
- Wallet objectives rejecting a forecast team victory that fails their condition.
- Reliable Partner seeking affordable qualifying attempts, honoring Blue cover
  promises even when seeking Red, and relaxing after two qualifying attempts.
- Passenger requesting a plausibly completing seat, discounting unreliable
  promises, and resuming ordinary funding after qualifying.
- Opposition Patron accepting useful opposing deposits, using mixed colors to
  complete the counter and win, and refusing an opposing game-ending victory.
- Close Race switching back before the opposing side gets a third point.
- Objective-based exclusion protests relaxing under rejection pressure.

Existing tests also cover terminal income timing, paid-counter exclusion of
penalties, private observation isolation, concealment, rumor limits, complaint
overlap, exact controller restoration, and replay from every phase. Designer
explanations now include the objective plan and projected wallet/income facts.

```bash
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 100 --seed 20260910 --out runs/objective-strategy-smoke
```

All 100 games completed and replayed exactly, with zero failures or unresolved
runs. Blue won 77 and Red 23; mean attempts were 7.14 (range 3–13), with 1,451
rejections, 58 penalty attempts, and 425 personal winners.

The same seeds as the `social.4` diagnostic dealt the same objective counts.
Final condition satisfaction changed as follows (this does not itself mean the
holder also won the game):

| Objective | Holders | social.4 satisfied | social.5 satisfied |
| --- | ---: | ---: | ---: |
| Saver | 62 | 42 | 54 |
| Spendthrift | 60 | 25 | 44 |
| Exact Change | 64 | 25 | 28 |
| Reliable Partner | 52 | 30 | 47 |
| Passenger | 50 | 26 | 29 |
| Opposition Patron | 58 | 48 | 51 |
| Close Race | 65 | 20 | 18 |

These are whole-population self-play diagnostics, not isolated strength tests:
every bot's behavior changed, and win rates are not a balance claim. Exact
Change and Close Race remain timing-sensitive. The policy plans affordable
actions and immediate income; it does not predict an entire future game or
know the other players' objectives.

## Payment uncertainty, harmful ties, and unnecessary saving

Reviewed the recorded human games [5F8D50](reviews/table-5f8d50.md) and
[C206B1](reviews/table-c206b1.md), verifying exact action replay before changing
the policy. `social.6` fixes their confirmed strategy defects: it scores weighted
integer payment outcomes, prefers a stronger tactical color margin when utility
ties, and removes automatic Less Blue complaints. It also removes the generic
spending penalty identified during review. Caution now discounts possible
downside, while wallet incentives remain objective-specific.

**152 Python tests and 13 client tests passed.** Seven new regression scenarios
cover legal integer forecasts and their means, a likely Blue tie hidden behind
a Red mean pot, Blue-seeking Loyalist/Contrarian/qualified Reliable Partner
plans across decision phases, no generic hoarding reward, risk caution,
Passenger's scenario-specific completion reward, and Saver's public complaint.
Existing objective, privacy, persistence, accusation, and replay tests still
pass. Client checks include the separate mission/personal outcome estimates.

Eleven original decision boundaries were independently reevaluated from the
recorded observations, traits, and beliefs. Artifacts are in
`runs/payment-forecast-review/{source-observations,decisions}.json`:

- 5F8D50: Fran and Drew replace unnecessary Red plans with all-Blue plans.
  At their actual contribution boundaries they now pay seven Blue each, instead
  of two Blue/two Red and one Blue/two Red respectively. This changes amount as
  well as color because extra funding now improves the uncertain outcome.
- 5F8D50: Ben still votes No while unready for Saver, but objects to Fran's
  unreliable promise instead of asking for Less Blue.
- C206B1: Gray's provisional plans become three Blue and one Blue.
- C206B1: Casey's final-crew approval changes to No. The new model estimates
  about 62% Blue versus 38% Red, rather than treating a fractional Red lead as
  a certain Red victory. Two Red remains his best payment if approved anyway.

These comparisons hold the historical information fixed. They are not claims
that the revised whole game would follow the original later trajectory.

```bash
python3 -m unittest discover -s tests -q
node --test tests/test_web_ui.cjs
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 100 --seed 20260910 --out runs/payment-forecast-smoke
```

All 100 games completed and replayed exactly, with no failures or unresolved
runs. Blue won 63 and Red 37; mean attempts were 7.66 (range 4–11), with 1,859
rejections, 97 penalty attempts, and 447 personal winners. Full objective
breakdowns are in `runs/payment-forecast-smoke/summary.json`.

Relative to `social.5` on these seeds, rejections increased from 1,451 and
penalty attempts from 58. That is a real interaction change to assess in human
play; removing forecast overconfidence does not automatically make voting more
cooperative. Personal-condition satisfaction improved for Exact Change (28 to
46) and Passenger (29 to 45), but declined for Reliable Partner (47 to 41) and
Spendthrift (44 to 38). These simultaneous population changes are diagnostics,
not an isolated strength comparison or a balance claim.

## Fixed teams and Blue-only Contrarian

Rules `0.1-objectives-dev.3` and `0.1-common-rules-dev.3` always deal five Blue
and three Red allegiances. Contrarian remains optional and can only go to a
Blue player. Objective dealing preserves the original eight drawn cards; if
Contrarian initially lands on Red, it swaps with a uniformly selected Blue
seat. Its inclusion chance remains 8/14 with the default deck. Presence and
holder are private. `social.7` starts from the public fixed team counts, with
own allegiance excluded from the prior for the other seven seats.

**158 Python tests and 13 client tests passed.** Setup tests cover both rules
profiles over 100 seeds, Blue-only eligibility, unchanged drawn-card sets,
optional presence, all eligible recipients, private observations, exact
snapshot restoration, and rejection of invalid team counts or a Red
Contrarian. Diagnostics tests verify separate results for games with and
without the optional fourth Red-seeking player.

```bash
python3 -m unittest discover -s tests -q
node --test tests/test_web_ui.cjs
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 100 --seed 20260910 --out runs/fixed-teams-smoke
```

Both local web servers were restarted and verified to serve the updated
player guide and fixed 5–3 table description over HTTP.

All 100 simulated games completed and replayed exactly, with zero failures or
unresolved runs. Every completed record has five Blue and three Red players,
and every Contrarian holder is Blue. Blue won 25 and Red 75; mean attempts were
7.58 (range 4–11), with 2,662 rejections, 178 penalty attempts, and 387 personal
winners. Full results are in `runs/fixed-teams-smoke/summary.json`.

| Contrarian | Games | Blue wins | Red wins | Rejections | Penalty attempts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Absent | 38 | 24 | 14 | 546 | 16 |
| Present, held by Blue | 62 | 1 | 61 | 2,116 | 162 |

This is a substantial swing toward Red in current bot self-play, especially
when Contrarian is present. Four players seeking Red can deny the five Yes
votes required for approval, and repeated rejections add Red tokens. The high
rejection and penalty counts in Contrarian games are consistent with that
advantage; this run does not isolate its causal contribution or establish
human-game balance. Mission costs, the three-mission victory target, approval
threshold, and rejection penalties remain unchanged.


## September 11, 2026 — hidden abilities and Contrarian disabled

New sessions use `0.1-abilities-dev.1`, schema 3, with a 13-card objective deck
excluding Contrarian. The eight ability implementations cover independent dealing,
private preparation, use limits, bonuses, clipped theft, paid off-crew deposits,
chained recoloring, audits, and public badges. Existing comparison profiles remain.

Validation on this change:

- `python3 -m unittest discover -s tests`: **177 tests passed**, including local
  HTTP integration tests (loopback socket access required).
- `node --test tests/test_web_ui.cjs`: **16 tests passed**, including guided
  private choices, separate spending/theft budgets, receipts, and badge rendering.
- Ten seeded default Social games (`20260911` through `20260920`) completed with
  no failures or unresolved games; every game verified deterministic action replay.
  This smoke sample produced eight Blue and two Red wins. It is an execution
  check, not evidence of balance.
- Chrome check against an isolated temporary local table verified the ability
  card and official badge, off-crew Thief pass/use controls, source selection,
  amount input, submission, actual-transfer receipt, and consumed use state.

New rule tests specifically check modifiers after the funding threshold is
crossed, mission theft clipping without color substitution, duplicate theft
initiative independent of response arrival, chained recolorings that unlock an
all-Green pot, penalty effects without audits/reports, sequential swaps with final
notifications, private scouting, post-modification original-deposit audits,
closing audits after terminal wallets freeze, invalid-action atomicity, sealed
arrival privacy, and every partial batch's save/restore/retry/replay behavior.

With abilities enabled, Social no longer uses public wallet/pot arithmetic to
certify original payments or lies. Private receipts and audits provide evidence;
unknown effects remain outside its tactical forecast. Arbitrary rule learning,
optimal joint ability/payment plans, and ability balance are not established.

## September 11, 2026 — joint ability planning (`social.9`)

Default Social bots now evaluate their own payment and ability as one plan,
including original paid-history credit, final wallets, funding, colors, and
rejection penalties. Scouting and audit choices use information value; private
evidence informs later beliefs. Repeated net effects with independently known
crew payments can become tentative forecast scenarios. Previous controller
versions retain their previous algorithms when restored.

Focused validation:

- The full Python suite passed **200 tests**, including HTTP integration and
  resuming every phase with identical actions, beliefs, and explanations. One
  additional forecast/engine conformance test then passed with the focused
  suite below, bringing coverage to **201 passing Python tests**.
- **24 ability-strategy tests passed**, including forecast/engine conformance,
  ability-dependent voting, clipped transfers after spending, choosing one stolen
  token to preserve funding, end-wallet objectives, original-payment credit,
  information targets, retained inspections, cautious residual learning, sealed
  arrival privacy, and exact controller restoration.
- **16 browser tests passed.** Designer decisions retain the joint ability plan,
  wallet estimates, alternatives, and effect hypotheses in their forecast details.
- Ten seeded default Social games (`20260911`–`20260920`) completed and replayed
  exactly, with zero failures and zero unresolved games. Blue won six and Red
  four. This small execution check does not establish balance or playing strength.
  Results: `runs/ability-planning-smoke/summary.json`; a complete saved game is
  in `runs/ability-planning-smoke/example-replay.json`.
- Both existing local servers (ports 8765 and 8766) were restarted with their
  original saved-game libraries; their pages and library endpoints returned 200.
  New tables use `social.9`; existing tables retain their recorded policy version.

```bash
python3 -m unittest tests.test_ability_strategy -v
python3 -m unittest discover -s tests
node --test tests/test_web_ui.cjs
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 10 --seed 20260911 --out runs/ability-planning-smoke
```

The new planner does not expose opponents' hidden cards. Unknown interactions
remain incompletely modeled, and inferred recurring effects can have competing
explanations. Random and Straightforward remain simpler comparison policies.

## September 11, 2026 — vote revenue, four missions, and paced tables

New defaults use `0.1-abilities-dev.2` and `social.10`. Every player receives
one token after all eight ballots, regardless of the proposal result. Existing
continuing-attempt income remains; first to four wins, with Close Race requiring
4–3. Previous rules and policy versions remain restorable.

- **214 Python tests passed**, including exactly-once vote revenue on both
  outcomes, all eight rejections, terminal wallet freeze after the fourth point,
  Close Race 4–3, spending newly received revenue, avoiding premature third-point
  victory forecasts, and compatibility with previous profiles/controllers.
- Paced/instant runs produced identical actions, bot memories, outcomes, and
  verified replays. Tests cover stopping for human input, read-only paced resume,
  persisted boundaries, stale step rejection, and at most one public ballot per
  advance. Other players’ sealed responses do not become visible steps.
- **24 client tests passed**, including score targets, public player histories,
  private-action isolation, exact wallet and pot comparisons, manual/speed/pause
  behavior, and ignoring responses from a previous route.
- Ten games (`20260911`–`20260920`) completed with zero failures or unresolved
  games and verified action replay. Records are in
  `runs/revenue-four-missions-smoke/`. These are execution checks, not balance
  measurements or an isolated estimate of the revenue rule’s effects.
- Chrome verification on an isolated table exercised manual and automatic
  progression, stopping at a human request, individual public votes, the eighth
  ballot’s revenue, player-history expansion, 5→6 wallet changes, net resolution
  changes, four-point score displays, and the 0→10 Blue pot comparison after a
  resolved mission. Both running user servers retain their original libraries.

```bash
python3 -m unittest discover -s tests
node --test tests/test_web_ui.cjs
python3 -m mission_game.cli simulate --games 10 --seed 20260911 \
  --out runs/revenue-four-missions-smoke
```

Pacing is browser-controlled but advances actual saved server state. Speed
changes apply between completed steps; an already submitted step may finish
when Pause is pressed. New rules require a new table; existing games gain the
UI improvements while retaining their recorded rules.

## September 11, 2026 — table clarity cleanup

- **31 client tests passed** (`node --test tests/test_web_ui.cjs`). Coverage
  includes named vote reasons, revealed pledge quantities, historical crew
  context across repeated proposals, correct final-ballot outcomes on resume,
  escaped player names, own sealed choices, and suppressing income notices
  while retaining accurate mission-resolution wallet deltas.
- Chrome verification on an isolated saved table confirmed the last-step
  explanation, full-card hover and click area including empty lower space,
  and a No-vote history entry with chairman, full crew, and complaint. Advancing
  the final two ballots updated the explanation individually; balances moved
  from five to six without income labels or added income history rows, and
  play stopped for the human's next ability choice.
- Changes are confined to browser presentation and documentation. Existing
  tables gain the cleanup on refresh; game rules and saved events are unchanged.

## September 11, 2026 — custom delay and collapsible comparison

- **32 client tests passed** (`node --test tests/test_web_ui.cjs`), including
  custom fractional delays, saved preferences, manual mode, invalid timer values,
  suspending automatic steps while editing, and preserving the comparison's
  expanded state through updates.
- Chrome verification confirmed a 2.75-second delay survives refresh, the entire
  comparison starts behind a caret, and expanding it preserves the existing
  token table. The comparison stays expanded when playback controls rerender.

## September 11, 2026 — compact private cards

- Restored the private cards above the live action panel. Objective and ability
  carets show concise reminders; full rules, objective progress, and private
  results start collapsed. Ability availability stays visible.
- **33 client tests passed**, covering the opposing color in Opposition Patron,
  three- and four-mission Close Race summaries, Contrarian's reversed win
  condition, hidden global progress, and expansion state across updates and
  different replay seats.
- Chrome verification with Opposition Patron and Thief confirmed both compact
  summaries and the action panel are visible together. Each caret reveals its
  existing full explanation, including the permitted objective progress.

## September 11, 2026 — aligned badges and stable replay perspectives

- Official badges now use a colored check on the avatar, preserving the same
  name and wallet alignment across players. Hover text retains the full team
  and official-badge description.
- Completed replays preserve the recorded moment when changing seats or
  toggling Designer view. Shared positions map to each view's visible frame;
  unfinished replays neither expose nor accept those positions.
- **35 client tests and 16 web tests passed**, including different visible
  frame counts, private-action boundaries, round trips between views, start/end
  positions, invalid positions, and existing replay privacy restrictions.
- Chrome verification confirmed aligned cards and a perspective/Designer-view
  switch that stayed on the same vote. Both running servers were updated with
  their existing save directories.

## September 11, 2026 — confirmed allegiance and cheap Blue pledges (`social.11`)

- Blue crew selection minimizes known Red seats before private-objective gains;
  covert Red likewise avoids publicly exposed allies. Votes object to avoidable
  known Red crew members, with exceptions for rejection pressure and a near-certain
  personal win. Public vote forecasts distinguish badges from private inspections.
- Blue pledges earn no allegiance or reliability credit. Unproven promises are
  discounted by inferred cooperation, while verified kept promises earn trust.
  Confirmed teams remain separate from uncertain payment behavior.
- **11 focused allegiance tests passed**, including repeated claims, both sources
  of team evidence, Close Race and Opposition Patron, forced crews, vote pressure,
  cast ballots, verified payment evidence, and deterministic controller restoration.
- **226 full-suite tests passed**, covering rules, abilities, sessions, replay,
  controller behavior, persistence, and the local HTTP interface.
- Reconstructed Drew's Opposition Patron proposal from saved table `08061740`:
  the new controller replaces the officially Red member. Twelve representative
  `social.9`/`social.10` decisions matched the pre-change implementation exactly,
  including designer explanations and controller snapshots.
- Stopped the leftover web server on port 8765. Restarted only 8766 with its
  existing save directory and verified the current table still loads over HTTP.
  New tables use `social.11`; saved tables retain their recorded controllers.

## September 11, 2026 — editable mission ranges and unique abilities

- New web and CLI tables read `configs/development_abilities.json`; web creation
  rereads the file for every table, and `web --config` selects an alternate file.
  The edited profile uses thresholds 15–30 and crew sizes 2–5. Saved sessions
  continue to use their embedded settings, including after subsequent file edits.
- Rules `0.1-abilities-dev.3` deal one copy of every ability with an independent
  shuffle. Duplicate abilities are rejected by current-game invariants and snapshot
  loading; earlier rules keep their original assignments and range validation.
- **8 config/dealing tests passed**: live file edits, invalid-file rejection,
  default and explicit CLI paths, larger missions with five-person crews, replay,
  uniqueness over 80 seeds, deterministic deals, isolated random streams, and
  preservation of old saves with duplicate abilities. **49 focused ability,
  revenue, rules, and pacing tests passed** as well.
- **235 full-suite tests passed**, including complete games, web transport,
  controller restoration, and replay compatibility across the supported profiles.
- Restarted the existing server on 8766 and checked the updated guide and old
  table over HTTP. The existing table's full replay also verified unchanged.

## September 11, 2026 — Red cover and reserves (`social.12`)

- Red ability planning now prices public exposure and lost reserves during
  continuing games. Helpful small Blue payments can build diminishing cover;
  public Red badges remove that incentive. Terminal outcomes retain personal
  win-condition scoring. Cover-pledge penalties are bounded independently of
  actual pledge-dependent objectives. Blue and older policy behavior is preserved.
- **65 focused tests and 248 full-suite tests passed**, including new checks for
  concealed/exposed Red, terminal wins and defense, redundant spending, losing
  cover pledges, wallet objectives, Close Race, public/private evidence separation,
  and deterministic controller restoration.
- Recomputed all **510 original `social.11` bot decisions** from the second blind
  game: actions, explanations, and final controller snapshots matched exactly.
  Both original blind-game replays still verify.
- On the original opening observations, the three Red payments change from
  11/11/10 Red to two Blue each. This comparison holds observations fixed; it
  does not rewrite the original game or predict its complete counterfactual.
- **32 paired bot games** (16 seeds, only Red upgraded) all finished and replayed
  exactly. Red won **3/16 with the revision versus 2/16 before**: inconclusive for
  strength. Revised Red spent no Red tokens in any opening attempt; caution and
  predictability need further blind testing. Mean attempts rose from 9.25 to
  10.56, and mean rejected proposals from 29.75 to 38.94. No weights were tuned
  against these results. Artifacts: `runs/red-strategy-2026-09-11/`.
- Restarted the existing server on 8765 with the same `runs` library. New games
  use `social.12`; saved games retain their recorded controllers.
