"""Per-seat evidence storage for scripted controllers, without inferred beliefs.

Only ingest a seat observation. Public reports remain attributed claims; they
are never converted into verified deposits or team assignments. Later policies
can build beliefs from this evidence without changing the session contract.
"""

from copy import deepcopy


class EvidenceMemory:
    def __init__(self):
        self.game_id = None
        self.viewer = None
        self.last_event_id = 0
        self.events = []
        self.own_deposits = {}
        self.desired_side = None

    def observe(self, observation):
        identity = observation["game_id"], observation["viewer"]
        if self.game_id is not None and identity != (self.game_id, self.viewer):
            raise ValueError("A controller's memory belongs to one game and seat")
        self.game_id, self.viewer = identity
        relevant = {"crew_selected", "pledges_revealed", "vote", "attempt_resolved", "reports_revealed"}
        for event in observation["history"]:
            if event["id"] > self.last_event_id:
                if event["type"] in relevant:
                    self.events.append(deepcopy(event))
                self.last_event_id = event["id"]
        receipt = observation["private"]["last_contribution"]
        if receipt:
            self.own_deposits[str(receipt["attempt"])] = deepcopy(receipt)
        private = observation["private"]
        team = private["team"]
        self.desired_side = ("red" if team == "blue" else "blue") if private["objective"]["id"] == "contrarian" else team

    def snapshot(self):
        return deepcopy(vars(self))

    @classmethod
    def from_snapshot(cls, data):
        memory = cls()
        if set(data) != set(vars(memory)):
            raise ValueError("Unsupported evidence memory shape")
        memory.__dict__.update(deepcopy(data))
        return memory
