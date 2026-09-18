"""Exact event-dispatch branching for opt-in AI experiments.

A snapshot is taken AFTER event.execute and BEFORE GameLoop._dispatch. Replaying
all earlier decisions inside that dispatch reaches the same decision, including
nested auctions and scripted prompts. Rollouts use the production engine.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from road_to_riches.ai.basic.player_input import BasicAIPlayerInput
from road_to_riches.ai.lab.strategy import StrategicPolicy
from road_to_riches.engine.game_loop import GameLog, GameLoop
from road_to_riches.events.pipeline import EventPipeline
from road_to_riches.events.turn_events import AdvanceTurnEvent
from road_to_riches.protocol import InputRequest


class RolloutLimit(Exception):
    pass


def clone_loop(source, player_input):
    loop = copy.copy(source)
    # Deepcopy only mutable simulation state; no sockets, locks, callbacks or logs.
    for key in ("state", "_move_snapshots", "_move_log_checkpoints", "_path_taken"):
        setattr(loop, key, copy.deepcopy(getattr(source, key)))
    loop.pipeline = EventPipeline()
    loop.pipeline._queue = copy.deepcopy(source.pipeline._queue)
    loop.input = player_input
    loop.log = GameLog()
    loop.diagnostic_log = None
    loop.lab = None
    loop._lab_depth = 0
    return loop


@dataclass
class DecisionContext:
    snapshot: GameLoop
    event: object
    policies: list
    random_state: object
    prefix: list = field(default_factory=list)

    def rollout(self, req, action, seed, turns=4):
        outer_rng = random.getstate()
        try:
            random.setstate(self.random_state)
            replay = ReplayInput(
                self.prefix + [(req.player_id, req.type, action)], self.policies, seed
            )
            loop = clone_loop(self.snapshot, replay)
            completed = 0
            try:
                loop._dispatch(copy.deepcopy(self.event))
                if replay.index != len(replay.prefix):
                    raise RuntimeError("Branch did not reach the requested decision")
                for _ in range(1500):
                    if loop.game_over or completed >= turns:
                        break
                    event = loop.pipeline.process_next(loop.state)
                    if event is None:
                        break
                    loop._dispatch(event)
                    if isinstance(event, AdvanceTurnEvent):
                        completed += 1
                else:
                    raise RolloutLimit()
            except RolloutLimit:
                if replay.index != len(replay.prefix):
                    raise RuntimeError("Rollout exhausted before candidate was applied") from None
            return loop.state, loop.winner
        finally:
            random.setstate(outer_rng)


class ReplayInput(BasicAIPlayerInput):
    def __init__(self, prefix, source_policies, seed):
        super().__init__(list(range(len(source_policies))), delay=0, presentation_delay=0)
        self.prefix, self.index, self.decisions = prefix, 0, 0
        self.seed = seed
        self.policies = [
            StrategicPolicy(i, params=getattr(p, "params", None))
            for i, p in enumerate(source_policies)
        ]
        for p, source in zip(self.policies, source_policies):
            p.deal_attempted = getattr(source, "deal_attempted", False)

    def _decide(self, state, player_id, request_type, data=None):
        self.decisions += 1
        if self.decisions > 160:
            raise RolloutLimit()
        req = InputRequest(request_type, player_id, data or {})
        if self.index < len(self.prefix):
            pid, kind, action = self.prefix[self.index]
            if (pid, kind) != (player_id, request_type):
                raise RuntimeError(
                    f"Branch replay diverged: {(pid, kind)} != {(player_id, request_type)}"
                )
            self.index += 1
            if self.index == len(self.prefix):
                # Earlier random events are already observed at this decision.
                # Only now replace future randomness, never forecast the live RNG.
                random.seed(self.seed)
                if state.venture_deck is not None:
                    state.venture_deck.remaining = list(state.venture_deck.full_deck)
                    random.shuffle(state.venture_deck.remaining)
            self.policies[player_id].record(req, action)
            return copy.deepcopy(action)
        return self.policies[player_id].choose(state, req)

    def notify(self, state, log):
        log.clear()

    def notify_dice(self, *args, **kwargs):
        pass


class PlanningGameLoop(GameLoop):
    """Production behavior with isolated simulation snapshots around dispatch."""

    lab = None
    _lab_depth = 0

    def _dispatch(self, event):
        outer = self._lab_depth == 0 and self.lab is not None
        if outer:
            policies = [
                StrategicPolicy(i, params=getattr(p, "params", None))
                for i, p in enumerate(self.lab.policies)
            ]
            for p, source in zip(policies, self.lab.policies):
                p.deal_attempted = getattr(source, "deal_attempted", False)
            self.lab.context = DecisionContext(
                clone_loop(self, None), copy.deepcopy(event), policies, random.getstate()
            )
        self._lab_depth += 1
        try:
            return super()._dispatch(event)
        finally:
            self._lab_depth -= 1
            if outer:
                self.lab.context = None
