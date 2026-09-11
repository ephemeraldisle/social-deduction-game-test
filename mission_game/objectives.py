"""Designer objective catalogue, private card projection, and victory predicates.

Progress derives from original paid history attached to seats. It is never
stored on the card, so receiving a card later uses the holder's entire history.
"""

from .types import ObjectiveCard

NAMES = {
    "loyalist": "Loyalist", "saver": "Saver", "spendthrift": "Spendthrift",
    "exact_change": "Exact Change", "opposition_patron": "Opposition Patron",
    "close_race": "Close Race", "reliable_partner": "Reliable Partner",
    "passenger": "Passenger", "contrarian": "Contrarian",
}


def opposing(team):
    return "red" if team == "blue" else "blue"


def deal(deck, rng, teams):
    """Draw without replacement, then give any Contrarian to a Blue seat.

    Relocate a Red recipient's card by a random Blue-seat swap. The drawn
    cards (and thus the chance of including Contrarian) stay unchanged, and
    all Blue seats have the same chance to receive it.
    """
    cards = [ObjectiveCard(f"objective-{i}", kind) for i, kind in enumerate(deck)]
    rng.shuffle(cards)
    cards = cards[:len(teams)]
    for seat, card in enumerate(cards):
        if card.kind == "contrarian" and teams[seat] != "blue":
            eligible = [i for i, team in enumerate(teams) if team == "blue"]
            if not eligible:
                raise ValueError("Contrarian requires a Blue player")
            recipient = rng.choice(eligible)
            cards[seat], cards[recipient] = cards[recipient], cards[seat]
            break
    return cards


def paid_deposits(history, color, player_id=None):
    """Gross original paid deposits, including future off-crew paid actions.

    Penalties/bonuses/recoloring are absent from original_contributions. Later
    transfers never rewrite these records; paying a recovered token again counts.
    """
    return sum(vector[color] for record in history
               for pid, vector in record["original_contributions"].items()
               if player_id is None or pid == player_id)


def reliable_attempts(history, player_id):
    count = 0
    for record in history:
        if record["penalty"] or player_id not in record["crew"]:
            continue
        original = record["original_contributions"][player_id]
        if sum(original.values()) >= 2 and original == record["pledges"][player_id]:
            count += 1
    return count


def passenger_attempts(history, player_id):
    return sum(not r["penalty"] and player_id in r["crew"] and r["mission"]["winner"] is not None
               and sum(r["original_contributions"][player_id].values()) == 0 for r in history)


def condition_satisfied(player, score, history, winner, missions_to_win=3):
    kind = player.objective.kind
    if kind == "loyalist":
        return True
    if kind == "saver":
        return player.wallet >= 10
    if kind == "spendthrift":
        return player.wallet == 0
    if kind == "exact_change":
        return player.wallet == 7
    if kind == "opposition_patron":
        return paid_deposits(history, opposing(player.team)) >= 20
    if kind == "close_race":
        return score[opposing(player.team)] == missions_to_win - 1
    if kind == "reliable_partner":
        return reliable_attempts(history, player.id) >= 2
    if kind == "passenger":
        return passenger_attempts(history, player.id) >= 1
    if kind == "contrarian":
        return winner is not None and winner != player.team
    raise ValueError("Unknown objective type")


def wins(player, score, history, winner, missions_to_win=3):
    if winner is None:
        return False
    condition = condition_satisfied(player, score, history, winner, missions_to_win)
    return condition and (player.objective.kind == "contrarian" or winner == player.team)


def result_text(player, winner, won):
    """Explain the player's result without disclosing hidden global counters."""
    if winner is None:
        return "The game is unresolved. No player wins, regardless of objective progress."
    if player.objective.kind == "contrarian":
        return ("Your team lost, fulfilling Contrarian. You won."
                if won else "Your team won, so Contrarian was not fulfilled. You did not win.")
    if winner != player.team:
        return "Your team lost. This objective requires your team to win."
    if won:
        return "Your team won and your personal condition was satisfied. You won."
    return "Your team won, but your personal condition was not satisfied. You did not win."


def private_card(player, score, history, missions_to_win=3):
    """Only this holder's truthful instructions and permitted progress."""
    kind = player.objective.kind
    own, other = player.team.title(), opposing(player.team).title()
    target = missions_to_win - 1
    number = "four" if missions_to_win == 4 else "three"
    ordinal = "fourth" if missions_to_win == 4 else "third"
    conditions = {
        "loyalist": f"Win if {own} wins {number} missions. You have no additional personal condition.",
        "saver": f"Win if {own} wins {number} missions and you finish with at least 10 wallet tokens.",
        "spendthrift": f"Win if {own} wins {number} missions and you finish with exactly 0 wallet tokens.",
        "exact_change": f"Win if {own} wins {number} missions and you finish with exactly 7 wallet tokens.",
        "opposition_patron": (f"Win if {own} wins {number} missions and at least 20 originally paid {other} tokens "
                              "were deposited by all players combined across the whole game. Bonuses, penalties, "
                              "and recoloring do not count. Later theft does not erase deposits; paying a recovered "
                              "token again counts again. The exact global total is hidden."),
        "close_race": f"Win if {own} wins its {ordinal} mission when {other} has exactly {target} mission wins: a {missions_to_win}–{target} finish.",
        "reliable_partner": (f"Win if {own} wins {number} missions and on at least 2 approved attempts your original "
                             "contribution exactly matched your pledge in all three colors and totaled at least "
                             "2 tokens. Two attempts on the same mission count. Later modifications do not matter."),
        "passenger": (f"Win if {own} wins {number} missions and on at least 1 approved attempt that completed a "
                      "mission you were on the crew and originally contributed 0 tokens. Either team's mission "
                      "win can qualify; the zero deposit must occur on the completing attempt itself."),
        "contrarian": (f"Win only if your own team, {own}, loses the game to {other}. This replaces the normal "
                       f"team-win requirement. Your allegiance stays {own}; an unresolved game is not a loss or a win."),
    }
    progress = {"visibility": "private", "value": None, "target": None, "condition_met": None}
    if kind in ("saver", "spendthrift", "exact_change"):
        target = {"saver": 10, "spendthrift": 0, "exact_change": 7}[kind]
        progress.update(label="Wallet balance", value=player.wallet, target=target,
                        condition_met=player.wallet >= target if kind == "saver" else player.wallet == target,
                        text=f"Current wallet: {player.wallet}. Need {'at least' if kind == 'saver' else 'exactly'} {target} at the finish, before further income.")
    elif kind in ("reliable_partner", "passenger"):
        value = reliable_attempts(history, player.id) if kind == "reliable_partner" else passenger_attempts(history, player.id)
        target = 2 if kind == "reliable_partner" else 1
        label = "Kept qualifying pledges" if kind == "reliable_partner" else "Qualifying passenger attempts"
        progress.update(label=label, value=value, target=target, condition_met=value >= target,
                        text=f"{label}: {value} / {target}. Your entire history counts, including before receiving this card.")
    elif kind == "opposition_patron":
        own_paid = paid_deposits(history, opposing(player.team), player.id)
        progress.update(visibility="hidden_global", label="Table-wide paid deposits", target=20,
                        own_paid=own_paid,
                        text=f"Global progress is hidden. Your own paid {other} deposits: {own_paid}. Player reports are claims, not verified progress.")
    elif kind == "close_race":
        value = score[opposing(player.team)]
        progress.update(label=f"{other} mission wins", value=value, target=target, condition_met=value == target,
                        text=f"Required finish: {own} {missions_to_win}, {other} {target}. Current score: {own} {score[player.team]}, {other} {value}.")
    else:
        desired = other if kind == "contrarian" else own
        progress.update(label="Desired winning team", text=f"You need {desired} to win {number} missions.")
    return {"id": kind, "name": NAMES[kind], "text": conditions[kind],
            "desired_winner": opposing(player.team) if kind == "contrarian" else player.team,
            "progress": progress}
