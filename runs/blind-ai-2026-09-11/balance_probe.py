"""Postgame experiments. No model calls; never modifies the original replay.

Run from the repository root: python3 runs/blind-ai-2026-09-11/balance_probe.py
The simple Red policy is deliberately restricted to current public wallets,
crew membership, its own card and receipt. It has no opponent belief model.
"""
import hashlib
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mission_game.config import GameConfig
from mission_game.engine import Game
from mission_game.session import Session, write_json
from mission_game.social_baseline import Traits

OUT = Path(__file__).resolve().parent / "balance-probe"
ORIGINAL = Path(__file__).resolve().parent / "cli-session-original.json"


class SimpleRed:
    version = "postgame-simple-red.1"
    last_decision = None

    def choose_action(self, obs):
        me, public, spec = obs["viewer"], obs["public"], obs["action_spec"]
        kind = spec["type"]
        assert obs["private"]["team"] == "red"
        assert obs["private"]["ability"]["id"] == "recolorer"
        if kind == "select_crew":
            others = sorted((p for p in public["players"] if p["id"] != me),
                            key=lambda p: (p["wallet"], p["id"]))
            return {"type": kind, "crew": [me] + [p["id"] for p in others[:public["mission"]["crew_size"] - 1]]}
        if kind == "vote":
            yes = me in public["crew"]
            return {"type": kind, "approve": yes, "complaints": [] if yes else [{"modifier": "less", "color": "blue"}]}
        if kind in ("pledge", "contribute"):
            color = "blue" if kind == "pledge" else "red"
            result = {"type": kind, "tokens": {c: spec["max_total"] if c == color else 0 for c in ("blue", "red", "green")}}
            if kind == "contribute":
                result["ability"] = {"from": "blue", "to": "red"}
            return result
        if kind == "report":
            receipt = obs["private"].get("last_contribution") or {}
            return {"type": kind, "statements": [{"player_id": me, "verb": "gave", "quantity": sum(receipt.get("tokens", {}).values()), "color": "blue"}]}
        if kind in ("prepare", "audit"):
            return {"type": kind, "ability": None}
        raise ValueError(f"Unexpected action: {kind}")


def run_one(task):
    group, seed = task
    start = time.monotonic()
    saved = json.loads(ORIGINAL.read_text())
    config = GameConfig(**saved["initial"]["config"])
    if group == "fresh_loyalist":
        config = replace(config, objective_deck=("loyalist",) * 8)
    session = Session(seed=seed, config=config)
    if group.startswith("same_deal"):
        session.initial = deepcopy(saved["initial"])
        session.game = Game.from_snapshot(session.initial)
        # Preserve the original seven personalities/settings, but restart their
        # memories and use independently seeded policy random streams.
        for pid, old in saved["policies"].items():
            session.policies[pid].traits = Traits(**old["traits"])
            assert session.policies[pid].settings.__dict__ == old["settings"]
        if group == "same_deal_simple":
            session.policies["p0"] = SimpleRed()
    # Skip session-level designer explanations to keep this sweep compact.
    session.session_version = 1
    session.run()
    session.replay()
    result = {"group": group, "seed": seed, "elapsed_seconds": round(time.monotonic() - start, 3),
              "initial_players": session.initial["players"], "initial_mission": session.initial["mission"],
              "metrics": session.metrics(), "replay_exact": True}
    write_json(OUT / f"{group}-{seed}.json", result)
    # One exact, GUI-loadable representative per population.
    if seed in (1000, 2000):
        session.session_version = 2
        if group != "same_deal_simple":
            session.save(OUT / f"{group}-example-session.json")
        else:
            write_json(OUT / "same_deal_simple-example-actions.json", {
                "initial": session.initial, "actions": session.game.action_log,
                "final": session.game.snapshot()})
    return result


def main():
    OUT.mkdir(exist_ok=True)
    tasks = [(g, seed) for seed in range(1000, 1012) for g in ("fresh_default", "fresh_loyalist")]
    tasks += [(g, seed) for seed in range(2000, 2006) for g in ("same_deal_social", "same_deal_simple")]
    # Start the directly comparable deal first, then the wider paired sample.
    tasks = tasks[24:] + tasks[:24]
    manifest = {"tasks": tasks, "original_sha256": hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
                "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((ROOT / "mission_game").glob("*.py"))},
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "note": "Postgame reviewer experiments; source access is allowed for the reviewer. No LLM calls. Fresh pairs share setup/ability/mission/policy seeds; objective deck alone changes. Same-deal runs preserve exact initial engine state and seven original bot personalities, but use new policy RNG seeds and a new seat-0 controller."}
    write_json(OUT / "manifest.json", manifest)
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(run_one, task): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                print(json.dumps({"error": repr(exc), "task": task}), flush=True)
                raise
            results.append(result)
            print(json.dumps({"completed": len(results), "total": len(tasks), "group": result["group"],
                              "seed": result["seed"], "seconds": result["elapsed_seconds"],
                              "winner": result["metrics"]["winner"], "score": result["metrics"]["score"]}), flush=True)
    summary = {g: {"n": sum(r["group"] == g for r in results),
                   "winners": dict(Counter(r["metrics"]["winner"] for r in results if r["group"] == g))}
               for g in sorted({r["group"] for r in results})}
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
