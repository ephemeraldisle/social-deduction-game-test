**Postgame investigation — balance, deduction, and benchmark potential**

The result is encouraging for the environment's benchmark potential, but the victory by itself provides weak evidence of goal inference. A simple script with no opponent deductions also won this starting deal frequently. The strongest current interpretation is that the AI found an effective way to exploit the existing bot population; neither universal Red advantage nor superior general social reasoning has been established.

This investigation happened after the blind run. The reviewer inspected source and final hidden state; none of this information was supplied to the original player. The original game and its during-play predictions are unchanged. No additional LLM games or API calls were made.

**1. Balance and the source of the victory**

I ran 36 follow-up games with the existing `social.11` bots:

| Experiment | Games | Blue wins | Red wins | Approximate 95% interval for Red win probability |
| --- | ---: | ---: | ---: | --- |
| Fresh deals, current configuration | 12 | 9 | 3 | 9–53% |
| Same fresh seeds, all objectives Loyalist | 12 | 11 | 1 | 1–35% |
| Original starting deal, Social bot replaces Abby | 6 | 5 | 1 | 3–56% |
| Original starting deal, simple Red script replaces Abby | 6 | 1 | 5 | 44–97% |

The simple script chooses itself and the lowest-wallet available partners, pledges its full wallet Blue, votes Yes when included and No otherwise, deposits its maximum Red, recolors Blue to Red, and reports Blue. It does not inspect opponents' history, estimate their teams, identify objectives, or learn which player is cooperative. It was constructed after reviewing the game, so this is a test of whether a simple strategy can succeed on this deal, not an independently held-out performance result.

The same-deal experiments preserve the exact initial engine state: teams, objectives, abilities, wallets, chairman, and mission random stream. The seven original bots retain their original personalities and settings, but start with empty memories and new policy random seeds. Each Social/script pair shares those seeds. The replacement Social player has a newly seeded personality. These are six controller-randomness variants of one deal, not six independently sampled deals or exact recreations of the original opponents' random choices. The original LLM still has only one game.

The 12 fresh default/Loyalist pairs use seeds 1000–1011, with setup, ability, mission, and policy seeds held fixed. Only the objective deck changes. The intervals are descriptive Wilson intervals; none addresses performance against stronger opponents or optimal play. The fixed-deal intervals only concern variation in the controller setup used here.

These results make an inherent Red advantage an unconvincing explanation of this particular victory. The current all-bot population more often favors Blue in this small sample. Changing the policy in Abby's seat can nevertheless make Red very effective on the same deal. That suggests exploitable opponent behavior and a useful role, rather than demonstrating a uniquely sophisticated LLM strategy.

The replay shows how that advantage worked:

- Abby's No was pivotal in 14 rejected proposals: each finished 4–4 and would have passed if only Abby's recorded vote changed. This is a local voting fact, not a claim that all 14 rejections improved its eventual chance of winning.
- Blue has five players and wins tied color totals, but needs five Yes votes to approve a crew. If three Reds oppose, one Blue dissenter blocks approval. Inclusion demands and personal objectives made that coordination difficult in this game.
- All players collect vote income, including after rejections. Abby used delays to rebuild its wallet and regain the chair. The 25 rejected proposals produced no automatic rejection-penalty attempts; the penalty rule cannot directly account for any actual Red deposits here, although its threat could influence voting.
- Ben's small wallet made him a manageable Blue partner. Abby selected itself with Ben three times and got approval each time, despite repeatedly pledging Blue and depositing Red. At mission four, it correctly predicted its 18-Red deposit plus recoloring would produce Red 24–Blue 19 if Ben paid nine Blue.
- Recolorer worked on all ten attempts, including off-crew attempts. Holding recorded payments and other effects fixed, removing Abby's three recolorings in mission three changes Red 25–Blue 23 into Blue 26–Red 22. That mission point therefore depended on the ability in this arithmetic comparison. The activation rule itself is easy to script. This does not predict a complete alternative game, because players would adapt to changed results.

I would test stronger opponents and rotate controllers through teams and abilities before changing the balance rules. A rule set can favor Blue under symmetric weak bots while permitting a strong Red exploit against those same bots. The all-Loyalist comparison also suggests that private incentives contribute to coordination problems, but 12 pairs cannot isolate a stable objective-balance effect.

**2. Did the AI need to infer everyone's goals?**

No complete or accurate model of others' goals was demonstrated, and the simple-script controls show that such a model is not necessary to win this deal against these bots. That is narrower than claiming that goal inference has no value across the game.

The AI did use useful behavioral observations: Ben wants inclusion, Ben reliably spends Blue, Harper can supply substantial Red funding, and certain pairings attract approval. Those observations can guide action without identifying the exact private objective behind them.

Gray is the clearest counterexample to successful motive inference. Gray was Blue with Opposition Patron: Blue must win and all players combined must have originally paid at least 20 Red tokens. That global total is hidden. Gray's actual payments were 16 Red on attempt three, then 10 Blue plus four Red on attempt seven, then 15 Blue on attempt nine. Its recorded bot plans estimated a 20-token shortfall before the first payment and a four-token shortfall before the second. Its own 20 Red then guaranteed the condition, even though the true table-wide total had already passed 20 on attempt three. The AI instead became highly confident Gray was Red and, because it knew the total team counts, shifted Drew toward Blue. Drew was actually a Red Loyalist. Predicting Gray well therefore involves both its incentive and its uncertainty about progress toward that incentive.

Those beliefs affected decisions. Abby selected Ben and Gray for mission four expecting concealed Red funding, but received mostly Blue. In mission five it repeatedly rejected wealthy Drew on the theory that Drew could overwhelm Red funding with Blue. The AI recovered despite those errors. Its reasons also acknowledged that personal objectives could explain mixed behavior; the failure was in assigning and acting on probabilities, not in never mentioning the possibility.

We did not elicit explicit objective probabilities during play, so the record cannot measure exact objective-inference accuracy or fully reveal the model's internal reasoning. Recorded explanations and team estimates are the available evidence.

Excluding Abby's known own team and Casey's public badge:

| Checkpoint | Correct most-likely team guesses | Mean squared probability error (Brier; lower is better) |
| --- | ---: | ---: |
| Mission 1 | 6/6 | 0.0459 |
| Mission 2 | 4/6 | 0.2633 |
| Mission 3 | 4/6 | 0.2961 |
| Mission 4 | 4/6 | 0.2902 |
| Mission 5 | 4/6 | 0.2154 |
| Mission 6 | 4/6 | 0.2356 |
| Uninformed team-count prior | — | 0.2222 |

The prior assigns each unknown player a two-thirds Blue probability: four of the six unknown seats are Blue. It respects the known total team count in its probability marginals. The final forecasts score slightly worse than that prior because the Drew/Gray mistakes are confident. The mission-one classification was perfect, but that did not mean certainty or sustained successful deduction. The six checkpoints are correlated observations from one game.

**3. Benchmark potential**

This is evidence that the environment can support a useful evaluation: a fresh tool-free agent can play from legitimate observations, decisions are mechanically checked, and its complete game and beliefs can be audited against hidden ground truth. The Gray/Drew error is already a substantive failure case that a win-only score misses.

Social deduction has precedent as an LLM evaluation environment in [AvalonBench](https://arxiv.org/abs/2310.05036). Evaluating adaptation to unfamiliar partners and opponents also has precedent in [Melting Pot](https://proceedings.mlr.press/v139/leibo21a.html). Those papers support the general direction, not the validity of this particular game as a finished benchmark.

More roles and teams could create useful challenges, but greater complexity alone would not establish that success measures the capabilities we intend. It can also increase rule-reading burden, ambiguity, and variance. The valuable ingredient already present is that allegiance, current incentives, and observed behavior can differ. Understanding when a temporary collaborator stops helping should sometimes change the best action.

The next evaluation should distinguish several outcomes:

- **Strategic performance:** individual objective success and team results, compared with a replacement baseline for the same seat/deal. Include stronger opponents and a diverse opponent pool; rotate teams, seats, and abilities.
- **Opponent understanding:** separate team, objective, and ability forecasts, scored probabilistically on information that is not already certified. Include next-action predictions, since useful behavioral understanding need not use the right role name.
- **Use of information:** scenarios where available evidence about another player's goal makes a decision materially better. Compare simple policies, inference-capable agents, and a clearly labeled oracle-information control. An oracle is a separate diagnostic condition, never part of the blind score.
- **Generalization:** hold out deals and opponent styles, and eventually combinations of roles. Standardize prompts, information, memory, and action/compute budgets. Success against one exploitable bot population should not dominate the score.

A game need not be exactly 50–50 to be a useful benchmark if role difficulty is measured and controlled. Conversely, a 50–50 win rate does not establish that deduction matters. For this project, the next decisive question is whether better inference reliably improves choices and results against opponents that punish the simple strategy found here. Adding explicit goal predictions to the next blind run would make that investigation more direct.

**Artifacts and reproduction**

[Experiment script](balance_probe.py), [experiment manifest](balance-probe/manifest.json), [population counts](balance-probe/summary.json), [audit script](audit_run.py), and [derived evidence](analysis-data.json) accompany this report. Per-game metrics and representative replay/action files are in `balance-probe/`.

Run both scripts from the repository root with Python 3. The sweep makes no API calls. All 36 games completed and replayed exactly; paired setup/ability assignments match, source hashes remained unchanged throughout the sweep, and the original blind game remains unchanged.
