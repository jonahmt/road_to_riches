"""Shared display constants for terminal clients."""

from __future__ import annotations

STANDARD_SUITS = ("SPADE", "HEART", "DIAMOND", "CLUB")
ALL_SUITS = (*STANDARD_SUITS, "WILD")

PLAYER_COLORS = ["bright_cyan", "orchid1", "bright_yellow", "bright_green"]

DISTRICT_COLORS = [
    "cyan",
    "magenta",
    "bright_green",
    "bright_yellow",
    "bright_red",
    "bright_blue",
]

SUIT_SYMBOLS = {
    "SPADE": "♠",
    "HEART": "♥",
    "DIAMOND": "♦",
    "CLUB": "♣",
    "WILD": "★",
}

BOARD_SUIT_SYMBOLS = {name: SUIT_SYMBOLS[name] for name in STANDARD_SUITS}

SUIT_COLORS = {
    "SPADE": "dodger_blue1",
    "HEART": "bright_red",
    "DIAMOND": "yellow",
    "CLUB": "green",
    "WILD": "white",
}

SUIT_ABBR = {"SPADE": "SPADE", "HEART": "HEART", "DIAMOND": "Dmnd", "CLUB": "CLUB"}

SUIT_LABELS = {
    "SPADE": "Spade",
    "HEART": "Heart",
    "DIAMOND": "Diamond",
    "CLUB": "Club",
    "WILD": "Wild",
}

SUIT_MENU_OPTIONS = [(SUIT_LABELS[name], name) for name in ALL_SUITS]

SUIT_TEXT_SYMBOLS = {
    "SPADE": "S",
    "HEART": "H",
    "DIAMOND": "D",
    "CLUB": "C",
    "WILD": "W",
}
