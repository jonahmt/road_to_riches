"""Tests for WASD direction mapping."""

from road_to_riches.client.direction import compute_direction_keys, format_key_hints


class TestDirectionKeys:
    def test_single_choice_right(self):
        mapping = compute_direction_keys((0, 0), [(1, (4, 0))])
        assert mapping == {"d": 1}

    def test_single_choice_left(self):
        mapping = compute_direction_keys((20, 16), [(10, (16, 16))])
        assert mapping == {"a": 10}

    def test_single_choice_down(self):
        mapping = compute_direction_keys((20, 0), [(6, (20, 4))])
        assert mapping == {"s": 6}

    def test_single_choice_up(self):
        mapping = compute_direction_keys((0, 16), [(15, (0, 12))])
        assert mapping == {"w": 15}

    def test_fork_two_directions(self):
        mapping = compute_direction_keys(
            (8, 0), [(3, (12, 0)), (99, (8, 4))]
        )
        assert mapping["d"] == 3   # right
        assert mapping["s"] == 99  # down

    def test_undo_direction(self):
        mapping = compute_direction_keys(
            (8, 0), [(3, (12, 0))], undo_pos=(4, 0)
        )
        assert mapping["d"] == 3       # right = forward
        assert mapping["a"] == "undo"  # left = undo

    def test_undo_only(self):
        mapping = compute_direction_keys((4, 0), [], undo_pos=(0, 0))
        assert mapping["a"] == "undo"

    def test_diagonal_choice(self):
        mapping = compute_direction_keys((0, 0), [(5, (4, 4))])
        # Down-right diagonal — should map to either s or d
        assert 5 in mapping.values()

    def test_no_choices(self):
        mapping = compute_direction_keys((0, 0), [])
        assert mapping == {}

    def test_conflict_resolution(self):
        # Two choices in the same direction (both right)
        mapping = compute_direction_keys(
            (0, 0), [(1, (4, 0)), (2, (8, 0))]
        )
        assert 1 in mapping.values()
        assert 2 in mapping.values()
        assert len(mapping) == 2  # both assigned different keys


class TestFormatKeyHints:
    def test_basic_format(self):
        mapping = {"d": 1, "a": "undo"}
        result = format_key_hints(mapping, {1: "SHOP"})
        assert "\\[A] Undo" in result
        assert "\\[D] SHOP sq1" in result

    def test_no_types(self):
        mapping = {"w": 5}
        result = format_key_hints(mapping)
        assert "\\[W] sq5" in result
