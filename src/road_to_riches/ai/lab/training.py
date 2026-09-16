"""Bounded expert-iteration experiment: search imitation + self-play win values."""

from __future__ import annotations

import json
import time
from pathlib import Path

from road_to_riches.ai.lab.graph import graph_input
from road_to_riches.ai.lab.network import Network, candidate_features
from road_to_riches.ai.lab.runner import match
from road_to_riches.ai.lab.strategy import features


class TrainingDeadline(Exception):
    pass


def fit_mlp(x, y, *, seed, epochs=80, initial=None, deadline=float("inf"), graphs=None):
    import numpy as np

    rng = np.random.default_rng(seed)
    x = np.clip(np.asarray(x, dtype=np.float64), -10, 10)
    y = np.asarray(y, dtype=np.float64)
    use_graph = graphs is not None
    if use_graph:
        nodes = max(len(g[0]) for g in graphs)
        u = np.zeros((len(graphs), nodes, 24), dtype=np.float32)
        pools = np.zeros((len(graphs), 3, nodes), dtype=np.float32)
        for i, (node, pool) in enumerate(graphs):
            u[i, : len(node)] = node
            pools[i, :, : len(node)] = pool
        gw = rng.normal(0, 0.15, (24, 8))
        gb = np.zeros(8)
        if initial:
            gw, gb = np.array(initial["graph"]["w"]).T, np.array(initial["graph"]["b"])
    dim = x.shape[1] + (24 if use_graph else 0)
    if initial is None:
        w, b = rng.normal(0, 0.15, (dim, 32)), np.zeros(32)
        v, c = rng.normal(0, 0.1, 32), np.array(0.0)
    else:
        w, b = np.array(initial["w1"]).T, np.array(initial["b1"])
        v, c = np.array(initial["w2"]), np.array(initial["b2"])
    params = [w, b, v, c] + ([gw, gb] if use_graph else [])
    moments = [np.zeros_like(z) for z in params]
    variances = [np.zeros_like(z) for z in params]
    step, losses = 0, []
    for _ in range(epochs):
        if time.monotonic() >= deadline:
            break
        total_loss, count = 0, 0
        for ids in np.array_split(rng.permutation(len(x)), max(1, (len(x) + 127) // 128)):
            if time.monotonic() >= deadline:
                break
            a, labels = x[ids], y[ids]
            if use_graph:
                nu, pm = u[ids], pools[ids]
                nh = np.tanh(nu @ gw + gb)
                pooled = np.einsum("brn,bng->brg", pm, nh).reshape(len(ids), 24)
                a = np.concatenate([a, pooled], axis=1)
            h = np.tanh(a @ w + b)
            logits = h @ v + c
            total_loss += float(np.sum(np.logaddexp(0, logits) - labels * logits))
            count += len(ids)
            prediction = 1 / (1 + np.exp(-np.clip(logits, -30, 30)))
            error = (prediction - labels) / len(ids)
            dh = error[:, None] * v[None, :] * (1 - h * h)
            grads = [a.T @ dh + 0.0001 * w, dh.sum(0), h.T @ error + 0.0001 * v, error.sum()]
            if use_graph:
                dpool = (dh @ w.T)[:, -24:].reshape(len(ids), 3, 8)
                dn = np.einsum("brn,brg->bng", pm, dpool) * (1 - nh * nh)
                grads += [np.einsum("bnf,bng->fg", nu, dn) + 0.0001 * gw, dn.sum((0, 1))]
            step += 1
            for i, (param, grad) in enumerate(zip(params, grads)):
                moments[i] = 0.9 * moments[i] + 0.1 * grad
                variances[i] = 0.999 * variances[i] + 0.001 * grad * grad
                param -= (
                    0.002
                    * (moments[i] / (1 - 0.9**step))
                    / (np.sqrt(variances[i] / (1 - 0.999**step)) + 1e-8)
                )
        losses.append(total_loss / max(1, count))
    result = {"w1": w.T.tolist(), "b1": b.tolist(), "w2": v.tolist(), "b2": float(c)}
    if use_graph:
        result["graph"] = {"w": gw.T.tolist(), "b": gb.tolist()}
    return result, losses


def train(output, *, seconds=900, games=160, seed=31000, architecture="graph"):
    if not 1 <= seconds <= 3600:
        raise ValueError("Training wall-clock budget must be 1..3600 seconds")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    deadline = start + seconds
    value_x, value_y, policy_x, policy_y = [], [], [], []
    value_graphs, policy_graphs = [], []
    records = []
    model = None
    stages = []
    board = "boards/conversion_tests/trodain/trodain.json"
    # First half teaches decisions from rules/search. Second half is mixed
    # self-play against frozen basic/strategic/search teachers and a checkpoint.
    for stage in range(2):
        for game in range(games // 2):
            if time.monotonic() > deadline - 20:
                break
            pending_values, pending_policy = [], []
            profiles = [
                "strategic",
                "rollout",
                "strategic" if model is None else "learned",
                "basic",
            ]
            rotation = game % 4
            profiles = profiles[rotation:] + profiles[:rotation]

            def collect(state, req, policy, record):
                if time.monotonic() >= deadline - 10:
                    raise TrainingDeadline()
                if req.type.value in ("PRE_ROLL", "INVEST", "BUY_STOCK", "BUY_SHOP", "CHOOSE_PATH"):
                    candidates = getattr(policy, "last_candidates", [])
                    if req.type.value == "CHOOSE_PATH" and len(candidates) <= 1:
                        return
                    base = features(state, req.player_id)
                    graph = graph_input(state, req.player_id) if architecture == "graph" else None
                    pending_values.append((base, req.player_id, graph))
                    if len(candidates) > 1:
                        for candidate in candidates[:12]:
                            row = base + candidate_features(state, req, candidate)
                            pending_policy.append(
                                (row, float(candidate.action == record["action"]), graph)
                            )

            try:
                r = match(
                    board,
                    profiles,
                    seed + stage * 10000 + game,
                    target=2500 if game % 3 else 5000,
                    model=model,
                    on_decision=collect,
                    samples=1,
                    horizon=4,
                    max_turns=500,
                )
            except TrainingDeadline:
                break
            records.append(
                {
                    k: r[k]
                    for k in (
                        "seed",
                        "profiles",
                        "target",
                        "winner",
                        "finished",
                        "turns",
                        "seconds",
                    )
                }
            )
            if r["finished"]:
                for x, pid, graph in pending_values:
                    value_x.append(x)
                    value_y.append(float(pid == r["winner"]))
                    value_graphs.append(graph)
                for x, y, graph in pending_policy:
                    policy_x.append(x)
                    policy_y.append(y)
                    policy_graphs.append(graph)
            if game % 10 == 0:
                print(
                    json.dumps(
                        {
                            "stage": stage,
                            "games": len(records),
                            "seconds": round(time.monotonic() - start),
                            "value_rows": len(value_x),
                            "policy_rows": len(policy_x),
                        }
                    ),
                    flush=True,
                )
        if not value_x or not policy_x:
            raise RuntimeError("Budget too small to collect complete training matches")
        previous = model.data if model else {}
        value, vl = fit_mlp(
            value_x,
            value_y,
            seed=seed + stage,
            initial=previous.get("value"),
            deadline=deadline,
            graphs=value_graphs if architecture == "graph" else None,
            epochs=30,
        )
        policy, pl = fit_mlp(
            policy_x,
            policy_y,
            seed=seed + 100 + stage,
            initial=previous.get("policy"),
            deadline=deadline,
            graphs=policy_graphs if architecture == "graph" else None,
            epochs=30,
        )
        data = {
            "version": 1,
            "state_dim": 20,
            "architecture": architecture + " policy/value: 32-unit tanh heads",
            "value": value,
            "policy": policy,
        }
        model = Network(data)
        (output / f"stage-{stage}.json").write_text(json.dumps(data))
        stages.append({"stage": stage, "games": len(records), "value_loss": vl, "policy_loss": pl})
        if time.monotonic() >= deadline - 20:
            break
    (output / "model.json").write_text(json.dumps(model.data))
    metadata = {
        "seed": seed,
        "architecture": architecture,
        "requested_seconds": seconds,
        "elapsed_seconds": time.monotonic() - start,
        "games": records,
        "stages": stages,
        "value_rows": len(value_x),
        "policy_rows": len(policy_x),
        "method": "search imitation, terminal win labels, mixed checkpoint self-play",
        "training_board": board,
        "evaluation_seeds": "reserved >= 90000",
    }
    (output / "training.json").write_text(json.dumps(metadata, indent=2))
    print(
        json.dumps(
            {
                "trained": str(output / "model.json"),
                "seconds": metadata["elapsed_seconds"],
                "games": len(records),
            }
        ),
        flush=True,
    )
