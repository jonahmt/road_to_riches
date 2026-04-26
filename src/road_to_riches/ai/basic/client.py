"""Basic AI client that connects to the game server via WebSocket.

Runs as a standalone process, spawned by the server. Connects to the
server, identifies with its assigned player_id, and responds to input
requests using a greedy suit-collector strategy.

See bead road_to_riches-ae5 for full strategy specification.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time

import websockets

from road_to_riches.ai.basic.pathfinder import (
    bfs_distances,
    find_bank_squares,
    next_step_toward,
    plan_route,
)
from road_to_riches.engine.property import max_capital
from road_to_riches.models.game_state import GameState
from road_to_riches.models.serialize import game_state_from_dict
from road_to_riches.models.square_type import SquareType
from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    decode,
    encode,
    msg_identify,
    msg_input_response,
)

logger = logging.getLogger(__name__)

# Districts where AI owns shops get this multiplier in stock buying score
OWN_DISTRICT_WEIGHT = 1.5

# Max auction bid as a multiple of shop value
AUCTION_BID_MULTIPLIER = 3


class BasicAIClient:
    """Greedy suit-collector AI.

    Plans an optimal BFS tour through uncollected suit squares and bank,
    always buys affordable shops, and buys stock in the highest-capital district.
    """

    def __init__(self, player_id: int, delay: float = 0.5) -> None:
        self.player_id = player_id
        self.delay = delay
        self.state: GameState | None = None
        self._route: list[int] = []  # planned tour of square IDs to visit

    def _player(self):
        assert self.state is not None
        return self.state.get_player(self.player_id)

    def _replan(self) -> None:
        """Recompute the promotion tour based on current state."""
        if self.state is None:
            return
        player = self._player()
        self._route = plan_route(
            self.state.board,
            player.position,
            player.suits,
        )
        logger.debug("Route planned: %s", self._route)

    @property
    def _next_target(self) -> int | None:
        """The next square ID the AI is heading toward."""
        return self._route[0] if self._route else None

    def decide(self, req: InputRequest) -> object:
        """Make a decision for the given input request."""
        if req.player_id != self.player_id:
            return None

        time.sleep(self.delay)

        # Replan route before making path decisions
        if req.type in (InputRequestType.CHOOSE_PATH, InputRequestType.PRE_ROLL):
            self._replan()

        handler = _HANDLERS.get(req.type, _default_handler)
        return handler(self, req)


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------

def _handle_pre_roll(ai: BasicAIClient, req: InputRequest) -> str:
    return "roll"


def _handle_choose_path(ai: BasicAIClient, req: InputRequest) -> int:
    choices = req.data.get("choices", [])
    if not choices or ai.state is None:
        return choices[0]["square_id"] if choices else 0

    choice_ids = [c["square_id"] for c in choices]
    target = ai._next_target

    if target is not None:
        return next_step_toward(ai.state.board, ai._player().position, target, choice_ids)

    # No target (shouldn't happen), pick first
    return choice_ids[0]


def _handle_confirm_stop(ai: BasicAIClient, req: InputRequest) -> bool:
    return True


def _handle_buy_shop(ai: BasicAIClient, req: InputRequest) -> bool:
    cost = req.data.get("cost", 0)
    cash = req.data.get("cash", 0)
    return cash >= cost


def _handle_invest(ai: BasicAIClient, req: InputRequest) -> tuple[int, int] | None:
    """Invest max into the owned shop with lowest current value.

    Prioritize shops in districts where AI owns stock.
    """
    if ai.state is None:
        return None

    investable = req.data.get("investable", [])
    if not investable:
        return None

    player = ai._player()
    cash = req.data.get("cash", player.ready_cash)
    if cash <= 0:
        return None

    # Separate into stock-district shops and others
    stock_districts = set(player.owned_stock.keys())
    in_stock_district = [s for s in investable if s.get("district") in stock_districts]
    candidates = in_stock_district if in_stock_district else investable

    # Pick the one with lowest current value
    best = min(candidates, key=lambda s: s.get("current_value", 999999))
    amount = min(cash, best.get("max_capital", 0))
    if amount <= 0:
        return None

    return (best["square_id"], amount)


def _handle_buy_stock(ai: BasicAIClient, req: InputRequest) -> tuple[int, int] | None:
    """Buy max stock in district with highest weighted max_capital."""
    if ai.state is None:
        return None

    stocks = req.data.get("stocks", [])
    cash = req.data.get("cash", 0)
    if not stocks or cash <= 0:
        return None

    board = ai.state.board
    player = ai._player()
    owned_districts = set()
    for sq_id in player.owned_properties:
        sq = board.squares[sq_id]
        if sq.property_district is not None:
            owned_districts.add(sq.property_district)

    # Score each district by total max_capital of ALL shops in it
    district_scores: dict[int, float] = {}
    for sq in board.squares:
        if sq.type == SquareType.SHOP and sq.property_district is not None and sq.property_owner is not None:
            mc = max_capital(board, sq)
            d = sq.property_district
            district_scores[d] = district_scores.get(d, 0) + mc

    # Apply weight for own districts
    for d in owned_districts:
        if d in district_scores:
            district_scores[d] *= OWN_DISTRICT_WEIGHT

    if not district_scores:
        return None

    # Pick highest scoring district
    best_district = max(district_scores, key=lambda d: district_scores[d])

    # Find price for that district
    price = None
    for s in stocks:
        if s["district_id"] == best_district:
            price = s["price"]
            break

    if price is None or price <= 0:
        return None

    quantity = cash // price
    held = ai._player().owned_stock.get(best_district, 0)
    quantity = min(quantity, 99 - held)
    if quantity <= 0:
        return None

    return (best_district, quantity)


def _handle_sell_stock(ai: BasicAIClient, req: InputRequest) -> tuple[int, int] | None:
    return None


def _handle_cannon_target(ai: BasicAIClient, req: InputRequest) -> int:
    """Pick the target player whose position brings AI closest to its next promotion target.

    The engine sends targets as [{"player_id": int, "position": int}] and
    expects the chosen target's player_id back.
    """
    targets = req.data.get("targets", [])
    if not targets:
        return 0
    if ai.state is None:
        return targets[0]["player_id"]

    next_target = ai._next_target
    if next_target is None:
        return targets[0]["player_id"]

    target_dists = bfs_distances(ai.state.board, next_target)

    best = targets[0]
    best_dist = 999999
    for t in targets:
        sq_id = t["position"]  # the square the target player currently occupies
        d = target_dists.get(sq_id, 999999)
        if d < best_dist:
            best_dist = d
            best = t

    return best["player_id"]


def _handle_vacant_plot_type(ai: BasicAIClient, req: InputRequest) -> str:
    """Randomly choose between checkpoint and tax office."""
    options = req.data.get("options", [])
    if not options:
        return SquareType.VP_CHECKPOINT.value
    return random.choice(options)


def _handle_forced_buyout(ai: BasicAIClient, req: InputRequest) -> bool:
    return False


def _handle_auction_bid(ai: BasicAIClient, req: InputRequest) -> int | None:
    """Bid if AI already owns a shop in this district, up to 3x shop value."""
    if ai.state is None:
        return None

    square_id = req.data.get("square_id")
    if square_id is None:
        return None

    sq = ai.state.board.squares[square_id]
    player = ai._player()

    # Check if we own a shop in this district
    if sq.property_district is not None:
        owns_in_district = any(
            ai.state.board.squares[sid].property_district == sq.property_district
            for sid in player.owned_properties
        )
        if owns_in_district and sq.shop_current_value is not None:
            max_bid = min(
                sq.shop_current_value * AUCTION_BID_MULTIPLIER,
                req.data.get("cash", 0),
            )
            min_bid = req.data.get("min_bid", 0)
            if max_bid >= min_bid:
                return min_bid  # bid the minimum to try to win cheaply
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


def _handle_liquidation(ai: BasicAIClient, req: InputRequest) -> tuple[str, int, int]:
    """Sell stock first (all shares of the first district), then shops."""
    options = req.data.get("options", {})

    stock = options.get("stock") or {}
    if stock:
        district_id, info = next(iter(stock.items()))
        return ("stock", int(district_id), int(info.get("quantity", 0)))

    shops = options.get("shops") or []
    if shops:
        return ("shop", shops[0]["square_id"], 0)

    return ("shop", 0, 0)


def _handle_script_decision(ai: BasicAIClient, req: InputRequest) -> object:
    """Pick the first option by default."""
    options = req.data.get("options", {})
    if options:
        return next(iter(options.values()))
    return None


def _handle_choose_any_square(ai: BasicAIClient, req: InputRequest) -> int:
    """Choose the square closest to the AI's next promotion target.

    Excludes the AI's current position — warping to where we already
    stand is wasteful (the venture card is consumed for nothing).
    """
    squares = req.data.get("squares", [])
    if not squares or ai.state is None:
        return squares[0]["square_id"] if squares else 0

    current_pos = ai._player().position
    candidates = [s for s in squares if s["square_id"] != current_pos]
    if not candidates:
        candidates = squares

    # Replan so _next_target reflects suits collected on this turn
    # (e.g. AI just landed on the suit that was its previous target).
    ai._replan()
    next_target = ai._next_target

    if next_target is not None:
        target_dists = bfs_distances(ai.state.board, next_target)
        best = min(candidates, key=lambda s: target_dists.get(s["square_id"], 999999))
        return best["square_id"]

    # No target — pick bank squares first, then random
    bank_squares = find_bank_squares(ai.state.board)
    for s in candidates:
        if s["square_id"] in bank_squares:
            return s["square_id"]
    return random.choice(candidates)["square_id"]


def _handle_choose_venture_cell(ai: BasicAIClient, req: InputRequest) -> list[int]:
    """Pick a venture grid cell that maximizes line-building potential.

    Strategy: score each unclaimed cell by counting how many adjacent cells
    (in all 4 axes) are already owned by this player, then pick the best.
    Ties broken randomly.
    """
    cells = req.data.get("cells", [])
    if not cells:
        return [0, 0]

    player_id = ai.player_id
    size = len(cells)

    # Find unclaimed cells
    unclaimed = []
    for r in range(size):
        for c in range(size):
            if cells[r][c] is None:
                unclaimed.append((r, c))

    if not unclaimed:
        return [0, 0]

    def count_dir(r: int, c: int, dr: int, dc: int) -> int:
        count = 0
        r, c = r + dr, c + dc
        while 0 <= r < size and 0 <= c < size:
            if cells[r][c] != player_id:
                break
            count += 1
            r += dr
            c += dc
        return count

    def score_cell(r: int, c: int) -> int:
        axes = [
            ((0, 1), (0, -1)),
            ((1, 0), (-1, 0)),
            ((1, 1), (-1, -1)),
            ((1, -1), (-1, 1)),
        ]
        total = 0
        for (dr1, dc1), (dr2, dc2) in axes:
            line_len = 1 + count_dir(r, c, dr1, dc1) + count_dir(r, c, dr2, dc2)
            if line_len >= 3:
                total += line_len * 10  # weight longer lines heavily
            else:
                total += line_len
        return total

    # Score all unclaimed cells, pick best (random tiebreak)
    best_score = -1
    best_cells = []
    for r, c in unclaimed:
        s = score_cell(r, c)
        if s > best_score:
            best_score = s
            best_cells = [(r, c)]
        elif s == best_score:
            best_cells.append((r, c))

    chosen = random.choice(best_cells)
    return list(chosen)


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
    InputRequestType.SCRIPT_DECISION: _handle_script_decision,
    InputRequestType.CHOOSE_ANY_SQUARE: _handle_choose_any_square,
    InputRequestType.CHOOSE_VENTURE_CELL: _handle_choose_venture_cell,
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
