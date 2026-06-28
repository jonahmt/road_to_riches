"""Tests for board file structural validation."""

from __future__ import annotations

import pytest

from road_to_riches.board.loader import load_board, validate_board_data


def _board_data(squares: list[dict]) -> dict:
    return {
        "target_networth": 10000,
        "squares": squares,
    }


def _square(square_id: int, waypoints: list[dict] | None = None, **kwargs) -> dict:
    data = {
        "id": square_id,
        "type": "BANK",
        "position": [0, 0],
        "waypoints": waypoints or [],
    }
    data.update(kwargs)
    return data


def test_validate_board_data_accepts_known_boards():
    for path in (
        "boards/test_board.json",
        "boards/solo_board.json",
        "boards/large_test_board.json",
        "boards/conversion_tests/bobomb/bobomb.json",
        "boards/conversion_tests/trodain/trodain.json",
    ):
        board, _ = load_board(path)
        assert board.squares


def test_validate_board_data_rejects_non_contiguous_ids():
    data = _board_data([_square(0), _square(2)])

    with pytest.raises(ValueError, match="contiguous"):
        validate_board_data(data)


def test_validate_board_data_rejects_missing_from_id():
    data = _board_data(
        [
            _square(0, waypoints=[{"from_id": 99, "to_ids": [1]}]),
            _square(1),
        ]
    )

    with pytest.raises(ValueError, match="missing from_id 99"):
        validate_board_data(data)


def test_validate_board_data_rejects_missing_to_id():
    data = _board_data(
        [
            _square(0, waypoints=[{"from_id": 1, "to_ids": [99]}]),
            _square(1),
        ]
    )

    with pytest.raises(ValueError, match="missing to_id 99"):
        validate_board_data(data)


def test_validate_board_data_rejects_invalid_square_type():
    data = _board_data([_square(0, type="NOT_A_SQUARE")])

    with pytest.raises(ValueError):
        validate_board_data(data)


def test_validate_board_data_can_require_transport_destinations():
    data = _board_data([_square(0, type="BACKSTREET")])

    with pytest.raises(ValueError, match="missing a destination"):
        validate_board_data(data, require_transport_destinations=True)
