from __future__ import annotations

import asyncio
import base64
import socket
from contextlib import suppress
from types import SimpleNamespace
from typing import cast

import websockets

from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.protocol import decode, encode, msg_submit_report
from road_to_riches.server.reporting import (
    MAX_ATTACHMENT_BYTES,
    InGameReportService,
    validate_report,
)
from road_to_riches.server.server import GameServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ValidatingReportService:
    def __init__(self) -> None:
        self.valid_reports = 0

    def submit(self, payload, **_kwargs):
        validate_report(payload)
        self.valid_reports += 1
        return SimpleNamespace(issue_id=f"road_to_riches-report-{self.valid_reports}")


async def _connect_when_ready(uri: str):
    for _ in range(100):
        try:
            return await websockets.connect(uri)
        except OSError:
            await asyncio.sleep(0.01)
    raise AssertionError("test server did not start")


def _png_payload(size: int) -> dict:
    data = b"\x89PNG\r\n\x1a\n" + b"x" * (size - 8)
    return msg_submit_report(
        "bug",
        2,
        "Screenshot boundary",
        "Verify the decoded image limit through the real WebSocket transport.",
        player_id=0,
        attachment={
            "filename": "screenshot.png",
            "mime_type": "image/png",
            "data_base64": base64.b64encode(data).decode(),
        },
        game_id="default",
    )


def test_report_websocket_transport_preserves_connection_at_image_size_boundary():
    async def scenario() -> None:
        service = ValidatingReportService()
        server = GameServer(
            GameConfig(board_path="boards/test_board.json", num_players=2),
            num_humans=2,
            num_ai=0,
            shutdown_when_default_finished=False,
            report_service=cast(InGameReportService, service),
        )
        port = _free_port()
        server_task = asyncio.create_task(server.serve("127.0.0.1", port))
        ws = await _connect_when_ready(f"ws://127.0.0.1:{port}")
        try:
            assert decode(await ws.recv()) == {
                "msg": "assign_player",
                "player_id": 0,
                "game_id": "default",
            }

            await ws.send(encode(_png_payload(MAX_ATTACHMENT_BYTES)))
            assert decode(await ws.recv()) == {
                "msg": "report_result",
                "success": True,
                "issue_id": "road_to_riches-report-1",
                "game_id": "default",
            }

            await ws.send(encode(_png_payload(MAX_ATTACHMENT_BYTES + 1)))
            oversized = decode(await ws.recv())
            assert oversized["msg"] == "report_result"
            assert oversized["success"] is False
            assert "10 MiB" in oversized["error"]

            invalid_type = _png_payload(16)
            invalid_type["attachment"]["mime_type"] = "image/gif"
            await ws.send(encode(invalid_type))
            invalid = decode(await ws.recv())
            assert invalid["msg"] == "report_result"
            assert invalid["success"] is False
            assert "PNG, JPEG, or WebP" in invalid["error"]

            await ws.send(
                encode(
                    msg_submit_report(
                        "bug",
                        2,
                        "Connection survived",
                        "The same report draft can be retried after validation errors.",
                        player_id=0,
                        game_id="default",
                    )
                )
            )
            assert decode(await ws.recv())["success"] is True
            assert service.valid_reports == 2
        finally:
            await ws.close()
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task

    asyncio.run(scenario())
