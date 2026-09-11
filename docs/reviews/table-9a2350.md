# Table 9A2350 — designer review and balance signals

Reviewed completed `social.6` game
`9a23505a-7857-4e8e-a554-b02f919c2cdf`. All **180 recorded actions replayed
exactly**. Blue won **3–1** after seven resolved attempts and ten crew proposals.
Three proposals failed; there were no rejection penalties. Five players won
their personal objectives.

[Open the revealed replay](http://127.0.0.1:8766/#replay/9a23505a-7857-4e8e-a554-b02f919c2cdf?step=-1&seat=p0&designer=true).
Replay steps below equal the saved action index plus one. Source:
`/private/tmp/hidden-rules-web-check/web/9a23505a-7857-4e8e-a554-b02f919c2cdf/session.json`.
Verified counts, reconstructed payment comparisons, and the population analysis
are in `runs/reviews/9a2350-audit.json`. No rules, bot behavior, or recordings
changed during this review.

## Revealed players

| Player | Allegiance | Objective | Final wallet | Personal result |
| --- | --- | --- | ---: | --- |
| Abby (human) | Blue | Loyalist | 3 | Won |
| Ben | Blue | Loyalist | 2 | Won |
| Casey | Red | Close Race | 0 | Lost; needed Red to win 3–2 |
| Drew | Blue | Spendthrift | 0 | Won |
| Ellis | Blue | Contrarian | 0 | Lost; wanted Red |
| Fran | Blue | Reliable Partner | 1 | Won; exact 6 Blue and 2 Blue payments qualified |
| Gray | Red | Opposition Patron | 4 | Lost; enough opposing Blue deposits, but Red lost |
| Harper | Blue | Loyalist | 0 | Won |

There were six Blue allegiances, but Ellis's Contrarian card made the eventual
winning preferences **five for Blue and three for Red**. Casey temporarily
helped Blue for Close Race. Other private conditions could also affect votes;
these counts do not imply automatic coordination.

## What happened

Resulting pots include carryover from unfinished attempts.

| Attempt | Mission / threshold | Crew | Actual payments in crew order | Resulting pot and outcome |
| --- | --- | --- | --- | --- |
| 1 | 1 / 11 | Drew, Ellis, Harper | 5B; 0; 5B | 10B; unfinished |
| 2 | 1 / 11 | Drew, Fran, Harper | 1B; 6B; 1B | 18B; Blue 1–0 |
| 3 | 2 / 8 | Drew, Fran, Gray, Harper | 1B; 1B; 7R; 1B | 3B + 7R; tied score 1–1 |
| 4 | 3 / 12 | Abby, Ben, Casey, Ellis | 8B; 8B; 8B; 8B | 32B; Blue 2–1 |
| 5 | 4 / 10 | Ben, Drew, Fran, Harper | 1B; 2B; 2B; 2B | 7B; unfinished |
| 6 | 4 / 10 | Casey, Drew, Ellis, Fran | 0; 1B; 0; 1B | 9B; unfinished |
| 7 | 4 / 10 | Casey, Drew, Ellis, Harper | 3B; 1B; 3B; 2B | 18B; Blue wins 3–1 |

Gray's mission-2 play was effective Red strategy. He selected three players
with only one token each, promised seven Blue, and paid seven Red at **step 52**.
His wallet let him beat their combined Blue spending. Their three Blue payments
also brought his Patron counter from eighteen to twenty-one. This is a concrete
case where Red can exploit resource differences without knowing other roles.

Casey's eight Blue at **step 73** had an objective-based motive: at 1–1, Red
Close Race needed Blue to reach two before Red finished. The tactical color was
correct. Spending the entire wallet is much less clearly justified; the policy
does not value keeping enough resources to win the later Red missions.

Ellis withheld payment on attempt 1 to keep the pot below eleven. Casey and
Ellis both withheld on attempt 6, successfully delaying Blue once more. Those
were sensible defensive actions, rather than arbitrary hoarding.

## Why the final mission became so hard for Red

Blue's deposits persisted: seven Blue became nine Blue after the next attempt.
The last crew's combined wallets contained only **nine tokens**. Even if every
member had paid its entire wallet in Red, the result would have been **9–9**,
which Blue wins. Any positive deposit would fund that mission, and Red could
not obtain a color majority on this crew.

Consequently, Casey and Ellis's final Blue payments looked particularly bad,
but changing both to Red would not have saved the game. With Drew and Harper's
recorded three Blue held fixed, withholding both payments would still produce
12 Blue and finish the mission. The decisive problem was earlier resource and
crew control, not the color of those last six tokens alone.

Five players ultimately wanted Blue. Once Drew's final crew seat allowed him to
spend his last token and Fran had qualified, all five could approve together.
The three players wanting Red could not reject the crew by themselves. Earlier
proposals excluding Drew drew his More me objection and failed with four Yes
votes. Including him supplied the fifth vote.

This exposes two important mechanics: Red tokens also fund missions, and Blue
wins color ties. Adding a little Red to a heavily Blue pot can complete Blue's
victory instead of sabotaging it. Red needs enough resources to overtake the
pot, control the crew, or prevent approval while the position is still viable.

## Remaining bot defects affect the result too

### Reputation cost overrides Red's actual goal

At **step 74**, Ellis wanted Red but changed from a private eight-Red plan to an
actual eight-Blue payment. Reconstructing his recorded information reproduces:

| Payment | Expected outcome utility | Pledge-breaking cost | Final score, including risk |
| --- | ---: | ---: | ---: |
| 8 Blue | −8.37 | 0 | −8.37 |
| 8 Red | −4.93 | 3.85 | −8.79 |

The fixed reputation cost outweighed the strategic preference for Red. Some
honest payments can earn useful cover, but the policy does not predict how this
specific investment in reputation helps its future winning chances.

The same cost produces a clearer error at **steps 173 and 175**. Both Casey and
Ellis forecast a terminal loss for either full-wallet color, then prefer Blue
because breaking their Blue promises still incurs a cost. Even their small
modeled chance of continuing by withholding loses to the reputation penalty.
There is no future reputation benefit after the game ends. The scoring should
not penalize a terminal plan for losing future social standing.

These problems make the opponents appear more cooperative with Blue than their
private goals warrant. Fixing them alone does not prove that Red would win this
recording; the final approved crew was already unable to produce a Red result.

### The planner does not budget for later missions

Mission 3 received thirty-two tokens against a twelve-token threshold, leaving
every participating wallet empty. Casey still needed two more Red victories,
and Ellis also wanted Red. Their need for future spending was not represented
in the one-attempt score. The absence of a blanket spending penalty is
appropriate; what is missing is a concrete estimate of future opportunities
and threats, rather than a generic bonus for saving.

### Public explanations remain weak

There were **31 No votes out of 80 votes**: twelve More Blue, fourteen Less
player, and five More me. Only three proposals actually failed. The More Blue
fallback described in [FD63F9](table-fd63f9.md) remains unchanged.

At **step 56**, Gray claimed seven Blue after an official result containing only
three Blue. That is another publicly impossible cover report. These are known
communication defects, separate from the numerical balance question.

## Does stronger play make Blue effectively unbeatable?

The current evidence shows a strong dependence on how many players ultimately
want each winner. It does not establish inevitable Blue victory under good play.

In the existing 100-game `social.6` self-play run, Blue won **63 games** and Red
won **37**. Splitting by original allegiance gives:

| Initial team split | Blue wins | Red wins |
| --- | ---: | ---: |
| 5 Blue / 3 Red | 37/68 (54%) | 31/68 |
| 6 Blue / 2 Red | 26/32 (81%) | 6/32 |

But original allegiance hides Contrarian's effect. Counting everyone by the
winner their objective ultimately requires gives a much sharper pattern:

| Players ultimately wanting Blue | Games | Blue wins | Red wins |
| --- | ---: | ---: | ---: |
| 4 | 22 | 1 (5%) | 21 |
| 5 | 51 | 35 (69%) | 16 |
| 6 | 24 | 24 (100%) | 0 |
| 7 | 3 | 3 (100%) | 0 |

Five Yes votes approve a proposal. A group of five can therefore pass a crew
without the remaining players, while a group of four can block approval.
Repeated rejection adds Red tokens. The four-Blue-preference group had fifty-five
penalty attempts across twenty-two games; the six/seven group had only four
across twenty-seven games. This is consistent with voting control and rejection
penalties being major drivers. It is observational evidence, not an experiment
isolating their causal effects; private objectives and deal composition differ.

The five-player group includes 9A2350's preference split, and Red won sixteen
of fifty-one such simulated games. That is enough to reject an “always Blue”
description of the current bots, while still taking the advantage seriously.
The six/seven group is particularly concerning: Blue won all twenty-seven in
this sample, although that is not a guarantee about future games or stronger
opponents.

The latest changes also did not monotonically increase Blue's aggregate win
rate: on these same seeds, `social.5` had 77 Blue wins and `social.6` had 63.
Changing every controller at once is not an isolated measure of playing
strength, but it distinguishes the observed results from the impression that
every intelligence improvement necessarily benefits Blue.

## Implications for the next design decision

Keep mission costs and the victory target undecided. More missions would give
more time for evidence and resource decisions, but do not inherently undo a
five-vote majority; they could also let the dominant group repeatedly exercise
that control. Higher costs change funding and wallet timing, but Red spending
still helps fund a Blue-controlled pot.

The next balance checks should distinguish original teams from actual winning
preferences, record how Red wins (paid deposits versus rejection penalties),
and inspect when a pot becomes impossible to overturn with available wallets.
Correct the reputation and forecasting defects before treating current bot
outcomes as an estimate of what strong players can achieve. Contrarian's large
effect on those voting numbers is itself a design issue worth investigating.
