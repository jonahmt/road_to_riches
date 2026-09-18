"""Evolution preserves frozen controls and validates independently deployable policies."""

import gzip
import json
import random
from dataclasses import replace

import pytest

from road_to_riches.ai.lab.evolution import identity, mutate, run_case
from road_to_riches.ai.lab.parameters import DEFAULT_PARAMETERS, PolicyParameters
from road_to_riches.ai.lab.runner import match
from road_to_riches.ai.lab.strategy import evaluate
from tests.test_ai_lab import BOARD, setup_loop


def test_defaults_preserve_pre_evolution_recorded_match():
    with gzip.open("artifacts/ai_lab/2026-09-17/old/off/matches.jsonl.gz", "rt") as stream:
        recorded = json.loads(next(stream))
    result = match(
        recorded["board"],
        ["basic", "strategic", "rollout", "rollout"],
        recorded["seed"],
        target=recorded["target"],
        parameters={3: DEFAULT_PARAMETERS},
    )
    assert result["final"] == recorded["final"]
    assert json.loads(json.dumps([d["action"] for d in result["decisions"]])) == [
        d["action"] for d in recorded["decisions"]
    ]


def test_checkpoint_roundtrip_mutation_bounds_and_phase_isolation(tmp_path):
    parent = DEFAULT_PARAMETERS
    rng = random.Random(7)
    for phase in ("strategic", "rollout"):
        child = parent
        for _ in range(100):
            child = mutate(child, rng, phase)
        path = tmp_path / f"{phase}.json"
        child.save(path)
        assert PolicyParameters.load(path) == child
        assert identity(child) != identity(parent)
        if phase == "strategic":
            assert child.leaf == parent.leaf
        else:
            assert child.reserve == parent.reserve
    with pytest.raises(ValueError):
        PolicyParameters(reserve=float("nan"))
    with pytest.raises(ValueError):
        PolicyParameters(leaf=(1,))


def test_evolved_terminal_outcomes_dominate_all_evolved_leaf_scores():
    loop, _ = setup_loop()
    p = replace(DEFAULT_PARAMETERS, leaf=(8.0,) * 9)
    loop.state.players[0].ready_cash = 10000000
    assert evaluate(loop.state, 0, params=p) <= 10
    assert evaluate(loop.state, 0, winner=0, params=p) == 12
    assert evaluate(loop.state, 0, winner=1, params=p) == -12


def test_parameterized_match_does_not_change_other_seats_and_records_real_end(tmp_path):
    checkpoint = tmp_path / "candidate.json"
    replace(DEFAULT_PARAMETERS, reserve=0.5).save(checkpoint)
    output = tmp_path / "game.json.gz"
    result = run_case(
        (str(checkpoint), "strategic", BOARD, 2500, 219000, 2, str(output), True, 1, 2)
    )
    assert result["finished"]
    with gzip.open(output, "rt") as stream:
        record = json.load(stream)
    assert record["challenger_seat"] == 1
    assert record["profiles"] == ["rollout", "challenger", "basic", "strategic"]
    assert record["frames"][-1]["terminal"]
    assert record["frames"][-1]["state"] == record["final"]


def test_direct_league_preserves_seat_labels_and_supports_report_without_basic(tmp_path):
    from road_to_riches.ai.lab.league import run_league_case
    from road_to_riches.ai.lab.report import build_report

    strategic = tmp_path / "strategic.json"
    rollout = tmp_path / "rollout.json"
    replace(DEFAULT_PARAMETERS, reserve=0.8).save(strategic)
    replace(DEFAULT_PARAMETERS, leaf=(2.5, 0.8, 0.3, 1, 0.2, 0.4, 0.8, 2.5, 0.9)).save(rollout)
    path = tmp_path / "0-440001-1.json"
    result = run_league_case(
        (str(strategic), str(rollout), BOARD, 2500, 440001, 1, str(path), True, 1, 2)
    )
    assert result["finished"]
    game = json.loads(path.read_text())
    assert game["profiles"] == ["rollout", "evolved_strategic", "evolved_rollout", "strategic"]
    assert {d["profile"] for d in game["decisions"]} == set(game["profiles"])
    build_report(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["finished"] == 1
    assert summary["bootstrap_reference"] in ("rollout", "strategic")
    assert sum(r["wins"] for r in summary["profiles"].values()) == 1
