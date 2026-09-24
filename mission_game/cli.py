"""Terminal, JSON-line, simulation, and trusted replay entry points."""

import argparse
import json
import secrets
import sys
from collections import Counter
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path
from statistics import mean

from .config import GameConfig, DEFAULT_CONFIG_PATH
from .engine import ActionError
from .policy import POLICY_NAMES, POLICY_VERSION, make_policy
from .session import Session, write_json
from .terminal import LeaveGame, choose_action, show
from .types import Phase


def guide():
    return files("mission_game").joinpath("public_player_guide.md").read_text()


def session_path(value):
    path = Path(value)
    return path / "session.json" if path.is_dir() or not path.suffix else path


def upgrade_bots(path):
    from .social_policy import VERSION
    original = path.read_bytes()
    session = Session.load(path)
    upgraded = session.upgrade_social_policies()
    if not upgraded:
        print("No social bots need upgrading.")
        return
    backup = path.with_name(f"{path.stem}.before-{VERSION}{path.suffix}")
    if path.read_bytes() != original:
        raise ValueError("The session changed during upgrade; pause play and try again")
    with backup.open("xb") as output:
        output.write(original)
    session.save(path)
    print(f"Upgraded {len(upgraded)} bots to {VERSION}. Past actions are unchanged. Backup: {backup}")


def human_loop(session, path):
    if session.human_id is None:
        raise ValueError("This session has no human seat; use replay to inspect it")
    print(guide())
    print(f"\nSaved session: {path}\nUse /history to inspect events; /save or /quit to save and leave.\n")
    cursor = 0
    session.save(path)
    try:
        while True:
            while session.step_bot():
                session.save(path)
            observation = session.game.observe(session.human_id)
            show(observation, cursor)
            cursor = len(observation["history"])
            if session.game.phase == Phase.GAME_OVER:
                return
            try:
                action = choose_action(observation)
                session.game.submit(session.human_id, observation["request_id"], observation["revision"], action)
                session.save(path)
            except (ActionError, ValueError) as exc:
                print(f"Action not accepted: {exc}")
    except (LeaveGame, KeyboardInterrupt):
        session.save(path)
        print(f"\nSaved. Resume with: python3 -m mission_game.cli resume {path}")


def json_loop(session, path, mission_checkpoints=False):
    """Seat binding comes from the trusted session, never from input payloads."""
    if session.human_id is None:
        raise ValueError("The JSON adapter requires a session with an external seat")

    def emit(data):
        print(json.dumps(data, allow_nan=False), flush=True)

    checkpointed = session.game.mission.number - 1

    def checkpoint():
        nonlocal checkpointed
        if not mission_checkpoints:
            return
        completed = len(session.game.completed_missions)
        # Wait for reports and inspections. Capture this boundary before
        # any subsequent preparation or proposal, including terminal missions.
        if completed > checkpointed and (session.game.phase == Phase.GAME_OVER
                                        or session.game.mission.number > completed):
            checkpointed = completed
            emit({"type": "mission_checkpoint", "mission": completed,
                  "observation": session.game.observe(session.human_id)})

    emit({"type": "instructions", "text": guide()})
    session.save(path)
    while True:
        checkpoint()
        while session.step_bot():
            session.save(path)
            checkpoint()
        observation = session.game.observe(session.human_id)
        emit({"type": "observation", "observation": observation})
        if session.game.phase == Phase.GAME_OVER:
            return
        while True:
            line = sys.stdin.readline()
            if not line:
                session.save(path)
                return
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict) or set(payload) != {"request_id", "revision", "action"}:
                    raise ValueError("Supply exactly request_id, revision, and action")
                accepted = session.game.submit(session.human_id, **payload)
                session.save(path)
                emit({"type": "acceptance", **accepted})
                break
            except (ActionError, ValueError, TypeError) as exc:
                emit({"type": "error", "code": getattr(exc, "code", "invalid_payload"), "message": str(exc)})


def summarize(records):
    healthy = [r for r in records if r["status"] != "FAILED"]
    counts = Counter(r["status"] for r in records)
    wins = Counter(r.get("winner") for r in healthy if r["status"] == "FINISHED")
    attempts = [r["attempts"] for r in healthy]
    mission_attempts = [n for r in healthy for n in r["mission_attempts"]]
    versions = sorted({r["rules_version"] for r in records if "rules_version" in r})
    # Older diagnostics predate selectable policies and always used random-legal.1.
    policy_versions = sorted({version for r in records for version in r.get("policy_versions", [POLICY_VERSION])})
    objectives = [p for r in healthy for p in r.get("objectives", [])]
    return {
        "rules_version": versions[0] if len(versions) == 1 else "mixed" if versions else None,
        "rules_versions": versions,
        "policy_version": policy_versions[0] if len(policy_versions) == 1 else "mixed" if policy_versions else None,
        "policy_versions": policy_versions,
        "games": len(records), "completed": counts["FINISHED"],
        "unresolved": counts["UNRESOLVED"], "failed": counts["FAILED"],
        "team_wins": {team: wins[team] for team in ("blue", "red")},
        "win_rate_among_completed": {team: wins[team] / counts["FINISHED"] if counts["FINISHED"] else None
                                     for team in ("blue", "red")},
        "attempts_per_game": {"mean": mean(attempts) if attempts else None,
                              "min": min(attempts) if attempts else None,
                              "max": max(attempts) if attempts else None},
        "attempts_per_completed_mission": mean(mission_attempts) if mission_attempts else None,
        "rejected_proposals": sum(r["rejected_proposals"] for r in healthy),
        "penalty_attempts": sum(r["penalty_attempts"] for r in healthy),
        "individual_winners": sum(r["individual_winners"] for r in healthy),
        "by_objective": {kind: {"holders": sum(p["objective"] == kind for p in objectives),
                                "individual_wins": sum(p["objective"] == kind and p["won"] for p in objectives),
                                "condition_satisfied": sum(p["objective"] == kind and p["condition_satisfied"] for p in objectives)}
                         for kind in sorted({p["objective"] for p in objectives})},
        "by_initial_blue_count": {
            str(count): {"games": sum(r["blue_players"] == count for r in healthy),
                         "blue_wins": sum(r["blue_players"] == count and r["winner"] == "blue" for r in healthy),
                         "red_wins": sum(r["blue_players"] == count and r["winner"] == "red" for r in healthy),
                         "unresolved": sum(r["blue_players"] == count and r["status"] == "UNRESOLVED" for r in healthy)}
            for count in sorted({r["blue_players"] for r in healthy})
        },
        "by_contrarian": {
            label: {"games": sum(r["contrarian_present"] == present for r in healthy),
                    "blue_wins": sum(r["contrarian_present"] == present and r["winner"] == "blue" for r in healthy),
                    "red_wins": sum(r["contrarian_present"] == present and r["winner"] == "red" for r in healthy),
                    "unresolved": sum(r["contrarian_present"] == present and r["status"] == "UNRESOLVED" for r in healthy)}
            for label, present in (("absent", False), ("present", True))
        },
        "interpretation": "Scripted-policy diagnostic. Policy versions identify the opponents; results do not establish balance or human-level difficulty.",
    }


def simulate(args):
    config = GameConfig.load(args.config or DEFAULT_CONFIG_PATH)
    settings = json.loads(Path(args.policy_config).read_text()) if args.policy_config else None
    controller = make_policy(args.policy, settings=settings)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for index in range(args.games):
        seed = args.seed + index
        session = Session(seed, config, policy=args.policy, policy_settings=settings)
        try:
            session.run()
            session.replay()
            metrics = session.metrics()
            if index == 0:
                session.save(output / "example-replay.json")
        except Exception as exc:
            session.save(output / f"failure-{index}.json")
            metrics = {"status": "FAILED", "rules_version": config.rules_version,
                       "policy_versions": [make_policy(args.policy).version],
                       "error": f"{type(exc).__name__}: {exc}"}
        records.append({"seed": seed, **metrics})
        if (index + 1) % 25 == 0:
            print(f"Simulated {index + 1}/{args.games}", file=sys.stderr)
    (output / "games.jsonl").write_text("".join(json.dumps(record) + "\n" for record in records))
    summary = summarize(records)
    write_json(output / "summary.json", summary)
    write_json(output / "config.json", config.to_dict())
    descriptor = {"name": args.policy, "version": controller.version}
    if hasattr(controller, "settings"):
        descriptor["settings"] = asdict(controller.settings)
    write_json(output / "policies.json", descriptor)
    print(json.dumps(summary, indent=2))
    return int(summary["failed"] > 0)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hidden Rules development game: private objectives and hidden abilities")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("play", "agent", "simulate"):
        sub = commands.add_parser(command)
        sub.add_argument("--seed", type=int, default=None if command != "simulate" else 20260910,
                         help="Trusted development seed (never included in player observations)")
        sub.add_argument("--config", help="Versioned development JSON configuration")
        sub.add_argument("--policy", choices=POLICY_NAMES, default="social",
                         help="Computer policy for new games; saved games keep their existing controllers")
        sub.add_argument("--policy-config", help="JSON settings for the social policy")
        if command != "simulate":
            sub.add_argument("--human-seat", type=int, choices=range(8), default=0)
            sub.add_argument("--session", help="Private session JSON file or directory")
            if command == "agent":
                sub.add_argument("--mission-checkpoints", action="store_true",
                                 help="Emit seat observations after each mission's reports and inspections")
        else:
            sub.add_argument("--games", type=int, default=100)
            sub.add_argument("--out", default="runs/smoke")
    resume = commands.add_parser("resume")
    resume.add_argument("session")
    upgrade = commands.add_parser("upgrade-bots", help="Upgrade saved social bots, preserving a backup and all past moves")
    upgrade.add_argument("session")
    replay = commands.add_parser("replay")
    replay.add_argument("session")
    visibility = replay.add_mutually_exclusive_group(required=True)
    visibility.add_argument("--seat", type=int, choices=range(8))
    visibility.add_argument("--omniscient", action="store_true", help="DESIGNER ONLY: expose full hidden state")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("directory")
    commands.add_parser("guide")
    web = commands.add_parser("web", help="Open a local web table and replay library")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--runs-dir", default="runs", help="Local saved-game library")
    web.add_argument("--config", help="Game configuration reloaded for every new table (default: configs/development_abilities.json)")
    web.add_argument("--policy", choices=POLICY_NAMES, default="social")
    web.add_argument("--policy-config", help="JSON settings for new social-policy tables")
    args = parser.parse_args(argv)
    try:
        if args.command == "web":
            from .server import serve
            if not 0 <= args.port <= 65535:
                raise ValueError("--port must be between 0 and 65535")
            settings = json.loads(Path(args.policy_config).read_text()) if args.policy_config else None
            serve(args.runs_dir, args.port, args.policy, settings, args.config)
        elif args.command == "guide":
            print(guide())
        elif args.command == "simulate":
            if args.games < 1:
                raise ValueError("--games must be positive")
            return simulate(args)
        elif args.command == "analyze":
            records = [json.loads(line) for line in (Path(args.directory) / "games.jsonl").read_text().splitlines() if line]
            print(json.dumps(summarize(records), indent=2))
        elif args.command == "replay":
            session = Session.load(session_path(args.session))
            game = session.replay()
            print("Replay verified against the saved state.")
            if args.omniscient:
                print("DESIGNER VIEW — contains all private information.")
                print(json.dumps(game.snapshot(), indent=2))
                print("SAVED BOT EXPLANATIONS — designer metadata, not re-generated during replay.")
                print(json.dumps(session.bot_decisions, indent=2))
            else:
                observation = game.observe(f"p{args.seat}")
                show(observation)
                print("\nYour private action history:")
                for record in observation["private"]["submissions"]:
                    print(json.dumps(record))
        elif args.command == "resume":
            path = session_path(args.session)
            human_loop(Session.load(path), path)
        elif args.command == "upgrade-bots":
            upgrade_bots(session_path(args.session))
        else:
            path = session_path(args.session) if args.session else None
            if path and path.exists():
                if args.command != "agent":
                    raise ValueError("Session already exists; use resume or choose a new path")
                session = Session.load(path)
            else:
                config = GameConfig.load(args.config or DEFAULT_CONFIG_PATH)
                settings = json.loads(Path(args.policy_config).read_text()) if args.policy_config else None
                session = Session(args.seed if args.seed is not None else secrets.randbits(128), config, args.human_seat,
                                  policy=args.policy, policy_settings=settings)
                path = path or Path("runs") / session.game.game_id / "session.json"
            if args.command == "agent":
                json_loop(session, path, mission_checkpoints=args.mission_checkpoints)
            else:
                human_loop(session, path)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
