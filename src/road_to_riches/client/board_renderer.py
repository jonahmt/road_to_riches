"""Board renderer for the TUI using Rich markup.

Renders the game board as a grid of 8x4 character cells with colors.
Each cell has a top border, two content lines, and a special bottom
row showing player IDs (left) and square ID (right).

Based on the design spec in design/p0_client.md.
"""

from __future__ import annotations

from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType

# Cell dimensions: 8 wide x 4 tall
INNER_W = 6
CELL_W = INNER_W + 2  # 8
CELL_H = 4

# Suit symbols and colors
SUIT_SYMBOLS = {"SPADE": "♠", "HEART": "♥", "DIAMOND": "♦", "CLUB": "♣"}
SUIT_COLORS = {"SPADE": "bright_blue", "HEART": "red", "DIAMOND": "yellow", "CLUB": "green"}
SUIT_ABBR = {"SPADE": "SPADE", "HEART": "HEART", "DIAMOND": "Dmnd", "CLUB": "CLUB"}

# District border colors
DISTRICT_COLORS = [
    "cyan", "magenta", "bright_green", "bright_yellow", "bright_red", "bright_blue",
]

# Player text colors
PLAYER_COLORS = ["bright_cyan", "bright_magenta", "bright_yellow", "bright_green"]

# Square type display config: (line1_text, line2_text, main_color, highlight_color)
# None for lines means use type-specific logic
_SPECIAL_DISPLAY: dict[SquareType, tuple[str, str, str, str]] = {
    SquareType.BANK: ("BANK", "", "gold1", "white"),
    SquareType.VENTURE: ("VNTR", "", "dark_orange", "white"),
    SquareType.TAKE_A_BREAK: ("BREAK", "", "grey70", "white"),
    SquareType.BOON: ("BOON", "", "bright_green", "white"),
    SquareType.BOOM: ("BOOM", "", "bright_red", "white"),
    SquareType.ROLL_ON: ("ROLL", "ON", "bright_blue", "white"),
    SquareType.STOCKBROKER: ("STOCK", "BROKR", "gold1", "white"),
    SquareType.BACKSTREET: ("BACK", "STRT", "grey50", "white"),
    SquareType.DOORWAY: ("DOOR", "WAY", "grey50", "white"),
    SquareType.CANNON: ("CANN", "ON", "bright_red", "white"),
    SquareType.VACANT_PLOT: ("VACNT", "PLOT", "grey70", "white"),
    SquareType.VP_CHECKPOINT: ("CHECK", "POINT", "bright_magenta", "white"),
    SquareType.VP_TAX_OFFICE: ("TAX", "OFFCE", "bright_magenta", "white"),
    SquareType.SUIT_YOURSELF: ("SUIT", "YRSLF", "orchid", "white"),
}


def _color(text: str, color: str) -> str:
    return f"[{color}]{text}[/{color}]"


def _render_cell(sq: SquareInfo, player_ids: list[int]) -> list[str]:
    """Render a single square as 4 lines of 8 visible characters.

    Lines contain Rich markup but visible width is always 8.
    Format:
      ┌──────┐   (highlight color)
      │ TEXT │   (border=highlight, text=main)
      │ TEXT │   (border=highlight, text=main)
      .1..──00   (players=white, ──=highlight, id=white)
    """
    from road_to_riches.models.suit import Suit

    main_color = "white"
    highlight_color = "white"
    line1_text = ""
    line2_text = ""

    if sq.type == SquareType.SHOP:
        # Shop: V + value on line 1, $ + rent on line 2 (if owned)
        val = sq.shop_current_value or sq.shop_base_value or 0
        line1_text = f"V{val:>5}"
        if sq.property_owner is not None:
            rent = sq.shop_base_rent or 0
            line2_text = f"${rent:>5}"
            main_color = PLAYER_COLORS[sq.property_owner % len(PLAYER_COLORS)]
        else:
            line2_text = ""
            main_color = "white"
        d = sq.property_district or 0
        highlight_color = DISTRICT_COLORS[d % len(DISTRICT_COLORS)]

    elif sq.type == SquareType.SUIT:
        suit_name = sq.suit.value if isinstance(sq.suit, Suit) else str(sq.suit)
        line1_text = SUIT_ABBR.get(suit_name, suit_name[:5]).center(INNER_W)
        symbol = SUIT_SYMBOLS.get(suit_name, "?")
        line2_text = f"  {symbol}{symbol}  "
        suit_color = SUIT_COLORS.get(suit_name, "white")
        main_color = "white"
        highlight_color = suit_color

    elif sq.type == SquareType.CHANGE_OF_SUIT:
        line1_text = "C.o.S."
        suit_name = sq.suit.value if isinstance(sq.suit, Suit) else "SPADE"
        symbol = SUIT_SYMBOLS.get(suit_name, "?")
        abbr = SUIT_ABBR.get(suit_name, suit_name[:4])
        line2_text = f" {abbr} " if len(abbr) <= 4 else abbr[:INNER_W]
        highlight_color = SUIT_COLORS.get(suit_name, "white")
        main_color = "bright_white"

    elif sq.type in _SPECIAL_DISPLAY:
        disp = _SPECIAL_DISPLAY[sq.type]
        line1_text = disp[0]
        line2_text = disp[1]
        main_color = disp[2]
        highlight_color = disp[3]

    else:
        line1_text = sq.type.value[:INNER_W]
        line2_text = ""
        main_color = "white"
        highlight_color = "white"

    # Center content within INNER_W
    l1 = line1_text.center(INNER_W) if len(line1_text) < INNER_W else line1_text[:INNER_W]
    l2 = line2_text.center(INNER_W) if len(line2_text) < INNER_W else line2_text[:INNER_W]

    # Build the 4 lines
    border_h = _color("┌" + "─" * INNER_W + "┐", highlight_color)
    vbar = _color("│", highlight_color)
    content1 = vbar + _color(l1, main_color) + vbar
    content2 = vbar + _color(l2, main_color) + vbar

    # Bottom row: player slots (4 chars) + ── (2 chars) + square id (2 chars)
    player_slots = ""
    for pid in range(4):
        if pid in player_ids:
            p_color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
            player_slots += _color(str(pid), p_color)
        else:
            player_slots += _color(".", "grey37")
    sep = _color("──", highlight_color)
    sq_id = _color(f"{sq.id:02d}", "white")
    bottom = player_slots + sep + sq_id

    return [border_h, content1, content2, bottom]


def render_square_cell(sq: SquareInfo, player_ids: list[int]) -> list[str]:
    """Public API for rendering a single cell. Returns CELL_H lines."""
    return _render_cell(sq, player_ids)


def render_board(state: GameState) -> str:
    """Render the full board as a multi-line string with Rich markup.

    Squares are placed on a grid based on their (x, y) positions.
    Adjacent squares sit side by side with separate borders.
    """
    board = state.board

    if not board.squares:
        return "(empty board)"

    # Build player position map: square_id -> list of player_ids
    player_positions: dict[int, list[int]] = {}
    for p in state.players:
        if not p.bankrupt:
            player_positions.setdefault(p.position, []).append(p.player_id)

    # Normalize positions to grid indices
    positions = [sq.position for sq in board.squares]
    unique_x = sorted(set(p[0] for p in positions))
    unique_y = sorted(set(p[1] for p in positions))
    x_to_col = {x: i for i, x in enumerate(unique_x)}
    y_to_row = {y: i for i, y in enumerate(unique_y)}

    cols = len(unique_x)
    rows = len(unique_y)

    # Grid of squares (None where empty)
    grid: list[list[SquareInfo | None]] = [
        [None] * cols for _ in range(rows)
    ]
    for sq in board.squares:
        grid[y_to_row[sq.position[1]]][x_to_col[sq.position[0]]] = sq

    # Build output line by line
    output_lines: list[str] = []

    for r in range(rows):
        # Render all cells in this row
        row_cells: list[list[str] | None] = []
        for c in range(cols):
            sq = grid[r][c]
            if sq is None:
                row_cells.append(None)
            else:
                pids = player_positions.get(sq.id, [])
                row_cells.append(_render_cell(sq, pids))

        # Combine cells horizontally for each of CELL_H lines
        for line_idx in range(CELL_H):
            parts: list[str] = []
            for c in range(cols):
                cell = row_cells[c]
                if cell is None:
                    parts.append(" " * CELL_W)
                else:
                    parts.append(cell[line_idx])
            output_lines.append("".join(parts))

    return "\n".join(line.rstrip() for line in output_lines)
