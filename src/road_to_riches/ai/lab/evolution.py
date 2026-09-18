"""Checkpointed, seeded evolution of non-neural opponents using real match wins."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from road_to_riches.ai.lab.parameters import BOUNDS, DEFAULT_PARAMETERS, PolicyParameters
from road_to_riches.ai.lab.runner import match

TRAIN_SETTINGS = [
    ("boards/conversion_tests/trodain/trodain.json", 2500),
    ("boards/conversion_tests/trodain/trodain.json", 10000),
    ("boards/test_board.json", 5000),
]
TEST_SETTINGS = [
    ("boards/conversion_tests/trodain/trodain.json", 10000),
    ("boards/large_test_board.json", 12000),
    ("boards/conversion_tests/bobomb/bobomb.json", 10000),
]


def mutate(parent, rng, phase, scale=0.35, mate=None):
    values = asdict(parent)
    other = asdict(mate or parent)
    keys = list(BOUNDS) if phase == "strategic" else ["leaf"]
    for key in keys:
        if key == "leaf":
            values[key] = tuple(
                max(0.02, min(8.0, (a if rng.random() < 0.5 else b) * rng.lognormvariate(0, scale)))
                for a, b in zip(values[key], other[key])
            )
        elif rng.random() < 0.7:
            lo, hi = BOUNDS[key]
            base = values[key] if rng.random() < 0.5 else other[key]
            values[key] = max(lo, min(hi, base * rng.lognormvariate(0, scale)))
    return PolicyParameters(**values)


def identity(params):
    return hashlib.sha256(json.dumps(asdict(params), sort_keys=True).encode()).hexdigest()[:12]


def run_case(job):
    checkpoint, mode, board, target, seed, rotation, path, replay, samples, horizon = job
    params = PolicyParameters.load(checkpoint)
    profiles = ["basic", "strategic", "rollout", mode]
    profiles = profiles[rotation:] + profiles[:rotation]
    pid = (3 - rotation) % 4
    result = match(
        board,
        profiles,
        seed,
        target=target,
        parameters={pid: params},
        samples=samples,
        horizon=horizon,
        replay=replay,
    )
    result["profiles"] = [name if i != pid else "challenger" for i, name in enumerate(profiles)]
    stats = {}
    for i, name in enumerate(result["profiles"]):
        decisions = [d for d in result["decisions"] if d["player"] == i]
        latency = sorted(d["ms"] for d in decisions)
        stats[name] = {
            "decisions": len(decisions),
            "p95_ms": latency[int(len(latency) * 0.95)] if latency else 0,
        }
    if replay:
        for d in result["decisions"]:
            if d["player"] == pid:
                d["profile"] = "challenger"
    else:
        result.pop("decisions")
    result["decision_stats"] = stats
    result["checkpoint"] = Path(checkpoint).name
    result["parameter_hash"] = identity(params)
    result["challenger_seat"] = pid
    result["challenger_mode"] = mode
    result["samples"] = samples
    result["horizon"] = horizon
    path = Path(path)
    temp = path.with_suffix(".tmp")
    with gzip.open(temp, "wt") as stream:
        json.dump(result, stream)
    temp.replace(path)
    return compact(result)


def compact(g):
    pid = g["challenger_seat"]
    ours = g["net_worth"][pid]
    return {
        "seed": g["seed"],
        "board": g["board"],
        "target": g["target"],
        "seat": pid,
        "win": int(g["finished"] and g["winner"] == pid),
        "finished": int(g["finished"]),
        "bankrupt": int(g["bankrupt"][pid]),
        "turns": g["turns"],
        "relative_wealth": (ours - max(v for i, v in enumerate(g["net_worth"]) if i != pid))
        / g["target"],
        "p95_ms": g["decision_stats"]["challenger"]["p95_ms"],
    }


def read_cases(directory):
    results = []
    for path in sorted(Path(directory).glob("*.json.gz")):
        with gzip.open(path, "rt") as stream:
            results.append(compact(json.load(stream)))
    return results


def metrics(rows):
    return {
        "games": len(rows),
        "wins": sum(r["win"] for r in rows),
        "finished": sum(r["finished"] for r in rows),
        "bankruptcies": sum(r["bankrupt"] for r in rows),
        "mean_relative_wealth": sum(r["relative_wealth"] for r in rows) / max(1, len(rows)),
        "median_game_p95_ms": sorted(r["p95_ms"] for r in rows)[len(rows) // 2] if rows else 0,
    }


def fitness(row):
    # Real wins dominate; capped games are never assigned a synthetic winner.
    return (row["wins"], row["finished"], -row["bankruptcies"], row["mean_relative_wealth"])


def jobs_for(checkpoint, mode, directory, seed_start, seeds, settings, samples=2, horizon=4):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    jobs = []
    for scenario, (board, target) in enumerate(settings):
        for seed in range(seed_start, seed_start + seeds):
            for rotation in range(4):
                path = directory / f"{scenario}-{seed}-{rotation}.json.gz"
                if not path.exists():
                    jobs.append(
                        (
                            str(checkpoint),
                            mode,
                            board,
                            target,
                            seed,
                            rotation,
                            str(path),
                            seed == seed_start and rotation == 0,
                            samples,
                            horizon,
                        )
                    )
    return jobs


def run_jobs(pool, jobs):
    for i, result in enumerate(pool.map(run_case, jobs)):
        if i % 12 == 0:
            print(json.dumps({"completed_batch_cases": i + 1, "last": result}), flush=True)


def evolve(out, phase, initial, seed, generations, workers, deadline):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    checkpoints = out / "checkpoints"
    checkpoints.mkdir(exist_ok=True)
    history = out / "history.json"
    if history.exists():
        raise ValueError("Evolution output already exists; use a fresh directory")
    base = PolicyParameters.load(initial) if initial else DEFAULT_PARAMETERS
    base.save(checkpoints / "baseline.json", phase=phase, origin="frozen starting checkpoint")
    elites = [base, base]
    rng = random.Random(seed)
    records = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for generation in range(generations):
            if time.time() >= deadline:
                break
            population = [base, *elites]
            # Fixed baseline and two elites are tested again on new seeds each generation.
            while len(population) < 6:
                population.append(
                    mutate(
                        rng.choice(elites),
                        rng,
                        phase,
                        scale=max(0.16, 0.40 * 0.9**generation),
                        mate=rng.choice(elites),
                    )
                )
            # Avoid duplicate evaluations within a generation.
            population = list({identity(p): p for p in population}.values())
            while len(population) < 6:
                p = mutate(rng.choice(elites), rng, phase, mate=rng.choice(elites))
                if identity(p) not in {identity(q) for q in population}:
                    population.append(p)
            round_rows = []
            jobs = []
            for index, params in enumerate(population):
                name = f"g{generation:02d}-c{index:02d}-{identity(params)}"
                path = checkpoints / f"{name}.json"
                params.save(
                    path, generation=generation, phase=phase, parents=[identity(e) for e in elites]
                )
                jobs.extend(
                    jobs_for(
                        path,
                        phase,
                        out / "matches" / name,
                        seed + generation * 100,
                        1,
                        TRAIN_SETTINGS,
                    )
                )
                round_rows.append({"checkpoint": name, "parameters": params})
            run_jobs(pool, jobs)
            for row in round_rows:
                row.update(metrics(read_cases(out / "matches" / row["checkpoint"])))
            round_rows.sort(key=fitness, reverse=True)
            elites = [r["parameters"] for r in round_rows[:2]]
            winner = round_rows[0]
            records.append(
                {
                    "generation": generation,
                    "seed": seed + generation * 100,
                    "ranking": [
                        {k: v for k, v in r.items() if k != "parameters"} for r in round_rows
                    ],
                }
            )
            history.write_text(json.dumps(records, indent=2))
            elites[0].save(
                out / "champion.json",
                phase=phase,
                generation=generation,
                selected_on="training only; requires held-out evaluation",
                source_checkpoint=winner["checkpoint"],
            )
            print(
                json.dumps(
                    {"generation": generation, "phase": phase, "winner": records[-1]["ranking"][0]}
                ),
                flush=True,
            )
    return records


def evaluate(out, checkpoint, mode, seeds, seed_start, workers, samples, horizon):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "checkpoint_sha256": hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
        "mode": mode,
        "seeds": seeds,
        "seed_start": seed_start,
        "settings": TEST_SETTINGS,
        "samples": samples,
        "horizon": horizon,
    }
    manifest = json.loads(json.dumps(manifest))
    path = out / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Incompatible evaluation output")
    path.write_text(json.dumps(manifest, indent=2))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        run_jobs(
            pool,
            jobs_for(
                checkpoint,
                mode,
                out / "matches",
                seed_start,
                seeds,
                TEST_SETTINGS,
                samples,
                horizon,
            ),
        )
    rows = read_cases(out / "matches")
    summary = metrics(rows)
    summary["scenarios"] = {
        f"{b}/{t}": metrics([r for r in rows if r["board"] == b and r["target"] == t])
        for b, t in TEST_SETTINGS
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["evolve", "evaluate"])
    p.add_argument("--output", required=True)
    p.add_argument("--mode", choices=["strategic", "rollout"], required=True)
    p.add_argument("--checkpoint")
    p.add_argument("--seed", type=int, default=210000)
    p.add_argument("--generations", type=int, default=4)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--seeds", type=int, default=4)
    p.add_argument("--samples", type=int, default=2)
    p.add_argument("--horizon", type=int, default=4)
    p.add_argument("--deadline", help="Optional UTC ISO timestamp; finish the current generation")
    args = p.parse_args()
    if not 1 <= args.workers <= 4 or args.seeds < 1 or args.generations < 1:
        p.error("Positive seeds/generations and 1..4 workers required")
    if args.command == "evolve":
        evolve(
            args.output,
            args.mode,
            args.checkpoint,
            args.seed,
            args.generations,
            args.workers,
            datetime.fromisoformat(args.deadline).timestamp() if args.deadline else float("inf"),
        )
    else:
        if not args.checkpoint:
            p.error("Evaluation requires a checkpoint")
        evaluate(
            args.output,
            args.checkpoint,
            args.mode,
            args.seeds,
            args.seed,
            args.workers,
            args.samples,
            args.horizon,
        )


if __name__ == "__main__":
    main()
