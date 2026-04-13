"""Tests for VentureDeck: draw, reshuffle, card loading, deck building."""

import os
import tempfile
from pathlib import Path

import pytest

from road_to_riches.models.venture_deck import (
    VentureCard,
    VentureDeck,
    build_deck,
    load_cards_from_directory,
)


def _make_card(card_id: int, name: str = "") -> VentureCard:
    return VentureCard(
        card_id=card_id,
        name=name or f"Card {card_id}",
        description=f"Desc {card_id}",
        script_path=f"/fake/cards/{card_id}/card.py",
    )


class TestVentureDeckDraw:
    def test_draw_returns_card(self):
        card = _make_card(1)
        deck = VentureDeck(
            cards={1: card},
            remaining=[1],
            full_deck=[1],
        )
        drawn = deck.draw()
        assert drawn.card_id == 1

    def test_draw_removes_from_remaining(self):
        cards = {i: _make_card(i) for i in range(1, 4)}
        deck = VentureDeck(
            cards=cards,
            remaining=[1, 2, 3],
            full_deck=[1, 2, 3],
        )
        deck.draw()
        assert len(deck.remaining) == 2

    def test_draw_all_then_reshuffles(self):
        cards = {1: _make_card(1), 2: _make_card(2)}
        deck = VentureDeck(
            cards=cards,
            remaining=[1, 2],
            full_deck=[1, 2],
        )
        deck.draw()
        deck.draw()
        assert len(deck.remaining) == 0
        # Next draw triggers reshuffle
        drawn = deck.draw()
        assert drawn.card_id in (1, 2)
        assert len(deck.remaining) == 1  # drew one from reshuffled deck

    def test_draw_empty_deck_reshuffles(self):
        cards = {1: _make_card(1)}
        deck = VentureDeck(
            cards=cards,
            remaining=[],
            full_deck=[1, 1, 1],
        )
        drawn = deck.draw()
        assert drawn.card_id == 1
        # After reshuffle, 3 copies minus the one drawn = 2 remaining
        assert len(deck.remaining) == 2

    def test_full_deck_with_duplicates(self):
        card = _make_card(1)
        deck = VentureDeck(
            cards={1: card},
            remaining=[1, 1, 1],
            full_deck=[1, 1, 1],
        )
        results = [deck.draw().card_id for _ in range(3)]
        assert all(r == 1 for r in results)


class TestBuildDeck:
    def test_build_with_all_cards(self):
        cards = {i: _make_card(i) for i in range(1, 6)}
        deck = build_deck(cards)
        assert set(deck.full_deck) == {1, 2, 3, 4, 5}
        assert len(deck.remaining) == 5

    def test_build_with_composition(self):
        cards = {1: _make_card(1), 2: _make_card(2), 3: _make_card(3)}
        deck = build_deck(cards, deck_composition=[1, 1, 2, 2, 3])
        assert sorted(deck.full_deck) == [1, 1, 2, 2, 3]
        assert len(deck.remaining) == 5

    def test_build_filters_missing_cards(self):
        cards = {1: _make_card(1)}
        deck = build_deck(cards, deck_composition=[1, 2, 3])
        # Only card 1 exists, so 2 and 3 are filtered out
        assert deck.full_deck == [1]

    def test_build_empty_cards(self):
        deck = build_deck({})
        assert deck.full_deck == []
        assert deck.remaining == []


class TestLoadCardsFromDirectory:
    def test_load_valid_cards(self, tmp_path):
        # Create card directory structure
        card_dir = tmp_path / "001"
        card_dir.mkdir()
        (card_dir / "card.py").write_text("def run(state, pid): pass")
        (card_dir / "Free Direction.txt").write_text("Choose your path next turn")

        cards = load_cards_from_directory(tmp_path)
        assert 1 in cards
        assert cards[1].name == "Free Direction"
        assert cards[1].description == "Choose your path next turn"
        assert cards[1].script_path.endswith("card.py")

    def test_load_skips_non_numeric_dirs(self, tmp_path):
        (tmp_path / "readme").mkdir()
        (tmp_path / "001").mkdir()
        (tmp_path / "001" / "card.py").write_text("def run(s,p): pass")
        (tmp_path / "001" / "name.txt").write_text("desc")

        cards = load_cards_from_directory(tmp_path)
        assert len(cards) == 1
        assert 1 in cards

    def test_load_skips_dir_without_py(self, tmp_path):
        card_dir = tmp_path / "001"
        card_dir.mkdir()
        (card_dir / "name.txt").write_text("desc")

        cards = load_cards_from_directory(tmp_path)
        assert len(cards) == 0

    def test_load_missing_txt_uses_defaults(self, tmp_path):
        card_dir = tmp_path / "005"
        card_dir.mkdir()
        (card_dir / "card.py").write_text("def run(s,p): pass")

        cards = load_cards_from_directory(tmp_path)
        assert 5 in cards
        assert cards[5].name == "Card 5"
        assert cards[5].description == ""

    def test_load_nonexistent_directory(self, tmp_path):
        cards = load_cards_from_directory(tmp_path / "nonexistent")
        assert len(cards) == 0
