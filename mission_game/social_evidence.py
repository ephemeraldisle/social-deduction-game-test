"""Claims and private receipts, reconstructed only from one seat's evidence.

Reports can persuade, but only an original-payment receipt can verify them.
Shared pots, team inspections, and repeated rumors cannot certify a payment.
"""

from collections import defaultdict


def claim_evidence(observation, known, own_deposits=None):
    public, private = observation["public"], observation["private"]
    me = observation["viewer"]
    players = [p["id"] for p in public["players"]]
    names = {p["id"]: p["name"] for p in public["players"]}
    evidence = {p: [] for p in players}
    credibility = {p: [2., 1.] for p in players}
    reliability = {p: [3., 1.] for p in players}
    support = {p: [0., 0.] for p in players}
    concerns = {}
    verified = {(int(a), me): r["tokens"] for a, r in (own_deposits or {}).items()}
    if private.get("last_contribution"):
        r = private["last_contribution"]
        verified[r["attempt"], me] = r["tokens"]
    for r in private.get("receipts", []):
        if r["type"] == "audit":
            verified[r["attempt"], r["target"]] = r["tokens"]

    pledges, claims, accusations = {}, {}, {}
    resolutions = {}
    for event in observation["history"]:
        attempt = event["attempt"]
        if event["type"] == "pledges_revealed":
            # A later accepted proposal replaces any rejected proposal's pledge.
            pledges[attempt] = event["pledges"]
        elif event["type"] == "attempt_resolved":
            resolutions[attempt] = event
        elif event["type"] == "reports_revealed":
            for speaker, statements in event["reports"].items():
                for claim in statements:
                    target, verb, color = claim["player_id"], claim["verb"], claim["color"]
                    key = (attempt, speaker, target, verb, color)
                    entry = claims.setdefault(key, {"quantities": set(), "event": event})
                    entry["quantities"].add(claim["quantity"])
                    if speaker != target and claim["quantity"] and (
                            (verb == "gave" and color == "red") or (verb == "took" and color == "blue")):
                        accusations[attempt, speaker, target] = event
        elif event["type"] == "vote" and not event["approve"]:
            speaker = event["player_id"]
            for complaint in event.get("complaints", []):
                target = complaint.get("player_id")
                if (target in names and target != speaker and complaint.get("modifier") == "less"
                        and complaint.get("color") in (None, "red")):
                    accusations.setdefault((attempt, speaker, target), event)

    def note(pid, event, text):
        evidence[pid].append({"event_id": event.get("id", 0), "text": text})

    def concern(pid, strength, reason):
        if strength > concerns.get(pid, {}).get("strength", 0):
            concerns[pid] = {"strength": strength, "reason": reason}

    for pid, team in known.items():
        if pid != me:
            note(pid, {}, f"Confirmed {team.title()} team; later behavior cannot change this fact.")
            if team == "red":
                concern(pid, 1., "confirmed Red team")

    # Exact payments are stronger than aggregate outcomes or unverified speech.
    for (attempt, pid), paid in sorted(verified.items()):
        event = resolutions.get(attempt, {})
        colored = paid["blue"] + paid["red"]
        if colored:
            weight = min(4., colored)
            support[pid][0] += weight * paid["blue"] / colored
            support[pid][1] += weight * paid["red"] / colored
        pledged = pledges.get(attempt, {}).get(pid)
        if pledged is not None:
            reliability[pid][int(sum(paid.values()) < pledged)] += 1
        note(pid, event, f"Attempt {attempt}: privately verified original payment "
             f"{paid['blue']} Blue, {paid['red']} Red, {paid['green']} Green; not proof of team.")
        if paid["red"] > paid["blue"]:
            concern(pid, .8, "privately verified Red-heavy payment")

    # Judge all sources before accepting any of their rumors. A third party's
    # assertion never verifies another assertion, even if both sound plausible.
    false, checked, refuted_accusations = set(), set(), set()
    for key, item in claims.items():
        attempt, speaker, target, verb, color = key
        paid = verified.get((attempt, target))
        conflict = len(item["quantities"]) > 1
        contradicted = verb == "gave" and paid is not None and item["quantities"] != {paid[color]}
        if conflict or contradicted:
            false.add((attempt, speaker))
            if contradicted and speaker != target and ((verb == "gave" and color == "red")
                                                       or (verb == "took" and color == "blue")):
                refuted_accusations.add((attempt, speaker, target))
            note(speaker, item["event"], f"Attempt {attempt}: " + (
                f"claim about {names[target]}'s {color.title()} payment contradicts my private receipt."
                if contradicted else f"made incompatible claims about {names[target]}'s {color.title()} payment."))
        elif verb == "gave" and paid is not None:
            checked.add((attempt, speaker))
    for attempt, speaker in sorted(false):
        credibility[speaker][1] += 4
        concern(speaker, .95, "contradictory contribution claims")
        support[speaker][1] += 2
    for attempt, speaker in sorted(checked):
        if (attempt, speaker) not in false:
            credibility[speaker][0] += .75

    credibility = {p: good / (good + bad) for p, (good, bad) in credibility.items()}

    def source_weight(speaker):
        # Red players can tell the truth. Their unsupported accusations still
        # deserve much less weight than a cooperative, corroborated source's.
        return credibility[speaker] ** 2 * (.15 if known.get(speaker) == "red" else 1.)

    # Unverified self-reports have bounded lifetime influence. Merely repeating
    # a Blue cover story cannot erase a receipt or build unlimited trust.
    reports = defaultdict(lambda: [0., 0.])
    for (attempt, speaker, target, verb, color), item in claims.items():
        if (speaker != target or speaker == me or verb != "gave" or color == "green"
                or (attempt, target) in verified or (attempt, speaker) in false):
            continue
        amount = next(iter(item["quantities"]))
        reports[speaker][int(color == "red")] += min(4, amount) * .08
    for speaker, values in reports.items():
        scale = min(1., .6 / max(.6, sum(values))) * source_weight(speaker)
        for index in (0, 1):
            support[speaker][index] += values[index] * scale
        if sum(values):
            note(speaker, {}, "Own contribution reports provide weak, unverified evidence; repetition is capped.")

    # Freeze independent evidence before processing accusations; rumors cannot
    # corroborate other rumors or give their speakers earned credibility.
    direct = {p: list(values) for p, values in support.items()}
    pairs = defaultdict(list)
    for (attempt, speaker, target), event in accusations.items():
        pairs[speaker, target].append((attempt, event))
    pressure = dict.fromkeys(players, 0.)
    for (speaker, target), entries in pairs.items():
        if speaker == me:
            continue  # My own accusations are not independent corroboration.
        grounded = known.get(target) == "red" or direct[target][1] >= 1
        defended = known.get(target) == "blue" or direct[target][0] >= 2 * max(1., direct[target][1])
        repeat = len(entries)
        event = entries[-1][1]
        disproved = any((attempt, speaker, target) in refuted_accusations for attempt, _ in entries)
        if not disproved and not defended:
            # One source-target pair has a fixed budget across reports/votes.
            support[target][1] += .25 * source_weight(speaker)
            note(target, event, f"Accused by {names[speaker]}; an attributed claim, with repeated accusations capped.")
        if disproved or (not grounded and (known.get(speaker) == "red" or (repeat >= 2 and defended))):
            pressure[speaker] = max(pressure[speaker], min(1., .4 + .15 * repeat))
            concern(speaker, .75, f"repeated or suspect accusations against {names[target]}")
            if not disproved:
                support[speaker][1] += .4 if defended else .15
            note(speaker, event, f"Pressure on {names[target]} has " + (
                "contradicted private payment evidence; possible framing."
                if disproved else "weak independent support; possible framing, not a proven lie."))

    return {"support": support, "credibility": credibility,
            "reliability": {p: good / (good + bad) for p, (good, bad) in reliability.items()},
            "evidence": evidence, "concerns": concerns, "pressure": pressure,
            "verified": verified, "claims": claims}


def information_target(observation, social, rng):
    """Prefer disputed original payments and consequential unknown teams."""
    spec = observation["action_spec"].get("ability")
    if not spec or spec["id"] not in ("auditor", "scout"):
        return None
    me, attempt = observation["viewer"], observation["public"]["attempt"]
    known, facts = social["known_teams"], social["claims"]
    targets = [p for p in spec["targets"] if p != me and (
        p not in known if spec["id"] == "scout" else (attempt, p) not in facts["verified"])]
    if not targets:
        return None
    rng.shuffle(targets)

    def rank(pid):
        conflict = defaultdict(set)
        accused = False
        for (a, speaker, target, verb, color), item in facts["claims"].items():
            if a == attempt and target == pid and verb == "gave":
                conflict[color].update(item["quantities"])
                accused |= speaker != target and color == "red" and max(item["quantities"]) > 0
        disputed = any(len(values) > 1 for values in conflict.values())
        concern = facts["concerns"].get(pid, {}).get("strength", 0)
        return 4 * disputed + 3 * accused + 2 * concern + facts["pressure"][pid]

    return max(targets, key=rank)
