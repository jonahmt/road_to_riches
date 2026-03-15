"""ASCII board renderer for the TUI.

Renders the game board as a grid of square cells. Adjacent squares
share borders (no gaps or connecting lines). Each square's (x, y)
position determines its grid placement.
"""

from __future__ import annotations

from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType

# Cell inner dimensions (excluding borders)
INNER_W = 7
INNER_H = 3

# Full cell with borders
CELL_W = INNER_W + 2  # 9
CELL_H = INNER_H + 2  # 5

# Square type abbreviations
TYPE_ABBR: dict[SquareType, str] = {
    SquareType.BANK: "BANK",
    SquareType.SHOP: "SHOP",
    SquareType.SUIT: "SUIT",
    SquareType.VENTURE: "VNTR",
    SquareType.TAKE_A_BREAK: "BREK",
    SquareType.BOON: "BOON",
    SquareType.BOOM: "BOOM",
    SquareType.ROLL_ON: "ROLL",
    SquareType.STOCKBROKER: "STCK",
    SquareType.CHANGE_OF_SUIT: "ChOS",
    SquareType.SUIT_YOURSELF: "SYou",
    SquareType.BACKSTREET: "BACK",
    SquareType.DOORWAY: "DOOR",
    SquareType.CANNON: "CANN",
    SquareType.VACANT_PLOT: "PLOT",
    SquareType.VP_CHECKPOINT: "CHKP",
    SquareType.VP_TAX_OFFICE: "TAX",
}

SUIT_SYMBOLS = {"SPADE": "♠", "HEART": "♥", "DIAMOND": "♦", "CLUB": "♣"}


def _get_cell_content(sq: SquareInfo, player_ids: list[int]) -> list[str]:
    """Return INNER_H lines of INNER_W chars for a cell's interior."""
    from road_to_riches.models.suit import Suit

    abbr = TYPE_ABBR.get(sq.type, sq.type.value[:4])

    # Info line: district + owner, or suit symbol
    info_parts: list[str] = []
    if sq.property_district is not None:
        info_parts.append(f"d{sq.property_district}")
    if sq.property_owner is not None:
        info_parts.append(f"O{sq.property_owner}")
    elif sq.suit is not None:
        suit_name = sq.suit.value if isinstance(sq.suit, Suit) else str(sq.suit)
        info_parts.append(SUIT_SYMBOLS.get(suit_name, suit_name[:2]))
    info_line = " ".join(info_parts)

    # Player line
    player_line = " ".join(f"P{pid}" for pid in player_ids)
    if len(player_line) > INNER_W:
        player_line = "P" + "".join(str(pid) for pid in player_ids)

    return [
        abbr.center(INNER_W),
        info_line.center(INNER_W),
        player_line.center(INNER_W),
    ]


def render_square_cell(sq: SquareInfo, player_ids: list[int]) -> list[str]:
    """Render a single square as a CELL_W x CELL_H character cell.

    Returns CELL_H lines of exactly CELL_W characters each.
    """
    content = _get_cell_content(sq, player_ids)
    lines = ["┌" + "─" * INNER_W + "┐"]
    for row in content:
        lines.append("│" + row + "│")
    lines.append("└" + "─" * INNER_W + "┘")
    return lines


# Box-drawing corner merge table.
# When two cells share a border point, merge their corners.
_MERGE: dict[tuple[str, str], str] = {
    ("┐", "┌"): "┬",  # top edge, horizontal neighbor
    ("┘", "└"): "┴",  # bottom edge, horizontal neighbor
    ("┘", "┐"): "┤",  # right edge, vertical neighbor
    ("└", "┌"): "├",  # left edge, vertical neighbor
    ("┤", "┌"): "┼",
    ("┤", "└"): "┼",
    ("├", "┐"): "┼",
    ("├", "┘"): "┼",
    ("┬", "└"): "┼",
    ("┬", "┘"): "┼",
    ("┴", "┌"): "┼",
    ("┴", "┐"): "┼",
    ("─", "─"): "─",
    ("│", "│"): "│",
}


def _merge_char(existing: str, new: str) -> str:
    """Merge two box-drawing characters at the same position."""
    if existing == " ":
        return new
    if existing == new:
        return existing
    return _MERGE.get((existing, new), new)


def render_board(state: GameState) -> str:
    """Render the full board as a multi-line string.

    Squares are placed on a grid based on their (x, y) positions.
    Adjacent squares share borders — no gaps or connecting lines.
    """
    board = state.board

    if not board.squares:
        return "(empty board)"

    # Build player position map
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

    # Buffer: cells share borders, so stride is (CELL_W - 1) and (CELL_H - 1)
    stride_x = CELL_W - 1  # 8
    stride_y = CELL_H - 1  # 4
    total_w = cols * stride_x + 1
    total_h = rows * stride_y + 1

    buf = [[" "] * total_w for _ in range(total_h)]

    # Place each cell
    for r in range(rows):
        for c in range(cols):
            sq = grid[r][c]
            if sq is None:
                continue
            pids = player_positions.get(sq.id, [])
            cell_lines = render_square_cell(sq, pids)
            y0 = r * stride_y
            x0 = c * stride_x
            for dy, line in enumerate(cell_lines):
                for dx, ch in enumerate(line):
                    by = y0 + dy
                    bx = x0 + dx
                    if 0 <= by < total_h and 0 <= bx < total_w:
                        buf[by][bx] = _merge_char(buf[by][bx], ch)

    # Convert buffer to string, strip trailing whitespace per line
    return "\n".join("".join(row).rstrip() for row in buf)
