"""Board renderer for the TUI using Rich markup.

Renders the game board onto a pixel buffer with camera support.
A "pixel" is 2 characters wide, 1 character tall.
Each square is 4x4 pixels (8 chars wide, 4 chars tall).
Square positions are in the same units as square size (multiples of 4).

Based on the design spec in design/p0_client.md.
"""

from __future__ import annotations

from road_to_riches.models.board_state import BoardState, SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType

# A pixel is 2 chars wide, 1 char tall.
# Each square is 4x4 pixels.
SQUARE_PX = 4      # square size in pixels (both axes)
PX_CHARS = 2        # chars per pixel horizontally

# Suit symbols and colors
SUIT_SYMBOLS = {"SPADE": "♠", "HEART": "♥", "DIAMOND": "♦", "CLUB": "♣"}
SUIT_COLORS = {"SPADE": "dodger_blue1", "HEART": "bright_red", "DIAMOND": "yellow", "CLUB": "green"}
SUIT_ABBR = {"SPADE": "SPADE", "HEART": "HEART", "DIAMOND": "Dmnd", "CLUB": "CLUB"}

# District border colors
DISTRICT_COLORS = [
    "cyan", "magenta", "bright_green", "bright_yellow", "bright_red", "bright_blue",
]

# Player text colors
PLAYER_COLORS = ["bright_cyan", "orchid1", "bright_yellow", "bright_green"]

# Square type display config: (line1_text, line2_text, main_color, highlight_color)
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

# Dimensions in chars for backward compat
INNER_W = 6
CELL_W = INNER_W + 2  # 8
CELL_H = SQUARE_PX


def _color(text: str, color: str) -> str:
    return f"[{color}]{text}[/{color}]"


def _render_cell(
    sq: SquareInfo,
    player_ids: list[int],
    active_player_id: int | None = None,
    board: BoardState | None = None,
    browsed: bool = False,
) -> list[str]:
    """Render a single square as 4 lines of 8 visible characters (4x4 pixels).

    Lines contain Rich markup but visible width is always 8 (4 pixels * 2 chars).
    Format:
      ┌──────┐   (highlight color, or active player color)
      │ TEXT │   (border=highlight, text=main)
      │ TEXT │   (border=highlight, text=main)
      .1..──00   (players=colored, ──=highlight, id=white)
    """
    from road_to_riches.models.suit import Suit

    main_color = "white"
    highlight_color = "white"
    line1_text = ""
    line2_text = ""
    bg_color: str | None = None

    if sq.type == SquareType.SHOP:
        val = sq.shop_current_value or sq.shop_base_value or 0
        line1_text = f"V{val:>5}"
        if sq.property_owner is not None:
            if board is not None:
                from road_to_riches.engine.property import current_rent
                rent = current_rent(board, sq)
            else:
                rent = sq.shop_base_rent or 0
            line2_text = f"${rent:>5}"
            main_color = "white"
            bg_color = PLAYER_COLORS[sq.property_owner % len(PLAYER_COLORS)]
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
        main_color = SUIT_COLORS.get(suit_name, "white")
        highlight_color = "white"

    elif sq.type == SquareType.CHANGE_OF_SUIT:
        line1_text = "C.o.S."
        suit_name = sq.suit.value if isinstance(sq.suit, Suit) else "SPADE"
        symbol = SUIT_SYMBOLS.get(suit_name, "?")
        abbr = SUIT_ABBR.get(suit_name, suit_name[:4])
        line2_text = f" {abbr} " if len(abbr) <= 4 else abbr[:INNER_W]
        main_color = SUIT_COLORS.get(suit_name, "white")
        highlight_color = "white"

    elif sq.type in _SPECIAL_DISPLAY:
        disp = _SPECIAL_DISPLAY[sq.type]
        line1_text = disp[0]
        line2_text = disp[1]
        main_color = disp[2]
        highlight_color = disp[3]
        # Vacant plots use their district's border color
        if sq.type == SquareType.VACANT_PLOT and sq.property_district is not None:
            d = sq.property_district
            highlight_color = DISTRICT_COLORS[d % len(DISTRICT_COLORS)]

    else:
        line1_text = sq.type.value[:INNER_W]
        line2_text = ""
        main_color = "white"
        highlight_color = "white"

    # Use double-line border if the active player is on this square or it's browsed
    is_active_square = browsed or (active_player_id is not None and active_player_id in player_ids)
    if browsed:
        highlight_color = "bright_white"

    # Active square: highlight entire border area with the active player's color
    active_bg: str | None = None
    if is_active_square and active_player_id is not None:
        active_bg = PLAYER_COLORS[active_player_id % len(PLAYER_COLORS)]
    elif browsed:
        active_bg = "bright_white"

    def _border(text: str) -> str:
        if active_bg:
            return f"[bold black on {active_bg}]{text}[/]"
        return _color(text, highlight_color)

    # Center content within INNER_W
    l1 = line1_text.center(INNER_W) if len(line1_text) < INNER_W else line1_text[:INNER_W]
    l2 = line2_text.center(INNER_W) if len(line2_text) < INNER_W else line2_text[:INNER_W]

    # Build the 4 lines
    if is_active_square:
        border_h = _border("╔" + "═" * INNER_W + "╗")
        vbar = _border("║")
    else:
        border_h = _color("┌" + "─" * INNER_W + "┐", highlight_color)
        vbar = _color("│", highlight_color)
    if bg_color:
        content1 = vbar + f"[black on {bg_color}]{l1}[/]" + vbar
        content2 = vbar + f"[black on {bg_color}]{l2}[/]" + vbar
    else:
        content1 = vbar + _color(l1, main_color) + vbar
        content2 = vbar + _color(l2, main_color) + vbar

    # Bottom row: player slots (4 chars) + ── (2 chars) + square id (2 chars)
    if active_bg:
        # Entire bottom row gets the highlight background
        player_slots = ""
        for pid in range(4):
            if pid in player_ids:
                player_slots += f"[bold black on {active_bg}]{pid}[/]"
            else:
                player_slots += f"[black on {active_bg}].[/]"
        sep = _border("══")
        sq_id = f"[bold black on {active_bg}]{sq.id:02d}[/]"
    else:
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


def render_board(
    state: GameState,
    active_player_id: int | None = None,
    browsed_square_id: int | None = None,
    camera_center: tuple[int, int] | None = None,
    viewport_w: int | None = None,
    viewport_h: int | None = None,
) -> str:
    """Render the board onto a pixel buffer with camera support.

    Positions are in board units (multiples of SQUARE_PX). Each square
    occupies SQUARE_PX x SQUARE_PX pixels starting at its position.
    The camera_center is in pixel coordinates; if None, the board is
    auto-centered. viewport_w/viewport_h are in pixels; if None, the
    full board extent is used.
    """
    board = state.board

    if not board.squares:
        return "(empty board)"

    # Build player position map: square_id -> list of player_ids
    player_positions: dict[int, list[int]] = {}
    for p in state.players:
        if not p.bankrupt:
            player_positions.setdefault(p.position, []).append(p.player_id)

    # Compute board extent in pixels
    min_px = min(sq.position[0] for sq in board.squares)
    min_py = min(sq.position[1] for sq in board.squares)
    max_px = max(sq.position[0] for sq in board.squares) + SQUARE_PX
    max_py = max(sq.position[1] for sq in board.squares) + SQUARE_PX
    board_w = max_px - min_px
    board_h = max_py - min_py

    # Determine viewport (in pixels)
    vw = viewport_w if viewport_w is not None else board_w
    vh = viewport_h if viewport_h is not None else board_h

    # Determine camera: top-left corner in pixel coords
    if camera_center is not None:
        cam_x = camera_center[0] - vw // 2
        cam_y = camera_center[1] - vh // 2
    else:
        # Auto-center on the board
        cam_x = min_px + (board_w - vw) // 2
        cam_y = min_py + (board_h - vh) // 2

    # Sparse map: (pixel_x, pixel_y) -> rendered line string for that row of the square
    # Each entry covers SQUARE_PX pixels wide (CELL_W chars).
    cell_at: dict[tuple[int, int], str] = {}

    for sq in board.squares:
        sx, sy = sq.position[0], sq.position[1]
        pids = player_positions.get(sq.id, [])
        is_browsed = browsed_square_id is not None and sq.id == browsed_square_id
        cell_lines = _render_cell(sq, pids, active_player_id, board, is_browsed)

        for row_offset in range(SQUARE_PX):
            py = sy + row_offset
            buf_y = py - cam_y
            buf_x = sx - cam_x
            if 0 <= buf_y < vh and buf_x + SQUARE_PX > 0 and buf_x < vw:
                cell_at[(buf_x, buf_y)] = cell_lines[row_offset]

    # Assemble output: scan each row, place cells or empty pixels
    empty_px = " " * PX_CHARS
    output_lines: list[str] = []
    for py in range(vh):
        parts: list[str] = []
        px = 0
        while px < vw:
            key = (px, py)
            if key in cell_at:
                parts.append(cell_at[key])
                px += SQUARE_PX
            else:
                parts.append(empty_px)
                px += 1
        output_lines.append("".join(parts))

    return "\n".join(line.rstrip() for line in output_lines)


def get_board_grid(board: "BoardState") -> list[list[int | None]]:
    """Return a 2D grid of square IDs (or None for empty cells).

    Used by the browse mode to navigate between squares spatially.
    Grid positions correspond to board positions divided by SQUARE_PX.
    """
    if not board.squares:
        return []
    positions = [(sq, sq.position[0] // SQUARE_PX, sq.position[1] // SQUARE_PX) for sq in board.squares]
    cols = max(p[1] for p in positions) + 1
    rows = max(p[2] for p in positions) + 1
    grid: list[list[int | None]] = [[None] * cols for _ in range(rows)]
    for sq, gc, gr in positions:
        grid[gr][gc] = sq.id
    return grid
