# Public JSON action contract

The observation's action_spec identifies your available action and its limits.
All token vectors contain exactly blue, red, green: nonnegative integers whose
sum does not exceed max_total. Player IDs are p0 through p7. Unknown fields are
invalid. The transport fills request_id and revision outside the action object.

- Select crew: {"type":"select_crew","crew":["p0","p2"]}. Supply exactly
  crew_size distinct IDs.
- Pledge: {"type":"pledge","tokens":{"blue":2,"red":0,"green":0}}.
- Vote Yes: {"type":"vote","approve":true,"complaints":[]}.
- Vote No: {"type":"vote","approve":false,"complaints":[{"modifier":"less","player_id":"p2"}]}.
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

Deposits may also include an optional ability field. Null or omission passes.
Use only a shape currently allowed by your own action_spec.ability and card:

- Stowaway: {"color":"blue"} for the separate one-token off-crew payment.
- Thief, wallet: {"source":"wallet","target":"p2","amount":3}.
- Thief, mission: {"source":"mission","tokens":{"blue":0,"red":2,"green":1}}.
- Recolorer: {"from":"red","to":"blue"}.

Echo and Standard Bearer are automatic, with no activation payload.
The engine fills unavailable cover actions; answer only explicit requests.
A mission_checkpoint observation is for a prediction only, after closing
inspections and reports, and before the next mission's decisions are shown.
