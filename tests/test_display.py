from __future__ import annotations

from types import SimpleNamespace

from road_to_riches.client.display import (
    ALL_SUITS,
    BOARD_SUIT_SYMBOLS,
    STANDARD_SUITS,
    SUIT_COLORS,
    SUIT_LABELS,
    SUIT_MENU_OPTIONS,
    SUIT_SYMBOLS,
    SUIT_TEXT_SYMBOLS,
)
from road_to_riches.client.text_input import _fmt_suits
from road_to_riches.models.suit import Suit


def test_suit_display_maps_cover_all_suits():
    assert STANDARD_SUITS == ("SPADE", "HEART", "DIAMOND", "CLUB")
    assert ALL_SUITS == ("SPADE", "HEART", "DIAMOND", "CLUB", "WILD")

    all_suit_names = set(ALL_SUITS)
    assert set(SUIT_SYMBOLS) == all_suit_names
    assert set(SUIT_COLORS) == all_suit_names
    assert set(SUIT_LABELS) == all_suit_names
    assert set(SUIT_TEXT_SYMBOLS) == all_suit_names


def test_board_suit_symbols_exclude_wild():
    assert set(BOARD_SUIT_SYMBOLS) == set(STANDARD_SUITS)
    assert "WILD" not in BOARD_SUIT_SYMBOLS


def test_suit_menu_options_follow_shared_order():
    assert SUIT_MENU_OPTIONS == [(SUIT_LABELS[name], name) for name in ALL_SUITS]


def test_text_input_suit_formatting_uses_shared_order_and_symbols():
    player = SimpleNamespace(
        suits={
            Suit.WILD: 2,
            Suit.HEART: 1,
            Suit.SPADE: 1,
        }
    )

    assert _fmt_suits(player) == "S H Wx2"
