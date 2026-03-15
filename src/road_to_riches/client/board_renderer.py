"""ASCII board renderer for the TUI.

Renders the game board as a grid of square cells connected by paths.
Each cell shows the square type, owner, and player positions.
"""

from __future__ import annotations

from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType

# Cell dimensions (characters)
CELL_W = 9
CELL_H = 5

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

# District colors (Rich markup)
DISTRICT_COLORS = [
    "bright_red",
    "bright_blue",
    "bright_green",
    "bright_yellow",
    "bright_magenta",
    "bright_cyan",
]

PLAYER_SYMBOLS = ["P0", "P1", "P2", "P3"]


def render_square_cell(sq: SquareInfo, player_ids: list[int]) -> list[str]:
    """Render a single square as a 9x5 character cell.

    Returns 5 lines of exactly 9 characters each.

    Layout:
        ┌───────┐   (border)
        │ SHOP  │   (type abbreviation)
        │ d0 O1 │   (district + owner)
        │ P0 P2 │   (players on this square)
        └───────┘   (border)
    """
    inner_w = CELL_W - 2  # 7

    abbr = TYPE_ABBR.get(sq.type, sq.type.value[:4])

    # Line 2: district + owner
    info_parts = []
    if sq.property_district is not None:
        info_parts.append(f"d{sq.property_district}")
    if sq.property_owner is not None:
        info_parts.append(f"O{sq.property_owner}")
    elif sq.suit is not None:
        from road_to_riches.models.suit import Suit

        suit_sym = {"SPADE": "♠", "HEART": "♥", "DIAMOND": "♦", "CLUB": "♣"}
        suit_name = sq.suit.value if isinstance(sq.suit, Suit) else str(sq.suit)
        info_parts.append(suit_sym.get(suit_name, suit_name[:2]))
    info_line = " ".join(info_parts)

    # Line 3: players (truncate to fit cell)
    player_line = " ".join(f"P{pid}" for pid in player_ids)
    if len(player_line) > inner_w:
        # Compact: P0123
        player_line = "P" + "".join(str(pid) for pid in player_ids)

    lines = [
        "┌" + "─" * inner_w + "┐",
        "│" + abbr.center(inner_w) + "│",
        "│" + info_line.center(inner_w) + "│",
        "│" + player_line.center(inner_w) + "│",
        "└" + "─" * inner_w + "┘",
    ]
    return lines


def render_board(state: GameState) -> str:
    """Render the full board as a multi-line string.

    Uses square position coordinates to place cells on a grid.
    Cells are connected by lines between adjacent squares.
    """
    board = state.board

    if not board.squares:
        return "(empty board)"

    # Build player position map
    player_positions: dict[int, list[int]] = {}
    for p in state.players:
        if not p.bankrupt:
            player_positions.setdefault(p.position, []).append(p.player_id)

    # Find grid dimensions from square positions
    # Positions are in abstract units; convert to grid cells
    positions = [sq.position for sq in board.squares]
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]

    # Normalize positions: find unique sorted x/y values and map to indices
    unique_x = sorted(set(xs))
    unique_y = sorted(set(ys))
    x_to_col = {x: i for i, x in enumerate(unique_x)}
    y_to_row = {y: i for i, y in enumerate(unique_y)}

    cols = len(unique_x)
    rows = len(unique_y)

    # Create grid of cells (None where no square exists)
    grid: list[list[SquareInfo | None]] = [
        [None] * cols for _ in range(rows)
    ]
    for sq in board.squares:
        c = x_to_col[sq.position[0]]
        r = y_to_row[sq.position[1]]
        grid[r][c] = sq

    # Build connection map for drawing paths between cells
    connections: set[tuple[int, int, int, int]] = set()
    for sq in board.squares:
        sc = x_to_col[sq.position[0]]
        sr = y_to_row[sq.position[1]]
        for wp in sq.waypoints:
            for to_id in wp.to_ids:
                to_sq = board.squares[to_id]
                tc = x_to_col[to_sq.position[0]]
                tr = y_to_row[to_sq.position[1]]
                connections.add((sr, sc, tr, tc))

    # Render: each cell is CELL_W x CELL_H, with 3-char gap between cells
    gap_h = 3  # horizontal gap between cells
    gap_v = 1  # vertical gap between cells

    total_w = cols * CELL_W + (cols - 1) * gap_h
    total_h = rows * CELL_H + (rows - 1) * gap_v

    # Build a character buffer
    buf = [[" "] * total_w for _ in range(total_h)]

    # Place cells
    for r in range(rows):
        for c in range(cols):
            sq = grid[r][c]
            if sq is None:
                continue
            pids = player_positions.get(sq.id, [])
            cell_lines = render_square_cell(sq, pids)
            y0 = r * (CELL_H + gap_v)
            x0 = c * (CELL_W + gap_h)
            for dy, line in enumerate(cell_lines):
                for dx, ch in enumerate(line):
                    if y0 + dy < total_h and x0 + dx < total_w:
                        buf[y0 + dy][x0 + dx] = ch

    # Draw connections between adjacent cells
    for sr, sc, tr, tc in connections:
        sy0 = sr * (CELL_H + gap_v)
        sx0 = sc * (CELL_W + gap_h)

        if sr == tr:
            # Horizontal connection
            left_c = min(sc, tc)
            right_c = max(sc, tc)
            y_mid = sy0 + CELL_H // 2
            x_start = left_c * (CELL_W + gap_h) + CELL_W
            x_end = right_c * (CELL_W + gap_h)
            for x in range(x_start, x_end):
                if 0 <= x < total_w and 0 <= y_mid < total_h:
                    buf[y_mid][x] = "─"
        elif sc == tc:
            # Vertical connection
            top_r = min(sr, tr)
            bot_r = max(sr, tr)
            x_mid = sx0 + CELL_W // 2
            y_start = top_r * (CELL_H + gap_v) + CELL_H
            y_end = bot_r * (CELL_H + gap_v)
            for y in range(y_start, y_end):
                if 0 <= x_mid < total_w and 0 <= y < total_h:
                    buf[y][x_mid] = "│"

    # Convert buffer to string, strip trailing whitespace per line
    return "\n".join("".join(row).rstrip() for row in buf)
