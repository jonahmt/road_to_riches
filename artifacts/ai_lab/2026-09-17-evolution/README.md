# Non-neural evolution experiment — 17 September 2026

864 engine-played games reached real victory conditions. No synthetic winner was
assigned from net worth or a turn limit. Neural training remained paused.

## Findings

| Opponent | Direct league wins / 72 |
| --- | ---: |
| Original strategic | 7 |
| Original rollout | 25 |
| Evolved strategic | 10 |
| Evolved rollout | 30 |

The evolved rollout's league lead is provisional: its paired seed-block bootstrap
95% interval relative to original rollout is −8.3 to +22.2 percentage points.
Fresh matched rollout testing tied at 6/24 wins each. Matched strategic testing
favored the original, 10/48 versus 4/48; the difference interval is −27.1 to +2.1
points. Keep original defaults. The finalists remain playable experiments, not
proven upgrades. Four strategic test seed blocks, six league blocks and two
rollout test blocks provide limited statistical power. Outcomes depend on the
opponent lineup. Do not compare win rates across those lineups as paired data.

## Method

- Five strategic generations: six candidates × twelve games = 360 games.
- Four rollout generations: six candidates × twelve games = 288 games.
- 54 candidate snapshots are preserved, including rejected candidates; identical
  parameter sets retained in later generations have separate versioned snapshots.
- Strategic evolution tunes eight bounded economic preferences. Rollout evolution
  freezes those preferences and tunes nine position-evaluation weights.
- Each generation tests its frozen baseline, retained elites and mutations on
  identical seeds and all four seats. Actual wins determine fitness; completed
  games, bankruptcies and relative wealth break ties. Fresh seeds each generation.
- Training: Trodain at 2500/10000G and small test board at 5000G; strategic seeds
  210000 + 100 × generation, rollout seeds 230000 + 100 × generation.
- Held-out settings: Trodain 10000G, large board 12000G, Bob-omb 10000G. Large and
  Bob-omb were excluded from evolution. Strategic paired seeds 310000–310003;
  direct league 330000–330005; fresh rollout pair 350000–350001.
- Search budget is two samples, four individual-player turns, three candidates.
  Finalists were frozen before evaluation and never revised using test results.
- Generation selection is noisy (twelve cases) and the two phases are coupled;
  this is not a controlled attribution of improvement to individual genes.
- Matching seeds does not guarantee identical later dice after actions diverge.

`summary.json` includes checkpoint SHA-256 hashes checked against evaluation
manifests. Each stage retains gzip JSONL records with terminal states; sampled
games also retain decision traces and final-frame replays. The direct league
retains every decision and three complete replays. `league/index.html` is standalone.

## Reproduce

Run from the experimental checkout with `PYTHONPATH=src` and the project Python:

```sh
python -m road_to_riches.ai.lab.evolution evolve --mode strategic --output NEW/strategic --seed 210000 --generations 5 --workers 3
python -m road_to_riches.ai.lab.evolution evolve --mode rollout --checkpoint NEW/strategic/champion.json --output NEW/rollout --seed 230000 --generations 4 --workers 3
python -m road_to_riches.ai.lab.league --strategic NEW/strategic/champion.json --rollout NEW/rollout/champion.json --output NEW/league --seed 330000 --seeds 6 --workers 3
python -m road_to_riches.ai.lab.evolution evaluate --checkpoint CHECKPOINT --mode strategic --output NEW/test --seed 310000 --seeds 4 --workers 1
```

For the matched rollout test, use mode rollout, seed 350000 and two seeds. Evaluate
both the original strategic-phase `checkpoints/baseline.json` and corresponding
selected champion in separate directories. `evolution_report` packages the named
run directories; see its CLI and this archive layout.

Validation: 811 tests passed; production frontend build passed. Default parameters
reproduce every action and terminal state in an archived pre-evolution game.
Browser inspection confirmed a human turn, all three AI turns, and return to
human control; no browser errors, only existing Three.js deprecation warnings.
The recorded replay reaches actual bank victory even when another bot has more
wealth. Under concurrent evaluation, evolved rollout decision p95 was 99.7ms
(searched decisions 144.0ms; maximum 718.2ms), comparable to original rollout's
101.3ms/145.8ms/855.8ms. These are observed timings, not latency guarantees.

Playable frozen source: commit d63cca9, frontend http://127.0.0.1:15213/,
backend port 18814. P0 human, P1 original rollout, P2 evolved strategic, P3 evolved
rollout. Previous game runtimes are preserved. Report: http://127.0.0.1:15214/.
