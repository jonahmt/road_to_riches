"""Paired neural-guidance ablation with fixed opponents and frozen checkpoints."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from road_to_riches.ai.lab.network import Network
from road_to_riches.ai.lab.report import build_report
from road_to_riches.ai.lab.runner import match

SETTINGS = [
    ("boards/conversion_tests/trodain/trodain.json", 2500),
    ("boards/conversion_tests/trodain/trodain.json", 10000),
    ("boards/large_test_board.json", 12000),
]
MODES = ("off", "ranking", "value", "both")


def run_case(job):
    board, target, seed, rotation, model_path, mode, path, replay = job
    names = ["basic", "strategic", "rollout", "learned"]
    names = names[rotation:] + names[:rotation]
    result = match(
        board,
        names,
        seed,
        target=target,
        model=Network.load(model_path, guidance=mode),
        samples=2,
        horizon=4,
        replay=replay,
    )
    result["guidance"] = mode
    temporary = Path(path).with_suffix(".tmp")
    temporary.write_text(json.dumps(result))
    temporary.replace(path)
    return {
        "mode": mode,
        "seed": seed,
        "rotation": rotation,
        "target": target,
        "finished": result["finished"],
        "winner": names[result["winner"]] if result["finished"] else None,
    }


def summarize(out, modes):
    results = {}
    wins = {}
    for mode in modes:
        directory = out / mode
        build_report(directory)
        games = [json.loads(p.read_text()) for p in sorted(directory.glob("[0-9]*-*.json"))]
        if not games:
            with gzip.open(directory / "matches.jsonl.gz", "rt") as stream:
                games = [json.loads(line) for line in stream]
        # Retain complete decisions/final states and replays in a compact durable archive.
        with gzip.open(directory / "matches.jsonl.gz", "wt") as stream:
            for game in games:
                stream.write(json.dumps(game) + "\n")
        results[mode] = json.loads((directory / "summary.json").read_text())
        wins[mode] = {
            (g["seed"], g["board"], g["target"], tuple(g["profiles"])): int(
                g["finished"] and g["profiles"][g["winner"]] == "learned"
            )
            for g in games
        }
    paired = {}
    if "off" in wins:
        for mode in modes:
            if mode == "off":
                continue
            assert wins[mode].keys() == wins["off"].keys()
            keys = sorted(wins[mode])
            seeds = sorted({k[0] for k in keys})
            blocks = {s: [wins[mode][k] - wins["off"][k] for k in keys if k[0] == s] for s in seeds}
            rng = random.Random(741)
            draws = []
            for _ in range(2000):
                sample = [d for _ in seeds for d in blocks[rng.choice(seeds)]]
                draws.append(sum(sample) / len(sample))
            draws.sort()
            paired[mode] = {
                "win_difference": sum(wins[mode].values()) - sum(wins["off"].values()),
                "seed_block_bootstrap95": [draws[50], draws[1949]],
                "seed_blocks": len(seeds),
            }
    summary = {
        "modes": results,
        "paired_vs_off": paired,
        "note": (
            "The learned seat is the challenger. Off is an identical second rollout bot. "
            "Same seeds, seats, opponents and search budgets; trajectories diverge "
            "after different actions. Few seed blocks: exploratory, "
            "not proof of universal strength."
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    rows = "".join(
        f'<tr><td><a href="{m}/index.html">{html.escape(m)}</a></td>'
        f"<td data-label='Wins'>{r['profiles']['learned']['wins']} / {r['matches']}</td>"
        f"<td data-label='Completed'>{r['finished']} / {r['matches']}</td>"
        f"<td data-label='Search p95'>{r['profiles']['learned']['search_p95_ms']:.1f} ms</td></tr>"
        for m, r in results.items()
    )
    (out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Graph AI diagnostic</title>"
        "<style>body{font:18px system-ui;background:#10182a;color:#eef2fa;"
        "max-width:950px;margin:60px auto;padding:24px}"
        "a{color:#8bd8ff}td,th{text-align:left;padding:16px;border-bottom:1px solid #43516b}"
        "table{width:100%}p{line-height:1.6}"
        "@media(max-width:600px){body{margin:16px auto;padding:16px}table,tbody{display:block}"
        "tr{display:grid;grid-template-columns:1fr 1fr;border:1px solid #43516b;margin:12px 0}"
        "tr:first-child{display:none}td{border:0;padding:12px;font-size:15px}"
        "td[data-label]::before{content:attr(data-label);display:block;color:#aabbd3}}"
        "</style>"
        "<h1>Graph AI diagnostic</h1><p>Each row changes only how "
        "the frozen network guides the challenger. "
        "Opponents remain Basic, Strategic, and Rollout. Click a mode "
        "for full results and actual match replays.</p>"
        "<table><tr><th>Neural guidance</th><th>Challenger wins</th>"
        "<th>Completed games</th><th>Search p95</th></tr>"
        + rows
        + "</table><p>Off: ordinary rollout. Ranking: neural candidate selection only. "
        "Value: neural position scoring only. Both: original combined guidance.</p><p>"
        + html.escape(summary["note"])
        + '</p><p><a href="summary.json">Full summary and paired uncertainty</a> · '
        '<a href="manifest.json">Experiment configuration</a></p>'
    )
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seeds", type=int, default=4)
    p.add_argument("--seed-start", type=int, default=92000)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    args = p.parse_args()
    if not 1 <= args.workers <= 4 or args.seeds < 1:
        p.error("Use 1..4 workers and at least one seed")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "model_sha256": hashlib.sha256(Path(args.model).read_bytes()).hexdigest(),
        "modes": args.modes,
        "seed_start": args.seed_start,
        "seeds": args.seeds,
        "settings": SETTINGS,
        "samples": 2,
        "horizon": 4,
        "width": 3,
        "opponents": ["basic", "strategic", "rollout"],
        "max_turns": 600,
    }
    manifest = json.loads(json.dumps(manifest))
    path = out / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Different experiment already exists; use a fresh output directory")
    path.write_text(json.dumps(manifest, indent=2))
    jobs = []
    for mode in args.modes:
        directory = out / mode
        directory.mkdir(exist_ok=True)
        (directory / "manifest.json").write_text(
            json.dumps({**manifest, "guidance": mode}, indent=2)
        )
        for setting, (board, target) in enumerate(SETTINGS):
            for seed in range(args.seed_start, args.seed_start + args.seeds):
                for rotation in range(4):
                    path = directory / f"{setting}-{seed}-{rotation}.json"
                    if path.exists():
                        continue
                    jobs.append(
                        (
                            board,
                            target,
                            seed,
                            rotation,
                            str(Path(args.model).resolve()),
                            mode,
                            str(path),
                            seed == args.seed_start and rotation == 0,
                        )
                    )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(run_case, jobs):
            print(json.dumps(result), flush=True)
    summarize(out, args.modes)


if __name__ == "__main__":
    main()
