"""Portable small neural policy/value models. Inference uses only the stdlib.

Training uses optional NumPy, exported as inspectable versioned JSON weights.
Both the MLP baseline and the trainable message-passing encoder export the same
policy/value interface. No graph or ML runtime is needed at inference time.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from road_to_riches.protocol import InputRequestType

KINDS = [t.value for t in InputRequestType]
STATE_DIM = 20


def candidate_features(state, req, candidate):
    action = candidate.action
    pid = req.player_id
    p = state.players[pid]
    target = max(1, state.board.target_networth)
    numeric = []
    if isinstance(action, (list, tuple)):
        numeric = [float(x) for x in action if isinstance(x, (int, float))]
    elif isinstance(action, (int, float)):
        numeric = [float(action)]
    amount = numeric[-1] if len(numeric) > 1 else 0
    sid = req.data.get("square_id")
    if req.type.value in ("CHOOSE_PATH", "CHOOSE_ANY_SQUARE") and isinstance(action, int):
        sid = action
    elif req.type.value == "INVEST" and numeric:
        sid = int(numeric[0])
    value = rent = own = 0
    if sid is not None and 0 <= sid < len(state.board.squares):
        from road_to_riches.engine.property import current_rent

        sq = state.board.squares[sid]
        value = (sq.shop_current_value or 0) / target
        rent = current_rent(state.board, sq) / target
        own = float(sq.property_owner == pid)
    return [
        max(-10, min(10, candidate.score / 5)),
        amount / target,
        amount / max(100, p.ready_cash),
        value,
        rent,
        own,
        float(action is None or action is False or action == "reject"),
        float(action is True or action == "accept"),
        *[float(req.type.value == kind) for kind in KINDS],
    ]


class Network:
    def __init__(self, data):
        if data.get("version") != 1 or data.get("state_dim") != STATE_DIM:
            raise ValueError("Unsupported AI checkpoint format")
        self.data = data

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    @property
    def uses_graph(self):
        return "graph" in self.data["value"]

    def forward(self, x, head, graph=None):
        weights = self.data[head]
        if "graph" in weights:
            if graph is None:
                raise ValueError("Graph checkpoint requires board graph input")
            messages, pooling = graph
            encoder = weights["graph"]
            node_embeddings = [
                [
                    math.tanh(sum(a * b for a, b in zip(node, row)) + bias)
                    for row, bias in zip(encoder["w"], encoder["b"])
                ]
                for node in messages
            ]
            encoded = [
                sum(mask[i] * node_embeddings[i][j] for i in range(len(messages)))
                for mask in pooling
                for j in range(len(encoder["b"]))
            ]
            x = x + encoded
        x = [max(-10, min(10, v)) for v in x]
        hidden = [
            math.tanh(sum(a * b for a, b in zip(x, row)) + bias)
            for row, bias in zip(weights["w1"], weights["b1"])
        ]
        return sum(a * b for a, b in zip(hidden, weights["w2"])) + weights["b2"]

    def value(self, state_features, graph=None):
        logit = self.forward(state_features, "value", graph)
        return 1 / (1 + math.exp(-max(-30, min(30, logit))))

    def policy(self, state_features, action_features, graph=None):
        return self.forward(state_features + action_features, "policy", graph)
