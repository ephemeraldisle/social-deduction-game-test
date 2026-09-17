# Blind AI playthrough

Model: gpt-6-astra. Seat: Abby. No tools or source access.

Result: {'blue': 2, 'red': 4}. 1152 actions replayed exactly.

## Postgame assessment

The player won as a Red Loyalist, 4–2, after ten resolved attempts and 25 rejected proposals. It made 60 game decisions and six prediction checkpoints, with no invalid actions.

Using the more likely team in each probability estimate, accuracy was **8/8 after mission 1**, then **6/8 after missions 2–6**. These counts include Abby's known own team and Casey's public Blue badge; accuracy on the other six seats was 6/6, then 4/6.

The persistent mistake was **Drew → Blue, Gray → Red**. Drew was actually a Red Loyalist; Gray was Blue with Opposition Patron. Gray's Red deposits advanced a personal condition, illustrating why observed color preference need not identify allegiance. The player explicitly acknowledged this uncertainty but still became too confident in the wrong assignment. These observations were added only after the final prediction; none was supplied to the player.

[Open all predictions in Designer view](http://127.0.0.1:8765/#replay/bbcbbc23-84a9-4eb9-8fe7-f62d557897c4?seat=p0&designer=true&step=-1).
Click a mission row to seek to its checkpoint. Earlier frames hide later predictions. Expand “Evidence and changes” for each player's explanation.

## Predictions recorded during play

Each cell is the model's probability of Blue; Red is the complement.

| Mission | Abby | Ben | Casey | Drew | Ellis | Fran | Gray | Harper |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0% | 92% | 100% | 34% | 79% | 88% | 82% | 25% |
| 2 | 0% | 97% | 100% | 69% | 88% | 95% | 6% | 45% |
| 3 | 0% | 99% | 100% | 94% | 95% | 98% | 6% | 8% |
| 4 | 0% | 99% | 100% | 94% | 94% | 97% | 8% | 8% |
| 5 | 0% | 99% | 100% | 78% | 97% | 98% | 18% | 10% |
| 6 | 0% | 99% | 100% | 86% | 97% | 98% | 18% | 2% |

Actual teams (revealed only after the final prediction): Abby: red; Ben: blue; Casey: blue; Drew: red; Ellis: blue; Fran: blue; Gray: blue; Harper: red

## After mission 1

Confirmed p0 Red and p2 Blue. Actual mission funding most strongly favors p1 and p5 as Blue; p3 and p7 are the leading remaining Red candidates, but objective-driven voting is a significant confounder. Marginals sum to five Blue players.

- **Abby (0% Blue):** Own private card confirms Red allegiance.
- **Ben (92% Blue):** Both resolutions strongly support substantial Blue payments: eight tokens initially and six subsequently, accounting for my known Red deposit and recoloring. Inclusion-driven voting leaves some objective-related uncertainty.
- **Casey (100% Blue):** Official public badge confirms Blue.
- **Drew (34% Blue):** Repeatedly blocks proposals when excluded, and p6 consistently objects to p3's inclusion. Blue pledges are untested; a personal participation objective could explain much of this behavior without Red allegiance.
- **Ellis (79% Blue):** Consistently approves Blue-pledged proposals and selects confirmed-Blue p2. Wallet gain and conservative pledge suggest possible wealth incentives, but do not establish allegiance.
- **Fran (88% Blue):** Second resolution's wallet loss and pot increase strongly support an eight-Blue payment that secured Blue's mission. Earlier inclusion demands plausibly reflect a personal objective.
- **Gray (82% Blue):** Pledges Blue and generally approves Blue funding, including the successful closing proposal. Opposition is concentrated on p3 rather than broadly obstructing missions; no paid contribution yet tests these signals.
- **Harper (25% Blue):** Rejects every proposal, including substantial Blue pledges, making persistent obstruction the strongest Red signal among unconfirmed seats. 'More blue' complaints and possible personal goals keep this uncertain.

## After mission 2

Confirmed p0 Red and p2 Blue. The major update is p6: official accounting strongly suggests a concealed 16-Red payment. Repeated Blue funding favors p1 and p5; p3, p4 and p7 remain less directly tested. Marginals sum to five Blue players.

- **Abby (0% Blue):** Own private card confirms Red allegiance.
- **Ben (97% Blue):** Three resolutions consistently support Blue payments. The first two strongly corroborate substantial Blue funding after accounting for my known Red deposits and recoloring.
- **Casey (100% Blue):** Official public badge confirms Blue allegiance.
- **Drew (69% Blue):** Voting mostly demands personal inclusion, which could reflect an objective rather than Red allegiance. No paid contribution tests the Blue pledges. Moves toward Blue because p6 now supplies much stronger evidence for a remaining Red seat.
- **Ellis (88% Blue):** Consistently approves Blue-pledged proposals and selected confirmed-Blue p2. Wealth accumulation and limited spending leave personal incentives and allegiance incompletely tested.
- **Fran (95% Blue):** Mission-one accounting strongly supports an eight-Blue payment securing Blue's point. The latest result also fits the reported two-Blue payment. Inclusion-driven voting is less informative than this funding.
- **Gray (6% Blue):** Latest wallet loss is 16. The final pot is exactly explained by p6 paying 16 Red, my eight Red and recoloring, and p1/p5 paying four Blue. This sharply contradicts p6's Blue report; hidden effects or temporary objective-driven behavior prevent certainty.
- **Harper (45% Blue):** Repeated earlier rejections and apparent nonpayment despite a 12-Blue pledge remain suspicious. However, conserving wealth or other personal goals could explain these choices, and strong Red evidence against p6 reduces the remaining Red probability available.

## After mission 3

Most likely Red trio is p0, p6 and p7. The latest mission supplies strong new Red-funding evidence against p7, shifting the untested p3 and p4 toward Blue. Only p0 and p2 are confirmed; hidden effects and personal objectives retain some uncertainty. Blue marginals sum to five.

- **Abby (0% Blue):** Own private card confirms Red allegiance.
- **Ben (99% Blue):** Repeated wallet losses and pot changes support Blue payments, especially on crews with me or p5. Inclusion-focused voting is less informative than this consistent funding.
- **Casey (100% Blue):** Official public badge confirms Blue allegiance.
- **Drew (94% Blue):** Blue pledges remain untested by payment, and voting largely demands personal inclusion. Strong Red-funding evidence against p6 and p7 makes p3 substantially more likely Blue under the fixed team count.
- **Ellis (95% Blue):** Consistently approves Blue-pledged proposals and previously selected confirmed-Blue p2. Wealth accumulation does not establish allegiance; the team count and stronger Red evidence elsewhere favor Blue.
- **Fran (98% Blue):** Repeated payments alongside p1 closely match Blue pot growth after accounting for my recoloring, including funding Blue's first mission victory. Participation and saving preferences explain some otherwise obstructive choices.
- **Gray (6% Blue):** Attempt 3's accounting strongly supports a concealed 16-Red payment despite reporting Blue: my known eight Red and recoloring explain the rest alongside p1/p5's apparent Blue payments. Personal goals and hidden effects prevent certainty.
- **Harper (8% Blue):** Latest resolution added seven Blue and twenty Red while p1 spent three and p7 spent twenty-four. My recoloring accounts for only one added Red; substantial remaining Red funding is strongly attributable to p7 despite the Blue report. Earlier obstruction reinforces this, though allegiance is not certified by behavior.

## After mission 4

The most likely Red trio remains p0, p6 and p7. Attempt 8 further corroborates p1's Blue funding; p6's mixed funding warrants some uncertainty about allegiance versus personal incentives. Only p0 and p2 are confirmed. Blue probabilities sum to 5.00.

- **Abby (0% Blue):** Own private card confirms Red allegiance.
- **Ben (99% Blue):** Repeated resolutions strongly support Blue payments. Attempt 8 added eight Blue and nineteen Red, exactly matching p1 paying nine Blue alongside my known eighteen Red and Blue-to-Red recoloring.
- **Casey (100% Blue):** Official public allegiance badge confirms Blue.
- **Drew (94% Blue):** Payments remain untested, but inclusion-focused voting can reflect a personal objective. Recently opposed my inclusion. Stronger Red-funding evidence against p6 and p7 leaves p3 likely Blue under the fixed team count.
- **Ellis (94% Blue):** Consistently approves Blue-pledged proposals and has selected confirmed-Blue p2. Wealth retention is not team evidence; the strongest support is the team count combined with Red evidence elsewhere.
- **Fran (97% Blue):** Repeated spending alongside p1 closely matches Blue pot growth after my recoloring, including Blue's mission-one victory. Recent objections to p6 and p7 also fit Blue, though approving my latest proposal shows voting is imperfect.
- **Gray (8% Blue):** Attempt 3 strongly supports a concealed sixteen-Red payment despite reporting Blue. Attempt 7 instead suggests mostly Blue funding, modestly increasing uncertainty, but that does not erase the earlier substantial Red payment.
- **Harper (8% Blue):** Attempt 6 added twenty Red with p7 spending twenty-four and p1 only three; my recoloring explains just one added Red. This strongly implicates p7 in substantial Red funding despite the Blue report. Blue-oriented complaints alone do not outweigh it.

## After mission 5

The leading Red trio remains p0, p6 and p7, but p6's repeated Blue funding weakens confidence in that assignment. The latest result strengthens p4's Blue estimate; p3 remains the least-tested alternative Red candidate. Only p0 and p2 are confirmed. Marginals sum to 5.00.

- **Abby (0% Blue):** Own private card confirms Red allegiance.
- **Ben (99% Blue):** Repeated official results closely corroborate Blue payments, including crews with my known Red deposits. Latest seven-token spending also fits the overwhelmingly Blue pot.
- **Casey (100% Blue):** Official public badge confirms Blue allegiance.
- **Drew (78% Blue):** Still has no resolved paid contribution to test Blue pledges. Inclusion-focused voting may reflect a personal objective, but rejecting the latest successful Blue crew leaves uncertainty. The fixed team count remains the main reason to favor Blue.
- **Ellis (97% Blue):** Latest 39-token wallet loss and overwhelmingly Blue result strongly support substantial Blue funding. Earlier Blue-oriented approvals and recent objections to my inclusion reinforce this.
- **Fran (98% Blue):** Repeated spending closely matches Blue pot growth, now including 21 tokens on the latest successful crew. Inclusion demands and wallet retention are plausibly personal-objective behavior.
- **Gray (18% Blue):** Attempt 3 strongly implicated p6 in sixteen Red despite a Blue report. However, attempt 7 suggested mostly Blue funding, and the latest fifteen-token spending fits an almost entirely Blue pot. These repeated mixed signals increase uncertainty about allegiance versus personal incentives.
- **Harper (10% Blue):** Attempt 6's substantial Red increase remains strongly attributable to p7's spending after accounting for my recoloring and p1's small payment. Repeated obstruction reinforces suspicion, though Blue-oriented complaints and hidden effects prevent certainty.

## After mission 6

Most likely Red trio: p0, p6 and p7. The final mission sharply strengthens the case against p7; p6 remains the main uncertainty because of mixed funding. Only p0 and p2 have confirmed allegiances. Blue marginals sum to 5.00.

- **Abby (0% Blue):** Own private card confirms Red allegiance; terminal result confirms the Red Loyalist objective was satisfied.
- **Ben (99% Blue):** Repeated resolutions closely corroborate Blue payments alongside my known Red deposits. The final two Blue tokens also fit p1 paying three Blue followed by my recoloring.
- **Casey (100% Blue):** Official public allegiance badge confirms Blue.
- **Drew (86% Blue):** No resolved payment tests the Blue pledges. Inclusion-focused voting is ambiguous and may reflect a personal objective. Stronger Red evidence against p7, together with the fixed team count, increases p3's Blue probability.
- **Ellis (97% Blue):** Mission five's 39-token wallet loss and overwhelmingly Blue pot strongly support substantial Blue funding. Earlier Blue-oriented approvals and objections to my inclusion reinforce this.
- **Fran (98% Blue):** Repeated spending closely matches Blue pot growth, including Blue victories on missions one and five. Inclusion demands and saving behavior do not outweigh the funding evidence.
- **Gray (18% Blue):** Attempt three strongly supports a concealed sixteen-Red payment, but later results support substantial Blue funding. Red remains more likely, with meaningful uncertainty about personal incentives and hidden effects.
- **Harper (2% Blue):** The final crew spent three tokens from p1 and twenty-two from p7, producing two Blue and twenty-four Red. My recoloring explains only one Red token. This strongly reinforces earlier evidence of substantial concealed Red funding by p7, now securing Red's fourth mission.

## Isolation and verification

The API player had `tools: []` and `tool_choice: "none"` on all 66 model requests. Requests had no prior conversation or response ID. Every transmitted observation was matched against an actual seat-0 CLI envelope; no source files, seeds, other players' cards, saved snapshots, or this development conversation were sent. The trusted local runner handled the CLI, credentials, and replay metadata.

All 1,152 actions replay to the exact saved game state. Each checkpoint's observation digest matches the reconstructed observation at its recorded replay position. Adding decision notes and predictions changed no game actions, cards, policy state, or results. See `verification.json`, `model-inputs.jsonl`, `model-outputs.jsonl`, `cli-transcript.jsonl`, and the original save `cli-session-original.json`.

Postgame follow-up: [balance, goal inference, and benchmark analysis](analysis.md), including 36 additional bot/script games and probability scoring of these predictions.
