# Graph AI diagnosis — paused for architecture review

The user paused further evaluation to discuss the training methodology on
17 September. No opponent was promoted and the existing live game is unchanged.

Completed old-checkpoint diagnostic (same 48 cases per mode): ordinary rollout
16 wins, ranking-only 20, value-only 13, both 13. These are four seed blocks,
not 48 independent random samples. Fresh ranking-only confirmation: 8/48 wins.
Its corresponding baseline was still incomplete when the user paused work;
do not interpret 8/48 as a paired comparison with the earlier 16/48.

Revised training completed all 240 games in 760.09 seconds: 216 fitting games
and 24 whole-game validation games, two boards and three targets. The checkpoint
is `src/road_to_riches/ai/lab/checkpoints/covered.json`. The original checkpoints
are unchanged. Training metadata and the first-stage checkpoint are retained here.

The new checkpoint has NOT completed its evaluation. `diagnostic-new` and
`confirmation-baseline` contain partial, resumable evidence with manifests;
there is no final result or promotion recommendation for the new checkpoint.
The `old` and `confirmation-old` folders contain completed reports/replays.
The value-overrides example includes the heuristic tie-breaker: the old value
head changed the baseline choice on 10 of 22 searched decisions in that one game.
That demonstrates influence, not that every override was a mistake.

Resume only after agreeing on the architecture and experimental protocol.
