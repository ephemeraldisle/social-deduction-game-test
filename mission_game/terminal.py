"""Guided terminal controls. This module never receives authoritative state."""

from .policy import truthful_statements


class LeaveGame(Exception):
    pass


def vector_text(vector):
    return ", ".join(f"{n} {c.title()}" for c, n in vector.items() if n) or "0 tokens"


def event_text(event):
    kind = event["type"]
    prefix = f"Attempt {event['attempt']} · "
    if kind == "crew_selected":
        return prefix + f"{event['chairman']} proposed {', '.join(event['crew'])}."
    if kind == "pledges_revealed":
        return prefix + "Player pledges: " + "; ".join(f"{p}: {vector_text(v)}" for p, v in event["pledges"].items())
    if kind == "vote":
        claims = [" ".join(str(claim[k]) for k in ("modifier", "player_id", "color") if claim.get(k))
                  for claim in event["complaints"]]
        return prefix + f"{event['player_id']} voted {'Yes' if event['approve'] else 'No'}" + (f"; complaints: {'; '.join(claims)}" if claims else "")
    if kind == "attempt_resolved":
        mission = event["mission"]
        result = f"{mission['winner'].title()} wins the mission" if mission["winner"] else "mission remains open"
        source = "rejection penalty" if event["penalty"] else "approved crew"
        return prefix + f"OFFICIAL RESULT ({source}): {vector_text(mission['pot'])}; {result}."
    if kind == "reports_revealed":
        lines = [f"{speaker} claims {s['player_id']} {s['verb']} {s['quantity']} {s['color'].title()}"
                 for speaker, statements in event["reports"].items() for s in statements]
        return prefix + "Player reports: " + ("; ".join(lines) or "everyone passed")
    if kind == "vote_income":
        return prefix + f"OFFICIAL VOTE REVENUE: everyone receives {event['amount_each']} token, pass or fail."
    if kind == "income":
        return prefix + f"OFFICIAL: everyone receives {event['amount_each']} token."
    if kind == "mission_drawn":
        mission = event["mission"]
        return prefix + f"Mission {mission['number']}: threshold {mission['threshold']}, crew {mission['crew_size']}."
    if kind == "proposal_rejected":
        return prefix + f"Proposal rejected ({event['rejections']} of 8)."
    if kind == "proposal_approved":
        return prefix + f"Proposal approved with {event['yes_votes']} Yes votes."
    if kind == "game_over":
        return f"OFFICIAL: {event['winner'].title() + ' wins the game' if event['winner'] else 'UNRESOLVED — attempt limit reached'}."
    objectives = "private objectives" if event.get("mode") != "development_common_rules" else "all Loyalists"
    return f"Development game started: {objectives}; abilities {'enabled' if event.get('mode') == 'development_abilities' else 'disabled'}."


def show(observation, after_event=0):
    for event in observation["history"]:
        if event["id"] > after_event:
            print(event_text(event))
    public, private = observation["public"], observation["private"]
    mission = public["mission"]
    print(f"\nMission {mission['number']} | Attempt {public['attempt']} | {observation['phase']}"
          f" | Chairman {public['chairman']} | Blue {public['score']['blue']} – Red {public['score']['red']}")
    print(f"Pot: {vector_text(mission['pot'])} / {mission['threshold']}; crew size {mission['crew_size']}")
    print("Wallets: " + " | ".join(f"{p['id']} {p['name']}: {p['wallet']}" for p in public["players"]))
    print(f"PRIVATE ({observation['viewer']}): {private['team'].title()}. {private['objective']['text']}")
    if "progress" in private["objective"]:
        print(private["objective"]["progress"]["text"])
    print(private["ability"]["text"])
    if private["ability"].get("uses_remaining") is not None:
        print(f"Ability uses remaining: {private['ability']['uses_remaining']}")
    if public.get("public_badges"):
        print("Official allegiance badges: " + ", ".join(f"{pid}: {team.title()}" for pid, team in public["public_badges"].items()))
    for receipt in private.get("receipts", []):
        print(f"PRIVATE RESULT · Attempt {receipt['attempt']}: {receipt_text(receipt)}")
    if private.get("last_contribution"):
        receipt = private["last_contribution"]
        print(f"Your original deposit on attempt {receipt['attempt']}: {vector_text(receipt['tokens'])}.")
    if "result" in private:
        result = private["result"]
        print(f"Your result: {'WON' if result['won'] else 'DID NOT WIN'}; final wallet {result['wallet']}.")
        if "text" in result:
            print(result["text"])


def receipt_text(receipt):
    kind = receipt["type"]
    if kind == "scout":
        return f"{receipt['target']} is {receipt['team'].title()}."
    if kind == "audit":
        return f"{receipt['target']} originally paid {vector_text(receipt['tokens'])}."
    if kind == "objective_changed":
        return "Your objective changed. " + receipt["objective"]["text"] + " " + receipt["objective"]["progress"]["text"]
    if kind == "echo":
        return f"Your deposit added 1 free {receipt['color'].title()} token."
    if kind == "thief":
        return (f"You took {receipt['amount']} uncolored tokens from {receipt['target']}'s wallet."
                if receipt["source"] == "wallet" else f"You took {vector_text(receipt['tokens'])} from the mission.")
    return ""


def choose_ability(spec, ask):
    if not spec:
        return None
    answer = ask(f"Use {spec['id'].replace('_', ' ').title()}? (yes/no; Enter passes): ").lower()
    if answer in ("", "n", "no"):
        return None
    if answer not in ("y", "yes"):
        raise ValueError("Enter yes or no")
    def target():
        pid = ask("Choose a player (" + ", ".join(spec["targets"]) + "): ")
        return pid if pid.startswith("p") else f"p{pid}"
    if spec["id"] in ("switcher", "scout", "auditor"):
        return {"target": target()}
    if spec["id"] == "stowaway":
        return {"color": ask("Deposit 1 token in which color (blue/red/green)? ").lower()}
    if spec["id"] == "recolorer":
        return {"from": ask("Source color: ").lower(), "to": ask("Destination color: ").lower()}
    source = ask("Take from mission or wallet? ").lower()
    if source == "wallet":
        return {"source": source, "target": target(), "amount": int(ask("Amount (1–3): "))}
    if source == "mission":
        amounts = ask("Requested Blue Red Green (total 1–3): ").split()
        if len(amounts) != 3:
            raise ValueError("Enter three quantities")
        return {"source": source, "tokens": dict(zip(("blue", "red", "green"), map(int, amounts)))}
    raise ValueError("Choose mission or wallet")


def parse_complaints(text):
    claims = []
    for expression in text.split(";"):
        if not expression.strip():
            continue
        claim = {}
        for word in expression.lower().split():
            key = ("modifier" if word in ("more", "less", "exact") else
                   "color" if word in ("blue", "red", "green") else "player_id")
            if key in claim:
                raise ValueError("Only one modifier, player, and color per complaint")
            claim[key] = word
        claims.append(claim)
    if len(claims) != 1:
        raise ValueError("A No vote needs exactly one complaint, for example: more blue")
    return claims


def parse_reports(text):
    statements = []
    for expression in text.split(";"):
        if not expression.strip():
            continue
        words = expression.lower().split()
        if len(words) != 4:
            raise ValueError("Use: p0 gave 2 blue; p1 took 1 red")
        player_id, verb, quantity, color = words
        statements.append({"player_id": player_id, "verb": verb, "quantity": int(quantity), "color": color})
    return statements


def choose_action(observation):
    def ask(prompt):
        while True:
            try:
                response = input(prompt).strip()
            except (EOFError, KeyboardInterrupt) as exc:
                raise LeaveGame from exc
            if response in ("/quit", "/save"):
                raise LeaveGame
            if response == "/history":
                for event in observation["history"]:
                    print(event_text(event))
                continue
            return response

    spec = observation["action_spec"]
    kind = spec["type"]
    if kind in ("prepare", "audit"):
        return {"type": kind, "ability": choose_ability(spec.get("ability"), ask)}
    if kind == "contribute" and spec.get("on_crew") is False:
        return {"type": kind, "tokens": dict.fromkeys(("blue", "red", "green"), 0),
                "ability": choose_ability(spec.get("ability"), ask)}
    if kind == "select_crew":
        seats = ask(f"Choose {spec['crew_size']} seats (e.g. 0 2 5): ").split()
        return {"type": kind, "crew": [seat if seat.startswith("p") else f"p{seat}" for seat in seats]}
    if kind in ("pledge", "contribute"):
        values = ask(f"{'Pledge' if kind == 'pledge' else 'Secret deposit'} Blue Red Green (e.g. 2 0 1; budget {spec['max_total']}): ").split()
        if len(values) != 3:
            raise ValueError("Enter three nonnegative integers: Blue Red Green")
        action = {"type": kind, "tokens": dict(zip(("blue", "red", "green"), map(int, values)))}
        if kind == "contribute" and "ability" in spec:
            action["ability"] = choose_ability(spec["ability"], ask)
        return action
    if kind == "vote":
        response = ask("Approve this crew? (yes/no): ").lower()
        if response not in ("y", "yes", "n", "no"):
            raise ValueError("Enter yes or no")
        approve = response in ("y", "yes")
        complaints = [] if approve else parse_complaints(ask("Explain your No vote with one complaint (e.g. less p2 or more blue): "))
        return {"type": kind, "approve": approve, "complaints": complaints}
    if kind == "report":
        default = truthful_statements(observation) if spec["min_statements"] else []
        print("Reports are player claims and may be false. Use: p0 gave 2 blue; p1 took 1 red")
        print("Enter uses " + ("; ".join(f"{s['player_id']} {s['verb']} {s['quantity']} {s['color']}" for s in default) if default else "pass") + ".")
        response = ask(f"Report ({spec['min_statements']}–3 statements): ")
        return {"type": kind, "statements": parse_reports(response) if response else default}
    raise ValueError("No decision is currently available")
