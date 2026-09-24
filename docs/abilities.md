# Hidden abilities: implemented rules and limits

New sessions use `0.1-abilities-dev.5` (schema 5) and a 14-card objective deck:
six Loyalists, one of each other objective except Contrarian. Contrarian is
currently disabled. The previous objectives and common-rules profiles remain
available for controlled comparisons with the new token rules. Old saves are incompatible.
Green Machine requires a team win and 20 Green tokens added across the whole
table, including deposits, reserves, bonuses, and recoloring into Green.
Later theft or recoloring away from Green does not erase prior additions.
Green Machine and Opposition Patron show exact table-wide progress out of 20
on their cards. Public history records cumulative original paid-color totals
and all Green additions after each resolution, without identifying individual deposits.
Every player receives one token when each crew is selected, before pledging.
No income arrives after voting. Continuing-attempt income remains separate.
First to four wins; Close Race is a 4–3 finish. Start a new table for these rules;
older saves are not migrated.

New deals shuffle one copy of each of the nine abilities and give eight to the
eight seats, leaving one out at random. Duplicate abilities are rejected in new-version snapshots; older versions
retain their original assignments, including duplicates. Ability randomness does
not change teams, objectives, missions, or bot
personality. Cards are private; public badges and vote bonuses remain visible.

New web/CLI tables load `configs/development_abilities.json`, currently thresholds
15–30 and crews of 2–5. Web creation rereads the file for each table. Current
rules accept positive ordered threshold ranges and crews of 2–8; saved profiles
retain their embedded ranges, and older versions retain their validation limits.

| Ability | Implemented behavior |
| --- | --- |
| Thief | Once per game, request 1–3 tokens from another wallet or the mission; clip to availability after all deposits and bonuses. A valid empty attempt still consumes the use. Own actual transfer is privately reported. |
| Stowaway | When off crew, pay one token for one chosen-color deposit, including on penalties. It counts as a paid deposit, but does not confer crew/report privileges. |
| Auditor | After crew reports are revealed, optionally inspect one crew member's original deposit, if the game continues. |
| Switcher | Once per game, exchange objectives before a proposal. Sequential swaps use current cards; all affected seats learn only their final card and permitted progress. Seat histories stay with their players. |
| Standard Bearer | True allegiance has an official public badge; objective and ability card stay private. |
| Scout | Once per game, learn another seat's true team after swaps and before crew selection. The target receives no notification. |
| Recolorer | Each attempt, commit two different colors; after theft change one available mission token, including old tokens. No source token means no effect. |
| Echo | An approved-crew original payment of at least two in exactly one color creates one free matching token. No cost, paid-history credit, or pledge mismatch. |
| Green Thumb | Every Yes or No ballot automatically receives 5 free influence, combined with spending for weighted votes and tiebreakers. No wallet cost, reserve generation, or activation. |

The authoritative sequence is accumulated Green reserves, paid deposits/penalty and Stowaway deposits, Echo
bonuses, thieves in initiative order, recolorers in initiative order, scoring,
objective history and terminal freeze, public result, then reports, private audits,
and income only if continuing. Initiative begins with the final proposer; preparation
begins with that proposal's chairman. All modifying choices use the same
pre-result information. Penalties allow hidden modifying actions but skip audits
and reports. A final resolution goes directly to game over and publishes every
player's personal win/loss outcome; wallet balances remain private.

Private preparation uses two fixed all-seat cover batches: swaps then scouting.
Hidden commitments and approved audits also have fixed cover slots. Sessions
fill slots with no available decision automatically; players are shown only
choices their own cards allow. Pending arrivals do not change another seat's
observation or revision. No public event identifies ability users or reveals a
pre-modification deposit total. Snapshots and designer replay retain receipts,
use counters, sealed choices, and ordered effects for verification.

Web abilities use a single dropdown to choose an action or pass: a player for
Scout, Switcher, and Auditor; a one-token color for Stowaway; a color change for
Recolorer; or a source for Thief. Thief then asks for a quantity (or quantities
by color for mission tokens). The submit button names the selected action.
Passive abilities are marked automatic, with an Echo bonus preview when a
contribution qualifies. The private panel shows remaining once-per-game uses
and receipt history. The terminal also guides targets, sources, quantities,
colors, and passing. Ordinary replays expose only a seat's permitted information; designer
inspection additionally shows hidden cards and effects.

## Scripted opponents

Current games use `social.15`, `straightforward.4`, or `random-legal.4`.
Wallets are private; no controller has another player’s exact funds or a public
balance-change oracle for their contributions. Old exact-payment forecasts are
bypassed. Current ability choices use private instructions and small heuristics;
see [bot notes](bots.md) for the current strategy and limitations.
