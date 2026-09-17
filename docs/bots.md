> September 11 update: New games enable all eight abilities and exclude Contrarian.
> New defaults pay everyone after each full vote and require four mission wins.
> The default `social.12` policy jointly plans payments and abilities, uses confirmed
> allegiances in crew choices, and gives Blue pledges no allegiance or trust credit.
> It values private inspections and retains tentative hypotheses about recurring effects.
> Red players also price public exposure and spending that reduces future reserves.
> Existing `social.7`/`social.8`/`social.9`/`social.10`/`social.11` saves keep their previous decision algorithm.
> The detailed abilities-off accounting model below remains a comparison baseline.
> See [ability behavior and limitations](abilities.md) for the active extension.

# Scripted computer players

The historical `social.7` baseline uses per-seat evidence, personality,
vote forecasts, and the holder's private objective to choose actions. The
`straightforward.2` and `random-legal.2` policies remain available as
baselines. Old development saves are not migrated across rules updates.

## Personality and objectives

Each Social bot draws three stable traits from a separate seeded stream:

- **Self-interest:** preference for including itself in a crew; high values
  produce an early No vote with **More me** when excluded. The protest relaxes
  after five rejections or a forecast game-ending result. Higher values also
  reduce the cost assigned to breaking a pledge.
- **Risk caution:** discounts a risky plan according to its possible downside.
  This trait does not set a spending penalty. In the current abilities profile,
  Red continuation planning separately values reserves for later missions.
- **Skepticism:** how strongly it discounts promises and unverified reports.

Traits are independent of allegiance and objective. A demanding player is not
automatically treated as Red. Other bots infer inclusion demands from public
protests and willingness to approve crews that exclude the voter; they cannot
read each other's traits.

The policy plans its own affordable contribution for each proposed crew, then
ranks the crew using that plan and expected votes. It no longer assumes every
objective will pay a generic funding share. Before promises are revealed, it
estimates whether the remaining crew can afford to cover the remaining funding
after its own planned deposit. Revealed promises then replace that assumption.

| Objective | Behavior before the finish |
| --- | --- |
| Loyalist | Fund and steer missions toward the desired side. |
| Saver | Strongly protect a ten-token reserve, promise/pay zero while saving, and spend surplus. Prefer crews that can fund missions without consuming that reserve. |
| Spendthrift | Seek inclusion whenever holding money, even with low selfishness, and strongly favor spending it. Stop demanding a seat for this objective when empty. |
| Exact Change | Save below seven; seek access to spending at/above seven. Compare reaching seven immediately with reaching six before continuing income. |
| Reliable Partner | Seek affordable crew opportunities until two qualifying attempts; promise at least two and value exact fulfillment, including honest Blue payments when seeking Red. Stop the special inclusion demand after qualifying. |
| Passenger | Seek crews whose other members can finish the mission while paying zero. Protest exclusion when replacing a member could plausibly allow a free ride. Either color's mission can qualify. Resume ordinary funding after qualifying. |
| Opposition Patron | Prefer crews and payments that advance the table-wide opposing-color total, including mixed deposits that preserve the desired mission winner. Stop rewarding additional opposing deposits at twenty. |
| Close Race | Initially help the own side; once it has a point, favor the opponent until it reaches two. Then return to the own side and avoid an opposing third point. |
| Contrarian | Only Blue players can hold it; pursue Red's eventual victory, using the same planning machinery as Loyalist. |

Spendthrift, Exact Change, Reliable Partner, and Passenger can say **More me**
because of their objective as well as their personality. Objective inclusion
protests relax after five rejections and never block a forecast personal win.
A risky crew can still be worth accepting when it advances the private condition;
the objective-aware outcome score decides whether the tradeoff is worthwhile.

Passenger considers both the discounted forecast and the possibility that the
remaining members honor sufficient promises. The latter is discounted by their
pledge reliability, so a nearly funded crew is an opportunity rather than an
automatic failure; repeatedly unreliable members provide much less support.
This is a heuristic estimate, not a calibrated completion probability.

Terminal scoring takes priority: all ordinary objectives still require the own
side to win, and wallets are checked before income. For example, Exact Change at
six cannot approve a game-ending result on the assumption it will receive a
seventh token. A continuing attempt at seven often calls for spending one to
remain at seven after income. Ordinary rejected proposals produce no income.
Opposition Patron infers paid totals only from available pot/accounting evidence;
penalties never advance that counter. These are plans for the current attempt
and its income, not multi-turn search or a guarantee of achieving the objective.

### Contrarian's historical design role (disabled in new deals)

Games now always have five Blue and three Red allegiances. Contrarian can only
belong to Blue, so its presence adds a secret fourth player who ultimately wants
Red to win. It remains optional: draw eight cards from the same deck, then move
a Contrarian drawn for a Red seat to a uniformly selected Blue seat by swapping
their cards. This preserves the drawn card set and the default 8/14 chance of
including Contrarian. It does not change actual allegiance. The deal and presence
remain private; no Red player learns the identities of allies or the Contrarian.

In the ability-free game the card adds no separate resource or timing puzzle.
Its current distinction is this hidden change in winning preferences. Future
objective swaps must also preserve Blue-only eligibility.

## What the bots learn

`mission_game/beliefs.py` keeps four separate estimates for each player:

| Estimate | Evidence |
| --- | --- |
| Blue preference | Deducible paid colors; weaker pledge/vote signals; bounded crew associations and attributed reports |
| Pledge reliability | Own receipts, public wallet changes and color bounds; weaker evidence from ambiguous crew totals |
| Report credibility | Claims corroborated or contradicted by independently available evidence |
| Inclusion demand | “More me” protests and approval while excluded |

Starting assumptions use the fixed public counts and exclude the bot's own
known allegiance: 4/7 of the other seats are Blue for a Blue bot, and 5/7 for a
Red bot. These are starting allegiance priors; the exact objective deck and
Contrarian's presence are not available to controllers. Blue preference then
describes observed desired outcomes,
not a certified allegiance: objectives can make a Blue player favor Red.

Contribution analysis subtracts the existing pot and uses actual wallet changes.
It subtracts the bot's own receipt when available. If the remaining colors can
be assigned in several ways, responsibility stays uncertain. Matching aggregate
pledges does not certify each individual's honesty. A rejection penalty is not
blamed on the previous crew or counted as a paid deposit.

Directly deducible colors carry more weight than promises or association.
Supporting a crew with poor cooperation evidence has a small negative effect;
supporting a crew with good evidence has a small positive effect. Association is
limited to once per actor per attempt, capped, and cannot recursively propagate
through other association judgments. Later truthful behavior can recover trust.

A report from a reliable speaker gets more weight, but remains an attributed
claim. Unverified claims never become known contribution vectors. Reports are
not weighted simply by whether the speaker appears Blue. The bots themselves
report their own deposits truthfully unless maintaining Red cover or concealing
an actual Red payment, including one made for a temporary objective. Off-crew seats never
receive report requests, and penalty attempts skip reports.

## How evidence changes actions

`mission_game/social_policy.py` ranks legal crews using expected contributions,
likely votes, personal objectives, and inclusion preference. It scores a bounded
set of affordable pledges/deposits, including zero, funding shares, color swings,
wallet targets before/after income, mixed counter-funding plans, and the exact
original pledge. Its own vote evaluates its planned actual deposit for every
objective; public promises and private contributions remain separate.

Forecasts enumerate possible integer deposits: honor the promise, pay zero, or
redirect its total to Blue or Red. If `r` is pledge reliability discounted by
skepticism and `b` is estimated Blue preference, those cases have weights `r`,
`0.3(1-r)`, `0.7(1-r)b`, and `0.7(1-r)(1-b)`. Identical outcomes are merged.
Before promises are available, an affordable funding share is split between
all-Blue and all-Red possibilities according to `b`. The bot's own plan is exact.

Each resulting pot is scored separately using actual funding, Blue's tie rule,
terminal wallet checks, and continuing income. The weighted mean score replaces
scoring a fractional average pot as a certain outcome. Risk caution subtracts
up to 10% of the expected downside below that mean; it does not penalize paying.
Among equally valuable plans, prefer the stronger tactical color margin, then
less Green, before seeded tie breaking. Personal conditions still take priority,
so Patron and Close Race retain opposing-color plans when useful.

Retained tokens have no generic utility. Saver and Exact Change explicitly value
their required balances; other objectives and keeping a public promise can also
justify paying less. There is no speculative reward for a future spending
opportunity that the current short-horizon planner does not actually evaluate.

Vote forecasts combine possible outcomes with observed inclusion demands;
already-public votes are fixed. Crew and pledge scores use the estimated chance
of receiving five Yes votes. A bot's own vote compares acceptance with rejection,
including the actual five-Red penalty at the rejection limit. Blue-seeking bots
also reject likely Red supporters even when those players have kept their
promises. This risk objection relaxes after five rejections or when the private
forecast completes a beneficial Blue mission. It never targets the bot itself.

Both sides choose from the same complaint rules on No:

- **More me** for an active exclusion protest, including Red players.
- **Less [player]** for observed Red support, unreliable promises, a public Red
  pledge, or a small Blue pledge relative to this mission's funding share.
- **More Blue** for stronger funding.

Concerns are scored against each other and the funding request; seeded tie
breaking chooses among equally ranked explanations. A complaint describes a
public objection, which may conceal the voter's real objective. Every No supplies
exactly one complaint, and Yes votes have none. No Social bot requests More Red
or Less Blue. Those remain legal options for human players.

## Concealment and accusations

In `social.12` abilities games, Red contribution plans include a continuation
value as well as the immediate mission and personal-objective values. A small
Blue payment can build cover when the public result also looks helpful. This
benefit diminishes after previous helpful funding. Large Red payments on a
Red-heavy result carry an exposure cost, and spending has an opportunity cost
while missions remain. Thus bots can decline an uncertain early sabotage,
retain cash, or let others fund a point that is already secured.

The public-cover estimate uses only public mission totals, wallet changes,
crew membership, and badges. Own receipts and private inspections do not become
assumptions about what opponents know. Wallet changes have an allowance for
hidden effects, and the estimate is a heuristic rather than proof of allegiance.
Unverified Blue reports and pledges do not rebuild cover. A public Red badge
eliminates the value of maintaining Blue cover.

The continuation weights diminish as either side approaches victory. They are
zero for terminal outcomes, which still use the bot's personal win condition.
The ordinary cost of breaking a cover pledge is bounded for these Red bots and
shrinks with public exposure; it cannot force them to empty their wallet into a
Blue mission merely to honor a lie. Reliable Partner and other actual objective
conditions retain their separate scoring. Designer metadata records the
`red_strategy` breakdown: cover value, exposure cost, reserve cost, and the
public evidence context. These values are not calibrated probabilities or a
model of an optimal opponent. Blue policy behavior and saved older policies
are unchanged by this continuation layer.

Bots seeking a Red win or pursuing a temporary Red goal use Blue cover promises.
This includes Blue Close Race while it needs Red to reach two points, and Blue
Opposition Patron while it needs more opposing-color spending. Any other
candidate Red pledge is also presented as a Blue promise. Pledge scoring separates the
public promise, used to estimate majority support, from a private spending plan.
Contribution choices still pursue the personal objective: they may pay Red,
honor a Blue pledge for Reliable Partner, or spend nothing for a wallet goal.
Their votes consider their own planned deposit rather than blindly believing
their own cover story. Crew selection also evaluates the public appearance of
the bot's proposed contribution separately from its intended color.

When tactically seeking Red, these bots reject crews containing likely Blue
supporters unless their private forecast completes a beneficial Red mission.
Their complaints follow the shared rules above. Among plausible targets they
give a small preference to removing a likely Blue supporter; a cooperative
history alone is no longer an excuse to accuse someone. Real teams are never inspected.
Crew reports claim the bot's actual total spending was Blue, maintaining cover
without inventing a publicly impossible spending total. The colors can still be
contradicted by public accounting or another crewmate's receipt.

The desired winning side and current objective both control this strategy: a
Blue Contrarian uses it; Red Contrarian is no longer a legal assignment. Close Race can temporarily
favor the opposite side without abandoning its eventual win condition. Reports
continue to cover a Red payment even if that mission just satisfied the
temporary goal. These exceptions preserve personal objectives.

All Social bots interpret **Less [player]** as an attributed accusation. An
accuser needs corroborated pledge fulfillment and strong observed Blue/honesty
evidence to earn trust. That speaker's accusation has more influence on the
target and adds no suspicion merely for speaking up. An unproven or suspect
accuser has less influence and can draw suspicion for potentially diverting blame.
However, an objection supported by the observer's existing contribution evidence
or the target's current Red/undersized Blue pledge adds no suspicion merely for
speaking up, even for a new accuser. Grounding does not increase the accusation's
weight or duplicate the underlying accounting evidence.
This interpretation replaces the generic No-vote preference signal, avoiding a
second automatic penalty on trusted accusers.

Accusations shift inferred Blue preference, not verified contribution vectors
or pledge-keeping counts. They affect later crew rankings and vote forecasts;
someone who has attracted suspicion also has less influence when accusing
another player. The same speaker/target pair counts once per attempt. Combined
hearsay evidence is capped, and positive cooperation evidence is required for
trusted status, so repeating accusations cannot manufacture proof or trust.
A bot never treats its own accusation as new evidence for its private beliefs.

Designer explanations record the accusation's source and weight, plus separate
private and public-promise forecasts for concealment. Tune `accusation_weight`
and `blue_reject_threshold` / `red_reject_threshold` in the policy config. Straightforward remains an
explicitly honest comparison baseline.

Authored paired scenarios verify that the same proposed Blue crew gets Yes
without adverse history, but No after repeatedly breaking Blue promises by
paying Red; subsequent crew selection avoids those members when wallets are
equal. Another pair changes only selfishness and produces Yes versus **More me**.

## Inspecting and tuning

After a game ends, enable **Designer view**, select a bot action, and read
**Why this bot acted**. The panel shows traits, expected pot, estimated mission
and personal outcome chances, estimated approval,
separate player estimates, and expandable attributed evidence. **Forecast and
policy limits** retains the full saved diagnostics and candidate alternatives.
Live play and ordinary seat replay do not receive this information. Saved
explanations also state the current objective plan, planned balance before
income, expected income, and the likelihood that the personal condition is ready
before income. The saved details include the weighted integer pots and risk
adjustment. This makes reserve protection, inclusion demands, and spending targets
inspectable in the same replay panel.

Tune weights and the protest threshold in `configs/policy_social.json`:

```bash
python3 -m mission_game.cli web --policy social --policy-config configs/policy_social.json
python3 -m mission_game.cli simulate --policy social \
  --policy-config configs/policy_social.json \
  --games 100 --seed 20260910 --out runs/social-smoke
python3 -m mission_game.cli simulate --policy straightforward \
  --games 100 --seed 20260910 --out runs/straightforward-comparison
```

The file controls scoring weights, report/association influence, and protest
threshold/relaxation. Lower-level evidence increments and candidate generation
currently live in Python. Trait values are sampled per seat, not set by this
file. Rules and policy configuration are separate. Saved sessions retain their
exact settings, traits, beliefs, evidence cursor, and decision RNG. Simulation
artifacts record the policy version and resolved settings. Start a new table
after restarting the server to use new settings.

Simulation summaries include `by_contrarian` results for games with and without
the card. With fixed teams, that split distinguishes four versus five players
whose objectives ultimately require Blue to win. The diagnostic presence flag
is never included in an ordinary player observation or live web table.

## Boundaries and follow-up

These estimates are uncalibrated. Payments and votes are treated as independent, private
objectives of other players are unknown, and the strategy has no multi-turn
search or a separate model of each other player's beliefs. Payment scenarios
omit partial fulfillment and spending above a revealed promise; they quantify
some uncertainty without covering every legal plan. Inclusion protests still
use a short-horizon completion heuristic. Concealment is a
scripted strategy and can become implausible as evidence accumulates. The next
tuning work should use paired scenarios, mixed opponents, and actual human play;
self-play completion alone does not demonstrate difficulty or balance.

The accounting model explicitly accepts only the current ability-free profiles.
Abilities will require revisiting the inference rules before enabling this
policy for them. Controllers receive only their own observation, never a game
object, hidden cards, sealed actions, or another controller. Memory is bound to
one game and seat. Replay executes recorded actions without invoking policies;
saved explanations are estimates, while engine outcomes are verified.

The Straightforward baseline still chooses the richest crews, pledges an
affordable desired-color funding share, trusts revealed pledges, votes for its
desired side, honors its own pledge, and reports its own receipt. Apart from
Contrarian it ignores personal conditions, trust, and rejection pressure. The
random baseline continues to sample legal actions without strategic reasoning.
