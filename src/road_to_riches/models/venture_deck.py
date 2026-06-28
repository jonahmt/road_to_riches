"""Venture card deck model.

Each card is defined by a directory in cards/ containing:
- A .py script file (the card effect, generator or plain function)
- A .txt file (filename = card name, contents = short description)

The deck tracks which cards remain to be drawn. When exhausted, the full
deck is reshuffled.
"""

from __future__ import annotations

import importlib.util
import random
from dataclasses import dataclass, field
from pathlib import Path

from road_to_riches.paths import resolve_resource_path


@dataclass
class VentureCard:
    """A single venture card definition."""

    card_id: int
    name: str
    description: str
    script_path: str


@dataclass
class VentureDeck:
    """A shuffled deck of venture cards that draws without replacement."""

    cards: dict[int, VentureCard] = field(default_factory=dict)
    """All card definitions, keyed by card_id."""

    remaining: list[int] = field(default_factory=list)
    """Card IDs remaining in the current draw pile (shuffled order)."""

    full_deck: list[int] = field(default_factory=list)
    """The complete deck composition (may contain duplicate IDs)."""

    def draw(self) -> VentureCard:
        """Draw a card from the deck. Reshuffles if empty."""
        if not self.remaining:
            self.remaining = list(self.full_deck)
            random.shuffle(self.remaining)
        card_id = self.remaining.pop()
        return self.cards[card_id]


def load_cards_from_directory(cards_dir: str | Path) -> dict[int, VentureCard]:
    """Discover all card definitions from a cards/ directory.

    Each subdirectory named with a numeric ID (e.g., 001, 002) contains:
    - A .py file: the card script
    - A .txt file: filename is card name, contents are description
    """
    cards_dir = resolve_resource_path(cards_dir)
    cards: dict[int, VentureCard] = {}

    if not cards_dir.is_dir():
        return cards

    for entry in sorted(cards_dir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            card_id = int(entry.name)
        except ValueError:
            continue

        py_files = sorted(entry.glob("*.py"))
        if len(py_files) != 1:
            raise ValueError(
                f"Card directory {entry} must contain exactly one .py script; found {len(py_files)}"
            )
        script_path = str(py_files[0])
        _validate_card_script(py_files[0])

        txt_files = sorted(entry.glob("*.txt"))
        if len(txt_files) != 1:
            raise ValueError(
                f"Card directory {entry} must contain exactly one .txt description; "
                f"found {len(txt_files)}"
            )
        name = txt_files[0].stem
        description = txt_files[0].read_text().strip()

        cards[card_id] = VentureCard(
            card_id=card_id,
            name=name,
            description=description,
            script_path=script_path,
        )

    return cards


def _validate_card_script(script_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        f"venture_card_validation_{script_path.stem}", script_path
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"Card script {script_path} cannot be imported")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = getattr(module, "run", None)
    if not callable(run):
        raise ValueError(f"Card script {script_path} must define callable run(state, player_id)")


def build_deck(
    cards: dict[int, VentureCard],
    deck_composition: list[int] | None = None,
) -> VentureDeck:
    """Build a shuffled deck from card definitions.

    If deck_composition is provided (list of card IDs, may have duplicates),
    use it. Otherwise, include one of each available card.
    """
    if deck_composition is not None:
        full_deck = [cid for cid in deck_composition if cid in cards]
    else:
        full_deck = list(cards.keys())

    remaining = list(full_deck)
    random.shuffle(remaining)

    return VentureDeck(
        cards=cards,
        remaining=remaining,
        full_deck=full_deck,
    )
