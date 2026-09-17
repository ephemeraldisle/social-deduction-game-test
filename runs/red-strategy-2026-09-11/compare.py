"""Paired bot games: social.11 everywhere vs social.12 in the Red seats only."""
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mission_game.config import GameConfig
from mission_game.session import Session, write_json

OUT = Path(__file__).resolve().parent / "paired-games"


def play(task):
    seed, upgraded = task
    session = Session(seed, GameConfig.load(ROOT / "configs/development_abilities.json"))
    session.session_version = 1
    for player in session.game.players:
        if not upgraded or player.team != "red":
            session.policies[player.id].version = "social.11"
    session.run()
    session.replay()
    red = {p.id for p in session.game.players if p.team == "red"}
    opening = session.game.resolutions[0]
    result = {"seed": seed, "upgraded_red": upgraded, "metrics": session.metrics(),
              "opening_red_payments": {pid: opening["original_contributions"].get(pid) for pid in sorted(red)},
              "opening_red_tokens": sum(paid["red"] for pid, paid in opening["original_contributions"].items() if pid in red),
              "replay_verified": True}
    write_json(OUT / f"{seed}-{'new' if upgraded else 'old'}.json", result)
    if seed == 4000:
        session.session_version = 2
        session.save(OUT / ("new" if upgraded else "old") / "session.json")
    return result


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [(seed, upgraded) for seed in range(4000, 4016) for upgraded in (False, True)]
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(play, task) for task in tasks]):
            result = future.result()
            results.append(result)
            print(json.dumps({"completed": len(results), "seed": result["seed"],
                              "new_red": result["upgraded_red"], "winner": result["metrics"]["winner"]}), flush=True)
    summary = {}
    for upgraded in (False, True):
        rows = [r for r in results if r["upgraded_red"] == upgraded]
        summary["new_red" if upgraded else "old_red"] = {
            "games": len(rows), "red_wins": sum(r["metrics"]["winner"] == "red" for r in rows),
            "finished": sum(r["metrics"]["status"] == "FINISHED" for r in rows),
            "mean_opening_red_tokens": sum(r["opening_red_tokens"] for r in rows) / len(rows)}
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary), flush=True)
