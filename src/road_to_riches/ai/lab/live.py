"""Opt-in, single-session live server. Existing servers remain untouched."""

from __future__ import annotations

import asyncio
import random
import subprocess
import sys

from road_to_riches.ai.lab.network import Network
from road_to_riches.ai.lab.policies import Lab
from road_to_riches.ai.lab.simulation import PlanningGameLoop
from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.protocol import InputRequestType, msg_input_request
from road_to_riches.server.server import GameServer
from road_to_riches.server.server_input import WebSocketPlayerInput
from road_to_riches.server.session import SessionError


class LabSocketInput(WebSocketPlayerInput):
    def __init__(self, loop, *, lab, game_id):
        super().__init__(loop, game_id=game_id)
        self.lab = lab

    def _request_input(self, req, state):
        if self.lab.profiles[req.player_id] != "human":
            self._send_state(state)
            if (
                self.pacer.enabled
                and req.type is InputRequestType.PRE_ROLL
                and self._introduced_player != req.player_id
            ):
                self._introduced_player = req.player_id
                self.pacer.run(game_state_to_dict(state), "turn_started", {}, req.player_id)
            self._pending_request = req
            self._broadcast(msg_input_request(req, game_id=self._game_id))
            try:
                return self.lab.decide(state, req)
            finally:
                self._pending_request = None
        response = super()._request_input(req, state)
        if self.lab.context is not None:
            self.lab.context.prefix.append((req.player_id, req.type, response))
        return response


class LabServer(GameServer):
    def __init__(self, config, profiles, model, *, target=None, seed=0, **kwargs):
        # The production launcher assumes humans occupy a prefix of seats.
        humans = sum(p == "human" for p in profiles)
        if profiles[:humans] != ["human"] * humans or len(profiles) != 4:
            raise ValueError("Use four profiles, with any human seats first")
        self.lab = Lab(profiles, model=model, seed=seed)
        self.target = target
        super().__init__(
            config,
            num_humans=humans,
            num_ai=4 - humans,
            create_default_session=True,
            reporting_enabled=False,
            **kwargs,
        )

    def _spawn_ai_clients(self, session, host, port):
        for pid in range(session.num_humans, session.config.num_players):
            command = [
                sys.executable,
                "-m",
                "road_to_riches.ai.lab.relay",
                "--host",
                host,
                "--port",
                str(port),
                "--player-id",
                str(pid),
                "--game-id",
                session.session_id,
            ]
            session.ai_processes.append(subprocess.Popen(command))

    def _settings_from_client_config(self, config):
        # Engine randomness is isolated serially within this dedicated process.
        raise SessionError("The AI laboratory supports only its default game")

    def _prepare_session(self, session):
        if session.player_input is None:
            session.attach_player_input(
                LabSocketInput(self._loop, lab=self.lab, game_id=session.session_id)
            )

    def _create_game_loop(self, session):
        loop = PlanningGameLoop(
            session.config, session.player_input, saved_state=session.saved_state
        )
        loop.lab = self.lab
        if self.target is not None:
            loop.state.board.target_networth = self.target
        return loop


def serve(model_path, profiles, port, target, seed, *, guidance="both"):
    random.seed(seed)
    model = Network.load(model_path, guidance=guidance)
    server = LabServer(
        GameConfig("boards/conversion_tests/trodain/trodain.json", starting_player_index=0),
        profiles,
        model,
        target=target,
        seed=seed,
        shutdown_when_default_finished=False,
    )
    print(
        f"AI lab ws://127.0.0.1:{port} | "
        + ", ".join(f"P{i}: {p}" for i, p in enumerate(profiles)),
        flush=True,
    )
    asyncio.run(server.serve("127.0.0.1", port))
