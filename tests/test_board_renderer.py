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


class TestCellDimensions:
    def test_cell_size(self):
        assert CELL_W == 8
        assert CELL_H == 4


class TestRenderSquareCell:
    def test_bank_cell(self):
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.BANK)
        lines = render_square_cell(sq, player_ids=[])
        assert len(lines) == CELL_H
        assert "BANK" in lines[1]
        assert "┌" in lines[0]
        assert "┐" in lines[0]
        # Bottom row has square id
        assert "00" in lines[3]

    def test_bank_with_players(self):
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.BANK)
        lines = render_square_cell(sq, player_ids=[1, 3])
        # Bottom row shows player 1 and 3
        assert "1" in lines[3]
        assert "3" in lines[3]

    def test_shop_unowned_shows_value(self):
        sq = SquareInfo(
            id=1,
            position=(0, 0),
            type=SquareType.SHOP,
            property_district=0,
            shop_base_value=150,
        )
        lines = render_square_cell(sq, player_ids=[])
        # Line 1: V + value
        assert "V" in lines[1]
        assert "150" in lines[1]
        # Line 2: no $ when unowned
        assert "$" not in lines[2]

    def test_shop_owned_shows_value_and_rent(self):
        sq = SquareInfo(
            id=5,
            position=(0, 0),
            type=SquareType.SHOP,
            property_district=1,
            property_owner=2,
            shop_base_value=200,
            shop_base_rent=30,
        )
        lines = render_square_cell(sq, player_ids=[])
        assert "V" in lines[1]
        assert "200" in lines[1]
        assert "$" in lines[2]
        assert "30" in lines[2]
        assert "05" in lines[3]  # square id

    def test_suit_spade(self):
        sq = SquareInfo(id=2, position=(0, 0), type=SquareType.SUIT, suit=Suit.SPADE)
        lines = render_square_cell(sq, player_ids=[])
        assert "SPADE" in lines[1]
        assert "♠" in lines[2]

    def test_suit_heart(self):
        sq = SquareInfo(id=4, position=(0, 0), type=SquareType.SUIT, suit=Suit.HEART)
        lines = render_square_cell(sq, player_ids=[])
        assert "HEART" in lines[1]
        assert "♥" in lines[2]

    def test_suit_diamond_abbreviated(self):
        sq = SquareInfo(id=6, position=(0, 0), type=SquareType.SUIT, suit=Suit.DIAMOND)
        lines = render_square_cell(sq, player_ids=[])
        assert "Dmnd" in lines[1]
        assert "♦" in lines[2]

    def test_colors_in_output(self):
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.BANK)
        lines = render_square_cell(sq, player_ids=[0])
        # Bank main color is gold
        assert "gold1" in lines[1]
        # Player 0 uses their player color (bright_cyan)
        assert "bright_cyan" in lines[3]

    def test_shop_district_color_on_border(self):
        sq = SquareInfo(
            id=1,
            position=(0, 0),
            type=SquareType.SHOP,
            property_district=0,
            shop_base_value=100,
        )
        lines = render_square_cell(sq, player_ids=[])
        # District 0 = cyan highlight
        assert "cyan" in lines[0]

    def test_suit_white_border_colored_text(self):
        sq = SquareInfo(id=2, position=(0, 0), type=SquareType.SUIT, suit=Suit.HEART)
        lines = render_square_cell(sq, player_ids=[])
        # Suit squares have white border, colored text
        assert "white" in lines[0]
        assert "bright_red" in lines[1]

    def test_absent_players_shown_as_dots(self):
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.BANK)
        lines = render_square_cell(sq, player_ids=[1])
        # Players 0, 2, 3 absent = dots, player 1 present
        assert "." in lines[3]
        assert "1" in lines[3]


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
        assert len(lines) > CELL_H
        assert "BANK" in output
        assert "V" in output  # shop values

    def test_player_shown_on_board(self):
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        # Player 0 at square 0
        assert "0" in output

    def test_no_border_merging(self):
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        # No merged border characters
        assert "┬" not in output
        assert "├" not in output
        assert "┤" not in output
        assert "┼" not in output

    def test_board_dimensions(self):
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        lines = output.split("\n")
        # Solo board: 4 unique y positions → 4 * CELL_H = 16 lines
        assert len(lines) == 4 * CELL_H

    def test_test_board_renders(self):
        state = self._make_state("boards/test_board.json", num_players=4)
        output = render_board(state)
        assert "BANK" in output

    def test_ownership_shown(self):
        state = self._make_state("boards/solo_board.json")
        sq = state.board.squares[1]
        sq.property_owner = 0
        state.players[0].owned_properties.append(1)
        output = render_board(state)
        # Owned shop shows $ (rent)
        assert "$" in output

    def test_empty_board(self):
        board, stock = load_board("boards/solo_board.json")
        board.squares = []
        players = [PlayerState(player_id=0, position=0, ready_cash=1500)]
        state = GameState(board=board, stock=stock, players=players)
        output = render_board(state)
        assert output == "(empty board)"

    def test_colors_present(self):
        state = self._make_state("boards/solo_board.json")
        output = render_board(state)
        assert "[gold1]" in output  # BANK main color
        assert "[white]" in output  # square ids
