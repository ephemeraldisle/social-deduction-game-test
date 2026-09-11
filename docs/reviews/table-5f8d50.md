# Table 5F8D50 — designer review

**Follow-up:** the recommended fixes were implemented in `social.6` after
[reviewing Table C206B1](table-c206b1.md). At the original decision boundaries,
Fran and Drew now choose all-Blue plans, and Ben's No complaint targets Fran's
unreliable promise instead of requesting Less Blue. Scoring compares possible
integer outcomes and no longer applies a generic spending penalty. The review
below describes the original recording; development saves are not migrated.

Reviewed the completed `social.5` game
`5f8d5079-9943-4f48-a984-239b00ec2abb`. Replayed all 156 actions from the initial
state and verified exact agreement with the saved result. The game ended
**Blue 3–1**, after six resolved attempts, nine proposals, and three rejections.
There were no rejection penalties. The source recording was not changed.

[Open the fully revealed replay](http://127.0.0.1:8766/#replay/5f8d5079-9943-4f48-a984-239b00ec2abb?step=-1&seat=p0&designer=true).
Links below select designer replay steps, which are the saved action index plus one.

## Revealed players

| Player | Allegiance | Objective | Final wallet | Personal result |
| --- | --- | --- | ---: | --- |
| Abby (human) | Blue | Reliable Partner | 0 | Won; two exact qualifying payments, 6 Blue and 4 Blue |
| Ben | Blue | Saver | 7 | Lost; below ten |
| Casey | Blue | Close Race | 1 | Lost; Red only reached one point |
| Drew | Red | Contrarian | 2 | Won; wanted Blue to win |
| Ellis | Red | Exact Change | 7 | Lost; correct wallet, wrong winning team |
| Fran | Blue | Loyalist | 2 | Won |
| Gray | Red | Opposition Patron | 0 | Lost; deposit condition met, wrong winning team |
| Harper | Blue | Loyalist | 6 | Won |

## Confirmed problems

### 1. Blue-seeking bots choose unnecessarily harmful colors

On attempt 3, both Fran and Drew wanted Blue's third point. Neither had a
personal condition that benefited from Red deposits. Nevertheless:

| Decision | Actual deposit | Same-cost alternative | Scores, including pledge-deviation cost |
| --- | --- | --- | --- |
| [Fran, replay step 53](http://127.0.0.1:8766/#replay/5f8d5079-9943-4f48-a984-239b00ec2abb?step=53&seat=p0&designer=true) | 2 Blue + 2 Red | 4 Blue | Both 99.50477608446394 |
| [Drew, replay step 54](http://127.0.0.1:8766/#replay/5f8d5079-9943-4f48-a984-239b00ec2abb?step=54&seat=p0&designer=true) | 1 Blue + 2 Red | 3 Blue | Both 99.9430168991494 |

Reconstructed each controller's observation history, personality, and settings,
then evaluated those alternatives. The saved scores were reproduced exactly.
The terminal utility returns the same reward for every forecast personal win;
the action selection shuffles equal-scoring candidates. Once the mean forecast
crosses the winning threshold, extra protection against a wrong forecast receives
no value. This is a strategy defect, not an objective-driven betrayal.

The real attempt ended at **3 Blue + 5 Red**, eight tokens toward a nine-token
threshold. Replacing those two deposits with the same-cost Blue alternatives,
while holding Ellis's payment fixed, would leave **7 Blue + 1 Red**. The mission
would still be unfinished, but its ownership would be much safer for Blue.

Fran then reported **4 Blue**, although the entire official pot contained only
3 Blue. That is publicly refutable. The unnecessary Red payment also triggered
an unnecessary cover story and damaged her credibility.

The same defect appears in provisional plans: Fran planned 1 Red behind her
1 Blue pledge on attempt 3; Drew planned 1 Blue + 4 Red behind his 5 Blue pledge
on attempt 5. Both tied with same-cost all-Blue alternatives.

**Recommended correction:** prefer a stronger margin for the desired winner
among otherwise equally valuable plans, while retaining opposing-color deposits
when a private objective actually rewards them. Include regression cases for
Loyalist and Contrarian, plus preservation of Patron and Close Race behavior.

### 2. “Less Blue” exposes a private motive

There was one such complaint in this recording:
[Ben, attempt 4, replay step 62](http://127.0.0.1:8766/#replay/5f8d5079-9943-4f48-a984-239b00ec2abb?step=62&seat=p0&designer=true).
He had eight tokens and needed ten. A Blue victory then would make him lose,
so resisting the proposal was coherent. The public explanation was poor cover.

The complaint selector explicitly rewards “Less Blue” when its public forecast
ends the game for Blue. Ben already had an ordinary objection available: Fran's
previous pledge was broken and her report contradicted public accounting. His
saved estimates put her pledge reliability at 58% and report credibility at 44%.

**Recommended correction:** remove the automatic “Less Blue” cover complaint.
Keep the private reason in designer diagnostics; use an evidence-backed player
objection or a plausible Blue-supporting request publicly. Do not replace it
with another complaint exclusive to Red-seeking bots.

### 3. Forecasts are too confident near the winning boundary

Several decisions make sense under the saved forecast but fail under the actual
payments. For example, Casey's six Red tokens on attempt 2 were forecast to
produce a narrow Red win. Abby actually paid six Blue and Harper paid zero:
the resulting **6–6 tie went to Blue**. Casey had only six tokens available.

By the final deposit, Gray expected his two Red tokens to produce roughly
**7.16 Blue versus 7.65 Red**, while the actual result was **9 Blue versus 7 Red**.
He had already met Patron's counter and was trying to win Red. His approval and
payment reflected a failed forecast, not a deliberate choice to lose.

These are broader modeling limitations: a win in a fractional mean forecast is
treated as certain, and each bot reasons as though the others follow discounted
promises while optimizing its own payment. Testing several plausible payment
outcomes would be a more substantial next step than adjusting complaint wording.

## Behavior that was understandable

- **Ben:** conserved money until attempt 4, then spent three Red to stop an
  anticipated immediate personal loss. That moved him further from ten, but
  bought time. His scorer preferred that costly continuation (about −42) to an
  immediate loss (−100). This was an emergency tradeoff, not forgotten Saver logic.
- **Casey:** sought Red points after Blue led, and kept concealing that intention
  behind Blue promises. Her high self-interest also explains early “More me.”
- **Drew:** generally helped Blue and eventually paid five Blue in the winning
  attempt. His Red allegiance does not conflict with Contrarian's Blue objective.
  His attempt-3 mixed payment is the exception identified above.
- **Ellis:** initially saved to seven, then used payments of one and two Red
  around continuing income to return to seven. She attained the wallet condition.
  A large provisional pledge followed by a smaller actual payment reflects
  replanning after other pledges became visible, though it harms credibility.
- **Gray:** initially paid five Blue because a Red Patron needs twenty paid Blue
  across the table. The cumulative Blue count reached 22 after attempt 4; he then
  contributed Red. The global paid count ended at 31 Blue.
- **Harper:** consistently paid Blue, sometimes less than promised when expecting
  others to finish the mission. That saves future resources but incurs a trust
  cost; the current bot gives that cost relatively little weight.
- **Abby:** the two exact Blue payments satisfied Reliable Partner. Her final
  vote helped secure both the team win and her already-earned personal condition.

The overall verdict is that most objective-driven behavior was coherent, but
the terminal-scoring tie and the public “Less Blue” explanation need correction.
Legal actions and exact replay do not establish strategically sensible choices.
