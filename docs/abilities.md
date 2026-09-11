# Hidden abilities: implemented rules and limits

New sessions use `0.1-abilities-dev.2` (schema 3) and a 13-card objective deck:
six Loyalists, one of each other objective except Contrarian. Contrarian is
currently disabled. The previous objectives and common-rules profiles remain
available for controlled comparisons; existing supported saves keep their rules.
No new objective types were added. Every player receives one token after each
full vote (pass or fail), before contributions or penalties. Continuing-attempt
income remains. First to four wins; Close Race is a 4–3 finish. The preceding
abilities profile retains its first-to-three rules and has no vote revenue.

Each seat independently draws one of eight abilities, uniformly, with duplicates
allowed. Ability randomness does not change teams, objectives, missions, or bot
personality. Only the holder's private card and controls disclose its rules.

| Ability | Implemented behavior |
| --- | --- |
| Thief | Once per game, request 1–3 tokens from another wallet or the mission; clip to availability after all deposits and bonuses. A valid empty attempt still consumes the use. Own actual transfer is privately reported. |
| Stowaway | When off crew, pay one token for one chosen-color deposit, including on penalties. It counts as a paid deposit, but does not confer crew/report privileges. |
| Auditor | After an approved result, inspect one crew member's original deposit before reports, including in the closing phase. |
| Switcher | Once per game, exchange objectives before a proposal. Sequential swaps use current cards; all affected seats learn only their final card and permitted progress. Seat histories stay with their players. |
| Standard Bearer | True allegiance has an official public badge; objective and ability card stay private. |
| Scout | Once per game, learn another seat's true team after swaps and before crew selection. The target receives no notification. |
| Recolorer | Each attempt, commit two different colors; after theft change one available mission token, including old tokens. No source token means no effect. |
| Echo | An approved-crew original payment of at least two in exactly one color creates one free matching token. No cost, paid-history credit, or pledge mismatch. |

The authoritative sequence is paid deposits/penalty and Stowaway deposits, Echo
bonuses, thieves in initiative order, recolorers in initiative order, scoring,
objective history and terminal freeze, public result, private audits, reports,
then income if continuing. Initiative begins with the final proposer; preparation
begins with that proposal's chairman. All modifying choices use the same
pre-result information. Penalties allow hidden modifying actions but skip audits
and reports. Closing audits cannot alter frozen wallets, cards, or outcomes.

Private preparation uses two fixed all-seat cover batches: swaps then scouting.
Hidden commitments and approved audits also have fixed cover slots. Sessions
fill slots with no available decision automatically; players are shown only
choices their own cards allow. Pending arrivals do not change another seat's
observation or revision. No public event identifies ability users or reveals a
pre-modification deposit total. Snapshots and designer replay retain receipts,
use counters, sealed choices, and ordered effects for verification.

Web and terminal adapters include guided targets, sources, quantities, colors,
and passing. The private panel shows remaining once-per-game uses and receipt
history. Ordinary replays expose only a seat's permitted information; designer
inspection additionally shows hidden cards and effects.

## Scripted opponents

New games default to `social.10`. Each policy receives only its own observation.
Saved `social.7`, `social.8`, and `social.9` controllers restore their previous decision
algorithm; a browser refresh does not upgrade an existing game's opponents.
`straightforward.3` and `random-legal.3` remain simpler diagnostic comparisons.
Random chooses legal activations and passes; Straightforward uses independent
ability heuristics. The joint planner described below is specific to Social.

Social compares its own deposit and ability together when selecting a crew,
pledging, voting, and committing. Each candidate ability is fixed across possible
opponent payments, then evaluated after deposits, bonuses, transfers, and color
changes. This avoids choosing a different secret action for each possible future.
Its private plan is separate from the public promise used to predict other votes.
The final rejected proposal also considers abilities during the penalty attempt.
`social.10` uses the table’s winning score and forecasts the pending vote revenue
for deposits and final wallets. Pledges remain limited to current funds; rejected
proposals also award revenue. Paid-history inference excludes both income sources.

| Ability | Social planning |
| --- | --- |
| Thief | Compare passing, mission requests totaling 1–3, and wallet amounts 1–3 from three promising public targets. Clip transfers after predicted spending; account for final wallet and funding. Preserve the limited use when no concrete benefit outweighs its heuristic cost. |
| Stowaway | Compare passing and each color off crew. Count the paid token toward spending/wallet goals and funding, without granting Passenger or Reliable Partner crew credit. |
| Recolorer | Compare passing and all six color changes, including Blue ties and effects on old mission tokens. |
| Echo | Include the free token when choosing pure deposits and testing funding; keep original payment and pledge credit separate. |
| Scout | Prefer relevant unknown allegiances, considering wallet, chairman, and uncertainty; retain the inspection as certain team evidence. |
| Auditor | Prefer substantial, unverified crew pledges; use original-payment receipts to update trust and future forecasts. |
| Switcher | Keep a met or readily achievable objective; consider an unknown replacement when the current condition is difficult near the finish. Never inspect the target's card. |
| Standard Bearer | Recognize official allegiance badges, while keeping allegiance separate from inferred cooperation and objective incentives. The badge itself is automatic. |

Audit and own-deposit receipts verify original payments. With abilities enabled,
public pot and wallet differences do **not** produce contribution bounds, liar
verdicts, or exact paid-history totals. Opposition Patron's tracked total is a
verified lower bound from available receipts; prospective payments are estimates.
Reports of removals or off-crew deposits are not automatically judged false.

Social also records unexplained color changes when **every crew payment is
independently known**. Two matching residuals with the same crew produce a
tentative extra forecast scenario, with confidence capped at 40% and a no-effect
alternative retained. Own known bonuses/transfers are removed first; ambiguous
own recoloring is excluded. Reports alone cannot train these hypotheses. The
inference identifies a recurring net effect, never an opponent's ability card.
Evidence and hypotheses persist across saves and appear in designer decisions.

This remains a short-horizon heuristic search, not optimal play or arbitrary
rule discovery. Unknown interactions, opponent wallet theft, and future swaps
are not exhaustively modeled. Residual patterns can have competing explanations
and need not recur. The implementation does not establish balanced win rates or
benchmark validity; adding or re-enabling objectives should follow playtesting.
