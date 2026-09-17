# Blind AI playthrough

Model: gpt-6-astra. Seat: Abby. No tools or source access.

Result: {'blue': 4, 'red': 1}. 585 actions replayed exactly.

## Postgame assessment

The agent won as a **Blue Loyalist with Switcher**, recovering from an opening Red mission to win four consecutive missions. It kept its original objective throughout and never activated Switcher. The game took eight resolved attempts and seven rejected proposals. All 47 model actions were accepted; five prediction requests brought the total to 52 model calls.

Its most-likely team assignments were **8/8 correct at every checkpoint**, including **6/6 among the genuinely unknown seats**. Abby's own Blue card and Ellis's public Blue badge were already certain. The probability table below preserves the agent's actual uncertainty; correct classifications do not mean certainty. Final mean squared probability error on the six unknown seats was 0.0304, compared with 0.25 for the team-count prior.

The opening mission gave unusually clear evidence: Ben, Fran, and Gray—the actual three Reds—spent heavily on a 32-Red result while reporting Blue. The agent retained the correct team assignment even as later Blue funding complicated that evidence. Fran was a Red Close Race player, so helping Blue temporarily served a personal condition. The agent recognized conflicting behavior without identifying that exact objective.

The agent's clearest successful choices were backing crews that excluded its leading suspects, accepting useful partial pots, and using its known payment plus vote income to complete mission four. In the final mission, it selected Casey, Ellis, and Harper—three actual Blues—and later supplied the fifth Yes vote for their winning proposal.

Recolorer remained in the game: **Drew, a Blue bot, held it**. Holding the recorded payments and other effects fixed, removing all of Drew's recolorings changes none of the five mission winners. That arithmetic comparison does not model how players would adapt in a separate game without the ability. The rules were not changed for this run.

[Open the replay with all predictions](http://127.0.0.1:8765/#replay/24412f2e-4d1b-4389-ad42-f17072fa8451?seat=p0&designer=true&step=-1). In Designer view, click a mission in **AI team predictions** to seek to its checkpoint. Earlier frames hide later forecasts.

## Selection and isolation

The trusted launcher selected the first random deal in which seat 0 did not hold Recolorer. It did not filter on team, objective, other players, or outcomes. The agent's instructions were identical to the first blind run, and it received no previous playtest, analysis, source, seed, or other players' private cards. All requests had tools disabled and no prior conversation. This is a fresh deal and a different team/ability, not a matched balance experiment.

Every transmitted observation matches an actual seat-0 CLI envelope. Each prediction's observation digest matches the reconstructed replay at its saved position. The final game, policies, initial setup, and action log are unchanged by the addition of review metadata. See `verification.json`, `web-verification.json`, `setup.json`, and the exact input/output logs.

## Predictions recorded during play

Each cell is the model's probability of Blue; Red is the complement.

| Mission | Abby | Ben | Casey | Drew | Ellis | Fran | Gray | Harper |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100% | 22% | 82% | 88% | 100% | 22% | 28% | 58% |
| 2 | 100% | 14% | 89% | 82% | 100% | 21% | 14% | 80% |
| 3 | 100% | 10% | 93% | 91% | 100% | 22% | 10% | 74% |
| 4 | 100% | 15% | 88% | 89% | 100% | 29% | 14% | 65% |
| 5 | 100% | 12% | 92% | 90% | 100% | 23% | 12% | 71% |

Actual teams (revealed only after the final prediction): Abby: blue; Ben: red; Casey: blue; Drew: blue; Ellis: blue; Fran: red; Gray: red; Harper: blue

## After mission 1

p0 and p4 are confirmed Blue. The main new evidence is the 32-Red/1-Blue result accompanying combined wallet losses of 32 from p1, p5, and p6, despite their Blue-payment reports. Those three are the leading Red suspects, but individual colors remain private and hidden effects could change attribution. Marginals sum to five.

- **Abby (100% Blue):** Own private card confirms Blue; current objective is Blue Loyalist.
- **Ben (22% Blue):** Wallet fell by 11 on the crew producing 32 Red and only 1 Blue. Claimed 11 Blue is unverified. Rejected an earlier heavily Blue-pledged proposal; strongly suspicious, though hidden effects prevent identifying paid colors.
- **Casey (82% Blue):** Outside the disastrous paying crew; modest Blue pledges and repeated objections to p6 offer some support. Inclusion-focused voting could instead reflect a personal objective.
- **Drew (88% Blue):** Pledged the full wallet in Blue when selected, but never actually paid. Always-Yes voting is weak evidence; elevated mainly because suspicion concentrates on the three major spenders.
- **Ellis (100% Blue):** Official public badge confirms Blue, regardless of voting behavior.
- **Fran (22% Blue):** Wallet fell by 11 during the overwhelmingly Red result despite claiming 11 Blue. Voting closely matched p1, including rejecting the strong Blue-pledged proposal. Hidden effects remain an alternative explanation.
- **Gray (28% Blue):** Wallet fell by 10 alongside p1 and p5, matching the crew's combined 32-token expenditure. Claimed Blue payment is not certified; the final approving vote adds suspicion, but attribution is uncertain.
- **Harper (58% Blue):** Repeated zero pledges and inclusion-focused voting are ambiguous. Wallet stayed unchanged on the Red-winning crew, making direct paid sabotage less supported than for p1/p5/p6; hidden abilities or wallet objectives could matter.

## After mission 2

p0 and p4 are confirmed Blue. Mission two strengthens p2 and p7; p1, p5, and p6 remain the leading Red suspects from mission one's spending and outcome. p3 is largely untested. Reports and wallet changes do not certify individual colors, and personal objectives can complicate allegiance inference. Probabilities sum to five.

- **Abby (100% Blue):** Own private card confirms Blue allegiance and a Blue Loyalist objective.
- **Ben (14% Blue):** Lost 11 wallet tokens on the 32-Red mission despite reporting Blue payment. Subsequently opposed the successful Blue proposal. Hidden effects prevent proving individual deposit colors.
- **Casey (89% Blue):** Selected the successful second-mission crew and lost seven wallet tokens in its 38-Blue result, consistent with the reported seven Blue. Earlier objections to p6 also fit Blue allegiance.
- **Drew (82% Blue):** Previously pledged eight Blue but has not paid on a resolved crew. Always approving is not diagnostic; the Blue lean comes mainly from stronger Red evidence against other seats.
- **Ellis (100% Blue):** Official public badge confirms Blue. The second mission's spending and result are consistent with that allegiance.
- **Fran (21% Blue):** Lost 11 tokens on the overwhelmingly Red first mission despite a Blue report. Approval of mission two and a one-token off-crew wallet loss during its all-Blue result provide some counterevidence, though the loss does not certify a Blue deposit.
- **Gray (14% Blue):** Lost ten tokens on the 32-Red first mission while claiming Blue payment, then opposed the successful second mission. Remains a leading Red suspect, subject to hidden-effect uncertainty.
- **Harper (80% Blue):** Second-mission wallet loss of 12 and reported 12 Blue align with the all-Blue result. Earlier zero pledges remain ambiguous, but no wallet loss accompanied the first mission's Red outcome.

## After mission 3

p0 and p4 are confirmed Blue. Repeated all-Blue outcomes strengthen p2, while p3's substantial spending provides new Blue evidence. p1, p5, and p6 remain the leading Red suspects from mission one, although p5's later behavior is more helpful. Hidden effects and personal objectives prevent treating outcomes or reports as individual allegiance proofs. Marginals sum to five.

- **Abby (100% Blue):** Own private card confirms Blue allegiance; current objective is Blue Loyalist.
- **Ben (10% Blue):** Spent 11 wallet tokens on the 32-Red first mission while reporting Blue payment. Subsequently opposed all three successful Blue-producing proposals. Hidden effects prevent certainty about original deposit colors.
- **Casey (93% Blue):** Participated in three consecutive all-Blue results, with wallet losses consistent with reported Blue payments of seven, two, and two. Selected the successful second-mission crew. Repeated helpful spending strengthens the Blue inference.
- **Drew (91% Blue):** Selected p2 and self, then spent 14 tokens in an attempt producing 17 Blue and no Red. This substantially strengthens the earlier Blue lean; universally approving votes remain less informative.
- **Ellis (100% Blue):** Official public badge confirms Blue allegiance.
- **Fran (22% Blue):** Spent 11 tokens on the overwhelmingly Red first mission despite reporting Blue. However, approved every subsequent Blue-producing proposal and lost one token off-crew on each, providing counterevidence without certifying payment colors.
- **Gray (10% Blue):** Spent ten tokens on the 32-Red first mission while claiming Blue payment, then opposed all three subsequent Blue-producing proposals. Remains a leading Red suspect, though abilities and personal objectives complicate attribution.
- **Harper (74% Blue):** Spent 12 tokens on the all-Blue second mission, consistent with the Blue report, and supported both third-mission attempts. Earlier zero pledges and unchanged wallet during the Red result are ambiguous; less repeatedly tested than p2 or p3.

## After mission 4

p0 and p4 are confirmed Blue. The leading allocation remains Blue p0/p2/p3/p4/p7 and Red p1/p5/p6. However, the latest Blue result includes the same three major spenders implicated in mission one's Red result, increasing uncertainty about hidden effects and objective-driven behavior. Reports do not certify individual colors. Marginals sum to five.

- **Abby (100% Blue):** Own private card confirms Blue allegiance and the Blue Loyalist objective.
- **Ben (15% Blue):** Spent 11 tokens on the 32-Red first mission despite reporting Blue, and repeatedly opposed later Blue-producing proposals. Seven-token spending on the latest overwhelmingly Blue result provides counterevidence; hidden effects prevent individual color attribution.
- **Casey (88% Blue):** Repeated spending and crew selection accompanied all-Blue results on missions two and three. Limited spending could reflect a wallet-related objective rather than Red allegiance. Remains strongly Blue-leaning, but not confirmed.
- **Drew (89% Blue):** Spent 14 tokens on an all-Blue attempt and another six on the latest Blue-winning attempt, consistent with Blue reports. Always approving proposals is less diagnostic than this repeated substantial spending.
- **Ellis (100% Blue):** Official public badge confirms Blue allegiance.
- **Fran (29% Blue):** Eleven-token spending on the first mission remains suspicious, but subsequent approvals, repeated off-crew wallet losses during Blue results, and recent crew spending provide sustained counterevidence. More plausibly Blue than p1 or p6, though payment colors remain uncertified.
- **Gray (14% Blue):** Ten-token spending accompanied the first mission's 32 Red, followed by repeated opposition to Blue-producing proposals. Latest ten-token spending accompanied a large Blue increase, weakening—but not eliminating—the Red inference.
- **Harper (65% Blue):** Substantial spending on missions two and four aligns with Blue reports and Blue-dominated outcomes. Initial zero pledges and inclusion-focused voting remain ambiguous. Less repeatedly tested than p2 or p3, especially given renewed uncertainty about the first mission's spenders.

## After mission 5

Most likely Blue: p0/p2/p3/p4/p7; Red: p1/p5/p6. Only p0 and p4 are confirmed. The final mission strengthens p2 and p7, while the three leading Red suspects opposed its completion. Hidden effects and personal objectives mean neither reports nor aggregate pots prove individual allegiance. Marginals sum to five.

- **Abby (100% Blue):** Own private card confirms Blue allegiance. The terminal result confirms the Blue Loyalist objective was satisfied.
- **Ben (12% Blue):** Spent 11 tokens on the first mission's 32-Red result despite reporting Blue. Repeatedly opposed Blue-producing proposals, including the winning finale. Later spending on a Blue result prevents certainty.
- **Casey (92% Blue):** Repeated spending accompanied Blue results, and selected the final winning crew. Both final-mission attempts produced only Blue with p2 aboard. Inclusion-focused votes and restrained spending could reflect personal goals.
- **Drew (90% Blue):** Substantial spending accompanied Blue results on missions three and four. Supported the final winning proposal. Consistent approvals alone are weak evidence, but the spending history strengthens the Blue lean.
- **Ellis (100% Blue):** Official public allegiance badge confirms Blue.
- **Fran (23% Blue):** Eleven-token spending on the first mission implicates p5 in the overwhelmingly Red result. Later helpful votes and off-crew wallet losses provide counterevidence, but renewed opposition to both final-mission approvals strengthens the Red lean.
- **Gray (12% Blue):** Spent ten tokens on the first mission's Red result while reporting Blue, then repeatedly opposed Blue-producing proposals through the finale. Later spending on a Blue result leaves hidden-effect and objective uncertainty.
- **Harper (71% Blue):** Repeated substantial spending aligned with Blue results, including both final-mission attempts, and supported the winning proposal. Earlier zero pledges remain ambiguous; no official allegiance confirmation exists.
