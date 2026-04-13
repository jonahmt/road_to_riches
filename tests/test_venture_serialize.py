"""Tests for venture deck and grid serialization round-trips."""

from road_to_riches.models.venture_deck import VentureCard, VentureDeck
from road_to_riches.models.venture_grid import VentureGrid
from road_to_riches.models.serialize import (
    game_state_to_dict,
    game_state_from_dict,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.board_state import BoardState, PromotionInfo
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.stock_state import StockState


def _minimal_state(
    venture_deck: VentureDeck | None = None,
    venture_grid: VentureGrid | None = None,
) -> GameState:
    """Create a minimal GameState for serialization testing."""
    return GameState(
        board=BoardState(
            max_dice_roll=6,
            target_networth=10000,
            max_bankruptcies=1,
            num_districts=3,
            promotion_info=PromotionInfo(
                base_salary=200,
                salary_increment=100,
                shop_value_multiplier=1,
                comeback_multiplier=1,
            ),
            squares=[],
        ),
        stock=StockState(stocks=[]),
        players=[PlayerState(player_id=0, position=0, ready_cash=1000)],
        current_player_index=0,
        venture_deck=venture_deck,
        venture_grid=venture_grid,
    )


class TestVentureDeckSerialization:
    def test_round_trip(self):
        deck = VentureDeck(
            cards={
                1: VentureCard(1, "Free Direction", "Go any way", "/cards/001/card.py"),
                2: VentureCard(2, "Roll Again", "Extra roll", "/cards/002/card.py"),
            },
            remaining=[2, 1],
            full_deck=[1, 2, 1],
        )
        state = _minimal_state(venture_deck=deck)
        d = game_state_to_dict(state)
        restored = game_state_from_dict(d)

        assert restored.venture_deck is not None
        rd = restored.venture_deck
        assert len(rd.cards) == 2
        assert rd.cards[1].name == "Free Direction"
        assert rd.cards[2].description == "Extra roll"
        assert rd.remaining == [2, 1]
        assert rd.full_deck == [1, 2, 1]

    def test_none_deck(self):
        state = _minimal_state(venture_deck=None)
        d = game_state_to_dict(state)
        restored = game_state_from_dict(d)
        assert restored.venture_deck is None


class TestVentureGridSerialization:
    def test_round_trip_empty(self):
        grid = VentureGrid()
        state = _minimal_state(venture_grid=grid)
        d = game_state_to_dict(state)
        restored = game_state_from_dict(d)

        assert restored.venture_grid is not None
        assert len(restored.venture_grid.cells) == 8
        assert all(cell is None for row in restored.venture_grid.cells for cell in row)

    def test_round_trip_with_claims(self):
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        grid.claim(3, 5, 1)
        grid.claim(7, 7, 2)

        state = _minimal_state(venture_grid=grid)
        d = game_state_to_dict(state)
        restored = game_state_from_dict(d)

        rg = restored.venture_grid
        assert rg.cells[0][0] == 0
        assert rg.cells[3][5] == 1
        assert rg.cells[7][7] == 2
        assert rg.cells[1][1] is None

    def test_none_grid(self):
        state = _minimal_state(venture_grid=None)
        d = game_state_to_dict(state)
        restored = game_state_from_dict(d)
        assert restored.venture_grid is None
