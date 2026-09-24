# Hidden Rules Mission Game — development table

New development tables deal **private personal objectives and hidden abilities**.
Contrarian is disabled in new tables. Eight of the nine abilities are dealt,
without duplicates; one is left out at random. Read your own ability for its exact rules.
Outdated saves are not compatible; start a fresh table for these rules. Read your own card to learn your win condition. The common-rules
comparison mode uses Loyalist objectives. Computer seats use scripted policies. Their decisions can be imperfect.
Each computer player has access only to its own cards and the evidence visible
to its seat. Reports and pledges remain claims regardless of who makes them.

There are eight seats, p0 through p7, in clockwise order. Each player secretly
belongs to Blue or Red. There are always **five Blue players and three Red
players**. You know your own team; you do not automatically know your teammates.
Official allegiance badges and private results are truthful. Your team must win
four missions and your objective may require an additional condition. Read your
own card; another player's allegiance alone does not tell you what outcome they
want on the current mission. Your
private progress display includes only information you are permitted to know.
Unknown progress is not a failure, and a condition met now can change before
the finish.

Green Machine requires your team to win and at least 20 Green tokens to have
been added to missions across the whole table and game. All sources count:
ordinary and Stowaway deposits, Green reserves, Echo bonuses, and tokens
recolored into Green. Later theft or recoloring away from Green does not erase
prior additions. Its objective card tracks the table-wide total out of 20.
Opposition Patron tracks all players' original paid deposits of your opposing
color, also out of 20; bonuses, penalties, and recoloring do not count for that
goal. Both totals update after each resolved attempt and remain available in
history. Individual deposits remain private; reports are still claims.

Each player starts with five uncolored wallet tokens. Wallet balances are private: you can see only your own.
You choose a color when spending a token: Blue, Red, or Green, regardless of your
team. You cannot spend more than your current wallet.

A mission's token threshold and number of distinct crew members are shown on
its card and drawn independently. They stay fixed until completion. Blue and
Red compete for ownership; Green only helps fund it. When the threshold is met,
Blue wins ties with Red. An entirely Green pot stays open until at least one Blue
or Red token remains. A completed mission awards one point. Surplus does not
carry to the next mission.

Before each proposal, any available private preparation choices appear on your
screen. Other players do not see your choices or private results. An objective
change uses the new holder's entire history; teams and wallets remain with their
players. Only your own controls and instructions are shown.

On each proposal, the chairman selects the required crew, possibly including
themself or players with empty wallets. Everyone then receives one wallet token,
before pledging. This happens once per proposed crew, including after a rejection.
Crew members privately pledge affordable
token quantities, assumed to be Blue. All pledges appear together. They are promises, not payment.

All eight players vote, starting with the chairman and continuing clockwise.
Earlier votes and vote spending are visible. You may immediately spend any
number of tokens you currently own on your Yes or No vote. Each side pools its
spending: every 10 tokens add one vote to that side, and the remainder breaks a
tie in whole votes. For example, 4 Yes + 8 tokens beats 4 No + 6 tokens. A complete
tie rejects. The proposal income is already included in your wallet. Every No
vote requires exactly one complaint explaining the objection. Yes votes cannot
include complaints. A complaint has an optional "more", "less", or "exact",
plus a player and/or color. For example:
"less p2", "more green", "exact p3 blue". These expressions have no certified
meaning. "Exact" does not take a quantity.

Green Thumb automatically adds 5 free influence to every Yes or No vote its
holder casts. It combines with paid influence for extra votes and tiebreakers,
including when the holder spends zero. The bonus is shown on the ballot;
it does not cost wallet tokens or generate Green reserves.

Ten percent of all vote spending becomes a Green reserve. Fractional credit
carries across ballots, rejected proposals, attempts, and missions, so every 10
spent tokens produce one Green token. Reserves do not count toward the pot until
an attempt resolves, including an eight-rejection penalty attempt. They enter
before hidden effects and scoring, then the reserve clears. Spending is never
refunded, even when the proposal fails.

There is no additional income after voting. Tokens spent on your ballot reduce
the wallet available for your mission payment. The usual end-of-attempt income
is separate from the token received before pledging.

After rejection the next seat becomes chairman. Rejected proposals spend no
pledged tokens. After eight rejections in one attempt, five Red
tokens are added to the mission. This is a deposit, not an automatic Red point.

After approval, crew members privately deposit any affordable vector, including
zero. Deposits may differ from pledges. Nobody sees another submission before
committing. The final pot is an official public result;
individual contribution quantities, colors, and wallet balances stay private. Available hidden ability choices
are committed with the same pre-result information, including off-crew choices.
All-rejected attempts may also have hidden effects. The order is Green reserves and paid deposits
(or the penalty), bonuses, transfers, color changes, then scoring. Matching
effects resolve clockwise from the last proposer; preparation starts with its
chairman. A threshold crossing before the final modifications does not lock in a
win. Wallet changes and pot changes need not equal original contributions.

If the game continues after the public result, crew reports are revealed first,
then any available private inspections occur. Auditors choose whom to inspect
after seeing everyone's claims.
Private results reveal only what your card promises. The game never certifies a
player's report merely because they received private information.

After resolution, only crew members report, with one to three statements each.
Their reports appear together. Off-crew players do not report. Eight-rejection
penalty attempts skip reporting entirely. Use a player,
"gave" or "took", a nonnegative integer, and a color: "p0 gave 2 blue". Reports
may be false, may name anyone, and are never certified by the engine. Quantities
must be at most 2,147,483,647. "Gave" means an original paid deposit; "took" means
a removal from the mission. Reports cannot describe uncolored wallet transfers.

After reports and any inspections, everyone receives one wallet token. The
next chairman is the seat after the attempt's last proposer. The pot persists
when the mission is incomplete. After eight rejections the chairman rotation
wraps back to the attempt's starting seat.

The game freezes when a team wins its fourth mission, before further income.
Your current objective is evaluated then, using your terminal wallet and your
whole history where required. A team victory need not be a personal victory.
The final attempt goes straight to the game results, without inspections, reports,
or income. The team winner and every player's personal win/loss outcome are public;
wallets remain private. A development guard ends an unfinished run after the configured number
of resolved attempts (normally 100), also without inspections, reports, or income. That run
is UNRESOLVED, with no winners. Victory on the final permitted attempt takes
precedence. There is no free-form table chat.

Web controls: click a player to expand their public action and vote history, grouped
by Mission and Attempt with results, token changes, and links to the full record;
use Add to crew / Remove from crew when proposing a crew. Enter the number of
seconds between steps (decimals allowed; zero for manual), pause automatic play,
or advance with Next step. Your delay is remembered in this browser.
Automatic play waits for your decision and pauses when you open a player history.
The last-step panel explains the latest visible choice or result. Vote histories
include the chairman and full proposed crew. The result shows each color’s before/after amount and change for this attempt.
Only your own wallet is visible. Expand Compare mission tokens to select an earlier pot and
see each color’s exact change; it starts collapsed.

Your objective and ability show short reminders. Expand their carets for the
full rules and permitted objective progress. Private results are available in
their own collapsed section. Once-per-game availability remains visible.

Use the quantity counter to pledge, or color counters for secret deposits; choose Yes or No before casting a vote. Choosing No opens a
required complaint builder, prefilled with your last submitted No objection.
An optional token-spending field strengthens either vote. Complaints appear on voter cards, and the previous
proposal’s objections remain visible as the next proposal begins. Crew reports
have dropdown builders. Ability controls let you pass or select a legal target,
color, source, or amount. Once-per-game availability and private results appear
with your card. Ineligible private choices are handled during the next step.
Your game saves after each decision. Return
to the game library to resume it later. "Review so far" opens a read-only replay
with previous/next buttons, a position slider, and a clickable decision list.
Finished-game replays offer other seat perspectives and a Reveal all option.
Reveal all shows objectives and abilities on every player card. Click a card to
switch perspective at the same replay moment, or use its History button to read
the player’s record. Revealed information is separate from play. The public history can be filtered to official results or claims.

Terminal controls: enter seat numbers to select a crew; a single pledge quantity;
three quantities in Blue Red Green order for deposits; yes/no and token spending to vote; semicolon-separated
complaints or reports when prompted. Ability prompts offer pass/use and guided choices. Use /history for the public record, or
/save or /quit to save and leave. A resumed session preserves private commitments.
