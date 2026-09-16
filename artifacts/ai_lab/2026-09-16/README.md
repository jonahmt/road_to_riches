# AI experiment results — 16 September 2026

Recommendation: use **rollout** as the strongest measured opponent in this batch.
The strategic, rollout and learned implementations remain experimental and
selectable. The original basic policy is preserved as the control.

## Main tournament: graph policy/value checkpoint

All 96 games reached an actual engine ending. Eight reserved seeds (90000–90007),
four seat rotations, and three settings: Trodain at 2,500G; Trodain at its normal
10,000G target; unseen large test board at 12,000G. Training used only Trodain at
2,500G and 5,000G. No test outcomes were used to fit the checkpoints.

| Opponent | Wins | Win rate | Decision p95 |
|---|---:|---:|---:|
| basic | 16/96 | 16.7% | 0.6 ms |
| strategic | 25/96 | 26.0% | 0.9 ms |
| rollout | 39/96 | 40.6% | 57.2 ms |
| learned | 16/96 | 16.7% | 68.3 ms |

These are mixed four-player games. They do not establish universal strength or
human enjoyment. Seed-block bootstrap intervals are in `summary.json`; rotations
share seeds and must not be treated as 96 independent random draws. Timing was
measured on this Mac during a three-process evaluation batch; it excludes browser
animation and event-snapshot overhead. Search-only p95 was 87.8 ms for rollout
and 109.5 ms for the graph policy, while simple/forced choices are much faster.

## Neural comparison

A separate 48-game MLP tournament used the same first four seeds, seat rotations,
boards and targets. With MLP in the learned seat: basic 4 wins, strategic 8,
rollout 18, learned 18. On those same 48 cases the graph checkpoint won 12.
This favors retaining the simpler MLP as an option. It is not a clean architecture
ablation: the graph model uses additional features, omits forced movement from
value training examples, and uses 30 fitting epochs per stage versus the MLP's
80. More training was not assumed to mean stronger play.

Total training time across all three runs was 18.52
minutes, below the one-hour cap. Each run collected 120 completed matches.
The first MLP run was discarded after correcting hypothetical suit-arrival
scoring; its metadata is retained for honest time accounting. The final MLP and
graph runs each used demonstration/search imitation followed by mixed checkpoint
self-play and terminal win labels. Graph weights were optimized by backpropagation,
not left as a fixed feature transform.

## Inspect and reproduce

Open `index.html` for the main results and actual recorded turn replays, including
the final winning state. `mlp/index.html` contains the MLP tournament. The gzip
JSONL archives retain every match's decisions, candidate search scores, outcomes,
final state and the recorded replay frames. `manifest.json` records checkpoint
hash, seed range and search budget. Checkpoints ship in
`src/road_to_riches/ai/lab/checkpoints/`: `trained.json` is the graph model and
`mlp.json` is the MLP model. `initial-model.json` is the graph run's first-stage
checkpoint.

From the experimental branch with the project Python environment active:

```sh
PYTHONPATH=src python -m road_to_riches.ai.lab serve --port 18812 --target 5000
PYTHONPATH=src python -m road_to_riches.ai.lab tournament --output .runtime/reproduce --seeds 8 --workers 3
PYTHONPATH=src python -m road_to_riches.ai.lab train --output .runtime/retrain --games 120 --seconds 900
```

The live default is P0 human, P1 strategic, P2 rollout, P3 learned graph. Pass
`--model src/road_to_riches/ai/lab/checkpoints/mlp.json` to try the MLP instead.
No current production/default AI or existing user match is replaced.

Validation: 797 Python tests passed, with the optional NumPy training test skipped
in the base environment; all 14 AI-lab tests passed separately with NumPy and
localhost access, including that training test. Ruff, TypeScript checking and
production web build passed. Browser inspection covered a human turn followed
by all three AI turns, and the report's replay controls; no console errors were
observed. The socket integration test also runs three full rounds using all
three final policies while preserving human control.
