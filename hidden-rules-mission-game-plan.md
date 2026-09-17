# Hidden Rules Mission Game: Rules and Prototype Build Plan

**Version:** 0.1 design specification  
**Date:** September 10, 2026  
**Status:** Objectives and all eight abilities implemented in the experimental prototype; balance and benchmark validity are untested.

**September 11 update:** Contrarian is disabled in new default deals while its Red advantage is investigated. The active deck has 13 cards: six Loyalists and one of each other objective except Contrarian. New sessions enable abilities (`0.1-abilities-dev.3`), with one copy of each ability. New web/CLI games read the editable profile, currently mission thresholds 15–30 and crews of 2–5. Contrarian references below describe the retained historical/experimental rule, not an active card in this profile.
**Working title:** Hidden Rules Mission Game. This is a descriptive placeholder, not a final game name.

**Ability strategy update:** New tables use `social.11`: joint payment/ability
forecasts inform crew selection, pledges, votes, and commitments; inspections
inform persistent beliefs. Confirmed teams guide crew choices, while Blue pledges
earn no allegiance or trust credit. Recurring residual effects after independently known
crew payments support tentative scenarios without revealing other cards. Earlier
saved controllers retain their previous behavior. See [implementation and
limits](docs/abilities.md); these heuristics do not establish general rule discovery.

**Revenue and pacing update:** Every player receives 1 wallet token once all eight
ballots resolve, whether a proposal passes or fails. This is in addition to
nonterminal attempt income. First to four missions wins; Close Race requires
4–3. Wallets remain public. The web table supports timed or manual visible
steps, expandable player histories, and persistent before/after accounting.
Existing saves retain their original rules.

## How to use this document

This document contains the complete designer rules, a proposed software architecture, a computer-opponent design, and an ordered implementation guide. It is intended to let a developer build a playable prototype without needing the original conversation.

**Do not give this entire document to a benchmark participant.** Discovering other players' abilities and incentives is part of the proposed challenge. The player-facing material must be generated separately from the public rules and that player's private cards.

Rules are identified as follows:

- **Agreed:** Established in the design conversation, including refinements accepted together by the user.
- **New objective:** The latest addition, “you only win if your team loses.” Its exact implementation is specified here.
- **Implementation default:** A choice that closes an unspecified edge case or makes the first build executable. Use it for version 0.1, keep it configurable where practical, and revisit it after playtesting.
- **Later experiment:** Not required for the first prototype.

“Agreed” does not mean balanced or validated. When a default changes, version the rules and configuration rather than silently mixing results.

### Contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Configuration and unresolved choices](#2-configuration-and-unresolved-choices)
3. [Setup, knowledge, and resources](#3-setup-knowledge-and-resources)
4. [Winning and mission scoring](#4-winning-and-mission-scoring)
5. [The complete play sequence](#5-the-complete-play-sequence)
6. [Structured communication](#6-structured-communication)
7. [Personal objectives](#7-personal-objectives)
8. [Abilities and their resolution](#8-abilities-and-their-resolution)
9. [Worked examples](#9-worked-examples)
10. [What players are taught](#10-what-players-are-taught)
11. [Software architecture and data contracts](#11-software-architecture-and-data-contracts)
12. [Computer opponents](#12-computer-opponents)
13. [Asynchronous operation and reproducibility](#13-asynchronous-operation-and-reproducibility)
14. [Step-by-step implementation guide](#14-step-by-step-implementation-guide)
15. [Verification and acceptance criteria](#15-verification-and-acceptance-criteria)
16. [Playtesting and benchmark evaluation](#16-playtesting-and-benchmark-evaluation)
17. [Risks, open questions, and extensions](#17-risks-open-questions-and-extensions)
18. [Instructions to give an implementation agent](#18-instructions-to-give-an-implementation-agent)

## 1. Purpose and scope

The game combines collective mission funding, secret contributions, private objectives, hidden abilities, and constrained communication. It is inspired by the proposal-and-vote structure of Resistance, but the rules below define an original prototype rather than a reproduction of another game.

The benchmark hypothesis is:

> An agent must infer unfamiliar mechanisms and other players' incentives from incomplete, potentially deceptive evidence, then use those inferences to improve its decisions.

The distinctive uncertainty is not merely “which person has which known role?” Each participant initially knows only their own team, objective, and ability. Other players may cause effects whose rules the participant has never been told. A successful learner should be able to distinguish explanations, arrange informative interactions, revise its beliefs, and apply what it learns.

The central information chain is:

**Public promise → private contribution → hidden modification → public outcome → potentially unreliable report.**

Each stage supplies different evidence. An honest contribution can produce an unexpected result because an ability changes it. A teammate can act against the team's immediate interests because of a personal objective. A report can be accurate without explaining the entire result.

### The first experiment

Build enough of the game to answer:

> Can a player discover an initially unknown ability through play, and use that understanding to improve an outcome against responsive computer opponents?

The first build should support complete games, human participation, structured agent participation, replay, and inspection. It does not need learned human imitation, advanced graphics, a large generated role library, or an official leaderboard.

### Claims this prototype does not establish

- That humans outperform current frontier agents.
- That social deduction is inherently a better reasoning test than all physics-based tasks.
- That the current eight abilities provide a durable benchmark once their rules become familiar.
- That win rate isolates rule acquisition from arithmetic, negotiation, resource management, or opponent exploitation.
- That this game satisfies an innovation/invention objective or has an uncapped score. A finite game has bounded outcomes; open-ended evaluation would require additional design.

These are questions for experiments, not premises of the implementation.

## 2. Configuration and unresolved choices

| Setting | Version 0.1 value | Status |
|---|---|---|
| Players | 8 | Agreed |
| Starting wallet | 5 uncolored tokens per player | Agreed |
| Attempt income | 1 token per player after each resolved attempt, if the game continues | Agreed |
| Vote revenue | 1 token per player after all eight ballots, pass or fail, before contributions or penalties | September 11 revision |
| Teams | Blue and Red | Agreed |
| Token colors | Blue, Red, Green | Agreed |
| Team distribution | Always 5 Blue / 3 Red | Revised after playtesting |
| Knowledge of distribution | Counts public; individual assignments private | Agreed |
| Team victory | First team to win 4 missions | Agreed |
| Mission threshold | Uniform integer from 8 through 12 | Range agreed; uniform sampling is a default |
| Crew size | Uniform integer from 2 through 4, independent of threshold | Variable size and minimum 2 agreed; maximum and sampling are defaults |
| Mission accumulation | Tokens persist across attempts on the same mission | Agreed |
| Proposal approval | At least 5 Yes votes out of 8 | Implementation default |
| Rejection limit | 8 consecutive rejected proposals within an attempt, one per chairman | Agreed |
| Rejection penalty | Add 5 Red tokens to the current mission, then resolve eligible abilities | Amount agreed; precise timing specified here |
| Mission ownership | Compare Blue and Red totals only; Blue wins ties | Agreed |
| Green tokens | Count toward funding, do not compete for ownership | Agreed |
| All-Green edge case | At least one Blue or Red token must remain before a mission can be awarded | Agreed |
| Public wallets | Current wallet balances visible | Adopted visibility rule |
| Complaints | Up to 3 opaque structured expressions per vote | Agreed |
| Reports | Crew only; 1–3 statements each, revealed together; penalties skip reports | Agreed |
| Pledge collection | Affordable vectors, collected privately and revealed together before voting | Implementation default |
| Voting order | Chairman first, then clockwise; all 8 votes recorded | Implementation default |
| Same-effect initiative | Clockwise from the final proposer; preparation uses its current chairman | Implementation default |
| First chairman | Uniformly random seat | Implementation default |
| Later chairman | Seat after the most recent proposer | Implementation default |
| Objective dealing | Finite 13-card deck described in Section 7 | Implementation default |
| Ability dealing | Shuffle the 8 abilities and deal each exactly once | Agreed; enforced for new deals |
| Contrarian copies | 0 in new default games | Disabled pending balance work |
| Automated run guard | Stop after 100 resolved attempts and label unresolved | Development default, not a gameplay victory rule |

The complete role catalogue, objective deck composition, and bot-policy mixture are designer information. Public configuration discloses the fixed team counts, Contrarian being disabled, and the mission-card distribution without revealing objective or ability assignments.

## 3. Setup, knowledge, and resources

### 3.1 Setup

1. Create eight named seats in a circular order. Names have no mechanical meaning.
2. Shuffle five Blue and three Red assignments and give one to each player.
3. Shuffle the objective deck and draw eight cards. Deal one to each player from the active deck described in Section 7.2.
4. Independently assign one ability to each player.
5. Give each player five uncolored wallet tokens.
6. Reveal any public allegiance badges created by Standard Bearer.
7. Randomly choose the first chairman.
8. Draw the first mission: a funding threshold and a crew size.
9. Give each player the common rules and their own truthful private cards.

Team, objective, ability, and bot personality use separate random streams. Contrarian is absent from the active deck. Neither team gets automatic knowledge of its teammates. A Red player knows there are three Red players, but not who the other two are.

### 3.2 What is public

- Player names, seating order, chairman, and current phase.
- Current mission threshold, crew size, accumulated Blue/Red/Green totals, and number of attempts.
- Completed mission results and team mission counts.
- Wallet balances at public checkpoints.
- Proposed crews, revealed pledges, sequential votes, and complaints.
- Revealed reports and public allegiance badges.
- Whether an attempt used an approved crew or the rejection penalty.
- Income awards and the common timing and communication rules.

### 3.3 What is private

- A player's team unless publicly revealed by an ability.
- Their current personal objective and own objective-progress information.
- Their ability instructions, private results, and remaining once-per-game use.
- Unrevealed contribution, ability, pledge, and report submissions.
- Individual original contribution colors, except to the contributor and an authorized Auditor.
- Other players' beliefs and computer-policy state.

The ordinary public result reveals final mission totals and final wallet balances. It does **not** publish a separate pre-ability contribution total, identify ability users, or explain which modification produced the outcome.

Public wallet changes often provide evidence about quantities. This is intentional. They do not directly certify contribution colors, and theft can complicate the interpretation of a balance change. Wallet visibility should later be tested as an experimental variable, rather than assuming that more secrecy makes a better game.

### 3.4 Token semantics

- Wallet tokens are uncolored.
- Tokens acquire a color when deposited into the current mission.
- A player may deposit Blue, Red, Green, or a mixture, regardless of allegiance.
- Contributions cost wallet tokens unless an ability explicitly creates a bonus.
- A player cannot spend more than the wallet balance available to fund that action.
- Tokens taken from a mission become uncolored wallet tokens.
- All token quantities are nonnegative integers. Wallets and mission piles cannot become negative.
- Tokens on a completed mission leave active play. Surplus does not carry into the next mission.
- No interest, ordinary token transfers, free conversion of mission tokens, or other actions exist unless explicitly granted by an ability.

### 3.5 Vocabulary

- **Game:** The entire contest until a team wins four missions.
- **Mission:** One card and its accumulating token piles. It may take several attempts to complete.
- **Attempt:** Up to eight proposals, followed by one resolution: either an approved crew acts or the rejection penalty is applied.
- **Proposal:** One chairman's crew selection, the crew's pledges, and the table's vote.
- **Turn:** One requested decision by a player, such as voting or choosing a contribution.
- **Night:** Informal name for hidden contribution and ability resolution. There is no real-time or overnight requirement.

Use “attempt” rather than “round” in the UI and code. If the UI says “round,” define it as an attempt and use it consistently. Each completed proposal vote pays revenue; only a resolved attempt can also pay continuing-attempt income.

## 4. Winning and mission scoring

### 4.1 Completing a mission

After all effects for an attempt have resolved, let `B`, `R`, and `G` be the current mission piles and `T` its threshold.

```text
funded = B + R + G >= T
has_competitive_color = B + R >= 1
complete = funded and has_competitive_color
```

If the mission is incomplete, all remaining tokens stay on it for the next attempt.

If complete:

- Blue wins the mission when `B >= R`.
- Red wins the mission when `R > B`.
- Green helps meet the threshold but is excluded from the ownership comparison.
- A mission awards exactly one mission point, regardless of surplus tokens.

Check completion only after theft and recoloring. Crossing the threshold earlier in resolution does not lock the mission or its winner.

### 4.2 Ending the game

The game ends when a team receives its fourth mission point. Capture the terminal wallet balances and contribution history after all modifying abilities for that attempt, **before any further income**.

Audits and final reports may still be delivered as the closing information phase. They cannot change the frozen outcome. No new proposal, objective swap, contribution, or income follows the terminal snapshot.

For an ordinary objective, a player wins if:

```text
their team is the winning team AND their personal condition is satisfied
```

For Contrarian, a player wins if:

```text
their team is NOT the winning team
```

Evaluate the objective currently held at the terminal snapshot, including any earlier swaps. Store a result for every player; there need not be exactly three, five, or even any individual winners. The winning team still exists even if all its ordinary members fail their personal conditions.

**Result-visibility default:** Publicly announce the winning team. Privately tell each player their own final objective and whether they won. Do not automatically expose other players' cards or individual outcomes; the trusted designer replay can show the full result.

If the development attempt limit is reached without a fourth mission, mark the run `UNRESOLVED` after that attempt's reports and before further income. A legitimate fourth-mission victory on the final permitted attempt takes precedence over the guard. Do not award a team victory for reaching the limit, treat Contrarian as successful, or silently convert it into a draw rule. Report unresolved runs separately in evaluation.

## 5. The complete play sequence

### 5.1 Begin an attempt

Keep the current mission if it is unfinished; otherwise draw the next mission after the preceding nonterminal attempt's income. Its threshold and crew size remain fixed until it completes.

Set the rejection count for the new attempt to zero. No income is paid merely for entering this phase; the initial five tokens fund the first attempt.

### 5.2 Private preparation before each proposal

Before the chairman selects a crew, allow eligible once-per-game preparation abilities:

1. Collect optional objective-swap choices privately and resolve them in initiative order.
2. Notify affected players of their final current objectives and any progress they are entitled to know under Section 10.2.
3. Collect optional team-inspection choices, then deliver those private results.

These are the Switcher and Scout windows. A player who has not used such an ability may pass and retain it for a later proposal. A rejected proposal creates another preparation window before the next chairman's selection.

For the public interface, use a generic “private preparation” phase. Do not reveal which abilities exist or who used them. Only show each player their own available controls.

### 5.3 Chairman selects a crew

The chairman selects exactly the crew size printed on the mission. Selected players must be distinct; the chairman may select themself. A zero-token player remains eligible.

Publish the selected crew.

### 5.4 Crew pledges

Each selected player submits a vector of promised Blue, Red, and Green contributions. For version 0.1, collect these privately and reveal them together before voting.

The promised total must be affordable using that player's currently visible wallet. A zero pledge is permitted. A pledge is a statement of intent, not an escrow or binding commitment.

No tokens are spent at this stage. The eventual contribution may use different quantities or colors.

### 5.5 Sequential voting

Starting with the chairman and proceeding clockwise, all eight players vote Yes or No. Every No vote must include exactly one complaint using Section 6's grammar; Yes votes have none.

Each player sees earlier votes and complaints in the same proposal. Everyone votes even if the outcome has already become mathematically certain; the remaining statements are still information.

- Five or more Yes votes approve the proposal.
- Four or fewer Yes votes reject it.
- A 4–4 tie rejects the proposal.

If rejected:

1. Increase the attempt's rejection count by one.
2. Advance the chairman one seat clockwise.
3. If fewer than eight proposals have been rejected, return to private preparation.
4. If all eight were rejected, proceed to rejection-penalty resolution.

After all eight ballots, pay every player one wallet token, whether approved or rejected. Rejected proposals do not spend pledged tokens or clear the existing mission pot. There is no withdrawal, revised pledge, or second vote on the same proposal.

### 5.6 Approved attempt: secret actions

For an approved crew:

1. Each crew member privately commits an actual contribution vector within their wallet budget.
2. Eligible non-crew Stowaways privately choose whether to deposit one token and its color.
3. Thieves and Recolorers privately commit their permitted actions or pass.
4. Derive Echo bonuses from the committed original contributions.

All hidden choices use the same pre-resolution public information. No player sees another player's submitted action before committing. An actor who chooses theft cannot condition it on contributions that have not yet been revealed; they choose a source and requested amount/colors in advance.

Resolve the committed actions according to Section 8. Do not ask for new choices partway through token modification.

### 5.7 All-rejected attempt: secret actions and penalty

If all eight chairmen are rejected:

- There is no selected crew, no ordinary contribution, and no Echo bonus.
- Eligible Stowaways, Thieves, and Recolorers may still commit actions privately.
- Add five Red tokens to the mission as the base deposit for the attempt.
- Apply Stowaway deposits, then theft, then recoloring.
- Check completion after those effects.

There is no ordinary Auditor target because nobody served on a crew. The penalty creates Red **tokens**, not an automatic Red mission point.

### 5.8 Reveal, audit, and report

Publish the final mission totals, final wallet balances before income, and any mission award. Keep the resolved mission's totals in the history even when its tokens are removed from active play.

After an approved attempt, each Auditor may select one crew member for a private inspection. This choice is made after the public result but before reports. Return the target's original contribution, unaffected by Echo, theft, or recoloring.

Then collect reports from the approved crew only:

- Crew members submit at least one and at most three statements.
- Non-crew members do not report.
- On an all-rejected attempt, skip reporting and finish the attempt immediately.
- Reveal all submitted reports together.

False reports are legal. A crew member who contributed zero can report, for example, `Abby gave 0 Blue`.

### 5.9 Continue or finish

If a team now has four missions, publish the already frozen game result after the closing information phase.

Otherwise:

1. Give every player one token.
2. Set the next chairman to the seat immediately after the last proposer in this attempt.
3. Retain an incomplete mission, or draw a new card if the mission completed.
4. Begin the next attempt.

After eight rejections, “after the last proposer” wraps back to the attempt's original chairman. This is the version 0.1 rotation rule; track seat effects during playtesting.

## 6. Structured communication

There is no free-form table chat in version 0.1. Communication comes from crew selection, pledges, votes, complaints, contributions, and reports.

### 6.1 Pledges

Represent a pledge as three integer quantities:

```json
{"blue": 3, "red": 0, "green": 1}
```

Show only the nonzero entries in the human UI, except that an all-zero pledge must be clearly displayed as zero.

### 6.2 Complaints attached to votes

Grammar:

```text
[optional modifier: more | less | exact]
[optional player]
[optional color: Blue | Red | Green]
```

At least a player or a color must be present. A modifier alone is invalid. Each expression contains at most one modifier, one player, and one color. A No vote has exactly one expression; a Yes vote has none.

Examples:

- `Less Abby`
- `More Green`
- `Less Red`
- `Abby Red`
- `Exact Abby Blue`

The engine does not interpret these as authoritative allegations or enforceable requests. `Abby Red` might mean “Abby is Red,” “Abby should contribute Red,” or something established through earlier play. `Exact` has no quantity field or certified meaning in version 0.1.

Bots may adopt tentative interpretations, but the game does not certify those interpretations. Complaints are required on No votes and prohibited on Yes votes.

Example payload:

```json
{
  "approve": false,
  "complaints": [
    {"modifier": "less", "player_id": "p2", "color": null}
  ]
}
```

### 6.3 Reports after resolution

Grammar:

```text
[player] [gave | took] [nonnegative integer quantity] [color]
```

The named player may be the speaker or anyone else.

- **Gave:** Claims an original paid deposit into the current mission during this attempt. Includes a Stowaway's paid deposit; excludes an Echo bonus and the automatic penalty.
- **Took:** Claims a removal of that color from the current mission during this attempt.

These are gross-action claims, not claims about a player's net effect on the final pot. A player may truthfully have given Blue even if it was later recolored Red.

Examples:

```text
Abby gave 3 Blue
Ben gave 1 Green
Casey took 2 Red
```

Reporting two tokens of different colors takes two statements. Omission is permitted, including omitting theft or one color of a mixed contribution. Quantities in reports do not need to agree with the speaker's wallet or the actual action. Validate their integer syntax, not their truth.

There is no source-wallet field. The grammar cannot fully describe wallet-to-wallet theft. Accept that limitation for the first build; do not silently reinterpret `took Red` as stealing uncolored wallet tokens.

### 6.4 Player claims versus engine information

Visually distinguish official results and private inspection results from player statements. A truthful-looking report is still a player statement. The engine never marks a report “verified” merely because it matches internal truth.

Private inspection information can influence a subsequent report, but the report does not carry a transferable certificate of the inspection.

## 7. Personal objectives

There are **eight active objective types**, plus the disabled historical Contrarian. All except Contrarian require the holder's team to win four missions.

| ID / name | Exact personal condition | Intended pressure |
|---|---|---|
| `loyalist` — Loyalist | No extra condition | Provides straightforward team-oriented players |
| `saver` — Saver | Finish with at least 10 wallet tokens | Encourages conservation |
| `spendthrift` — Spendthrift | Finish with exactly 0 wallet tokens | Encourages spending before the game ends |
| `exact_change` — Exact Change | Finish with exactly 7 wallet tokens | Requires resource and endgame timing |
| `opposition_patron` — Opposition Patron | At least 20 paid token deposits, across all players and the whole game, were originally of the opposing team's color | Makes helping the opposition instrumentally useful |
| `close_race` — Close Race | The opposing team has won exactly 3 missions when the holder's team wins its fourth | Requires a 4–3 finish |
| `reliable_partner` — Reliable Partner | On at least 2 approved attempts, the holder's original contribution exactly matched their pledge in every color and totaled at least 2 tokens | Rewards a history of keeping substantial promises |
| `passenger` — Passenger | On at least 1 approved attempt that completed a mission, the holder was selected and originally contributed 0 tokens | Encourages benefiting from others' spending |
| `contrarian` — Contrarian | Only a Blue holder is eligible; win when Red wins the game, replacing the normal team-win requirement | Creates a possible secret fourth player wanting Red while preserving five Blue allegiances |

**Current status:** Contrarian is disabled in default deals because playtesting
found a systemic Red advantage when it was present. Its old Blue-only predicate
is retained for saved games and explicit abilities-off comparisons.

### 7.1 Exact accounting

- End-wallet objectives use the terminal snapshot before further income.
- Opposition Patron counts original paid deposits by everyone, including Stowaways. Blue holders count Red deposits; Red holders count Blue deposits. Green does not count.
- Automatic penalty tokens, Echo bonuses, and color changes do not count as paid deposits.
- Later theft does not erase a historical deposit. If a stolen token is paid into a mission again, that later deposit is another counted contribution event.
- Reliable Partner checks the original contribution vector against the original pledge vector, before modifications. Two qualifying attempts on the same accumulating mission are sufficient.
- Passenger can qualify on a mission won by either color. The ordinary final team-win requirement still applies.
- Only a Blue player may hold Contrarian. It does not change the player's actual allegiance, team-inspection results, or public badge. It changes their victory condition.
- Unresolved games satisfy none of these victory conditions.

### 7.2 Proposed objective deck

Use a 13-card deck:

- Six Loyalist cards.
- One of each other objective except Contrarian (seven cards).

Shuffle and draw eight cards without replacement. Contrarian cannot appear in
the abilities profile. Some active objective types will be absent in each game.
The composition is designer information, not a player-facing list. Historical
abilities-off configurations can explicitly include one Contrarian, restricted
to Blue; that experimental setup must be identified separately.

For targeted scenarios, explicitly assign cards instead of using a random deal. Tag those games as scenarios so they do not accidentally enter random-deal benchmark statistics.

### 7.3 Objective swaps

History belongs to the player, not the card. A received objective is evaluated against its new holder's entire game history, including actions taken before receiving it.

Both affected players privately learn their new objective and any progress they are entitled to know under Section 10.2 when a swap resolves. A player retains their team, wallet, ability, use counters, and historical actions.

Swaps are implemented for all active objectives, across either team. A player can receive the same type they already held if duplicates are involved. Contrarian is excluded from the abilities profile, so swaps cannot introduce it. Any future reintroduction needs explicit swap-eligibility rules that do not leak hidden teams through target validation.

## 8. Abilities and their resolution

There are eight ability types. Each player receives one and is truthfully taught its exact behavior. Other players are not given the catalogue.

### 8.1 Thief

**Once per game**, secretly request a transfer of one to three tokens from one source into your own wallet.

- Source may be another player's wallet or the current mission.
- Wallet theft requests an uncolored amount. You cannot target your own wallet.
- Mission theft requests a Blue/Red/Green vector totaling one to three.
- Resolve after ordinary deposits, penalty deposits, Stowaway deposits, and Echo bonuses.
- Transfer only what remains available at the selected source at resolution. For mission theft, clip each requested color independently; do not substitute a different color.
- Stolen mission tokens become uncolored wallet tokens.
- You may act whether or not selected, including on a rejection-penalty attempt.

**Default:** A syntactically valid, non-pass attempt consumes the once-per-game use even if the source is empty by resolution. The ability card must disclose this. The Thief privately learns the actual transfer they performed, but not why competing actions changed availability.

This is the narrowed once-per-game version discussed to avoid a recurring three-token drain dominating one-token income. A repeatable one-token Thief is a later balance experiment.

### 8.2 Stowaway

On each attempt when you are **not selected**, you may secretly spend one wallet token and deposit it into the current mission in a chosen color.

- Requires at least one wallet token at commitment.
- Costs one; does not generate a free token.
- On an all-rejected attempt, nobody is selected, so Stowaways are eligible.
- Cannot make this extra deposit while on an approved crew.
- Counts as an original paid contribution for global contribution totals.

### 8.3 Auditor

After each approved attempt's public result, you may select one player who served on its crew and privately learn their exact original Blue/Red/Green contribution vector.

- You do not need to have served on the crew.
- The result is truthful and arrives before reports.
- It excludes bonus creation, theft, and recoloring.
- It does not reveal team, objective, ability, or later modifications.
- No inspection on an all-rejected attempt.
- Inspecting yourself is permitted but normally uninformative.

### 8.4 Switcher

**Once per game**, before a proposal, exchange your objective with another player's objective.

- Choose another player; no consent is required.
- Both privately learn their new objective and any permitted progress information.
- No team, ability, wallet, or historical action is transferred.
- Using the ability consumes the user's use even if both cards have the same objective type.
- The recipient is told that their objective changed, but is not automatically told who initiated the swap.

### 8.5 Standard Bearer

Your true allegiance is publicly visible throughout the game.

- Display an official Blue or Red badge from setup.
- Your objective and ability card remain private.
- This grants no extra tokens, immunity, or guarantee of cooperative intent.
- Contrarian and other objectives can make a publicly Blue player prefer actions that help Red.

### 8.6 Scout

**Once per game**, before a proposal, choose another player and privately learn their true team.

- The answer is reliable even if their objective makes them want their team to lose.
- The target is not notified by this ability.
- No objective or ability information is revealed.
- Using the ability on an already public allegiance still consumes the use; do not create a secret validation shortcut.

### 8.7 Recolorer

On each attempt, you may secretly change one token on the current mission from one color to a different color.

- Choose source and destination colors before resolution.
- Resolve after theft.
- May affect a token placed on an earlier attempt, the rejection penalty, an Echo bonus, or a current contribution.
- If no token of the source color remains when your action resolves, nothing changes.
- May act whether or not selected, including on a rejection-penalty attempt.
- Costs no wallet tokens and preserves the total number of tokens.

### 8.8 Echo

Whenever you are on an approved crew and your original paid contribution is at least two tokens of exactly one color, add one bonus token of that same color to the mission.

- Automatic; no separate activation or wallet cost.
- Two Blue qualifies; three Blue qualifies; one Blue does not; two Blue plus one Green does not.
- Green contributions can trigger Echo.
- The bonus does not count as personal spending, a paid historical deposit, or a pledge mismatch.
- No activation on all-rejected attempts.

### 8.9 Authoritative resolution order

For each attempt:

1. Apply all original paid contributions simultaneously and deduct their costs. On an all-rejected attempt, use the five-Red base deposit instead of crew contributions. Include eligible Stowaway deposits in either case.
2. Add all derived Echo bonuses.
3. Resolve Thief actions in initiative order.
4. Resolve Recolorer actions in initiative order.
5. Check mission completion and award one point if applicable.
6. Record objective history and freeze any terminal result.
7. Reveal the public result and deliver actors' own private action receipts.
8. Collect and deliver authorized audits.
9. Collect and reveal reports.
10. If nonterminal, pay income and continue.

**Initiative default:** Clockwise seat order beginning with the final proposer of the attempt. Within a preparation window, begin with that proposal's chairman. Publish the general convention but not which private actions occurred.

Duplicate abilities are allowed. Multiple thefts may exhaust a source; later requests transfer less or nothing. Multiple recolorings may move the same token more than once. Multiple simultaneous swap requests resolve in initiative order against the then-current objective assignments; notify affected players of their final objective before they make another decision.

A stolen token cannot fund a contribution already committed in the same attempt. Audit choices are an explicit post-result exception to the rule that modifying actions are committed before outcomes are seen.

## 9. Worked examples

### 9.1 Green funds a Red victory

The threshold is 10. After resolution the mission contains 2 Blue, 3 Red, and 5 Green.

- Total funding is 10, so the threshold is met.
- Red beats Blue by 3 to 2.
- Red wins the mission even though Green is the largest pile.

### 9.2 Blue tiebreak and all-Green exception

At threshold 10, a pot of 3 Blue, 3 Red, and 4 Green awards Blue the mission.

A pot of 0 Blue, 0 Red, and 10 Green stays open. On a later attempt, recoloring one Green to Red would make the pot 0 Blue, 1 Red, and 9 Green, completing the mission for Red without increasing its total funding.

### 9.3 An honest contribution produces a suspicious result

An empty mission has threshold 10 and crew size 3. Abby pledges and contributes 3 Blue, Ben 2 Blue, and Casey 2 Green. All promises are honored.

- Original deposits: 5 Blue, 0 Red, 2 Green.
- Abby has Echo, adding 1 Blue: 6 Blue, 0 Red, 2 Green.
- A Recolorer changes 1 Blue to Red: 5 Blue, 1 Red, 2 Green.
- Total 8 is below 10, so the mission remains open.

Abby's report `Abby gave 3 Blue` is true. It does not explain the extra total token or the Red token. An Auditor inspecting Abby sees her original three Blue, not four Blue and not her net effect after recoloring.

If the game continues, all players receive one income token after reporting. The eight mission tokens remain for the next attempt.

### 9.4 Rejection does not guarantee a Red mission

The threshold is 10 and the mission currently has 5 Blue. Eight proposals are rejected.

- Add 5 Red: the pot is 5 Blue and 5 Red.
- With no further effects, total 10 completes for Blue on the tiebreak.
- If a Recolorer changes 1 Blue to Red, it completes for Red at 4–6 instead.
- If a Thief removes 1 Red and nothing replaces it, total 9 leaves the mission unfinished.

### 9.5 Historical example: Contrarian and a truthful inspection (disabled)

Abby is Blue and holds Contrarian. A Scout correctly learns “Abby is Blue.” Abby nevertheless wants Red to reach four missions.

The Scout's information is accurate. The inference “therefore Abby wants Blue to win” is not guaranteed by the rules. If Abby later swaps away Contrarian, her current objective determines her new victory condition.

## 10. What players are taught

Create separate artifacts for public instructions, private cards, and designer documentation. They must not be assembled by handing a model the entire designer catalogue and asking it to ignore parts.

### 10.1 Public teaching script

The player-facing guide should explain:

1. There are eight players: five Blue and three Red. Contrarian is disabled in new tables.
2. Each player privately receives an allegiance, a personal objective, and an ability. These can produce conflicting incentives and unfamiliar effects. Some assignments may repeat or be absent.
3. Each player is told the truth about their own current cards and official private results. Other players' claims can be false.
4. Missions accumulate colored tokens; the threshold, Green rule, Blue tiebreak, and first-to-four rule work as specified above.
5. A personal objective can add requirements or replace the ordinary team-win condition; read your own objective.
6. Crew proposals, pledges, sequential voting, the eight-rejection penalty, hidden actions, public outcomes, and reports follow the stated sequence.
7. Wallet tokens are uncolored, players may contribute any color, and pledges/reports are not binding.
8. Hidden effects resolve in a stable order: deposits and bonuses, transfers, color changes, then mission scoring. Explain this generic ordering without listing individual abilities.
9. Public records are accurate; absence of a visible explanation does not mean the engine is wrong.
10. There is no direct free-form chat, ordinary inspection action, or free reset of the official game.

Do not teach the eight ability names, their exact triggers, the nine-objective list, which cards are present, or a checklist of possible explanations for every discrepancy. The players should know the interface and common rules while acquiring the private mechanisms through evidence.

### 10.2 Private cards

Each player's objective card states the exact win predicate and any relevant progress counters. Their ability card states its trigger, timing, legal targets, cost, use limit, failure behavior, and private information returned.

Progress information must respect visibility. For example, a Reliable Partner can see their own qualifying actions. An Opposition Patron's exact global paid-deposit counter is **not** automatically visible: it would reveal hidden contribution information. Show the condition and public evidence, and evaluate the hidden total internally at the end. The same rule applies after an objective swap.

### 10.3 Interface tutorial

Use a short separate tutorial to teach controls and public scoring. Clearly label any example-specific special rule and avoid demonstrating the complete hidden evaluation catalogue. Humans and agents should receive equivalent instruction content, even if one uses buttons and the other JSON.

Maintain a revealed-rules development mode for debugging and an explicitly labelled experimental control. Never mix its results with the hidden-rules condition.

## 11. Software architecture and data contracts

### 11.1 Recommended first stack

Use Python for the authoritative engine, policies, simulator, and analysis. Keep the engine independent of the UI and any model provider.

- Standard-library dataclasses/enums for core state and typed actions.
- Explicit JSON serialization with a schema version.
- Standard-library `unittest`, or the repository's existing test framework if this becomes part of an established project.
- JSON Lines for development event logs and SQLite for resumable local sessions.
- A thin local HTTP service and a basic HTML/CSS/JavaScript interface after the terminal version works. A small web framework is optional; it must not contain game rules.
- Model adapters added only after scripted opponents can complete games.

These are implementation choices, not claims that particular package versions are required. Pin any added dependencies when building. Avoid introducing training infrastructure, a physics engine, a game renderer, or a large orchestration framework for the first prototype.

### 11.2 Suggested repository

```text
mission_game/
  README.md
  pyproject.toml
  configs/
    prototype_v01.json
    development_population.json
  docs/
    designer_rules.md
    public_player_guide.md
    protocol.md
  src/mission_game/
    types.py                 # Enums, immutable value objects, action payloads
    config.py                # Versioned setup and runtime configuration
    setup.py                 # Deal teams, objectives, abilities, and missions
    engine.py                # State transitions and phase orchestration
    resolution.py            # Deposit, bonus, theft, recoloring, award order
    objectives.py            # Progress tracking and terminal win predicates
    abilities.py             # Private card text and effect implementations
    observations.py          # Strict public/private projection
    actions.py               # Validation against the appropriate information
    events.py                # Authoritative and player-visible event types
    rng.py                   # Reproducible, separated random streams
    persistence.py           # Snapshots, logs, resume, idempotency
    runner.py                # Runs games with interchangeable controllers
    policies/
      base.py                # Policy interface
      random_legal.py
      straightforward.py
      objective_aware.py
      belief_tracking.py
      traits.py
    adapters/
      terminal.py
      json_agent.py
      model_agent.py         # Later: provider-independent model adapter
    server.py                # Later: local human/agent HTTP endpoints
    cli.py
  web/                       # Human UI; no authoritative rules
  scenarios/                 # Explicit fixtures for mechanics and reasoning
  tests/
    test_resolution.py
    test_objectives.py
    test_phases.py
    test_visibility.py
    test_replay.py
    test_actions.py
  runs/                      # Ignored local logs, snapshots, and reports
```

This is a proposed layout, not a requirement to create empty abstractions in advance. Combine small modules until their responsibilities justify separation.

### 11.3 Authoritative state

The engine should maintain at least:

| Object | Required fields |
|---|---|
| Game | ID, rules/config versions, phase, revision, seat order, chairman, attempt/proposal counters, team mission counts, status |
| Player | ID, true team, objective card instance, ability, wallet, remaining use flags, public badge, objective history |
| Mission | ID, threshold, crew size, token vector, attempt count |
| Proposal | ID, chairman, selected crew, committed/revealed pledges, ordered votes and complaints |
| Pending batch | Eligible request IDs, accepted hidden submissions, batch visibility state |
| History | Paid contribution records, pledge matches, completed-mission participation, mission awards, swaps |
| Private inbox | Information available only to that seat, including inspections and objective changes |
| Terminal result | Winning team, final wallets/objectives, individual outcomes, termination reason |
| Reproducibility | Private setup seed/stream state, policy versions, controller state, event sequence |

Use stable objective-card instance IDs so swaps are unambiguous, but do not disclose deck positions or other players' card IDs in observations.

Represent colors in a fixed order, such as `blue`, `red`, `green`. Never rely on incidental dictionary order to decide effect resolution.

### 11.4 State machine

```text
SETUP
  -> ATTEMPT_START
  -> PREPARE_SWAP -> PREPARE_SCOUT
  -> SELECT_CREW -> COMMIT_PLEDGES -> REVEAL_PLEDGES
  -> VOTE_1 ... VOTE_8
       rejection 1..7 -> next chairman -> PREPARE_SWAP
       rejection 8   -> COMMIT_PENALTY_ABILITIES
       approval      -> COMMIT_CONTRIBUTIONS_AND_ABILITIES
  -> RESOLVE -> PUBLIC_RESULT
  -> AUDIT (approved attempts only)
  -> COMMIT_REPORTS -> REVEAL_REPORTS
       terminal    -> GAME_OVER
       nonterminal -> INCOME -> ATTEMPT_START
```

Use explicit phase types rather than a single mutable “turn” integer. Store pending decisions so execution can stop at any request and resume without reconstructing hidden commitments from UI state.

### 11.5 Policy contract

Conceptual interface:

```python
class Policy:
    def choose_action(self, observation, memory):
        # Returns a legal structured action and the policy's next memory.
        # Has no access to authoritative state, other seats, or the setup seed.
        return action, next_memory

class Game:
    def pending_requests(self): ...
    def observe(self, player_id, request_id): ...
    def submit(self, player_id, request_id, action): ...
    def snapshot(self): ...  # Trusted runner/persistence only.
```

The runner owns controllers and submits their responses. Policies must not receive a `Game` reference or closures that can inspect it. Snapshots and authoritative events belong to the trusted runner, never the participant protocol.

The same action contract must work for a terminal player, a browser human, a scripted policy, and a model-backed agent.

### 11.6 Observation example

This is illustrative JSON, not a demand to use exactly these field names:

```json
{
  "schema_version": "0.1",
  "game_id": "game-001",
  "request_id": "attempt-3-proposal-2-vote-p2",
  "revision": 81,
  "viewer": "p2",
  "phase": "vote",
  "public": {
    "chairman": "p1",
    "mission": {
      "id": "mission-2",
      "threshold": 10,
      "crew_size": 3,
      "pot": {"blue": 2, "red": 1, "green": 0}
    },
    "score": {"blue": 1, "red": 0},
    "crew": ["p1", "p2", "p4"],
    "wallets": {"p0": 6, "p1": 5, "p2": 7, "p3": 6,
                "p4": 4, "p5": 5, "p6": 7, "p7": 6},
    "pledges": {
      "p1": {"blue": 2, "red": 0, "green": 0},
      "p2": {"blue": 2, "red": 0, "green": 1},
      "p4": {"blue": 1, "red": 0, "green": 1}
    },
    "votes_so_far": [
      {"player_id": "p1", "approve": true, "complaints": []}
    ],
    "public_badges": {}
  },
  "private": {
    "team": "blue",
    "objective": {
      "id": "exact_change",
      "text": "Win with Blue and finish with exactly 7 wallet tokens."
    },
    "ability": {
      "id": "scout",
      "used": true,
      "text": "Once per game, before a proposal, inspect another player's team."
    },
    "inbox": [
      {"type": "team_inspection", "target": "p6", "team": "red"}
    ]
  },
  "action_spec": {
    "type": "vote",
    "approve": "boolean",
    "max_complaints": 1,
    "complaint_required_on_no": true
  },
  "history_cursor": 81
}
```

Provide the complete permitted history initially, or an explicit paginated history API. The cursor cannot substitute for evidence the player never received. If agents summarize their own histories, that is their controller's responsibility, not a reason to give them less information than humans.

### 11.7 Validation rules

Validate:

- Correct actor, current request, action type, and phase.
- Distinct legal crew IDs and exact crew size.
- Integer, nonnegative, affordable pledges and actual spending.
- Valid colors, report syntax, complaint syntax, and cardinality limits.
- Ability use limits and eligibility based on the actor's own information.
- At most one accepted submission per request.

Do not validate player statements against secret truth. Do not return errors such as “that player cannot be targeted because they have hidden ability X.” Unknown target-dependent effects should resolve according to the rule, usually as a no-op or reduced transfer, without turning action validation into an inspection oracle.

An invalid action should return a stable error explaining the violated public or own-card constraint and leave the game unchanged. Local smoke runs may use a logged fallback action to keep testing. Official evaluation must define invalid-action retries and failure handling in advance and count them; do not silently repair strategic choices.

### 11.8 Event logs and debug explanations

Maintain two distinct products:

1. **Authoritative event stream:** Full committed actions, effects, private information, random draws, and outcomes. Restricted to the engine and developer analysis.
2. **Player-visible stream:** Public events plus only the requesting player's private events.

Computer policies may also record concise developer explanations:

```text
Voted No: expected final pot favors Red; my current objective favors Blue.
Contributed 0: retaining tokens for Saver, despite the accepted pledge.
Reported the pledge: concealing my deviation under this policy's deception rule.
```

Store these separately from player observations. They are debug metadata describing a scripted policy's decision, not privileged truth that another player may inspect and not a requirement to expose a model's private reasoning.

An observation projector should construct a new allowlisted object. Do not serialize the full state and attempt to delete sensitive fields afterward.

## 12. Computer opponents

### 12.1 What makes a computer opponent useful

A useful first opponent:

- Chooses legal actions.
- Responds to the current pot, proposal, history, and its own cards.
- Has coherent incentives rather than random disruption.
- Can be influenced by evidence and communication.
- Produces repeatable behavior under a saved policy configuration and random seed.
- Does not inspect information unavailable to its seat.

It does not need to imitate every human or find optimal play. The benchmark question is initially whether a participant can learn and exploit meaningful structure, not whether seven bots reproduce a human table perfectly.

### 12.2 Keep four components separate

1. **Knowledge:** The common rules, own private cards, and observations actually received.
2. **Incentives:** Current objective and true allegiance, including the reversal caused by Contrarian.
3. **Beliefs:** Tentative estimates about allegiance, desired outcomes, statement reliability, and unexplained effects.
4. **Behavioral traits:** Resource caution, willingness to break promises, trust in statements, and willingness to test an uncertain explanation.

Sample traits independently of cards and team. Do not make every Red player dishonest, every Auditor cautious, or every Thief consistently vote last. Do not give bots a shared private memory or a side channel for coordinating their actions.

A player's **allegiance** and their **desired eventual winning team** must be represented separately. Conditional objectives can also make helping the eventual opponent temporarily useful.

### 12.3 Build opponent levels in order

| Level | Behavior | Purpose |
|---|---|---|
| 0: Random legal | Samples legal choices, with no claim to coherent strategy | Exercise transitions and detect crashes |
| 1: Straightforward | Supports its desired winner, spends conservatively, usually honors pledges, reports its own deposits accurately | Establish understandable complete games |
| 2: Objective-aware | Adjusts resource use and mission timing for all nine objectives; makes intentional deviations | Exercise the actual incentive structure |
| 3: Belief-tracking | Remembers claims, audits, outcomes, and uncertainty; changes trust and crew preferences | Make social evidence consequential |
| 4: Adaptive | Compares candidate actions using approximate forecasts and chooses informative experiments | Test strategic rule acquisition more seriously |
| Later: Model or learned policy | Uses the same observation/action interface | Compare stronger behavior or explore human-derived policies |

Level 0 is not a benchmark opponent population. Level 1 alone will not establish that deception or hidden-rule discovery matters. Start evaluating the central hypothesis with a mixture that includes Levels 2 and 3, plus deliberately diagnostic scenarios.

### 12.4 Concrete initial decisions

**Crew selection:** Enumerate all legal crews. With eight players and crew size two through four, there are 28, 56, or 70 choices. Rank crews by estimated helpful contribution, available wallets, remembered cooperation, and any reason to test a hypothesis. Include oneself only if that serves the current objective.

**Pledges:** Generate a small set of affordable vectors: zero, a small contribution, an estimated fair share of remaining funding, and a larger contribution that could complete or swing the mission. Include wallet-preserving options relevant to personal objectives. Straightforward bots pledge their intended action. Other policies may promise a more acceptable action than they intend to take.

**Votes:** Forecast the pot using existing totals and discounted pledges. Judge both whether the proposal improves the position and whether it would complete a mission for the desired side. Consider the rejection count and the likely effect of a five-Red penalty. An unfunded but helpful proposal can still deserve a Yes.

**Contributions:** Compare candidate quantities and colors against the accepted proposal. Consider mission ownership, funding, remaining wallet, objective progress, and the future cost of visibly breaking a promise. A Contrarian evaluates eventual victory from the opposite side of its actual allegiance.

**Complaints:** On a No vote, produce exactly one relevant expression: a preferred contributor, a suspected harmful contributor, or a color to increase/decrease. Interpret received complaints cautiously; they are signals, not commands or official role labels.

**Reports:** Choose among an accurate self-report, a repeated pledge that conceals deviation, an accurate statement based on an audit, or another policy-supported claim. A false accusation should have a strategic purpose, not be sampled just to make the transcript noisy.

**Abilities:** Read the bot's own card and score permitted uses. Examples include stealing a color to stop an unfavorable mission, recoloring to alter ownership, auditing a crew member implicated by a discrepancy, or using Scout on someone whose allegiance would change a crew decision. Switcher should value its current condition and uncertainty about the replacement; it cannot inspect target objectives before swapping.

#### An exact Straightforward baseline to implement first

Use these deliberately simple defaults to get an interpretable opponent running before adding candidate scoring. This baseline uses its own ability and desired winning side, but does not adequately pursue most additional personal conditions; the Objective-aware level must address that limitation.

1. **Desired side:** Use the bot's own team, except that its own Contrarian card reverses the side. Recompute after an objective swap.
2. **Crew:** Choose the `k` players with the largest visible wallets. Break ties using a saved per-policy random stream. Do not inspect their cards.
3. **Pledge:** Compute `gap = max(0, threshold - current_total)`. Pledge `min(wallet, ceil(gap / k))` tokens of the desired color. If the pot is all Green and already funded, use a one-token pledge when affordable. Pledge zero in the remaining zero-gap case.
4. **Vote:** Add the revealed pledge vectors to the current pot as a simple forecast. If it would complete, approve exactly when its winner is the desired side. If it would not complete, approve when total promised funding is positive and promised desired-color tokens are at least promised opposing-color tokens. This baseline ignores hidden modifications and rejection-pressure strategy; log those limitations.
5. **Contribution:** Honor the accepted pledge exactly.
6. **Report:** Accurately report the bot's own paid deposits, or a zero deposit if a selected player paid nothing. Non-crew players do not report.
7. **Stowaway:** When eligible and holding at least one wallet token, spend one token of the desired color.
8. **Recolorer:** Choose opposing color to desired color if an opposing token is currently visible; otherwise choose Green to desired color if possible; otherwise pass. The committed action can still no-op if intervening effects remove its source.
9. **Thief:** Use the once-per-game action to request up to three visible opposing-color mission tokens when any exist; otherwise retain the use. This intentionally simple baseline does not steal from wallets.
10. **Auditor:** Inspect the crew member with the largest total pledge, breaking ties with the policy's saved randomness. Store the result for later policies' memory support; the basic self-report rule does not automatically announce it.
11. **Scout:** At the first opportunity, inspect the richest other player whose allegiance is not already officially known to this bot. If none exists, pass.
12. **Switcher / Standard Bearer / Echo:** Switcher passes in this baseline; the other two abilities are passive. Exercise Switcher through fixtures and Objective-aware policies.

This opponent is intentionally exploitable. It provides a baseline against which to show that memory, objective reasoning, and more strategic decisions actually improve play. Do not fix its weaknesses by granting hidden-state access.

### 12.5 Objective-aware behavior

Use the exact win predicate as the terminal goal. Approximate intermediate preferences are only heuristics.

| Objective | Initial heuristic |
|---|---|
| Loyalist | Improve the chance of the actual team winning |
| Saver | Value reaching and preserving a 10-token terminal wallet while maintaining a path to team victory |
| Spendthrift | Plan affordable spending near the likely final mission; do not assume spending everything early guarantees a zero finish |
| Exact Change | Prefer terminal wallets near 7 and account for intervening income/theft |
| Opposition Patron | Seek evidence and opportunities for opposing-color paid deposits while preserving eventual own-team victory; retain uncertainty about the true hidden global count |
| Close Race | Help the opponent reach 3 if necessary, then try to prevent their fourth |
| Reliable Partner | Seek crew participation and honor pledges of at least 2 until two qualifying attempts are achieved |
| Passenger | Seek a place on a likely completing crew and submit 0 at least once |
| Contrarian | Favor the opposite team's eventual victory while managing what others infer from allegiance and conduct |

Do not implement each objective as an unconditional rule such as “Saver never spends below ten.” Such a rule can make its own victory impossible. Candidate scoring should account for imminent wins and losses; simple heuristics are allowed to be imperfect, but their failure should be visible in logs.

### 12.6 A manageable candidate-scoring loop

```python
def choose_action(observation, memory):
    memory = update_from_visible_evidence(memory, observation)
    candidates = generate_candidates(observation, memory)
    scored = []

    for action in candidates:
        forecasts = forecast_visible_consequences(
            observation=observation,
            memory=memory,
            candidate=action,
        )
        score = evaluate_for_current_objective(
            forecasts,
            resource_preferences=memory.traits,
            reputation_cost=estimate_reputation_cost(action, memory),
            information_value=estimate_information_value(action, memory),
        )
        scored.append((action, score))

    return choose_with_seeded_variation(scored, memory), memory
```

For the first version, `forecast_visible_consequences` can be a small arithmetic model over the current pot, plausible pledge fulfillment, and the actor's known ability. It does not need full-game tree search.

The initial score can combine mission progress, projected ownership, wallet suitability, personal-objective progress, and social consequences with documented weights. Those weights are uncalibrated policy parameters, not probabilities of winning. When a candidate leads to a terminal outcome in the forecast, use the actual personal win condition rather than rewarding team victory alone. If a required condition is hidden, estimate it from the bot's information rather than querying the engine.

As wallets grow, avoid enumerating every possible three-color vector. Generate useful candidate totals, such as `0`, `1`, `2`, a funding gap, an ownership-swing amount, and objective-relevant spend amounts; clamp to affordability, then consider pure colors and a few useful mixtures. This controls policy cost without restricting the actual game action space.

Full rollouts are a later improvement. If used, roll out sampled hypotheses consistent with the bot's information. Passing the actual hidden state to a rollout, even if the final chosen action is legal, makes that opponent omniscient.

### 12.7 Memory and uncertainty

Track separate records for each player:

- Possible allegiance and confidence.
- Evidence about what outcomes they seem to favor.
- Promise history and specific contradictions supported by private inspection.
- Reliability of particular claims; avoid collapsing everything into one permanent “liar” bit.
- Crews and events associated with unexplained token gains, losses, or color changes.

Track global unresolved explanations separately. A discrepancy involving a crew is not proof that each crew member lied. A non-crew ability or a previous mission token can be involved.

An initial belief-tracking bot can use simple weighted evidence:

```text
Observation: final total exceeds the total promised, after accounting for the known penalty.
Possible explanations: someone paid more, an outside contribution occurred,
or an unknown mechanism created tokens.
Action implication: retain multiple explanations; seek a comparable later attempt.
```

A later rule learner can propose mechanisms from observed features, such as an extra token appearing only when a certain person is selected and contributes at least two of one color. It should retain alternatives and test predictions instead of receiving the correct Echo label from the evaluator.

Two explicit development modes are useful:

- **Catalogue-informed reference:** A policy may know the ability catalogue but not assignments. This helps test strategy and engine mechanics. Label its informational advantage.
- **Catalogue-hidden policy:** Receives only common rules and its own cards. Hypothesis generation must not secretly load the designer catalogue.

Do not present the first mode as evidence that the second mode has learned unfamiliar rules.

### 12.8 Responsive policies instead of fixed ghosts

A recording says what a person did in a state that actually happened. A responsive policy computes what to do in the current state, which may differ because the evaluated player acted differently.

Begin with scripted policies and inspect whether their responses make sense. Human recordings can later help estimate such tendencies as spending restraint, reactions to broken promises, or choice among complaint expressions. A learned policy must still be evaluated on states outside the recorded paths.

Do not attempt to enumerate every possible playthrough or claim that a stochastic role script is a validated human simulator. Its usefulness comes from responsive, coherent opposition and controlled evaluation, not from resemblance by assertion.

### 12.9 Opponent-population defaults

For an initial development mixture, sample among straightforward, objective-aware opportunistic, and skeptical evidence-tracking policies. Include more than one spending/deception setting within each family. Keep the mixture in a versioned configuration file.

Use one-controller-per-seat state, even when all controllers share the same policy implementation. For the first evaluation mode, one human or evaluated agent takes one seat and seven frozen policies fill the rest.

Later maintain separate practice and held-out populations. Changing only the random seed is not a meaningful held-out policy family. Vary actual response rules and strategies, and report the population version with every score.

## 13. Asynchronous operation and reproducibility

### 13.1 No live table is required

The engine requests an action, waits, accepts it, and advances only when the phase permits. The game clock is an action sequence, not wall-clock time. Computer seats respond when invoked; human or external-agent seats can resume later.

One-player-against-bots mode is the simplest asynchronous prototype. Human-versus-human async play can use the same request queue later, but is not required to demonstrate the concept.

### 13.2 Save at every decision boundary

Persist:

- Authoritative game state and pending sealed submissions.
- Current request IDs and accepted-response IDs.
- Event revision and all RNG stream positions.
- Controller memory and controller RNG state.
- Rules, schema, setup, and policy configuration versions.

On resume, regenerate the same pending observation. Do not redraw missions, redeal cards, rerun an already accepted action, or regenerate a stochastic bot's earlier response.

### 13.3 Simultaneous phases in a sequential process

The server may call policies one after another for convenience, but all must see the same phase snapshot until the batch closes. Later calls must not see early contributions, reports, or updated wallets.

Expose neither the contents nor the arrival order of sealed responses to other players. A player may see that their own response was accepted. Internally, skip ineligible ability choices without exposing which seats were skipped through the participant protocol.

### 13.4 Proposed HTTP interface

The local human/agent adapter can expose:

```text
POST /games                         Create a configured game; trusted runner only
GET  /games/{id}/requests/current    Fetch this authenticated seat's pending request
GET  /games/{id}/history?after=...    Fetch this seat's permitted events
POST /games/{id}/actions             Submit request_id + revision + action
GET  /games/{id}/result              Fetch permitted terminal results
```

Seat identity comes from its credential or local controller binding, not a freely editable `player_id` query parameter. Developer replay and omniscient inspection use a separate trusted interface.

Require idempotency: retrying the same accepted request must return its acceptance status without charging tokens or executing an ability again. Reject stale conflicting submissions without changing the state.

### 13.5 Randomness and replay

- Separate setup, mission generation, and per-policy random streams.
- Keep future mission draws independent of how often a bot samples candidate actions.
- Save sampled outcomes in the authoritative log as well as the necessary stream state.
- Treat setup seeds as private: a seed can reveal the hidden deal to someone with the generator.
- A replay reconstructs state from the recorded actions/events; a fresh stochastic model call is not a replay.
- Matched seeds help comparisons but do not guarantee identical later trajectories after different player choices.

The required determinism claim is: **same rules, initial state, recorded random outcomes, and accepted actions produce the same game state and result.** Do not promise that a nondeterministic external model produces the same actions each time it is called.

### 13.6 Evaluation isolation

For local development, the designer can inspect everything. For an actual hidden-information evaluation, the participant process must not be able to read authoritative snapshots, other-seat logs, role-dealing seeds, or hidden evaluation configuration from a shared filesystem.

The protocol should enforce information boundaries; a prompt saying “do not look at the other roles” is not sufficient. The public engine can be documented while evaluation instances and private state remain on the trusted side. This does not by itself settle broader practice/replica policy, which must be declared separately.

## 14. Step-by-step implementation guide

Build a small working slice at each milestone. Do not start by training opponents or adding a large user interface. The first deliverable is an engine that can run, stop, resume, explain its state, and finish games correctly.

**Implementation order update — September 10, 2026:** After the common-rules slice,
the local web play interface and replay viewer were moved ahead of the remaining
mechanics at the user's request. This brings the minimal human-interface work
from milestone 6 forward, supported by the implemented observation and
persistence foundations. Objectives are now implemented. At the user’s request,
scripted opponents have also been brought forward before abilities. The
Straightforward baseline is implemented, followed by `social.7`: per-seat
evidence estimates, seeded self-interest/caution/skepticism, predicted votes,
objective-specific spending plans for every candidate crew, wallet/income
targets, objective-driven inclusion demands, cover for permanent and temporary Red goals,
shared situational complaints, credibility-weighted accusations, and inspectable
designer diagnostics. Setup now fixes five Blue and three Red, with any Contrarian
restricted to Blue. Payment forecasts compare weighted integer outcomes,
including Blue ties, and tied plans prefer the safer tactical color margin.
Generic token-retention utility has been removed; wallet incentives come from
the objective. Public bot complaints no longer include Less Blue.
These are initial heuristics requiring behavioral tuning, not a completed
difficulty or balance evaluation. See `docs/bots.md` for current behavior.

**September 11, 2026:** All eight abilities now have engine rules, guided web/terminal controls, and replay support. Preparation uses fixed private cover slots; swaps resolve before scouting. Hidden deposits, bonuses, theft, and recoloring precede scoring. Audits precede reports even on game-ending approved attempts. Contrarian is disabled in new default decks. Bot ability tactics remain initial heuristics; unexplained public changes are not treated as proof of dishonesty. Further interface refinement and balance work follow. This changes
development order only; it does not change the game rules or declare the full
prototype complete.

### Milestone 1 — Freeze configuration and implement common rules

**Work:**

1. Create the repository, package, configuration file, and test entry point.
2. Implement color vectors, player/mission state, setup, and independently seeded randomness.
3. Implement mission accumulation, funding checks, Blue tiebreak, the all-Green exception, and first-to-four scoring.
4. Implement crew selection, pledges, sequential voting, rejection advancement, the five-Red penalty, vote revenue after each full vote, and continuing-attempt income.
5. Add a development-only configuration with all Loyalist objectives and abilities disabled. Clearly label this simplification.
6. Implement a terminal state summary and legal-action random policy so complete transitions can be exercised.

**Deliverables:** A configurable engine, a single-game CLI runner, and focused rule tests.

**Acceptance:** A scripted example can complete a game; each completed vote pays everyone once, including rejections; a nonterminal eight-rejection attempt also pays attempt income; terminal wallets never receive an extra income token. The all-Green and Blue-tie examples match Section 9.

### Milestone 2 — Add all objectives and abilities

**Work:**

1. Implement the nine objective predicates and historical accounting.
2. Implement the eight abilities and exact resolution order.
3. Add once-per-game flags and per-attempt eligibility.
4. Support duplicate abilities and multiple objective swaps with deterministic initiative.
5. Add explicit scenario setup files so tests can choose cards and pot states directly.
6. Add receipts and inspection events internally, even before the human UI exists.

**Deliverables:** Complete version 0.1 mechanics, card definitions, and fixtures.

**Acceptance:** Every objective has passing and failing examples; ability interactions match the rules; original contributions remain distinguishable from final outcomes. Run at least 100 seeded random-legal games to find transition errors, recording unresolved games rather than declaring the game balanced.

### Milestone 3 — Enforce observations and structured communication

**Work:**

1. Implement public and seat-private observation projection.
2. Implement pledges, complaints, reports, and their syntax validation.
3. Collect pledges and reports in sealed batches; keep votes sequential.
4. Generate the public guide and the correct private cards for each seat.
5. Ensure hidden actions cannot be read through history, errors, shared policy objects, or pending-request metadata.
6. Give all controllers the same permitted event history.

**Deliverables:** Documented observation/action schemas and a terminal player adapter.

**Acceptance:** A person can manually control one seat without seeing other cards. False reports are accepted. A player cannot infer hidden submissions by polling between other seats' responses. Visibility tests pass.

### Milestone 4 — Build coherent scripted opponents

**Work:**

1. Implement Straightforward policies using public pot arithmetic and their own cards.
2. Add objective-aware candidate scoring for all nine objectives.
3. Add memory of pledges, private audits, observed discrepancies, and reports.
4. Introduce independently sampled spending, trust, and deception tendencies.
5. Log the reason each scripted policy selected its action.
6. Build three reproducible development populations and run the same seeds against each.

**Deliverables:** A bot-policy configuration format, multiple responsive policies, and a simulation summary command.

**Acceptance:** Bots have no privileged state access; swapping their objective can change their preferences; private audit evidence can change a later crew decision; a bot does not automatically equate allegiance with desired victory. A batch of roughly 1,000 inexpensive scripted games reports termination, mission lengths, personal wins, ability usage, and objective frequencies without uncaught engine exceptions.

Treat that batch as a diagnostic sample. It is not a human comparison or proof of strategic quality.

### Milestone 5 — Add persistence and asynchronous execution

**Work:**

1. Save snapshots, event logs, policy memory, and random streams.
2. Assign stable request IDs and implement idempotent submission.
3. Pause and resume during sequential voting and during partially committed simultaneous batches.
4. Separate replay from invoking fresh controllers.
5. Implement the JSON agent adapter and optional local HTTP service.

**Deliverables:** Resumable sessions, replay tooling, and an external-agent protocol.

**Acceptance:** An interrupted game resumed from each major phase reaches the same result under the same remaining actions. Resending a contribution or once-per-game ability cannot execute it twice. An observer cannot read pending sealed actions.

### Milestone 6 — Add the human play interface

**Work:**

1. Show mission threshold, crew size, pot, score, wallets, chairman, and phase.
2. Give the human a private panel for their own objective, ability, legal choices, and messages.
3. Add crew selection controls, pledge/contribution color counters, Yes/No buttons, complaint builders, ability controls, and report builders.
4. Show a chronological history that distinguishes official events from player claims.
5. Allow local save/leave/resume and replay of the human's own perspective.
6. Keep the omniscient developer view visibly separate from play mode.

**Deliverables:** One human versus seven computer opponents, playable without editing JSON.

**Acceptance:** A first-time player can follow a complete game using the public guide and their private cards. Buttons cannot produce actions the schema rejects. The UI explains whether it is waiting for the player's action, a sealed batch, or a transition; it does not expose hidden-role participation.

Do not display designer terminology, internal policy scores, catalogue hypotheses, or hidden-event explanations as ordinary gameplay help.

### Milestone 7 — Test the rule-acquisition hypothesis

**Work:**

1. Author the diagnostic scenarios in Section 16.
2. Collect human play against fixed scripted populations.
3. Add a model-agent adapter using the same permitted observations and actions.
4. Compare hidden-rules and explicitly revealed-rules conditions.
5. Test whether reports, audits, and opportunities to select crews materially affect inference and outcomes.
6. Record examples where an inferred rule produces a correct new prediction or useful decision.

**Deliverables:** A short experimental report, replay examples, failures, and a go/no-go recommendation for further investment.

**Acceptance:** Evidence supports or rejects the narrow hypothesis. An honest negative result is acceptable: if basic spending dominates and hidden mechanics do not matter, revise the game before investing in sophisticated opponents.

### Proposed CLI workflow

The following commands describe the interface to implement. They do not exist merely because this plan has been written.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests

python -m mission_game.cli simulate \
  --config configs/prototype_v01.json \
  --population configs/development_population.json \
  --games 100 --seed 20260910 --out runs/smoke

python -m mission_game.cli scenario scenarios/echo_discovery.json
python -m mission_game.cli play --human-seat 0 --seed 42
python -m mission_game.cli resume runs/session-001
python -m mission_game.cli replay runs/session-001 --seat 0
python -m mission_game.cli analyze runs/smoke
```

Do not print private setup seeds in the participant-facing interface. Explicit seeds in these examples are for trusted local development.

## 15. Verification and acceptance criteria

The game has enough interacting state and hidden information to warrant meaningful tests. Focus on behavior, invariants, privacy boundaries, and replay rather than tests that merely mirror helper functions.

### 15.1 Core examples

| Case | Required result |
|---|---|
| Below threshold | Pot persists; no mission point |
| Funded Blue/Red tie | Blue mission point |
| Green is largest pile | Ignore Green for ownership |
| Funded entirely Green | Mission remains open |
| Funded pot reduced below threshold by theft | No mission point |
| Recoloring changes competitive lead | Score the final colors |
| Rejected proposal | No pledged spending; everyone receives one vote-revenue token |
| Eight rejections | Eight vote-revenue payments, exactly five base Red tokens, eligible effects, then attempt income if nonterminal |
| Mission surplus | No bonus points or carryover |
| Fourth mission won | No further income, swap, or modifying action |

### 15.2 Ability interactions

- Echo produces exactly one token for a qualifying pure contribution, including pure Green.
- Echo does not trigger on one token, a mixed contribution, a non-crew action, or the penalty.
- Stowaway pays one, can act after all rejections, and cannot act while on the crew.
- Multiple Thieves targeting the same pile cannot create negative quantities.
- A Thief's empty-source activation consumes their use under this version's rule.
- Mission theft respects requested colors and does not substitute other colors.
- Same-attempt stolen tokens cannot retroactively fund a deposit.
- Recolorer preserves total tokens and no-ops if its source color is absent.
- Auditor sees the original contribution even after bonus creation, theft, and recoloring.
- Standard Bearer reveals only allegiance; Contrarian does not alter that allegiance.
- Scout's result is truthful and not shown to the target or other seats.
- Objective swaps preserve histories and use counters; overlapping swaps obey initiative.

### 15.3 Objectives

- Test just below, at, and above each wallet threshold.
- Verify Spendthrift at zero wins before hypothetical next income would make it one.
- Verify Contrarian wins with the opposite team and fails with its own; do not accidentally apply both team conditions.
- Confirm Opposition Patron counts paid opposing-color deposits only, including Stowaway, and counts later redeposits as new events.
- Confirm Reliable Partner uses original contributions and includes two attempts on one mission.
- Confirm Passenger requires the zero-contribution attempt itself to complete the mission.
- Confirm Close Race requires the opponent's two mission points at the finish.
- After swapping, evaluate the received card against the holder's earlier history.
- Unresolved runs never satisfy a victory predicate.

### 15.4 Token accounting invariant

Across a run, the following must hold after each resolved transition:

```text
sum(wallets) + current_mission_tokens + tokens_removed_with_completed_missions
  = initial_wallet_tokens + income_tokens + rejection_penalty_tokens + Echo_tokens
```

Theft and recoloring do not change this total. Original contributions and Stowaway spending move tokens between terms. This is a conservation check, not a public source-attribution report.

Also verify nonnegative wallets/piles, at most one mission award per attempt, and no more than the configured once-per-game uses.

### 15.5 Information-boundary tests

- Inspect every observation schema for hidden fields, seeds, policy state, and other seats' inboxes.
- Change an unobserved opponent objective in a fixture without changing public consequences; the observer's current observation must remain identical.
- Make one player submit a sealed action; another player's observation must remain unchanged until the proper reveal.
- Query history as different seats and confirm private results never cross seats.
- Submit a false report and verify that acceptance does not depend on whether it is true.
- Check that action errors reveal only public constraints or the actor's own card constraints.
- Verify private objective progress does not leak an otherwise hidden global contribution count.
- Check that polling or request ordering does not reveal which hidden abilities are active.

### 15.6 Replay and adapter tests

- Replay a recorded game to the same final state and public/private event streams.
- Resume after one of several sealed contributions has been received, preserving secrecy and exactly-once effects.
- Resume after an objective swap without dealing a new card or changing progress.
- Reject a stale action and accept an identical retry idempotently.
- Drive the same fixture through terminal and JSON adapters and compare accepted actions and results.

## 16. Playtesting and benchmark evaluation

### 16.1 Separate game health from reasoning evidence

First measure whether the rules produce playable games:

- Completed and unresolved run counts, with denominators.
- Attempts per game and per mission; proposal rejections per attempt.
- Blue and Red team win rates, split by Contrarian presence under the fixed 5/3 composition.
- Individual win rates by objective, ability, seat, and policy family.
- Objective condition satisfaction separately from final team victory.
- Token use, hoarding, Green contributions, penalty frequency, and ability activation rates.
- Frequency and effect of swaps, including Contrarian moves.
- Whether common simple strategies dominate across populations.

Team win rate alone is insufficient because some players are explicitly trying to make their team lose. Report nominal team composition and, in trusted analysis, how many players hold objectives favoring each eventual winning side. A swap can change that during a game.

### 16.2 Rule-discovery scenarios

Create a small set of authored scenarios with explicit ground truth and controlled sources of ambiguity. These supplement full games; they are not all standard random starts.

| Scenario | Evidence and decision to exercise | Success evidence |
|---|---|---|
| Extra token | A recurring participant is associated with an additional token under some contribution patterns | Learner predicts a qualifying and nonqualifying Echo case, then uses the distinction |
| Changed color | Audited original contributions conflict with final colors | Learner recognizes that truthful deposits can be modified and chooses a useful next test |
| Missing tokens | A pot or wallet loses tokens through a transfer | Learner distinguishes loss from an ordinary under-contribution when evidence permits |
| Visible ally, adverse incentives | Public Blue allegiance coexists with choices helping Red | Learner separates allegiance from desired outcome instead of declaring the badge false |
| Credible conflict | Two reports cannot both describe the same original contribution | Learner seeks discriminating evidence and updates the relevant claim's credibility |
| Changed incentives | An objective swap alters behavior while allegiance remains fixed | Learner revises a behavioral prediction rather than assuming a permanent persona |

For Echo, do not supply only examples where crew membership and qualifying contributions always coincide. Arrange opportunities to vary membership, amount, and color mixture; otherwise several rules fit the same evidence. A player's ability to obtain cooperation in setting up these contrasts can itself be part of the challenge.

For each scenario, write a designer note containing:

1. The actual hidden mechanism.
2. At least two plausible competing explanations.
3. Evidence initially available to the participant.
4. One or more legal actions that can help discriminate the explanations.
5. The cost or risk of those actions.
6. A later decision where the distinction changes a useful choice.
7. What remains genuinely unidentifiable from the permitted evidence.

Do not require certainty when two hidden states are observationally equivalent. Success can involve calibrated uncertainty and a robust action, not always naming the exact ability.

### 16.3 Evidence of understanding

Use a combination of:

- **Individual victory rate** under declared budgets and opponent populations.
- **Predictions of observable outcomes** in controlled follow-up situations.
- **Transfer:** Performance when a learned mechanism appears in a different crew, pot state, or incentive situation.
- **Information gathering:** Whether selected interventions distinguish useful hypotheses.
- **Belief quality:** Optional probabilities about allegiance or specific outcomes, collected privately and never shown to opponents.

A counterfactual prediction must specify which actions are held fixed and which other players may respond. Otherwise the evaluator may confuse an uncertain opponent choice with a misunderstanding of the rules.

Probability questions can use Brier score or a declared clipped log-loss convention. Specify the event and scoring formula in the evaluation protocol. Asking for probabilities over a complete list of ability names would disclose the hidden catalogue; use observable events or generic causal predictions instead.

Repeated forecasts within one game are correlated. Report uncertainty across games and, for humans, account for repeated participation. Do not treat hundreds of statements from one trajectory as hundreds of independent demonstrations of reasoning.

### 16.4 Human and agent comparisons

Use one evaluated participant against the same frozen seven-opponent population. Match or counterbalance:

- Seat and team composition.
- Objective and ability assignment frequencies.
- Mission distributions and scenario types.
- Public instructions, private information, and history access.
- Opponent versions and stochastic configurations.
- Permitted practice and familiarity with the interface and mechanics.

Humans may click buttons while agents submit JSON, but the choices and information should be equivalent. Use fresh humans or counterbalanced ordering when studying genuinely unfamiliar rules; exposing someone to the revealed catalogue first destroys a later hidden-catalogue comparison.

Record action counts, attempts, invalid actions, and model/tool usage. Report compute and latency as separate measurements with a clearly stated accounting boundary. Asynchronous gameplay does not require a wall-clock game penalty. Do not claim server-side action counting measures all off-platform computation.

Scripted bots are an environment, not a human baseline. Human results must come from people playing under the declared conditions.

### 16.5 Essential controls

1. **Hidden catalogue vs revealed catalogue:** Does prior knowledge of the actual mechanisms change performance? A difference is suggestive, not by itself proof that all remaining difficulty is rule acquisition.
2. **Reports enabled vs disabled:** Do reports convey strategically useful evidence, or mainly noise?
3. **Evidence-tracking vs memoryless opponents:** Does behavior actually respond to interactions?
4. **Abilities enabled vs disabled:** Does the hidden-mechanism layer change decisions and predictive performance?
5. **Ordinary objectives vs mixed objectives:** Do conflicting incentives add useful inference rather than indiscriminate sabotage?
6. **Familiar vs held-out policies and mechanics:** Does success transfer beyond known scripts and the initial eight abilities?

Keep each control explicitly versioned. Do not alter several mechanisms and then attribute the entire performance difference to one of them.

### 16.6 Go/no-go decision after the prototype

Continue developing this direction if there are repeatable examples where:

- Participants can obtain evidence that distinguishes important explanations.
- Learning a mechanism improves a subsequent prediction or decision.
- Other players' responses matter, including cooperation and reactions to deception.
- Simple fixed strategies do not dominate across the tested scenarios and populations.
- Humans can learn the interface and demonstrate the intended reasoning.

Revise before scaling if:

- Outcomes are mostly wallet arithmetic and seat luck.
- The best policy ignores reports, objectives, or hidden abilities.
- Most mysteries are impossible to distinguish within a game's available evidence.
- Bots make implausible choices that are easy to exploit regardless of rule understanding.
- Games stall because several objectives reward delay and no one wants completion.
- Extra mechanics add opacity without creating informative, consequential decisions.

No human–AI advantage should be asserted until measured with the actual agents and harnesses of interest.

## 17. Risks, open questions, and extensions

### 17.1 Balance questions to investigate first

- Is one token of income per attempt enough with thresholds of eight to twelve and small crews?
- Do the initial five tokens let early missions finish before useful evidence accumulates?
- Does Blue's numerical majority plus its tiebreak overcompensate for Red's rejection penalty?
- How sharply does the optional Blue Contrarian change balance between five and four players ultimately wanting Blue to win?
- Can coordinated zero contributions or rejection choices stall a mission indefinitely?
- Is recurrent one-token recoloring too influential near the final mission?
- Does once-per-game theft feel consequential without ruining exact-wallet objectives unpredictably?
- Are Opposition Patron's twenty paid tokens feasible often enough, given hidden totals and short games?
- Is Close Race excessively dependent on other players' choices?
- Is Passenger too easy to obtain, or does selection create meaningful negotiation?
- Does Green create useful compromise, or mostly hide an obvious benefit to the current leader?
- Does a public Standard Bearer help coordination enough to be a worthwhile ability?

Change one or a small number of parameters at a time and retain versioned before/after runs. A Blue tiebreak is a provisional balance mechanism, not evidence that the sides are fair.

### 17.2 Communication capacity

The complaint language deliberately leaves meanings open. The report language has clearer semantics but permits lies. Keep both until play reveals which one carries useful information.

Large quantity fields and combinations of statements can also become signaling channels. Record emergent conventions rather than assuming all communication retains its intended ordinary meaning. Before formal evaluation, declare transport integer limits and any message-size limits consistently across humans and agents; do not silently truncate large claims or allow arbitrary payloads outside the grammar.

If the missing source in theft reports materially prevents useful reasoning, test an explicit source field as a separately versioned extension. If compulsory reports become rote repetition of pledges, test order or capacity changes rather than automatically adding free-form chat.

### 17.3 Novelty beyond the starting catalogue

Eight fixed abilities will eventually become familiar. Hidden assignment of known abilities is still deduction, but it no longer tests acquisition of those rules from scratch.

A later content pipeline could author new abilities by varying a small number of meaningful components:

- Trigger: selected, not selected, a contribution threshold, a previous public event.
- Condition: pure color, mixed colors, particular mission state, limited personal history.
- Effect: add, transfer, recolor, reveal, or change a private objective.
- Scope and limit: actor, crew, mission, once per game, once per attempt.

This is a designer mechanism for creating and validating held-out content, not a complete public role grammar to hand to players. Each proposed rule needs legality checks, token accounting, example traces, and evidence that humans can infer something useful about it. More combinations alone do not guarantee better reasoning tasks.

Use truly different held-out triggers or mechanisms where the scientific question requires novelty. Merely renaming Echo or changing an assignment seed does not accomplish that.

### 17.4 Uncapped scores and invention

The current game produces bounded individual outcomes and at most five completed missions. It primarily tests discovery, application, resource allocation, and coordination. It does not explicitly require inventing a new machine or mechanism.

If an uncapped evaluation remains an organizational requirement, treat it as a separate layer to investigate after the prototype works. Possible directions include progression through an extendable sequence of new rule families, or a separately reported competitive rating. A rating can move beyond a fixed numerical ceiling but remains relative to its comparison population; an extendable curriculum still needs content validation and a fixed evaluation budget.

Do not create an apparently uncapped score by rewarding endless attempts, raw transcript length, or accumulated easy wins. Maintain frozen reference versions for comparisons even if new content is added over time.

### 17.5 Scope to defer

Defer these until the first hypothesis test justifies them:

- More than two teams or additional token colors.
- Free-form voice/text negotiation.
- Learned human “ghosts” and extensive imitation training.
- Large-scale multi-agent self-play or evolving opponent leagues.
- Public leaderboards and automated benchmark submission infrastructure.
- Complex graphics, animation, mobile polish, or real-time networking.
- General-purpose rule invention or open-ended role generation.

## 18. Instructions to give an implementation agent

The following can be used as the starting implementation request alongside this document:

> Build the version 0.1 Hidden Rules Mission Game specified in this document. Treat agreed rules as fixed and use the labelled implementation defaults for unresolved details. Preserve the separation between public rules, each player's truthful private cards, player claims, and authoritative hidden state.
>
> Implement milestones 1 through 6 in order: deterministic engine, all nine objectives and eight abilities, structured communication and strict observations, responsive scripted opponents, persistence/async operation, and a minimal human interface. Produce a working slice and verify it before expanding. Do not substitute a different game or silently simplify a rule in the default mode.
>
> Use Python for the core. Keep game logic out of the UI and model prompts. Implement the proposed action interface so humans, bots, and model adapters make the same legal choices. No external model service or learned opponent is required to run the prototype. Optional provider integration must remain separate.
>
> Give every bot only its seat's observation and its own memory. Keep personality independent of role and team. Implement objective-aware behavior, including Contrarian and objective swaps, and add evidence tracking without treating every unexplained result as a lie. Label any catalogue-informed reference policies explicitly.
>
> Implement focused rule, interaction, privacy, and replay tests from Section 15. Run seeded complete-game simulations and report failures, unresolved runs, and basic game-health statistics. Do not claim that simulations establish balance, human superiority, or benchmark validity.
>
> Deliver source code, a README with exact setup/play/simulate/replay commands, public player instructions, private-card generation, documented JSON contracts, versioned configuration, a small scenario set, and an example replay. Clearly separate developer inspection from player views. Finish with the known limitations and the next experiment needed to test rule acquisition.

### Definition of the first prototype being complete

- A human can play one seat against seven responsive computer opponents from setup to a correctly scored finish.
- All agreed mechanics and the new Contrarian objective work under the documented defaults.
- A JSON-speaking agent can replace the human without changing the rules or information available.
- A game can pause and resume without changing its state, randomness, or hidden commitments.
- A designer can replay and diagnose decisions without exposing that information during play.
- The required tests pass and simulation outcomes are summarized with unresolved runs included.
- At least one authored scenario demonstrates how an unfamiliar rule could be inferred and then used, with competing explanations and limitations documented.

Completing this prototype makes the design testable. Establishing it as a useful reasoning benchmark is the separate experimental milestone described in Section 16.
