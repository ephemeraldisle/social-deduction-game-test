# Table FD63F9 — designer review

Reviewed completed `social.6` game
`fd63f945-f230-40bf-9867-b43956919bfd`. All **91 actions replayed exactly**.
Blue won **3–1**, after four resolved attempts and six crew proposals. Every
approved crew completed its mission immediately. Two proposals failed; no
rejection penalty occurred. Four players won their personal objectives.

[Open the revealed replay](http://127.0.0.1:8766/#replay/fd63f945-f230-40bf-9867-b43956919bfd?step=-1&seat=p0&designer=true).
Replay steps below equal the saved action index plus one. Source:
`/private/tmp/hidden-rules-web-check/web/fd63f945-f230-40bf-9867-b43956919bfd/session.json`.
This review changes neither the recording nor game rules or bot behavior.
Verified counts and reconstructed decision comparisons are saved in
`runs/reviews/fd63f9-audit.json`.

## Revealed players

| Player | Allegiance | Objective | Final wallet | Personal result |
| --- | --- | --- | ---: | --- |
| Abby (human) | Red | Spendthrift | 0 | Lost; empty wallet, but Red lost |
| Ben | Blue | Reliable Partner | 0 | Won; exact payments of 5 Blue and 3 Blue qualified |
| Casey | Blue | Loyalist | 0 | Won |
| Drew | Blue | Opposition Patron | 2 | Lost; 19 paid Red tokens, needed 20 |
| Ellis | Blue | Contrarian | 1 | Lost; wanted Red to win |
| Fran | Blue | Loyalist | 0 | Won |
| Gray | Blue | Loyalist | 8 | Won; never on an approved crew |
| Harper | Red | Loyalist | 8 | Lost; never on an approved crew |

## What happened

| Mission | Approved crew | Actual payments | Threshold | Outcome |
| --- | --- | --- | ---: | --- |
| 1 | Abby, Ben, Casey | 2B; 5B; 5B | 10 | 12 Blue; Blue leads 1–0 |
| 2 | Drew, Fran | 6R; 6B | 11 | 6–6 tie; Blue leads 2–0 |
| 3 | Abby, Ellis | 5R; 7R | 9 | 12 Red; Blue leads 2–1 |
| 4 | Abby, Ben, Casey, Fran | 1R; 3B; 3B; 2B | 8 | 8 Blue + 1 Red; Blue wins 3–1 |

All four accepted proposals received exactly five Yes votes. The two rejected
proposals, both before mission 3, received four each: Casey proposed Abby/Gray,
then Drew proposed Drew/Gray. Ellis's subsequent Abby/Ellis proposal passed.

The deposits mostly followed intelligible objectives:

- Ben kept two qualifying pledges. His three mission-3 **More me** objections
  followed a real need to participate before Blue finished the game.
- Casey and Fran paid Blue, including their full remaining wallets at the end.
  Gray pledged all seven tokens on both rejected crews. His final eight tokens
  reflect lack of an approved seat, not refusal to pay.
- Drew's six Red on mission 2 advanced Patron while still allowing a Blue tie
  win. Later, an immediate Blue victory would leave his condition unfulfilled,
  explaining his resistance. His underfunded Drew/Gray proposal could not reach
  the nine-token threshold with their combined eight-token wallet; continuing
  the game and earning income was useful to him.
- Ellis correctly pursued Red as Contrarian. His seven Red would beat Abby's
  five even if her Blue cover promise were true. Harper's opposition to that
  crew was a mistaken forecast, not knowledge of his allies: Abby had previously
  paid Blue and Ellis had not yet revealed a Red contribution.

Abby's Yes on the final proposal was the fifth supporting vote alongside Ben,
Casey, Fran, and Gray. With all other recorded votes fixed, a No would have
rejected that crew. Emptying the wallet fulfilled Spendthrift's personal
condition, but it still required a Red team victory.

## “More Blue” really is a generic fallback

There were **20 individual No votes out of 48 votes**, not twenty failed crews.
Their complaints were:

| Complaint | Count | Speakers |
| --- | ---: | --- |
| More Blue | 7 | Harper 3; Ellis 2; Drew 2 |
| More me | 7 | Ben 3; Drew 2; Abby 2 |
| Less player | 6 | Ellis and Harper, targeting Abby or Drew |

The bot decides Yes/No first. `SocialPolicy.complaint` then always offers
**More Blue**, with a base score plus an estimated funding-shortfall bonus.
It competes against player objections unless an exclusion protest forces
**More me**. It does not check whether more Blue is possible or whether the
requested change would actually make the voter approve.

Every More Blue request in this game was made when the proposed members had
already pledged **their entire combined wallet: twelve Blue tokens**.

| Replay steps | Proposed crew | Cost | Speakers and actual motive |
| --- | --- | ---: | --- |
| 25, 28 | Drew, Fran | 11 | Ellis and Harper wanted Red, while forecasting a likely Blue point |
| 38, 39, 42 | Abby, Gray | 9 | Drew needed more Patron progress; Ellis and Harper wanted to prevent Blue's third point |
| 62, 66 | Abby, Ellis | 9 | Harper forecast a Blue finish; Drew forecast finishing before his Patron condition was met |

So these were public cover explanations for real private objections, rather
than evidence of a missing reason inside the controller. As communication,
however, they were unhelpful: the current crew could not offer another Blue
token, and more successful Blue funding would work against those immediate
private motives. Removing Less Blue left this always-available fallback too
broad. In this table, none of its seven uses came from an ordinary Blue Loyalist.
That is a pattern in this recording, not a universal role-identification rule.

**Next correction:** tie complaints to a feasible proposed change. A covert bot
can bluff about its motive, but the public request should still identify a
change the table can make. Check affordability and existing pledges before
requesting more color; do not just replace the fallback with a different phrase
exclusive to Red-seeking bots.

## Other remaining defects

### Publicly impossible cover reports

At **step 70**, Ellis reported seven Blue after mission 3's official pot showed
**zero Blue and twelve Red**. Anyone could disprove the claim. The report policy
still automatically recolors all actual spending as Blue when maintaining cover.
It needs to respect public color bounds, even when lying.

Drew's earlier six-Blue report conflicted with Fran's six-Blue report and a pot
containing only six Blue. Outsiders could see conflicting claims; Fran's own
receipt identified Drew's false report. This differs from Ellis's claim, which
was impossible even without trusting another player's statement.

### A pledge forecast still rewards undersized promises

At **step 75**, Fran had two tokens but promised one Blue. Reconstructing her
observation and beliefs reproduces these scores:

| Fran's candidate pledge | Assumed other payments: Abby, Ben, Casey | Total funding | Score |
| --- | --- | ---: | ---: |
| 1 Blue | 1, 3, 3 | 8 | 47.34 |
| 2 Blue | 1, 2, 2 | 7 | 1.31 |

Before promises are revealed, the estimator divides the remaining funding gap
equally, rounds up, and caps each wallet. Increasing Fran's pledge changes the
rounded share from three to two; Abby's one-token cap is not redistributed.
The model therefore treats Fran paying more as making the crew unable to finish.
This is an allocation artifact, separate from the spending penalty removed in
`social.6`. Simultaneous sealed pledges also mean Ben and Casey cannot actually
react to her unseen choice this way.

Once their three-Blue promises were public, Fran correctly chose to pay two Blue
at **step 87**. Her payment was sensible; the earlier planning assumption needs
attention. A future correction should avoid assuming an immediate coordinated
response to an unseen pledge and handle capped wallets consistently.

## Mission pacing: evidence for discussion, not a rules change

This table supplied only **four resolution/report cycles** and three income
payments. Blue reached match point after just two missions. Gray and Harper
never contributed; Harper never became chairman. That is little time for some
players to generate direct evidence or pursue longer objectives. Drew missing
Patron by one token makes the timing pressure particularly visible.

The four costs totaled 38; actual deposits totaled 45, leaving seven surplus
tokens across the missions. With these exact recorded payments held fixed,
adding one to every threshold would still complete all four missions on their
first attempt. This arithmetic is not a simulated alternative game: changed
costs would also change proposals, votes, and spending.

Higher costs could create more funding attempts, while a higher victory target
would require more completed missions. Both could lengthen evidence gathering,
but affect income, objective feasibility, and voting differently. The current
rules and bot terminal checks assume three victories; changing that target
also requires revisiting Close Race's fixed 3–2 condition.

For comparison, the recent 100-game `social.6` self-play diagnostic averaged
7.66 resolved attempts. This human game was at its four-attempt minimum, so it
demonstrates that very short games happen, not that every game is this short.
Keep the pacing decision open while fixing the specific communication and
forecast defects. No costs, victory target, or policy behavior changed in this
review.
