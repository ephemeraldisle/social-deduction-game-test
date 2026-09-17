"""Derive postgame evidence for analysis.md from recorded artifacts."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

FOLDER = Path(__file__).resolve().parent


def wilson(k, n):
    z = 1.959963984540054
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [center - width, center + width]


def main():
    saved = json.loads((FOLDER / "session.json").read_text())
    original = json.loads((FOLDER / "cli-session-original.json").read_text())
    assert saved["game"] == original["game"]
    game = saved["game"]
    truth = {p["id"]: int(p["team"] == "blue") for p in game["players"]}
    unknown = [pid for pid in truth if pid not in ("p0", "p2")]
    prior = sum(truth[p] for p in unknown) / len(unknown)
    predictions = []
    for checkpoint in saved["agent_predictions"]:
        estimates = {p["player_id"]: p["p_blue"] for p in checkpoint["estimates"]}
        predictions.append({"mission": checkpoint["mission"], "unknown_seats": len(unknown),
                            "correct_unknown": sum((estimates[p] >= .5) == truth[p] for p in unknown),
                            "brier_unknown": sum((estimates[p] - truth[p]) ** 2 for p in unknown) / len(unknown)})
    votes = []
    proposals = []
    for event in game["events"]:
        if event["type"] == "crew_selected":
            votes = []
            crew = event["crew"]
            chair = event["chairman"]
        if event["type"] == "vote":
            votes.append(event)
        if event["type"] in ("proposal_rejected", "proposal_approved"):
            yes = sum(v["approve"] for v in votes)
            own = next(v for v in votes if v["player_id"] == "p0")
            proposals.append({"attempt": event["attempt"], "chair": chair, "crew": crew,
                              "yes": yes, "ai_yes": own["approve"],
                              "ai_no_pivotal_holding_other_votes_fixed": yes == 4 and not own["approve"]})
    recolors = Counter()
    payment_counterfactuals = []
    for resolution in game["resolutions"]:
        number = resolution["mission"]["number"]
        recolors[number] += sum(e["type"] == "recolorer" and e["player_id"] == "p0"
                                and e["from"] == "blue" and e["to"] == "red" and e["changed"]
                                for e in resolution["effects"])
        if resolution["mission"]["winner"]:
            pot = resolution["mission"]["pot"]
            without = {**pot, "blue": pot["blue"] + recolors[number], "red": pot["red"] - recolors[number]}
            payment_counterfactuals.append({"mission": number, "actual_pot": pot,
                "recolorings": recolors[number], "pot_without_ai_recolorings": without,
                "winner_without_ai_recolorings": "blue" if without["blue"] >= without["red"] else "red"})
    samples = [json.loads(path.read_text()) for path in (FOLDER / "balance-probe").glob("*.json")
               if path.name.startswith(("fresh_default-1", "fresh_loyalist-1", "same_deal_social-2", "same_deal_simple-2"))]
    assert len(samples) == 36
    for seed in range(1000, 1012):
        pair = [r for r in samples if r["seed"] == seed]
        assert len(pair) == 2
        assert pair[0]["initial_mission"] == pair[1]["initial_mission"]
        assert [(p["id"], p["team"], p["ability"]) for p in pair[0]["initial_players"]] == [
            (p["id"], p["team"], p["ability"]) for p in pair[1]["initial_players"]]
    manifest = json.loads((FOLDER / "balance-probe" / "manifest.json").read_text())
    root = FOLDER.parents[1]
    assert hashlib.sha256((FOLDER / "cli-session-original.json").read_bytes()).hexdigest() == manifest["original_sha256"]
    for relative, digest in manifest["source_sha256"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
    populations = {}
    for group in sorted({r["group"] for r in samples}):
        rows = [r for r in samples if r["group"] == group]
        red = sum(r["metrics"]["winner"] == "red" for r in rows)
        assert all(r["replay_exact"] and r["metrics"]["status"] == "FINISHED" for r in rows)
        populations[group] = {"n": len(rows), "red_wins": red, "blue_wins": len(rows) - red,
                              "red_win_rate": red / len(rows), "wilson_95": wilson(red, len(rows)),
                              "mean_rejections": sum(r["metrics"]["rejected_proposals"] for r in rows) / len(rows)}
    result = {"postgame_only": True, "prior_p_blue_unknown": prior,
              "prior_brier_unknown": sum((prior - truth[p]) ** 2 for p in unknown) / len(unknown),
              "prediction_metrics": predictions, "proposals": proposals,
              "pivotal_no_count": sum(p["ai_no_pivotal_holding_other_votes_fixed"] for p in proposals),
              "funding_totals": {p["id"]: {c: sum(r["original_contributions"].get(p["id"], {}).get(c, 0)
                  for r in game["resolutions"]) for c in ("blue", "red")} for p in game["players"]},
              "fixed_payment_counterfactual_note": "Arithmetic only: hold every recorded payment and other effect fixed, remove Abby's recolorings. This does not predict how opponents would adapt or how a seventh mission would play.",
              "fixed_payment_counterfactuals": payment_counterfactuals,
              "populations": populations,
              "verification": {"paired_setup_and_abilities_equal": True, "all_36_replay_exact": True,
                               "source_unchanged_during_probe": True, "original_game_unchanged": True}}
    (FOLDER / "analysis-data.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"populations": populations, "predictions": predictions, "pivotal_no_count": result["pivotal_no_count"]}, indent=2))


if __name__ == "__main__":
    main()
