"""Continuation heuristics for Red: public cover and money for later missions.

These are strategy scores, not certified deposit bounds or calibrated beliefs.
In particular, transfers and hidden abilities can obscure public accounting.
"""


def public_cover(observation):
    """Estimate remaining cover from public outcomes, never private receipts."""
    public, me = observation["public"], observation["viewer"]
    exposure, support = 0., 0.
    wallets = {p["id"]: public["rules"].get("starting_wallet", 5) for p in public["players"]}
    pot, crew = {"blue": 0, "red": 0, "green": 0}, []
    noise = 2 if public["rules"].get("abilities_enabled") else 0
    for event in observation["history"]:
        kind = event["type"]
        if kind == "mission_drawn":
            pot = event["mission"]["pot"]
        elif kind == "crew_selected":
            crew = event["crew"]
        elif kind in ("income", "vote_income"):
            wallets = event["wallets"]
        elif kind == "attempt_resolved":
            final = event["mission"]["pot"]
            if me in crew and not event["penalty"]:
                spent = max(0, wallets[me] - event["wallets"][me])
                blue = max(0, final["blue"] - pot["blue"])
                green = max(0, final["green"] - pot["green"])
                red = max(0, final["red"] - pot["red"])
                if spent:
                    # A large wallet loss on a nearly all-Red result is hard
                    # to hide. Allow some accounting noise; do not call it proof.
                    exposure = max(exposure, min(1., max(0., spent - blue - green - noise) / spent))
                    support += min(2, spent) * blue / max(1, blue + red + green)
            pot, wallets = final, event["wallets"]
    if public.get("public_badges", {}).get(me) == "red":
        exposure = 1.
    target = public["rules"]["missions_to_win"]
    return {"public_exposure": exposure, "public_blue_support": support,
            "future_weight": max(0., (target - max(public["score"].values())) / target)}


def continuation(observation, context, case, own, crew, choice):
    """Price a candidate's public signal and lost reserves in a continuing game."""
    public, me = observation["public"], observation["viewer"]
    payment = own if me in crew else {"blue": 0, "red": 0, "green": 0}
    if me not in crew and observation["private"]["ability"]["id"] == "stowaway" and choice:
        payment = {c: int(c == choice["color"]) for c in payment}
    spent = sum(payment.values())
    blue = max(0, case["pot"]["blue"] - public["mission"]["pot"]["blue"])
    red = max(0, case["pot"]["red"] - public["mission"]["pot"]["red"])
    green = max(0, case["pot"]["green"] - public["mission"]["pot"]["green"])
    total = max(1, blue + red + green)
    cover = 1 - context["public_exposure"]
    future = context["future_weight"]
    # Helpful funding earns diminishing cover value, only insofar as the
    # resulting public pot looks helpful too. Repeating a Blue claim earns none.
    cover_value = (6 * future * cover * min(1, payment["blue"] / 2) * blue / total
                   / (1 + .5 * context["public_blue_support"]))
    signal = min(1, payment["red"] / 3) * red / total
    if me in crew and payment["red"]:
        noise = 2 if public["rules"].get("abilities_enabled") else 0
        signal = max(signal, min(1., max(0., spent - blue - green - noise) / max(1, spent)))
    exposure_cost = 9 * future * cover * signal
    reserve_cost = .35 * future * max(0, spent - case["transferred"])
    return {"cover_value": cover_value, "exposure_cost": exposure_cost, "reserve_cost": reserve_cost,
            "continuation_value": cover_value - exposure_cost - reserve_cost}
