"""Presentation-only socket peer for an in-process experimental policy."""

from __future__ import annotations

import argparse
import asyncio

import websockets

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.protocol import decode, encode, msg_identify


async def relay(host, port, pid, game_id):
    presenter = BasicAIClient(pid)
    async with websockets.connect(f"ws://{host}:{port}") as ws:
        await ws.send(encode(msg_identify(pid, game_id=game_id)))
        async for raw in ws:
            msg = decode(raw)
            if msg["msg"] == "presentation_request":
                ack = presenter.presentation_ack_message(
                    msg["request_id"],
                    msg["player_id"],
                    game_id=game_id,
                    presentation_type=msg["type"],
                    data=msg.get("data", {}),
                    coordinated=msg.get("coordinated", False),
                )
                if ack:
                    await ws.send(encode(ack))
            elif msg["msg"] == "playback_settings":
                presenter.playback_speed = float(msg.get("speed", 1))
            elif msg["msg"] == "game_over":
                return


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--port", required=True, type=int)
    p.add_argument("--player-id", required=True, type=int)
    p.add_argument("--game-id", required=True)
    a = p.parse_args()
    asyncio.run(relay(a.host, a.port, a.player_id, a.game_id))


if __name__ == "__main__":
    main()
