# Current computer players

New games use `social.16`, `straightforward.5`, or `random-legal.4` with private
wallets, quantity-only pledges, weighted votes, and Green reserves. Previous bot
behavior and old replay compatibility are not maintained.

`mission_game/hidden_policy.py` is the current Social/Straightforward decision
path. It receives only the same seat observation as a human. It never reconstructs
other players’ balances or treats aggregate pot changes as exact contributions.
The previous exact-payment forecasting modules are bypassed.

Social bots rank crews using their own seat, known badges/scouting, private
audits, attributed reports, weak shared outcome evidence, and costly voting
behavior. Inclusion requests receive a bonus only with sufficient trust; asking
repeatedly cannot override a confirmed opponent or a verified liar. A quantity pledge is assumed
Blue but does not prove allegiance or honesty. Forecasts distribute others’
pledges across Blue and Red using observed payment behavior, separately from
confirmed allegiance. Actual funds and payments remain unknown. A second case
allows each other crew member to exceed a pledge by half its quantity, or one
token for a small pledge. This is a sensitivity check, not a payment cap or a claim about
their wallet. Plausible opponent match-point completions override cover and
rejection pressure. These estimates are not calibrated probabilities.

Secret deposits come from a small set of affordable choices, scored for mission
progress, ownership, and the private objective. Saver and Exact Change retain
funds, Spendthrift seeks spending, Reliable Partner tries to honor qualifying Blue
pledges, and Passenger seeks a free ride. Green Machine considers Green and mixed
deposits, Green Stowaway payments, Echo bonuses, and recoloring into Green while
pursuing its table-wide goal. The exact resolved global counters, plus pending
Green reserves, determine how much more is needed. Opposition Patron also
uses the global paid-color counter instead of assuming it must fund the goal alone.
Close Race pursues its own match point before temporarily preferring the
opponent to reach the required close finish. Red spending may be concealed by a Blue report. Cover quantities are
capped by the bot's pledge and this attempt's visible Blue increase, after
subtracting other Blue deposits it privately audited on this attempt. They do
not repeat the hidden amount spent in Red. Truthful original-payment reports
remain intact even if theft or recoloring reduced the visible net increase.
Reports are claims.

Audits and remembered own payments verify only the original deposit on the
matching attempt. A contradicted report damages its speaker's credibility and
affects later crew selection, forecasts, and voting. An audit of a deposit
cannot verify a theft claim. An aggregate net change cannot prove a report false:
theft, recoloring, Echo, and off-crew payments can change the pot. A truthful
partial report does not deny other colors. Another player's private receipt
never becomes public knowledge automatically.

Self-reports have small, capped influence. Accusations are attributed to their
speaker, weighted by credibility, and capped per speaker/target across repeated
reports and complaints. Own accusations supply no independent corroboration.
Known Red accusers and repeated pressure against independently supported players
raise concerns about framing, without automatically proving their claims false.
Bots can answer with a targeted `Less player` complaint when rejecting a crew.
They prefer a safer available crew, while allowing favorable funded missions
and relaxing objections before rejection penalties. They do not invent an exact
Red payment merely because a team inspection revealed Red.

Auditors prioritize disputed payment reports instead of picking randomly. Scouts
prioritize consequential unknown players. Both use only their own seat's view.

Votes consider those estimated deposits and the objective. Social and Straightforward
bots may bid at any point in the vote, without a ten-token cap. They use the
current weighted tally, remaining voters' estimated preferences, observed spending,
and plausible counter-bids. Early bids weigh improved odds against token cost,
valuing a full unit of success probability at 40 tokens, or 120 for a possible
match-point completion. Value stops growing at 95% confidence, or 99% near game
end. Bots may conserve tokens below those targets when an improvement is too
expensive, and do not insure every remote modeled counter-bid. These are
heuristic values and confidence targets, not calibrated probabilities.
Once all other votes are cast, the calculation is exact and the bot pays only
what is needed to approve or reject. An ineffective bid is not spent.

Yes bids preserve the funding needed for the favorable mission forecast. No
bids can use money previously intended for the rejected mission; preventing an
immediate loss can override a wallet-saving objective. Green Thumb's free
influence is included. Other wallets remain hidden, so early bids cannot provide
an unconditional guarantee against future spending.

Proposal income arrives before pledging and is already in the wallet. Planned
deposits never add that income a second time after voting. Crews can be supported
for improving a persistent pot in stages even while the opposing color leads,
provided the payment sensitivity case does not predict an opposing completion.
Red may approve a nonterminal crew for cover without paying to accelerate a
forecast that only improves the other side's position.

Paid Yes/No votes update behavioral preferences in the context of the proposed
mission. Heavier spending is stronger evidence; automatic Green Thumb bonuses
are not treated as voluntary spending. Bots reassess that evidence against the
actual mission result, without confusing an earlier rejected crew's voters with
the approved crew's voters. A self-inclusion complaint weakens the allegiance
inference. Scout and public-badge team estimates remain exactly 0% or 100% Blue;
behavior is tracked separately and cannot dilute those facts. Behavior can still reflect private objectives.
These beliefs affect later crew choices, contribution forecasts, and bids.
Reveal all explanations include claim credibility, verified pledge reliability,
known teams, evidence, and the bid forecast.

Ability choices use private instructions
and basic heuristics; another player’s hidden wallet is never a theft oracle.

Straightforward uses simpler pledge-honoring forecasts. Random samples legal
quantities, colors, and affordable influence. All policies preserve enough state
for current games to save and resume. Designer explanations identify uncertainty.

Routine validation is `make test`: a small current-rules smoke suite. Historical
bot regressions and replay audit batches are not required for routine changes.
