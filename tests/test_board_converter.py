"""Golden tests for the FRB board converter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.board_converter.convert_frb import (
    FrbBoard,
    FrbSquare,
    convert_to_json,
    parse_frb,
)

CONVERSION_FIXTURES = [
    Path("boards/conversion_tests/bobomb/bobomb"),
    Path("boards/conversion_tests/trodain/trodain"),
]


@pytest.mark.parametrize("fixture_stem", CONVERSION_FIXTURES)
def test_frb_conversion_matches_checked_in_json(fixture_stem: Path, tmp_path: Path):
    frb_path = fixture_stem.with_suffix(".frb")
    expected_json_path = fixture_stem.with_suffix(".json")

    parsed = parse_frb(frb_path.read_bytes())
    converted = convert_to_json(parsed)

    output_path = tmp_path / expected_json_path.name
    output_path.write_text(json.dumps(converted, indent=2) + "\n")

    assert json.loads(output_path.read_text()) == json.loads(expected_json_path.read_text())


def test_parse_frb_rejects_invalid_header():
    with pytest.raises(ValueError, match="Invalid magic"):
        parse_frb(b"not an frb")


def test_convert_to_json_rejects_unknown_square_type():
    board = FrbBoard(
        initial_cash=1200,
        target_networth=10000,
        base_salary=300,
        salary_increment=100,
        max_dice_roll=6,
        num_districts=0,
        squares=[
            FrbSquare(
                index=0,
                frb_type=999,
                x=0,
                y=0,
                waypoints=[],
                district=0,
                value=0,
                price=0,
            )
        ],
    )

    with pytest.raises(ValueError, match="Unrecognized square type 999"):
        convert_to_json(board)
