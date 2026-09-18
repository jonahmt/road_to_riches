"""Direct four-way games between frozen and evolved strategic/rollout opponents."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from road_to_riches.ai.lab.evolution import TEST_SETTINGS
from road_to_riches.ai.lab.parameters import PolicyParameters
from road_to_riches.ai.lab.report import build_report
from road_to_riches.ai.lab.runner import match


def run_league_case(job):
    strategic, rollout, board, target, seed, rotation, path, replay, samples, horizon = job
    modes = ["strategic", "rollout", "strategic", "rollout"]
    labels = ["strategic", "rollout", "evolved_strategic", "evolved_rollout"]
    modes = modes[rotation:] + modes[:rotation]
    labels = labels[rotation:] + labels[:rotation]
    params = {
        (2 - rotation) % 4: PolicyParameters.load(strategic),
        (3 - rotation) % 4: PolicyParameters.load(rollout),
    }
    result = match(
        board,
        modes,
        seed,
        target=target,
        parameters=params,
        samples=samples,
        horizon=horizon,
        replay=replay,
    )
    result["profiles"] = labels
    for d in result["decisions"]:
        d["profile"] = labels[d["player"]]
    temporary = Path(path).with_suffix(".tmp")
    temporary.write_text(json.dumps(result))
    temporary.replace(path)
    return {
        "seed": seed,
        "board": board,
        "target": target,
        "rotation": rotation,
        "finished": result["finished"],
        "winner": labels[result["winner"]] if result["finished"] else None,
        "turns": result["turns"],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--strategic", required=True)
    p.add_argument("--rollout", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=330000)
    p.add_argument("--seeds", type=int, default=4)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--samples", type=int, default=2)
    p.add_argument("--horizon", type=int, default=4)
    args = p.parse_args()
    if not 1 <= args.workers <= 4 or args.seeds < 1:
        p.error("Positive seeds and 1..4 workers required")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "strategic_sha256": hashlib.sha256(Path(args.strategic).read_bytes()).hexdigest(),
        "rollout_sha256": hashlib.sha256(Path(args.rollout).read_bytes()).hexdigest(),
        "seed_start": args.seed,
        "seeds": args.seeds,
        "samples": args.samples,
        "horizon": args.horizon,
        "description": (
            "Frozen strategic and rollout bots compete directly against their "
            "evolved counterparts. No neural network participates."
        ),
        "context": (
            "All four seats rotate. Checkpoints were frozen before these matches; "
            "unseen Bob-omb and large boards are included."
        ),
    }
    path = out / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Incompatible league directory")
    path.write_text(json.dumps(manifest, indent=2))
    jobs = []
    for scenario, (board, target) in enumerate(TEST_SETTINGS):
        for seed in range(args.seed, args.seed + args.seeds):
            for rotation in range(4):
                path = out / f"{scenario}-{seed}-{rotation}.json"
                if not path.exists():
                    jobs.append(
                        (
                            args.strategic,
                            args.rollout,
                            board,
                            target,
                            seed,
                            rotation,
                            str(path),
                            seed == args.seed and rotation == 0,
                            args.samples,
                            args.horizon,
                        )
                    )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(run_league_case, jobs):
            print(json.dumps(result), flush=True)
    build_report(out)


if __name__ == "__main__":
    main()
