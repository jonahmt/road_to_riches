"""Basic AI client that connects to the game server via WebSocket.

Runs as a standalone process, spawned by the server. Connects to the
server, identifies with its assigned player_id, and responds to input
requests automatically using a simple greedy strategy.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

import websockets

from road_to_riches.models.game_state import GameState
from road_to_riches.models.serialize import game_state_from_dict
from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    decode,
    encode,
    msg_identify,
    msg_input_response,
)

logger = logging.getLogger(__name__)


class BasicAIClient:
    """A simple AI client that plays the game automatically.

    Strategy (to be implemented):
    - Pathfinding: BFS shortest path to collect all 4 suits then bank
    - Shop buying: always buy when affordable
    - Stock buying: buy in district with highest total capital
    - Everything else: sensible defaults
    """

    def __init__(self, player_id: int, delay: float = 0.5) -> None:
        self.player_id = player_id
        self.delay = delay
        self.state: GameState | None = None

    def decide(self, req: InputRequest) -> object:
        """Make a decision for the given input request.

        Returns the response value to send back to the server.
        """
        # Only respond to requests for our player
        if req.player_id != self.player_id:
            return None

        time.sleep(self.delay)

        handler = _HANDLERS.get(req.type, _default_handler)
        return handler(self, req)


def _handle_pre_roll(ai: BasicAIClient, req: InputRequest) -> str:
    return "roll"


def _handle_choose_path(ai: BasicAIClient, req: InputRequest) -> int:
    # For now, always pick the first choice
    choices = req.data.get("choices", [])
    if choices:
        return choices[0]["square_id"]
    return 0


def _handle_confirm_stop(ai: BasicAIClient, req: InputRequest) -> bool:
    return True


def _handle_buy_shop(ai: BasicAIClient, req: InputRequest) -> bool:
    # Buy if we can afford it
    cost = req.data.get("cost", 0)
    cash = req.data.get("cash", 0)
    return cash >= cost


def _handle_invest(ai: BasicAIClient, req: InputRequest) -> tuple[int, int] | None:
    # Skip investment for now
    return None


def _handle_buy_stock(ai: BasicAIClient, req: InputRequest) -> tuple[int, int] | None:
    # Skip stock buying for now
    return None


def _handle_sell_stock(ai: BasicAIClient, req: InputRequest) -> tuple[int, int] | None:
    return None


def _handle_cannon_target(ai: BasicAIClient, req: InputRequest) -> int:
    targets = req.data.get("targets", [])
    if targets:
        return targets[0]["square_id"]
    return 0


def _handle_vacant_plot_type(ai: BasicAIClient, req: InputRequest) -> str:
    options = req.data.get("options", [])
    return options[0] if options else "SHOP"


def _handle_forced_buyout(ai: BasicAIClient, req: InputRequest) -> bool:
    return False


def _handle_auction_bid(ai: BasicAIClient, req: InputRequest) -> int | None:
    return None


def _handle_shop_auction(ai: BasicAIClient, req: InputRequest) -> int | None:
    return None


def _handle_shop_buy(ai: BasicAIClient, req: InputRequest) -> tuple | None:
    return None


def _handle_shop_sell(ai: BasicAIClient, req: InputRequest) -> tuple | None:
    return None


def _handle_accept_offer(ai: BasicAIClient, req: InputRequest) -> str:
    return "reject"


def _handle_counter_price(ai: BasicAIClient, req: InputRequest) -> int:
    return req.data.get("original_price", 0)


def _handle_renovate(ai: BasicAIClient, req: InputRequest) -> str | None:
    return None


def _handle_trade(ai: BasicAIClient, req: InputRequest) -> dict | None:
    return None


def _handle_liquidation(ai: BasicAIClient, req: InputRequest) -> tuple[str, int]:
    # Sell first available shop
    options = req.data.get("options", {})
    if "shops" in options and options["shops"]:
        shop = options["shops"][0]
        return ("sell_shop", shop["square_id"])
    if "stocks" in options and options["stocks"]:
        stock = options["stocks"][0]
        return ("sell_stock", stock["district_id"])
    return ("bankrupt", 0)


def _default_handler(ai: BasicAIClient, req: InputRequest) -> object:
    logger.warning("No handler for request type: %s", req.type)
    return None


_HANDLERS: dict[InputRequestType, object] = {
    InputRequestType.PRE_ROLL: _handle_pre_roll,
    InputRequestType.CHOOSE_PATH: _handle_choose_path,
    InputRequestType.CONFIRM_STOP: _handle_confirm_stop,
    InputRequestType.BUY_SHOP: _handle_buy_shop,
    InputRequestType.INVEST: _handle_invest,
    InputRequestType.BUY_STOCK: _handle_buy_stock,
    InputRequestType.SELL_STOCK: _handle_sell_stock,
    InputRequestType.CANNON_TARGET: _handle_cannon_target,
    InputRequestType.VACANT_PLOT_TYPE: _handle_vacant_plot_type,
    InputRequestType.FORCED_BUYOUT: _handle_forced_buyout,
    InputRequestType.AUCTION_BID: _handle_auction_bid,
    InputRequestType.CHOOSE_SHOP_AUCTION: _handle_shop_auction,
    InputRequestType.CHOOSE_SHOP_BUY: _handle_shop_buy,
    InputRequestType.CHOOSE_SHOP_SELL: _handle_shop_sell,
    InputRequestType.ACCEPT_OFFER: _handle_accept_offer,
    InputRequestType.COUNTER_PRICE: _handle_counter_price,
    InputRequestType.RENOVATE: _handle_renovate,
    InputRequestType.TRADE: _handle_trade,
    InputRequestType.LIQUIDATION: _handle_liquidation,
}


async def run(host: str, port: int, player_id: int, delay: float = 0.5) -> None:
    """Connect to the server and play the game."""
    uri = f"ws://{host}:{port}"
    ai = BasicAIClient(player_id=player_id, delay=delay)

    async with websockets.connect(uri) as ws:
        # Identify ourselves to the server
        await ws.send(encode(msg_identify(player_id)))
        logger.info("AI player %d connected to %s", player_id, uri)

        async for raw in ws:
            msg = decode(raw)
            msg_type = msg.get("msg")

            if msg_type == "state_sync":
                ai.state = game_state_from_dict(msg["state"])

            elif msg_type == "input_request":
                req = InputRequest(
                    type=InputRequestType(msg["type"]),
                    player_id=msg["player_id"],
                    data=msg.get("data", {}),
                )
                response = ai.decide(req)
                if response is not None:
                    if isinstance(response, tuple):
                        response = list(response)
                    await ws.send(encode(msg_input_response(response, player_id)))

            elif msg_type == "log":
                logger.debug("[log] %s", msg.get("text"))

            elif msg_type == "dice":
                logger.debug("[dice] %d (remaining: %d)", msg["value"], msg["remaining"])

            elif msg_type == "game_over":
                winner = msg.get("winner")
                logger.info("Game over! Winner: %s", winner)
                break

    logger.info("AI player %d disconnected", player_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic AI client")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--player-id", type=int, required=True)
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Response delay in seconds")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format=f"[AI-{args.player_id}] %(levelname)s %(message)s",
    )
    logging.getLogger("websockets").setLevel(logging.WARNING)

    asyncio.run(run(args.host, args.port, args.player_id, args.delay))


if __name__ == "__main__":
    main()
