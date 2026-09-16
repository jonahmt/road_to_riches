"""Standalone, inspectable tournament report and turn-by-turn match replays."""

from __future__ import annotations

import gzip
import json
import math
import random
from collections import defaultdict
from pathlib import Path


def build_report(directory):
    directory = Path(directory)
    games = [json.loads(p.read_text()) for p in sorted(directory.glob("[0-9]*-*.json"))]
    archive = directory / "matches.jsonl.gz"
    if not games and archive.exists():
        with gzip.open(archive, "rt") as stream:
            games = [json.loads(line) for line in stream]
    if not games:
        raise ValueError("No recorded matches in report directory")
    stats = defaultdict(
        lambda: {"games": 0, "wins": 0, "bankruptcies": 0, "ms": [], "turns": [], "search_ms": []}
    )
    for g in games:
        for i, p in enumerate(g["profiles"]):
            row = stats[p]
            row["games"] += 1
            row["wins"] += int(g["winner"] == i)
            row["bankruptcies"] += int(g["bankrupt"][i])
            row["turns"].append(g["turns"])
        for d in g["decisions"]:
            stats[d["profile"]]["ms"].append(d["ms"])
            if d.get("search"):
                stats[d["profile"]]["search_ms"].append(d["ms"])
    compact = {}
    for name, row in stats.items():
        n, w = row["games"], row["wins"]
        p, z = w / n, 1.96
        center = (p + z * z / (2 * n)) / (1 + z * z / n)
        radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        lat = sorted(row["ms"])
        search = sorted(row["search_ms"])
        compact[name] = {
            "games": n,
            "wins": w,
            "win_rate": p,
            "wilson95": [center - radius, center + radius],
            "bankruptcies": row["bankruptcies"],
            "median_ms": lat[len(lat) // 2],
            "p95_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))],
            "max_ms": max(lat),
            "searched_decisions": len(search),
            "search_p95_ms": search[int(len(search) * 0.95)] if search else None,
        }
    summary = {
        "matches": len(games),
        "finished": sum(g["finished"] for g in games),
        "profiles": compact,
        "note": (
            "Wilson intervals are descriptive; seat-rotated games share seeds and are correlated."
        ),
    }
    scenarios = {}
    for g in games:
        key = f"{Path(g['board']).stem} / {g['target']}G"
        row = scenarios.setdefault(
            key, {"games": 0, "finished": 0, "wins": dict.fromkeys(stats, 0)}
        )
        row["games"] += 1
        row["finished"] += int(g["finished"])
        if g["winner"] is not None:
            row["wins"][g["profiles"][g["winner"]]] += 1
    summary["scenarios"] = scenarios
    # Resample entire seed blocks, keeping all seat rotations/scenarios together.
    blocks = defaultdict(list)
    for g in games:
        blocks[g["seed"]].append(g)
    rng = random.Random(744)
    keys = sorted(blocks)
    bootstrap = {name: [] for name in stats if name != "basic"}
    for _ in range(2000):
        sample = [g for _ in keys for g in blocks[rng.choice(keys)]]
        wins = {name: 0 for name in stats}
        for g in sample:
            if g["winner"] is not None:
                wins[g["profiles"][g["winner"]]] += 1
        for name in bootstrap:
            bootstrap[name].append((wins[name] - wins["basic"]) / len(sample))
    summary["win_rate_difference_vs_basic_seed_bootstrap95"] = {
        name: [sorted(vals)[50], sorted(vals)[1949]] for name, vals in bootstrap.items()
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2))
    replays = [g for g in games if g["frames"]]
    metadata = directory / "manifest.json"
    comparison = directory / "comparison.json"
    data = json.dumps(
        {
            "summary": summary,
            "replays": replays,
            "manifest": json.loads(metadata.read_text()) if metadata.exists() else {},
            "comparison": json.loads(comparison.read_text()) if comparison.exists() else None,
        }
    ).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", data)
    (directory / "index.html").write_text(html)
    print(json.dumps(summary, indent=2))


TEMPLATE = Path(__file__).with_suffix(".html").read_text()
