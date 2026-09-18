# Experimental AI laboratory

The user approved comparing strategic, simulation and learned opponents, including
local training for at most one hour. This experiment branches from the preserved
3D checkpoint `ed8e1e8` on `codex/ai-lab`. It does not replace the default basic AI
or change gameplay rules, the five-card deck, or any running user match.

## Architectures

- `basic`: the existing greedy suit-collector, retained as the control.
- `strategic` (A): explicit candidate scores for legal route progress, cash
  reserve, district consolidation, stock exposure and investment. Directed BFS
  includes entry direction and collected suits. Once eligible, the objective
  becomes a bank visit. It can accept/counter offers, propose purchases and
  one-for-one exchanges, with at most one voluntary financial/deal action per turn.
- `rollout` (B): ranks the same candidates by engine-backed Monte Carlo rollouts.
  Default budget: three candidate actions, two samples each, four individual
  player turns. The same sampled seeds are used for each candidate. Opponents
  inside hypothetical futures use the strategic policy, not their actual future
  choices. The leaf score includes relative wealth, liquidity, development and
  distance to promotion/victory. Real terminal outcomes dominate this score.
- `learned` (C): a small policy network ranks candidates, then the same rollout
  budget tests them. A separately trained value network augments the leaf score.
  The graph variant learns a message-passing encoder: twelve public features per
  square plus its neighbors' mean features feed an eight-unit tanh layer. Three
  readouts pool the whole board, the acting player's location and owned shops.
  These graph embeddings join strategic features in separate 32-unit tanh
  policy/value heads. Policy also sees decision type and candidate attributes;
  value predicts the player's terminal win indicator. An MLP-only checkpoint
  provides a simpler neural comparison. Both support arbitrary board sizes and
  use only standard Python at inference; training learns the graph weights too.

Candidate generation is a restricted strategic action set, not exhaustive game
search. Investment and stock quantities are sampled; exchanges propose one shop
per side. Unsupported decisions retain the basic policy. Candidates include
neutral actions so search can decline an attractive-looking purchase. Model C
can change both the candidate shortlist and valuation; its results should not be
interpreted as a pure value-network ablation.

## Simulator fidelity and information

`PlanningGameLoop` captures the current production event after its execution and
before its interactive dispatch. A branch copies state, pending events, movement
undo data and transient turn fields. Earlier input responses within that dispatch
are replayed, including nested script and negotiation decisions. It then applies
the alternative and advances the actual production engine.

Random events before the decision are replayed to reproduce already-observed
facts. At the candidate boundary, future RNG is independently seeded and the
future deck is sampled from its public full composition. The experiment does
not exploit the remaining card order or remember the depletion cycle. All
policies use the same public board/player/stock inputs. Live RNG and state are
restored after every hypothetical branch; candidate tie-breaking has its own
RNG stream. Automated tests check this isolation and repeatability.

Search is bounded by candidate count, samples, turn horizon and defensive event /
decision limits. It runs serially in a dedicated game process because the existing
engine uses module-level Python randomness. The opt-in live server rejects extra
sessions; ordinary servers and the default AI launch path are unchanged. The
server's only shared change is an overridable loop-construction method.

## Training and evaluation

`python -m road_to_riches.ai.lab train --output PATH --seconds 900 --games 120`
uses optional NumPy (`pip install -e '.[ai]'`) for training only. First it collects
strategic/search demonstrations and terminal labels. Then it collects mixed
self-play against basic/strategic/rollout and the first neural checkpoint,
followed by another fitting pass. `--architecture mlp` selects the dense-only
comparison; the default is the graph encoder. This is small-scale expert iteration, not a
large PPO run. Partial games do not become training win labels. The command
validates a requested training budget of 1–3600 seconds, checks the deadline
inside collection and fitting, and exports both checkpoints and provenance.

`python -m road_to_riches.ai.lab tournament --model PATH/model.json --output DIR`
runs all four seat rotations of each reserved evaluation seed, on short Trodain,
normal-target Trodain and an unseen larger test board. It records real victory,
bankruptcy, turn counts, decision latency and search scores. Turn-capped games
remain explicitly unfinished; net worth is never substituted for a real win.
The output manifest prevents mixing different model/budget runs when resuming.

`index.html` contains the comparison and actual recorded turn snapshots.
`summary.json` includes results by setting, descriptive Wilson intervals, and
seed-block bootstrap differences against basic. Seed blocks retain rotations and
settings together; few blocks still mean substantial uncertainty. No Elo or
unqualified superiority is inferred from a small tournament.

## Play and inspect

`python -m road_to_riches.ai.lab serve --model PATH/model.json
--profiles human,strategic,rollout,learned --port 18810 --target 5000`
starts an isolated server for the existing 3D frontend. Profiles are explicit and
human seats must precede AI seats. Presentation-only socket peers handle presentation
acknowledgments while decisions execute through the same lab policies used in
tournaments. This preserves browser animation pacing. The live server accepts
only the one experimental default session.

## Follow-up: controlled neural guidance diagnosis

The 17 September follow-up preserves the original graph/MLP checkpoints and
adds `python -m road_to_riches.ai.lab.ablation --model PATH --output DIR`.
Four modes change only the learned seat: `off` is ordinary rollout, `ranking`
uses the policy head only, `value` uses the value head only, and `both` preserves
the original combination. Other seats are basic, strategic and rollout. All
modes share the same four seat rotations, board/target settings, seeds and
search budgets. Turning both heads off is tested to reproduce rollout's exact
actions, search scores and terminal state. Changing an action can change future
random consumption; matching seeds does not imply identical subsequent dice.
Reports retain actual game endings, replays, checkpoint hashes, and paired
seed-block bootstrap intervals. Small seed counts remain exploratory evidence.
Diagnostic seeds start at 92000; fresh confirmation seeds start at 94000.

Revised training uses Trodain and the small test board, each at 2,500G, 5,000G
and 10,000G; the large board remains unseen. Training seeds start at 51000 and
61000, separate from evaluation. Every tenth whole game is withheld from fitting
for value calibration and policy teacher-agreement diagnostics. Only rollout
teacher decisions supervise the policy head. Mixed self-play still contributes
terminal value labels, but the learner's own choices are not imitation targets.
All candidates are kept, including chosen actions beyond the old twelve-row cap.
Collection covers every searched decision type encountered. A checkpoint records
per-type training counts and only ranks types with at least 32 teacher decisions;
other types preserve strategic ordering. This also avoids applying learned
ranking to unsupported non-search menus. Legacy checkpoints without this metadata
retain their old behavior for honest comparisons.

The graph encoder and search budget are unchanged in this follow-up. Retraining
is a combined data/coverage intervention, not an isolated architecture test.
Each of the two training stages reserves time for fitting. The revised run is
capped at 30 minutes, keeping combined training with the previous 18.52 minutes
below the user's one-hour allowance. New results/checkpoints are stored separately;
no default opponent or existing live game is replaced automatically.

`serve` and `tournament` also accept `--guidance off|ranking|value|both` so the
measured configuration can be played explicitly. The default remains `both`
with the original checkpoint; selecting a recommended deployment is separate
from running this experiment. `train --seed N` makes collection seeds explicit.

### Paused for architecture review

The user paused this follow-up before the revised checkpoint finished evaluation.
The completed first diagnostic was off16/ranking20/value13/both13 wins per48
cases. Fresh ranking-only confirmation was8/48; its matching baseline was still
partial when stopped, so it does not establish a paired advantage or deficit.
Revised training finished240 games in760.09 seconds, with216 fitting and24
whole-game validation games. Its checkpoint is `checkpoints/covered.json`.
Further runs and any promotion await discussion of the learning objective,
representation, search/learning interface, and evaluation protocol. Completed
and clearly labeled partial evidence is in `artifacts/ai_lab/2026-09-17/`.
