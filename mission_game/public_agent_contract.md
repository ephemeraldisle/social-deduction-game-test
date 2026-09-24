# Public JSON action contract

The observation's action_spec identifies your available action and its limits.
All token vectors contain exactly blue, red, green: nonnegative integers whose
sum does not exceed max_total. Player IDs are p0 through p7. Unknown fields are
invalid. The transport fills request_id and revision outside the action object.

- Select crew: {"type":"select_crew","crew":["p0","p2"]}. Supply exactly
  crew_size distinct IDs.
- Pledge: {"type":"pledge","quantity":2}.
  Quantity is a nonnegative integer at most max_total; the promise is assumed Blue.
- Vote Yes: {"type":"vote","approve":true,"influence":0,"complaints":[]}.
- Vote No: {"type":"vote","approve":false,"influence":3,"complaints":[{"modifier":"less","player_id":"p2"}]}.
  Exactly one complaint is required. Optional modifier is more, less, or exact;
  include a player_id and/or color (blue, red, green). No quantity field.
- Deposit: {"type":"contribute","tokens":{"blue":2,"red":0,"green":0}}.
  Only ordinary crew may pay with this vector; off-crew max_total is zero.
- Report: {"type":"report","statements":[{"player_id":"p0","verb":"gave","quantity":2,"color":"blue"}]}.
  Supply 1–3 statements; verb is gave or took. Quantity is an integer from 0
  through 2147483647. These refer to this attempt and may be false. Only crew
  reports. There is no past-attempt or free-text field.
- Preparation: {"type":"prepare","ability":null} to pass, or
  {"type":"prepare","ability":{"target":"p2"}} when action_spec.ability
  allows a target. Follow the truthful text of your own ability.
- Audit: {"type":"audit","ability":null} to pass, or
  {"type":"audit","ability":{"target":"p2"}} for an allowed crew target.
  Choose after the crew's reports have been revealed.

Deposits may also include an optional ability field. Null or omission passes.
Use only a shape currently allowed by your own action_spec.ability and card:

- Stowaway: {"color":"blue"} for the separate one-token off-crew payment.
- Thief, wallet: {"source":"wallet","target":"p2","amount":3}.
- Thief, mission: {"source":"mission","tokens":{"blue":0,"red":2,"green":1}}.
- Recolorer: {"from":"red","to":"blue"}.

Echo, Standard Bearer, and Green Thumb are automatic, with no activation payload.
The engine fills unavailable cover actions; answer only explicit requests.
A mission_checkpoint observation is for a prediction only, after any
reports and inspections, and before the next mission's decisions are shown.
The final attempt skips inspections and reports. At game_over,
public.result.players maps every player ID to their personal won outcome;
wallet balances remain private.

Wallets are private: only private.wallet contains your balance. Public player
records and history never contain wallet balances. Vote influence is an optional
nonnegative integer (default 0), at most action_spec.max_influence, spent immediately.
Green Thumb adds action_spec.vote_bonus (5) automatically. Do not put a bonus
field in your action. Public vote records include bonus influence separately
from paid influence. public.vote_tally gives each side’s ballots, weighted votes,
remainder tokens, spent tokens, and bonus influence. Both spent and bonus
influence affect the tally. Whole votes compare first, then remainders; a full tie rejects.
public.reserve is pending Green funding; public.reserve_credit is the fractional
credit in tenths. Reserves join the pot at attempt resolution, before abilities
and scoring. Vote spending earns 10% Green with fractional credit carried forward.
Free bonus influence does not create reserves.

Everyone receives public.rules.proposal_income after a crew is selected and
before pledging. That income is already included in private.wallet during
pledge, vote, and contribute. No extra income arrives at the end of voting.

public.token_totals and each attempt_resolved event's token_totals contain
paid (a Blue/Red/Green vector of cumulative original paid deposits) and
green_added (all cumulative Green additions, including reserves and bonuses).
These include only resolved attempts, never current sealed payments or player
identities. Opposition Patron and Green Machine show exact table-wide progress
in private.objective.progress.value, with target 20 and condition_met. The
own_paid field remains a separate count of your personal paid deposits.
