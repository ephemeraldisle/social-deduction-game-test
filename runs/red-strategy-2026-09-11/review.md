# Red bot strategy follow-up — September 11, 2026

The second blind run exposed an immediate-payoff bias: each Red player forecast mostly Blue funding from the others, tried to swing the opening alone, and emptied its wallet into Red. The planner did not price the resulting exposure or the loss of money for later missions. Its linear pledge-breaking penalty also encouraged later large Blue donations to preserve a cover story.

## Change

New abilities games use `social.12`. Red plans now include heuristic values for public cover and reserves. Helpful-looking small Blue payments can preserve cover; repeated helpful funding earns diminishing additional value. Red-heavy spending has an exposure cost. These values diminish as the match approaches its end and are absent from terminal outcomes, which still use the player’s actual personal win condition. Public Red badges remove the cover incentive. Cover-pledge penalties are bounded; genuine pledge-dependent objectives retain their own scoring.

The public-cover estimate uses only public events, wallets, crews, and badges. It does not assume opponents know the bot’s private receipts or other players’ hidden teams. These are strategy scores, not calibrated probabilities or a model of optimal opponents. Rules, roles, and Recolorer are unchanged.

## Original decisions, held fixed

Applying each version to the same recorded observations and accumulated bot memory produces:

| Recorded decision | social.11 payment | social.12 payment |
| --- | --- | --- |
| Opening, Ben | 11 Red | 2 Blue |
| Opening, Fran | 11 Red | 2 Blue |
| Opening, Gray | 10 Red | 2 Blue |
| Attempt 6, Ben | 7 Blue | 0 |
| Attempt 6, Gray | 10 Blue | 2 Blue |

This is a decision comparison, not a claim that changing the opening would leave the subsequent game unchanged. The original replay has not been rewritten. Full fixtures and forecasts are in `recorded-decisions.json` and `decision-comparison.json`.

## Paired full games

`compare.py` ran seeds 4000–4015 with the current development abilities config. Each seed was played twice: all seats on `social.11`, then only the Red seats upgraded to `social.12`. Blue kept the same algorithm; deals, personality streams, and initial configuration matched within each pair. Decisions and later game paths naturally diverged. These were scripted bot games, with no new LLM calls.

| Metric | Old Red | Revised Red |
| --- | ---: | ---: |
| Games | 16 | 16 |
| Finished | 16 | 16 |
| Red team wins | 2 | 3 |
| Mean Red tokens paid in opening attempt | 1.25 | 0.0 |
| Mean Red final score | 2.00 | 2.38 |
| Mean attempts | 9.25 | 10.56 |
| Mean rejected proposals | 29.75 | 38.94 |

Red gained wins on seeds 4000 and 4010 and lost its previous win on 4011. Every game completed and its action log reproduced its final state exactly. Per-game metrics are in `paired-games/`; seed 4000 also has full old/new session saves.

**Interpretation:** 3/16 versus 2/16 is inconclusive. The intended opening behavior changed, but improved win probability is not established. All revised games had zero original Red-token payments by Red seats in the opening attempt; excessive caution or predictable small Blue payments remain possible weaknesses. This batch does not test whether an adaptive LLM still identifies Red early. It also does not isolate balance, prove that concealment caused any additional wins, or demonstrate that Recolorer is balanced. No weights were tuned against these 16 results.

## Verification

- 65 focused tests passed, including 10 new Red-strategy tests: opening cover, exposed Red, terminal wins and defense, redundant spending, cover pledges, personal wallet objectives, Close Race, public/private evidence separation, and version restoration.
- All 248 Python tests passed, including complete games, persistence, replay, and local HTTP behavior.
- With the modified source, all 510 `social.11` bot actions and explanations from the second blind run matched exactly; final controller snapshots also matched.
- Both original blind-run sessions still load and replay exactly. See `compatibility.json`.
- Saved older policies retain their recorded behavior; new games use `social.12`.
- The local server on port 8765 was restarted with the same save library. Refresh an open page before creating a new table.
