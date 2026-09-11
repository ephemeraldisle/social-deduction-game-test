# Table C206B1 — designer review

Reviewed the completed `social.5` game
`c206b1bf-d1c0-4977-9f48-96b47d22544a`. All 227 recorded actions replayed exactly.
The result was **Blue 3–2**, after eight resolved attempts, thirteen proposals,
and five rejections. There were no rejection penalties. All six Blue players
met their personal objectives. The source recording was not changed.

Source: `/private/tmp/hidden-rules-web-check/web/c206b1bf-d1c0-4977-9f48-96b47d22544a/session.json`.
Replay steps below are the saved action index plus one. This document preserves
the review across development policy updates; old saves are not migrated.

## Revealed players

| Player | Allegiance | Objective | Final wallet | Personal result |
| --- | --- | --- | ---: | --- |
| Abby (human) | Blue | Spendthrift | 0 | Won |
| Ben | Blue | Loyalist | 0 | Won |
| Casey | Red | Loyalist | 0 | Lost |
| Drew | Blue | Loyalist | 10 | Won |
| Ellis | Red | Loyalist | 4 | Lost |
| Fran | Blue | Saver | 12 | Won |
| Gray | Blue | Reliable Partner | 0 | Won; exact 5 Blue and 3 Blue payments qualified |
| Harper | Blue | Close Race | 4 | Won; Red reached exactly two points |

## What happened

The pot includes any carryover from the previous unfinished attempt.

| Attempt | Crew | Deposits in crew order | Resulting pot | Result |
| --- | --- | --- | --- | --- |
| 1 | Ben, Drew, Ellis, Gray | 1B; 2B; 4R; 5B | 8B + 4R | Blue, threshold 10 |
| 2 | Abby, Ben, Casey, Harper | 6B; 0; 6R; 2R | 6B + 8R | Red, threshold 8 |
| 3 | Ben, Drew, Ellis, Fran | 1B; 0; 1R; 0 | 1B + 1R | Unfinished, threshold 9 |
| 4 | Abby, Casey, Ellis, Gray | 2B; 1R; 0; 3B | 6B + 2R | Unfinished, threshold 9 |
| 5 | Abby, Casey, Gray, Harper | 1B; 0; 0; 6R | 7B + 8R | Red, threshold 9 |
| 6 | Abby, Ben | 1B; 8B | 9B | Blue, threshold 9 |
| 7 | Casey, Ellis, Gray, Harper | 3R; 3R; 3B; 0 | 3B + 6R | Unfinished, threshold 11 |
| 8 | Abby, Ben, Casey, Gray | 2B; 2B; 2R; 1B | 8B + 8R | Blue wins the tie and the game |

Harper's Red deposits were coherent with Close Race. After Blue's first point,
he helped Red reach two, then returned to seeking Blue. This differs from the
unnecessary Red payments by Blue-seeking Fran and Drew in Table 5F8D50.

Fran consistently paid zero, preserving her Saver reserve. Five starting tokens
plus seven continuing-attempt income payments left her twelve at the finish.
Gray pursued inclusion while still needing his second qualifying pledge; his
early “More me” objections relaxed after five rejections. After his second exact
payment, ordinary Blue-winning play was appropriate. Abby's spending and empty
final wallet fit Spendthrift. Casey and Ellis generally sought Red outcomes.

## Confirmed problems

### 1. A fractional mean hides a likely Blue tie

At **step 212**, Casey approved the final crew. His private plan was two Red,
with a forecast around **7.2 Blue versus 8.2 Red**. The policy treated that as a
game-ending Red victory worth 100. At **step 222**, he paid those two Red.
The other members paid their two, two, and one Blue tokens, producing **8–8**.

The amount was not necessarily foolish: two was all Casey had, and Red was his
correct color. The confident approval was the problem. Slightly discounting
several Blue promises creates a fractional Red lead even when their most likely
joint fulfillment produces a Blue-winning tie. The forecast needs to score
possible payments separately, including all promises being honored.

Reevaluating this exact saved observation with `social.6` gives approximately
**62% Blue / 38% Red** under its payment model and changes Casey's vote to **No**.
His best contribution, if the crew is approved anyway, remains two Red.

### 2. The harmful-color tie also appears in provisional plans

At **step 189**, Gray pledged three Blue but privately planned **one Blue plus
two Red**, despite having completed Reliable Partner and seeking Blue's victory.
His eventual actual payment at step 201 was three Blue; the provisional plan
still exposed the same terminal-score tie defect as Table 5F8D50.

At **step 211**, Gray again promised Blue while privately planning one Red.
The corrected policy plans **three Blue** and **one Blue**, respectively, when
given these original observations. Personal utility remains the primary score;
otherwise tied candidates now prefer a stronger tactical color margin.

### 3. Unnecessary saving had an explicit scoring incentive

The old policy subtracted `amount * (0.12 + 0.25 * caution)` from nonterminal
outcomes, regardless of objective. That rewards hoarding without evaluating a
future use for the saved money. It also encourages undersized promises when the
average forecast says someone else can cover the funding.

Drew finishing with ten tokens is not itself proof of an error: crew access
limits spending opportunities. But Loyalist has no terminal wallet requirement,
and this generic penalty had no corresponding strategic planner. It has been
removed. Saver and Exact Change keep their explicit balance incentives;
caution now concerns the downside of uncertain outcomes. Breaking a public
promise still has a reputation cost.

There were **no Less Blue complaints in C206B1**. The confirmed example was Ben
in [Table 5F8D50](table-5f8d50.md). That automatic complaint is now removed for
all Social bots; both teams retain the same other public complaint choices.

## Fixes and limits

`social.6` implements the payment scenarios, safer tie selection, shared
Blue-compatible complaints, and removal of generic saving utility. Designer
inspection shows estimated mission and personal outcome chances as well as the
mean pot. Regression cases preserve the distinct objective behaviors, including
strategic Red payments for Close Race and Opposition Patron.

The before/after decisions above reuse each bot's recorded information and
beliefs. They do not predict how the whole game would unfold after earlier
actions changed. The payment model is still heuristic: players are independent,
other objectives remain unknown, and its small set of payment possibilities
does not include every legal deviation. See [bot behavior](../bots.md) and
[validation results](../validation.md) for details.
