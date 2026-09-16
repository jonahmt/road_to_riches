"""Public board graph inputs for a trainable message-passing encoder."""

from __future__ import annotations

from road_to_riches.engine.property import current_rent, max_capital
from road_to_riches.models.square_type import SquareType

NODE_DIM = 12
GRAPH_DIM = NODE_DIM * 2
POOL_DIM = 3
GRAPH_HIDDEN = 8


def graph_input(state, pid):
    p = state.players[pid]
    nodes = []
    neighbors = []
    for sq in state.board.squares:
        adj = {n for wp in sq.waypoints for n in wp.to_ids}
        for dest in (sq.doorway_destination, sq.backstreet_destination):
            if dest is not None:
                adj.add(dest)
        neighbors.append(sorted(adj))
        nodes.append(
            [
                (sq.shop_current_value or 0) / 1000,
                current_rent(state.board, sq) / 1000,
                max_capital(state.board, sq) / 1000,
                float(sq.property_owner == pid),
                float(sq.property_owner not in (None, pid)),
                float(sq.property_owner is None),
                float(sq.type == SquareType.BANK),
                float(sq.suit is not None and not p.suits.get(sq.suit, 0)),
                float(sq.id == p.position),
                sum(o.position == sq.id for o in state.players if o.player_id != pid) / 3,
                p.owned_stock.get(sq.property_district, 0) / 100,
                len(adj) / 4,
            ]
        )
    messages = []
    n = len(nodes)
    for i, row in enumerate(nodes):
        adj = neighbors[i]
        mean = [sum(nodes[j][f] for j in adj) / max(1, len(adj)) for f in range(NODE_DIM)]
        messages.append(row + mean)
    owned = max(1, len(p.owned_properties))
    pooling = [
        [1 / n] * n,
        [float(sq.id == p.position) for sq in state.board.squares],
        [float(sq.property_owner == pid) / owned for sq in state.board.squares],
    ]
    return messages, pooling
