"""Shared candidate generation and transparent strategic evaluation.

No policy reads deck order or game RNG. Monetary amounts are deliberately
sampled candidates, not an assertion that the whole legal action space is searched.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.board.pathfinding import get_next_squares
from road_to_riches.engine.property import current_rent, max_capital
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit
from road_to_riches.protocol import InputRequest
from road_to_riches.protocol import InputRequestType as T


@dataclass
class Candidate:
    action: object
    score: float
    reason: str


def route_distance(state, pid, position=None, previous=None):
    """Directed BFS over (square, entry direction, collected suits).

    Finds a legal bank route when eligible; otherwise the shortest promotion tour.
    Rotating suits are evaluated at their currently visible value.
    """
    p = state.players[pid]
    start = p.position if position is None else position
    prev = p.from_square if position is None else previous
    suits = [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]
    mask = sum(1 << i for i, s in enumerate(suits) if p.suits.get(s, 0))
    if position is not None:
        arrival = state.board.squares[start]
        if arrival.suit in suits:
            mask |= 1 << suits.index(arrival.suit)
    winning = state.net_worth(p) >= state.board.target_networth
    wild = p.suits.get(Suit.WILD, 0)
    queue = deque([(start, prev, mask, 0)])
    seen = {(start, prev, mask)}
    while queue:
        sqid, frm, collected, dist = queue.popleft()
        sq = state.board.squares[sqid]
        if sq.type == SquareType.BANK and (winning or collected.bit_count() + wild >= 4):
            return dist
        for nxt in get_next_squares(state.board, sqid, frm):
            tile = state.board.squares[nxt]
            next_mask = collected
            if tile.suit in suits:
                next_mask |= 1 << suits.index(tile.suit)
            # Doorway traversal is compulsory and costs no extra die step.
            dest = tile.doorway_destination
            node = (dest, None, next_mask) if dest is not None else (nxt, sqid, next_mask)
            if node not in seen:
                seen.add(node)
                queue.append((*node, dist + 1))
    return len(state.board.squares) * 4


def shop_value(state, pid, sid):
    """Reservation value includes the marginal benefit of district consolidation."""
    sq = state.board.squares[sid]
    value = sq.shop_current_value or 0
    peers = [
        s
        for s in state.board.squares
        if s.property_district == sq.property_district and s.shop_current_value is not None
    ]
    owned = sum(s.property_owner == pid and s.id != sid for s in peers)
    shares = state.players[pid].owned_stock.get(sq.property_district, 0)
    return (
        value * (1.05 + 0.55 * owned + (0.6 if owned == len(peers) - 1 and owned else 0))
        + shares * 0.5
    )


def reserve(state, pid):
    p = state.players[pid]
    rents = [
        current_rent(state.board, sq)
        for sq in state.board.squares
        if sq.property_owner not in (None, pid) and sq.type == SquareType.SHOP
    ]
    # Avoid immobilizing all cash because of one far-away expensive shop.
    return min(500, max(100, (sum(rents) / max(1, len(rents))) * 2, p.level * 40))


def features(state, pid):
    """Board-size-independent state embedding, solely from public game facts."""
    p = state.players[pid]
    target = max(1, state.board.target_networth)
    worth = state.net_worth(p)
    others = [state.net_worth(o) for o in state.players if o.player_id != pid and not o.bankrupt]
    district_counts = {}
    rents = capacity = shop_total = 0
    for sid in p.owned_properties:
        sq = state.board.squares[sid]
        district_counts[sq.property_district] = district_counts.get(sq.property_district, 0) + 1
        rents += current_rent(state.board, sq)
        capacity += max_capital(state.board, sq)
        shop_total += sq.shop_current_value or 0
    stocks = sum(q * state.stock.get_price(d).current_price for d, q in p.owned_stock.items())
    dist = route_distance(state, pid)
    return [
        worth / target,
        p.ready_cash / target,
        shop_total / target,
        stocks / target,
        (worth - max(others, default=0)) / target,
        sum(bool(p.suits.get(s, 0)) for s in (Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB)) / 4,
        min(4, p.suits.get(Suit.WILD, 0)) / 4,
        p.level / 10,
        len(p.owned_properties) / max(1, len(state.board.squares)),
        rents / target,
        capacity / target,
        sum(n * n for n in district_counts.values()) / 25,
        min(100, dist) / 40,
        float(worth >= target),
        float(p.has_all_suits),
        float(p.bankrupt),
        max(0, reserve(state, pid) - p.ready_cash) / target,
        sum(others) / max(1, len(others)) / target,
        float(state.current_player.player_id == pid),
        len(state.active_players) / 4,
    ]


def evaluate(state, pid, winner=None):
    if winner is not None:
        return 12.0 if winner == pid else -12.0
    p = state.players[pid]
    if p.bankrupt:
        return -12.0
    f = features(state, pid)
    # Net worth alone must not encourage an eligible player to wander forever.
    return (
        2.4 * f[0]
        + 0.7 * f[4]
        + 0.3 * f[1]
        + 1.0 * f[9]
        + 0.2 * f[10]
        + 0.4 * f[11]
        - (2.0 if f[13] else 0.55) * f[12]
        - 0.9 * f[16]
    )


def offer_surplus(state, pid, offer):
    p = state.players[pid]
    if offer.get("type") == "trade":
        proposer = offer["proposer_id"]
        giving = offer["offer_shops"] if pid == proposer else offer["request_shops"]
        taking = offer["request_shops"] if pid == proposer else offer["offer_shops"]
        gold = offer.get("gold_offer", 0) * (1 if pid == proposer else -1)
        surplus = sum(shop_value(state, pid, s) for s in taking)
        surplus -= sum(shop_value(state, pid, s) for s in giving) + gold
    else:
        sid, price = offer["square_id"], offer["price"]
        gold = price if pid == offer["buyer_id"] else -price
        surplus = shop_value(state, pid, sid) - price
        if pid == offer["seller_id"]:
            surplus = -surplus
    if gold > max(0, p.ready_cash - reserve(state, pid) / 2):
        return -100000.0
    return surplus


class StrategicPolicy:
    name = "strategic"

    def __init__(self, pid):
        self.pid = pid
        self.basic = BasicAIClient(pid, delay=0, presentation_delay=0)
        self.deal_attempted = False
        self.last_candidates = []

    def candidates(self, state, req):
        pid, p, d, t = self.pid, state.players[self.pid], req.data, req.type
        cash = p.ready_cash
        safe = max(0, cash - reserve(state, pid))
        choices = []

        def add(action, score, why):
            if not any(c.action == action for c in choices):
                choices.append(Candidate(action, float(score), why))

        if t == T.PRE_ROLL:
            add("roll", 0, "Advance toward promotion or victory")
            if not self.deal_attempted and state.net_worth(p) < state.board.target_networth:
                for action, prompt in [("buy_shop", T.CHOOSE_SHOP_BUY), ("trade", T.TRADE)]:
                    offers = self.candidates(state, InputRequest(prompt, pid))
                    if any(c.action is not None and c.score > 0 for c in offers):
                        add(action, 0.1, "One district-consolidation negotiation this turn")
            if cash < reserve(state, pid) / 2 and p.owned_stock and not self.deal_attempted:
                add("sell_stock", 0.2, "Restore cash reserve")
        elif t == T.CHOOSE_PATH:
            remaining = d.get("remaining", 1)
            for row in d.get("choices", []):
                sid = row["square_id"]
                sq = state.board.squares[sid]
                dist = route_distance(state, pid, sid, p.position)
                rent = current_rent(state.board, sq) if sq.property_owner not in (None, pid) else 0
                cost = (rent / max(100, cash + 1)) if remaining == 1 else 0
                add(sid, -dist / 10 - cost, "Legal route progress and landing cost")
        elif t == T.CHOOSE_ANY_SQUARE:
            for row in d.get("squares", []):
                sid = row["square_id"]
                add(
                    sid,
                    -route_distance(state, pid, sid, None) / 10,
                    "Warp toward bank or missing suits",
                )
        elif t == T.CANNON_TARGET:
            for row in d.get("targets", []):
                add(
                    row["player_id"],
                    -route_distance(state, pid, row["position"], None) / 10,
                    "Cannon destination advances route",
                )
        elif t in (T.BUY_SHOP, T.FORCED_BUYOUT):
            cost = d["cost"]
            add(False, 0, "Keep liquidity")
            if cost <= cash:
                benefit = shop_value(state, pid, d["square_id"]) - cost
                penalty = max(0, reserve(state, pid) / 2 - (cash - cost)) * 0.5
                add(True, (benefit - penalty) / 100, "Property value and district synergy")
        elif t == T.INVEST:
            add(None, 0, "Keep cash available")
            for shop in d.get("investable", []):
                limit = min(shop["max_capital"], int(safe))
                district = shop["district"]
                own = p.owned_stock.get(district, 0)
                opponent = max(
                    (o.owned_stock.get(district, 0) for o in state.players if o != p), default=0
                )
                for amount in sorted({limit // 2, limit}):
                    if amount > 0:
                        gain = amount * (0.04 * (own - 0.6 * opponent) + 0.12)
                        add(
                            (shop["square_id"], amount),
                            gain / 100,
                            "Stock exposure and rent growth",
                        )
        elif t == T.BUY_STOCK:
            add(None, 0, "Save cash for shops")
            for row in d.get("stocks", []):
                district, price = row["district_id"], row["price"]
                cap = sum(
                    max_capital(state.board, sq)
                    for sq in state.board.squares
                    if sq.property_district == district and sq.property_owner is not None
                )
                owncap = sum(
                    max_capital(state.board, state.board.squares[sid])
                    for sid in p.owned_properties
                    if state.board.squares[sid].property_district == district
                )
                limit = min(99, int(safe // max(1, price)))
                for qty in sorted({min(10, limit), limit // 2, limit}):
                    if qty > 0:
                        growth = 0.04 * (owncap * 0.5 + (cap - owncap) * 0.15)
                        add(
                            (district, qty),
                            qty * (growth + (price // 16 + 1 if qty >= 10 else 0)) / 100,
                            "Expected development and purchase price effect",
                        )
        elif t == T.SELL_STOCK:
            add(None, 0, "Retain investments")
            for district, held in p.owned_stock.items():
                price = state.stock.get_price(district).current_price
                qty = min(held, math.ceil(max(0, reserve(state, pid) - cash) / max(1, price)))
                if qty:
                    add((district, qty), 1, "Sell enough to restore reserve")
        elif t == T.AUCTION_BID:
            add(None, 0, "Pass auction")
            limit = min(safe, shop_value(state, pid, d["square_id"]))
            if 0 < d["min_bid"] <= limit:
                add(
                    d["min_bid"],
                    (limit - d["min_bid"]) / 100 + 0.01,
                    "Bid within reservation value",
                )
        elif t == T.CHOOSE_SHOP_BUY:
            add(None, 0, "No beneficial purchase")
            for sq in state.board.squares:
                if sq.property_owner in (None, pid) or sq.shop_current_value is None:
                    continue
                seller = sq.property_owner
                value = shop_value(state, pid, sq.id)
                ask = math.ceil(shop_value(state, seller, sq.id) * 1.08)
                if value > ask and ask <= safe:
                    add(
                        (seller, sq.id, ask),
                        (value - ask) / 100,
                        "Consolidate district at a fair premium",
                    )
        elif t == T.TRADE:
            add(None, 0, "No mutually beneficial exchange")
            for give in p.owned_properties:
                for other in state.active_players:
                    if other.player_id == pid:
                        continue
                    for take in other.owned_properties:
                        mine = shop_value(state, pid, take) - shop_value(state, pid, give)
                        theirs = shop_value(state, other.player_id, give) - shop_value(
                            state, other.player_id, take
                        )
                        gold = round((mine - theirs) / 2)
                        if (
                            mine - gold > 30
                            and theirs + gold > 30
                            and gold <= safe
                            and -gold <= other.ready_cash / 2
                        ):
                            add(
                                {
                                    "target_player_id": other.player_id,
                                    "offer_shops": [give],
                                    "request_shops": [take],
                                    "gold_offer": gold,
                                },
                                (mine - gold) / 100,
                                "Exchange isolated shops for stronger districts",
                            )
        elif t == T.ACCEPT_OFFER:
            surplus = offer_surplus(state, pid, d["offer"])
            add("reject", 0, "Terms below reservation value")
            add("accept", surplus / 100, "Evaluate property synergy and cash transfer")
            if -500 < surplus < 0:
                add("counter", 0.01, "Propose reservation price")
        elif t == T.COUNTER_PRICE:
            offer = d.get("offer", {})
            if offer.get("type") == "trade":
                surplus = offer_surplus(state, pid, offer)
                sign = 1 if pid == offer["proposer_id"] else -1
                price = round(offer["gold_offer"] + sign * surplus)
            elif "square_id" in offer:
                price = max(1, round(shop_value(state, pid, offer["square_id"])))
            else:
                price = d.get("original_price", 0)
            add(price, 0, "Reservation counteroffer")
        if not choices:
            self.basic.state = state
            # Isolate fallback randomness in the adapter; no strategic hidden state.
            add(self.basic.decide(req), 0, "Basic policy for this prompt")
        return sorted(choices, key=lambda c: c.score, reverse=True)

    def record(self, req, action):
        if req.type == T.PRE_ROLL:
            self.deal_attempted = action != "roll"
        elif req.type == T.CHOOSE_PATH:
            self.deal_attempted = False

    def choose(self, state, req, context=None):
        self.last_candidates = self.candidates(state, req)
        action = self.last_candidates[0].action
        self.record(req, action)
        return action
