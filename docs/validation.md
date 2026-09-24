# Current validation — September 23, 2026

Run `make test` for the current rules: 38 Python smoke checks and 15 client
checks. They cover weighted votes/ties, affordability, private wallets, quantity
pledges, reserve timing/rounding, current save/resume, complete games for all three
bot types, remembered objections, per-color result deltas, plausible bot cover reports,
linked player histories, revealed-card navigation, immediate game endings without
reports, every player's final outcome, and an optional audit after revealed reports
using a single dropdown, Green Machine's additions from every source (including
reserves, Echo, Stowaway, and recoloring despite subsequent theft), and Green
Thumb's free vote influence. Bot checks also cover early bids, decisive Yes/No
bids above ten tokens, preserving mission funding, ineffective bids, and learning
from paid votes and their mission outcomes. Table 6022F9-inspired checks cover
fixed Scout certainty, private audit contradictions, remembered own payments,
claim credibility and repetition limits, targeted objections to a known Red
accuser, useful audit targets, and the distinction between original deposits,
partial reports, theft claims, and net pot changes. The reserve display combines
whole tokens and fractional progress (for example, `0.8 Green in reserve`).
Historical full-suite and replay/bot audits are not required validation for
the current rules. Old validation notes and raw diagnostics are kept locally
under the ignored `runs/` directory.

## Browser deployment preparation

The static build was checked in headless Chrome 153 under `/site/`, matching a
GitHub Pages project subdirectory. The real Pyodide 314.0.7 worker created and
resumed games after reload, shared saves between tabs, rejected stale actions,
and preserved two concurrently created games. One generated sample completed
and opened its replay in about 1.8 seconds in the final browser check. Bot
rankings followed the selected seat and replay position; rewinding cleared
later assessments. Desktop and 390px mobile screenshots were inspected, with
no page overflow. The check saw no page errors, HTTP game API requests, or
requests to external hosts. The original local HTTP create/state flow also passed.

`make test` passed all 38 Python and 15 client checks. Packaging checks reject
unfinished examples and mismatched runtime checksums, include only explicitly
selected finished saves, and exclude unlisted model transcripts. All three
final Astra playthroughs are now bundled: 86 recorded decisions and 15 mission
predictions. Every completed replay verified exactly, and each
prediction matched the reconstructed seat observation at its saved position.
All three featured replays passed the browser check, including prediction
display, selected-bot rankings, rewind, and mobile layout. See the
[playthrough provenance](../examples/provenance.md).
GitHub Pages has not been enabled or deployed from this session; the workflow
and setup steps are in [deployment instructions](deployment.md).
