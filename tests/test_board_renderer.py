"""Tests for the board renderer."""

from __future__ import annotations

from road_to_riches.board import load_board
from road_to_riches.client.board_renderer import (
    CELL_H,
    CELL_W,
    render_board,
    render_square_cell,
)
from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit


class TestRenderSquareCell:
    def test_basic_bank_cell(self):
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.BANK)
        lines = render_square_cell(sq, player_ids=[])
        assert len(lines) == CELL_H
        assert all(len(line) == CELL_W for line in lines)
        assert "BANK" in lines[1]
        assert lines[0].startswith("┌")
        assert lines[0].endswith("┐")
        assert lines[-1].startswith("└")
        assert lines[-1].endswith("┘")

    def test_shop_cell_with_owner(self):
        sq = SquareInfo(
            id=1,
            position=(4, 0),
            type=SquareType.SHOP,
            property_district=0,
            property_owner=2,
        )
        lines = render_square_cell(sq, player_ids=[])
        assert "SHOP" in lines[1]
        assert "d0" in lines[2]
        assert "O2" in lines[2]

    def test_cell_with_players(self):
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.BANK)
        lines = render_square_cell(sq, player_ids=[0, 3])
        assert "P0" in lines[3]
        assert "P3" in lines[3]

    def test_suit_cell_shows_symbol(self):
        sq = SquareInfo(
            id=3, position=(0, 0), type=SquareType.SUIT, suit=Suit.SPADE
        )
        lines = render_square_cell(sq, player_ids=[])
        assert "♠" in lines[2]

    def test_suit_heart(self):
        sq = SquareInfo(
            id=4, position=(0, 0), type=SquareType.SUIT, suit=Suit.HEART
        )
        lines = render_square_cell(sq, player_ids=[])
        assert "♥" in lines[2]

    def test_unowned_shop(self):
        sq = SquareInfo(
            id=1,
            position=(0, 0),
            type=SquareType.SHOP,
            property_district=1,
        )
        lines = render_square_cell(sq, player_ids=[])
        assert "d1" in lines[2]
        assert "O" not in lines[2]  # no owner


class TestRenderBoard:
    def _make_state(self, board_path: str, num_players: int = 1) -> GameState:
        board, stock = load_board(board_path)
        players = [
            PlayerState(player_id=i, position=0, ready_cash=1500)
            for i in range(num_players)
        ]
        return GameState(board=board, stock=stock, players=players)

    def test_solo_board_renders(self):
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        assert isinstance(output, str)
        lines = output.split("\n")
        # Should have multiple lines
        assert len(lines) > CELL_H
        # Should contain square types
        assert "BANK" in output
        assert "SHOP" in output
        assert "SUIT" in output

    def test_player_shown_on_board(self):
        state = self._make_state("boards/solo_board.json")
        # Player 0 starts at square 0 (BANK)
        output = render_board(state)
        # P0 should appear in the BANK cell area
        assert "P0" in output

    def test_player_moves(self):
        state = self._make_state("boards/solo_board.json")
        state.players[0].position = 5  # Move to sq5 (SHOP d1)
        output = render_board(state)
        assert "P0" in output

    def test_test_board_renders(self):
        state = self._make_state("boards/test_board.json", num_players=4)
        output = render_board(state)
        assert "BANK" in output
        assert "P0" in output

    def test_connections_present(self):
        """Board should have connecting lines between squares."""
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        # Horizontal connections use ─
        assert "─" in output

    def test_board_dimensions_reasonable(self):
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        lines = output.split("\n")
        # Solo board is 4 columns x 4 rows of positions
        # Should be roughly 4*CELL_W + 3*gap_h wide
        max_width = max(len(line) for line in lines)
        assert max_width > CELL_W * 2  # at least 2 cells wide
        assert max_width < 200  # not absurdly wide

    def test_ownership_shown_after_purchase(self):
        state = self._make_state("boards/solo_board.json")
        # Simulate buying shop at sq1
        sq = state.board.squares[1]
        sq.property_owner = 0
        state.players[0].owned_properties.append(1)
        output = render_board(state)
        assert "O0" in output  # Owner 0 shown

    def test_multiple_squares_have_connections(self):
        """Vertical and horizontal connections should both exist."""
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        assert "─" in output  # horizontal
        assert "│" in output  # vertical

    def test_empty_board(self):
        board, stock = load_board("boards/solo_board.json")
        board.squares = []
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1500)
        ]
        state = GameState(board=board, stock=stock, players=players)
        output = render_board(state)
        assert output == "(empty board)"
