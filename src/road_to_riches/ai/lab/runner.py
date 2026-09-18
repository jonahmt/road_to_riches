"""Reproducible no-animation matches using the unchanged production rules."""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from pathlib import Path

from road_to_riches.ai.basic.player_input import BasicAIPlayerInput
from road_to_riches.ai.lab.policies import Lab
from road_to_riches.ai.lab.simulation import PlanningGameLoop
from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.events.turn_events import AdvanceTurnEvent, TurnEvent
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.protocol import InputRequest


class LabInput(BasicAIPlayerInput):
    def __init__(self, lab):
        super().__init__(list(range(len(lab.policies))), delay=0, presentation_delay=0)
        self.lab = lab

    def _decide(self, state, player_id, request_type, data=None):
        return self.lab.decide(state, InputRequest(request_type, player_id, data or {}))

    def notify_dice(self, *args, **kwargs):
        pass


def match(
    board,
    profiles,
    seed,
    *,
    target=None,
    model=None,
    max_turns=600,
    samples=2,
    horizon=4,
    on_decision=None,
    replay=False,
):
    random.seed(seed)
    lab = Lab(profiles, model=model, seed=seed, samples=samples, horizon=horizon)
    lab.on_decision = on_decision
    inp = LabInput(lab)
    loop = PlanningGameLoop(
        GameConfig(board, num_players=len(profiles), starting_player_index=0), inp
    )
    loop.lab = lab
    if target is not None:
        loop.state.board.target_networth = target
    loop.pipeline.enqueue(TurnEvent(player_id=0))
    start = time.perf_counter()
    turns = 0
    frames = []
    event_counts = Counter()
    for _ in range(max_turns * 100):
        if loop.game_over or turns >= max_turns:
            break
        event = loop.pipeline.process_next(loop.state)
        if event is None:
            raise RuntimeError("Engine queue empty before game ended")
        loop._dispatch(event)
        loop._log_event(event)
        event_counts[type(event).__name__] += 1
        if isinstance(event, AdvanceTurnEvent):
            turns += 1
            if replay:
                frames.append(
                    {
                        "turn": turns,
                        "state": game_state_to_dict(loop.state),
                        "logs": inp.messages[-12:],
                        "decision_count": len(lab.trace),
                    }
                )
        # Historical events are not required for gameplay and can retain large snapshots.
        if len(loop.pipeline.history) > 500:
            loop.pipeline.history.clear()
    if loop.game_over and replay:
        frames.append(
            {
                "turn": turns + 1,
                "terminal": True,
                "state": game_state_to_dict(loop.state),
                "logs": inp.messages[-12:],
                "decision_count": len(lab.trace),
            }
        )
    elapsed = time.perf_counter() - start
    return {
        "board": board,
        "seed": seed,
        "profiles": profiles,
        "target": loop.state.board.target_networth,
        "turns": turns + int(loop.game_over),
        "seconds": elapsed,
        "winner": loop.winner,
        "finished": loop.game_over,
        "net_worth": [loop.state.net_worth(p) for p in loop.state.players],
        "bankrupt": [p.bankrupt for p in loop.state.players],
        "events": dict(event_counts),
        "decisions": lab.trace,
        "frames": frames,
        "final": game_state_to_dict(loop.state),
    }


def tournament_game(job):
    from road_to_riches.ai.lab.network import Network

    board, names, seed, target, model_path, path, samples, horizon, replay, *guidance = job
    result = match(
        board,
        names,
        seed,
        target=target,
        model=Network.load(model_path, guidance=guidance[0] if guidance else "both"),
        samples=samples,
        horizon=horizon,
        replay=replay,
    )
    path = Path(path)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result))
    temporary.replace(path)
    return {
        k: result[k]
        for k in ("board", "seed", "profiles", "winner", "turns", "seconds", "finished")
    }
