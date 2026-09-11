from mission_game import Game, GameConfig
from mission_game.types import Phase


def game(**config):
    return Game(seed=42, game_id="test-game", config=GameConfig.common_rules(
        threshold_min=config.pop("threshold", 8), threshold_max=config.pop("threshold_max", 8),
        crew_min=2, crew_max=2, **config))


def submit(game, pid, action):
    observation = game.observe(pid)
    return game.submit(pid, observation["request_id"], observation["revision"], action)


def tokens(blue=0, red=0, green=0):
    return {"blue": blue, "red": red, "green": green}


def set_teams(game, assignments):
    """Build a designer fixture while preserving the required team counts."""
    remaining = [p for p in game.players if p.id not in assignments]
    blues = game.config.blue_players - sum(team == "blue" for team in assignments.values())
    assert 0 <= blues <= len(remaining)
    for player in game.players:
        if player.id in assignments:
            player.team = assignments[player.id]
    for player, team in zip(remaining, ["blue"] * blues + ["red"] * (len(remaining) - blues)):
        player.team = team


def proposal(game, crew=("p0", "p1"), pledges=None, approvals=8):
    chairman = game.players[game.chairman].id
    submit(game, chairman, {"type": "select_crew", "crew": list(crew)})
    for pid in crew:
        submit(game, pid, {"type": "pledge", "tokens": (pledges or {}).get(pid, tokens())})
    for index in range(8):
        pid = next(iter(game.pending_requests()))
        approve = index < approvals
        submit(game, pid, {"type": "vote", "approve": approve,
                           "complaints": [] if approve else [{"modifier": "more", "color": "blue"}]})


def resolve(game, contributions=None, crew=("p0", "p1"), pledges=None):
    proposal(game, crew, pledges)
    for pid in crew:
        submit(game, pid, {"type": "contribute", "tokens": (contributions or {}).get(pid, tokens())})


def reports(game):
    assert game.phase == Phase.REPORT
    for pid in list(game.pending_requests()):
        statements = [{"player_id": pid, "verb": "gave", "quantity": 0, "color": "blue"}]
        submit(game, pid, {"type": "report", "statements": statements})
