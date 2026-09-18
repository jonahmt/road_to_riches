"""Bounded expert-iteration experiment: search imitation + self-play win values."""

from __future__ import annotations

import json
import math
import time
from collections import Counter
from pathlib import Path

from road_to_riches.ai.lab.graph import graph_input
from road_to_riches.ai.lab.network import Network, candidate_features
from road_to_riches.ai.lab.policies import SEARCH_TYPES
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


TRAIN_SETTINGS = [
    ("boards/conversion_tests/trodain/trodain.json", 2500),
    ("boards/conversion_tests/trodain/trodain.json", 5000),
    ("boards/conversion_tests/trodain/trodain.json", 10000),
    ("boards/test_board.json", 2500),
    ("boards/test_board.json", 5000),
    ("boards/test_board.json", 10000),
]
MIN_POLICY_DECISIONS = 32


def policy_examples(state, req, policy, record, base, graph):
    """Only search-teacher decisions supervise ranking; keep every legal candidate.

    Unsupported/rare types remain on the heuristic order at inference. Self-play
    contributes value outcomes, never labels that teach the policy its own mistakes.
    """
    candidates = getattr(policy, "last_candidates", [])
    if (
        getattr(policy, "name", None) != "rollout"
        or req.type not in SEARCH_TYPES
        or len(candidates) < 2
    ):
        return []
    return [
        (base + candidate_features(state, req, c), float(c.action == record["action"]), graph)
        for c in candidates
    ]


def validation_metrics(model, values, decisions):
    brier = loss = 0.0
    for x, y, graph in values:
        pred = model.value(x, graph)
        brier += (pred - y) ** 2
        pred = max(1e-9, min(1 - 1e-9, pred))
        loss -= y * math.log(pred) + (1 - y) * math.log(1 - pred)
    accuracy = Counter()
    counts = Counter()
    for prompt, rows in decisions:
        scores = [model.forward(x, "policy", graph) for x, _, graph in rows]
        chosen = max(range(len(rows)), key=scores.__getitem__)
        accuracy[prompt] += int(rows[chosen][1] == 1)
        counts[prompt] += 1
    n = max(1, len(values))
    return {
        "value_rows": len(values),
        "value_brier": brier / n,
        "value_log_loss": loss / n,
        "policy": {
            p: {"decisions": c, "teacher_agreement": accuracy[p] / c} for p, c in counts.items()
        },
    }


def train(output, *, seconds=900, games=160, seed=51000, architecture="graph"):
    if not 1 <= seconds <= 3600:
        raise ValueError("Training wall-clock budget must be 1..3600 seconds")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    deadline = start + seconds
    value_x, value_y, policy_x, policy_y = [], [], [], []
    value_graphs, policy_graphs = [], []
    records = []
    prompt_counts = Counter()
    validation_values, validation_decisions = [], []
    model = None
    stages = []
    # First half teaches decisions from rules/search. Second half is mixed
    # self-play against frozen basic/strategic/search teachers and a checkpoint.
    for stage in range(2):
        stage_deadline = start + seconds * (stage + 1) / 2
        collection_deadline = stage_deadline - min(120, seconds / 8)
        for game in range(games // 2):
            if time.monotonic() > collection_deadline:
                break
            pending_values, pending_policy = [], []
            board, target = TRAIN_SETTINGS[(game + stage * 3) % len(TRAIN_SETTINGS)]
            is_validation = game % 10 == 9
            profiles = [
                "strategic",
                "rollout",
                "strategic" if model is None else "learned",
                "basic",
            ]
            rotation = game % 4
            profiles = profiles[rotation:] + profiles[:rotation]

            def collect(state, req, policy, record):
                if time.monotonic() >= collection_deadline:
                    raise TrainingDeadline()
                candidates = getattr(policy, "last_candidates", [])
                if len(candidates) < 2 and req.type.value != "PRE_ROLL":
                    return
                base = features(state, req.player_id)
                graph = graph_input(state, req.player_id) if architecture == "graph" else None
                pending_values.append((base, req.player_id, graph))
                rows = policy_examples(state, req, policy, record, base, graph)
                if rows:
                    pending_policy.append((req.type.value, rows))

            try:
                r = match(
                    board,
                    profiles,
                    seed + stage * 10000 + game,
                    target=target,
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
                        "board",
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
            records[-1]["validation"] = is_validation
            if r["finished"]:
                for x, pid, graph in pending_values:
                    y = float(pid == r["winner"])
                    if is_validation:
                        validation_values.append((x, y, graph))
                    else:
                        value_x.append(x)
                        value_y.append(y)
                        value_graphs.append(graph)
                for prompt, rows in pending_policy:
                    if is_validation:
                        validation_decisions.append((prompt, rows))
                    else:
                        prompt_counts[prompt] += 1
                        for x, y, graph in rows:
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
            deadline=min(deadline, (time.monotonic() + stage_deadline) / 2),
            graphs=value_graphs if architecture == "graph" else None,
            epochs=30,
        )
        policy, pl = fit_mlp(
            policy_x,
            policy_y,
            seed=seed + 100 + stage,
            initial=previous.get("policy"),
            deadline=stage_deadline,
            graphs=policy_graphs if architecture == "graph" else None,
            epochs=30,
        )
        data = {
            "version": 1,
            "state_dim": 20,
            "architecture": architecture + " policy/value: 32-unit tanh heads",
            "value": value,
            "policy": policy,
            "policy_prompts": sorted(
                p for p, n in prompt_counts.items() if n >= MIN_POLICY_DECISIONS
            ),
            "policy_prompt_counts": dict(prompt_counts),
        }
        model = Network(data)
        (output / f"stage-{stage}.json").write_text(json.dumps(data))
        stages.append(
            {
                "stage": stage,
                "games": len(records),
                "value_loss": vl,
                "policy_loss": pl,
                "validation": validation_metrics(model, validation_values, validation_decisions),
            }
        )
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
        "method": (
            "rollout-teacher imitation, terminal win labels, mixed self-play; "
            "10% entire games withheld"
        ),
        "training_settings": TRAIN_SETTINGS,
        "policy_prompt_counts": dict(prompt_counts),
        "policy_prompts": model.data["policy_prompts"],
        "minimum_policy_decisions": MIN_POLICY_DECISIONS,
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
