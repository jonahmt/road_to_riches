"""Package completed evolution runs, paired tests and the final direct league."""

import argparse
import gzip
import hashlib
import html
import json
import random
import shutil
from pathlib import Path

from road_to_riches.ai.lab.evolution import read_cases


def archive(source, destination):
    files = sorted(source.rglob("*.json.gz"))
    with gzip.open(destination, "wt") as output:
        for path in files:
            with gzip.open(path, "rt") as stream:
                game = json.load(stream)
            if not game["finished"] or game["winner"] is None:
                raise ValueError(f"Cannot report unfinished game as completed: {path}")
            game["source_record"] = str(path.relative_to(source))
            output.write(json.dumps(game) + "\n")
    return len(files)


def bootstrap(blocks):
    rng = random.Random(3888)
    seeds = sorted(blocks)
    draws = []
    for _ in range(2000):
        sample = [d for _ in seeds for d in blocks[rng.choice(seeds)]]
        draws.append(sum(sample) / len(sample))
    draws.sort()
    return [draws[50], draws[1949]]


def package(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    stages = {}
    total = 0
    for phase in ("strategic", "rollout"):
        src = source / f"evolution-{phase}"
        dest = output / phase
        dest.mkdir(exist_ok=True)
        shutil.copytree(src / "checkpoints", dest / "checkpoints", dirs_exist_ok=True)
        for name in ("history.json", "champion.json"):
            shutil.copyfile(src / name, dest / name)
        count = archive(src / "matches", dest / "matches.jsonl.gz")
        total += count
        stages[phase] = {"games": count, "history": json.loads((src / "history.json").read_text())}
    tests = {}
    pairs = {}
    for kind in ("baseline", "selected"):
        src = source / f"evolution-{kind}-strategic-test"
        dest = output / f"{kind}-strategic-test"
        dest.mkdir(exist_ok=True)
        for name in ("manifest.json", "summary.json"):
            shutil.copyfile(src / name, dest / name)
        count = archive(src / "matches", dest / "matches.jsonl.gz")
        total += count
        tests[kind] = json.loads((src / "summary.json").read_text())
        pairs[kind] = {
            (r["seed"], r["board"], r["target"], r["seat"]): r["win"]
            for r in read_cases(src / "matches")
        }
    assert pairs["baseline"].keys() == pairs["selected"].keys()
    keys = sorted(pairs["baseline"])
    seeds = sorted({k[0] for k in keys})
    blocks = {
        s: [pairs["selected"][k] - pairs["baseline"][k] for k in keys if k[0] == s] for s in seeds
    }
    paired = {
        "wins_difference": tests["selected"]["wins"] - tests["baseline"]["wins"],
        "seed_block_bootstrap95": bootstrap(blocks),
        "seed_blocks": len(seeds),
    }
    rollout_tests = {}
    rollout_pairs = {}
    for kind in ("baseline", "selected"):
        src = source / f"evolution-{kind}-rollout-test"
        dest = output / f"{kind}-rollout-test"
        dest.mkdir(exist_ok=True)
        for name in ("manifest.json", "summary.json"):
            shutil.copyfile(src / name, dest / name)
        total += archive(src / "matches", dest / "matches.jsonl.gz")
        rollout_tests[kind] = json.loads((src / "summary.json").read_text())
        rollout_pairs[kind] = {
            (r["seed"], r["board"], r["target"], r["seat"]): r["win"]
            for r in read_cases(src / "matches")
        }
    assert rollout_pairs["baseline"].keys() == rollout_pairs["selected"].keys()
    src = source / "evolution-league"
    dest = output / "league"
    dest.mkdir(exist_ok=True)
    for name in ("index.html", "summary.json", "manifest.json"):
        shutil.copyfile(src / name, dest / name)
    games = [json.loads(p.read_text()) for p in sorted(src.glob("[0-9]*-*.json"))]
    with gzip.open(dest / "matches.jsonl.gz", "wt") as stream:
        for g in games:
            stream.write(json.dumps(g) + "\n")
    league = json.loads((src / "summary.json").read_text())
    total += len(games)
    assert league["matches"] == len(games) and league["finished"] == len(games)
    assert all(test["finished"] == test["games"] for test in tests.values())
    league_blocks = {}
    for g in games:
        winner = g["profiles"][g["winner"]]
        league_blocks.setdefault(g["seed"], []).append(
            int(winner == "evolved_rollout") - int(winner == "rollout")
        )
    rollout_interval = bootstrap(league_blocks)
    manifest = {
        "total_experiment_games": total,
        "evolution": stages,
        "strategic_tests": tests,
        "paired_strategic": paired,
        "rollout_tests": rollout_tests,
        "league_evolved_vs_original_rollout_seed_bootstrap95": rollout_interval,
        "league": league,
        "checkpoint_sha256": {},
    }
    for phase in stages:
        path = output / phase / "champion.json"
        manifest["checkpoint_sha256"][phase] = hashlib.sha256(path.read_bytes()).hexdigest()
        evaluated = json.loads((output / f"selected-{phase}-test" / "manifest.json").read_text())
        assert manifest["checkpoint_sha256"][phase] == evaluated["checkpoint_sha256"]
        league_manifest = json.loads((dest / "manifest.json").read_text())
        assert manifest["checkpoint_sha256"][phase] == league_manifest[f"{phase}_sha256"]
    (output / "summary.json").write_text(json.dumps(manifest, indent=2))
    names = {
        "strategic": "Original strategic",
        "rollout": "Original rollout",
        "evolved_strategic": "Evolved strategic",
        "evolved_rollout": "Evolved rollout",
    }
    rows = "".join(
        f"<article><span>{names[n]}</span><strong>{r['wins']} / {r['games']}</strong>"
        f"<small>wins · decision p95 {r['p95_ms']:.1f} ms</small></article>"
        for n, r in sorted(league["profiles"].items(), key=lambda x: -x[1]["wins"])
    )
    generations = ""
    for phase, stage in stages.items():
        generations += f"<h3>{phase.title()} evolution · {stage['games']} games</h3><ul>"
        for g in stage["history"]:
            w = g["ranking"][0]
            generations += (
                f"<li>Generation {g['generation'] + 1}: selected {w['checkpoint']}, "
                f"{w['wins']}/{w['games']} training wins.</li>"
            )
        generations += "</ul>"
    winner = max(league["profiles"], key=lambda n: league["profiles"][n]["wins"])
    page = Path(__file__).with_suffix(".html").read_text()
    values = {
        "TOTAL": total,
        "CARDS": rows,
        "LEAGUE_MATCHES": league["matches"],
        "WINNER": html.escape(names[winner]),
        "GENERATIONS": generations,
        "BASE_WINS": tests["baseline"]["wins"],
        "BASE_GAMES": tests["baseline"]["games"],
        "NEW_WINS": tests["selected"]["wins"],
        "NEW_GAMES": tests["selected"]["games"],
        "LO": f"{paired['seed_block_bootstrap95'][0] * 100:.1f}",
        "HI": f"{paired['seed_block_bootstrap95'][1] * 100:.1f}",
        "PAIR_BLOCKS": len(seeds),
        "ROLLOUT_BASE_WINS": rollout_tests["baseline"]["wins"],
        "ROLLOUT_NEW_WINS": rollout_tests["selected"]["wins"],
        "ROLLOUT_GAMES": rollout_tests["selected"]["games"],
        "ROLLOUT_LO": f"{rollout_interval[0] * 100:.1f}",
        "ROLLOUT_HI": f"{rollout_interval[1] * 100:.1f}",
        "CANDIDATES": sum(len(g["ranking"]) for st in stages.values() for g in st["history"]),
        "GENERATIONS_COUNT": sum(len(st["history"]) for st in stages.values()),
    }
    for key, value in values.items():
        page = page.replace(f"__{key}__", str(value))
    (output / "index.html").write_text(page)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default=".runtime/ai-lab")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    package(args.source, args.output)


if __name__ == "__main__":
    main()
