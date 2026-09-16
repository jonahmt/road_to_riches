"""CLI for reproducible experimental AI training, tournaments and live games."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from road_to_riches.ai.lab.runner import tournament_game


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    checkpoint = str(Path(__file__).with_name("checkpoints") / "trained.json")
    sub = parser.add_subparsers(dest="command", required=True)
    train = sub.add_parser("train")
    train.add_argument("--output", required=True)
    train.add_argument("--seconds", type=int, default=900)
    train.add_argument("--games", type=int, default=160)
    train.add_argument("--architecture", choices=["graph", "mlp"], default="graph")
    tournament = sub.add_parser("tournament")
    tournament.add_argument("--model", default=checkpoint)
    tournament.add_argument("--output", required=True)
    tournament.add_argument("--seeds", type=int, default=12)
    tournament.add_argument("--seed-start", type=int, default=90000)
    tournament.add_argument("--samples", type=int, default=2)
    tournament.add_argument("--horizon", type=int, default=4)
    tournament.add_argument("--workers", type=int, default=1)
    serve = sub.add_parser("serve")
    serve.add_argument("--model", default=checkpoint)
    serve.add_argument("--profiles", default="human,strategic,rollout,learned")
    serve.add_argument("--port", type=int, default=18810)
    serve.add_argument("--target", type=int, default=5000)
    serve.add_argument("--seed", type=int, default=91234)
    args = parser.parse_args()
    if args.command == "train":
        from road_to_riches.ai.lab.training import train

        train(args.output, seconds=args.seconds, games=args.games, architecture=args.architecture)
    elif args.command == "tournament":
        from road_to_riches.ai.lab.network import Network

        model = Network.load(args.model)
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        manifest = {
            "model_sha256": hashlib.sha256(Path(args.model).read_bytes()).hexdigest(),
            "architecture": model.data.get("architecture"),
            "workers": args.workers,
            "samples": args.samples,
            "horizon": args.horizon,
            "seed_start": args.seed_start,
            "seeds": args.seeds,
            "max_turns": 600,
            "profiles": ["basic", "strategic", "rollout", "learned"],
        }
        manifest_path = out / "manifest.json"
        if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
            raise ValueError("Output contains a different experiment; use a fresh directory")
        manifest_path.write_text(json.dumps(manifest, indent=2))
        settings = [
            ("boards/conversion_tests/trodain/trodain.json", 2500),
            ("boards/conversion_tests/trodain/trodain.json", 10000),
            ("boards/large_test_board.json", 12000),
        ]
        jobs = []
        for scenario, (board, target) in enumerate(settings):
            for seed in range(args.seed_start, args.seed_start + args.seeds):
                for rotation in range(4):
                    path = out / f"{scenario}-{seed}-{rotation}.json"
                    if path.exists():
                        continue
                    names = ["basic", "strategic", "rollout", "learned"]
                    names = names[rotation:] + names[:rotation]
                    jobs.append(
                        (
                            board,
                            names,
                            seed,
                            target,
                            str(Path(args.model).resolve()),
                            str(path),
                            args.samples,
                            args.horizon,
                            seed == args.seed_start and rotation == 0,
                        )
                    )
        if not 1 <= args.workers <= 4:
            raise ValueError("Use 1..4 workers to leave capacity for the browser")
        if args.workers == 1:
            for job in jobs:
                print(json.dumps(tournament_game(job)), flush=True)
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                for result in pool.map(tournament_game, jobs):
                    print(json.dumps(result), flush=True)
        from road_to_riches.ai.lab.report import build_report

        build_report(out)
    else:
        from road_to_riches.ai.lab.live import serve

        serve(args.model, args.profiles.split(","), args.port, args.target, args.seed)


if __name__ == "__main__":
    main()
