"""Convert Fortune Street .frb binary board files to our JSON format.

Usage:
    python convert_frb.py <input.frb> [output.json]

If output is omitted, writes to stdout.
"""

from __future__ import annotations

import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- Binary format constants ---

HEADER_MAGIC = b"I4DT"
SQUARE_SECTION_MAGIC = b"I4PL"
HEADER_SIZE = 0x30       # Two I4DT headers + board config
SQUARE_HEADER_SIZE = 16  # I4PL + size + padding + count + padding
SQUARE_RECORD_SIZE = 32
MAX_WAYPOINT_ENTRIES = 4
WAYPOINT_ENTRY_SIZE = 4
UNUSED_ID = 0xFF

# Square type IDs in the binary format
FRB_TYPE_PROPERTY = 0
FRB_TYPE_BANK = 1
FRB_TYPE_VENTURE = 2
FRB_TYPE_SPADE = 3
FRB_TYPE_HEART = 4
FRB_TYPE_DIAMOND = 5
FRB_TYPE_CLUB = 6
FRB_TYPE_COS_SPADE = 7
FRB_TYPE_COS_HEART = 8
FRB_TYPE_COS_DIAMOND = 9
FRB_TYPE_COS_CLUB = 10
FRB_TYPE_TAKE_A_BREAK = 11
FRB_TYPE_BOON = 12
FRB_TYPE_BOOM = 13
FRB_TYPE_STOCKBROKER = 14
FRB_TYPE_ROLL_ON = 16
FRB_TYPE_ARCADE = 17
FRB_TYPE_CANNON = 19
FRB_TYPE_SWITCH = 18
FRB_TYPE_WARP_A = 20
FRB_TYPE_WARP_B = 21
FRB_TYPE_WARP_C = 22
FRB_TYPE_WARP_D = 23
FRB_TYPE_WARP_E = 24
FRB_TYPE_GATEWAY_A = 28
FRB_TYPE_GATEWAY_B = 29
FRB_TYPE_GATEWAY_C = 30
FRB_TYPE_GATEWAY_D = 31
FRB_TYPE_GATEWAY_END = 34
FRB_TYPE_VACANT_PLOT = 48

# Mapping from FRB type to our system's square type string
FRB_TO_OUR_TYPE: dict[int, str] = {
    FRB_TYPE_BANK: "BANK",
    FRB_TYPE_PROPERTY: "SHOP",
    FRB_TYPE_VENTURE: "VENTURE",
    FRB_TYPE_SPADE: "SUIT",
    FRB_TYPE_HEART: "SUIT",
    FRB_TYPE_DIAMOND: "SUIT",
    FRB_TYPE_CLUB: "SUIT",
    FRB_TYPE_COS_SPADE: "CHANGE_OF_SUIT",
    FRB_TYPE_COS_HEART: "CHANGE_OF_SUIT",
    FRB_TYPE_COS_DIAMOND: "CHANGE_OF_SUIT",
    FRB_TYPE_COS_CLUB: "CHANGE_OF_SUIT",
    FRB_TYPE_TAKE_A_BREAK: "TAKE_A_BREAK",
    FRB_TYPE_BOON: "BOON",
    FRB_TYPE_BOOM: "BOOM",
    FRB_TYPE_STOCKBROKER: "STOCKBROKER",
    FRB_TYPE_ROLL_ON: "ROLL_ON",
    FRB_TYPE_ARCADE: "ARCADE",
    FRB_TYPE_CANNON: "CANNON",
    FRB_TYPE_SWITCH: "SWITCH",
    FRB_TYPE_VACANT_PLOT: "VACANT_PLOT",
    # Warps = backstreets (forced warp on land)
    FRB_TYPE_WARP_A: "BACKSTREET",
    FRB_TYPE_WARP_B: "BACKSTREET",
    FRB_TYPE_WARP_C: "BACKSTREET",
    FRB_TYPE_WARP_D: "BACKSTREET",
    FRB_TYPE_WARP_E: "BACKSTREET",
    # Gateways = doorways (pass-through teleport, no move cost)
    FRB_TYPE_GATEWAY_A: "DOORWAY",
    FRB_TYPE_GATEWAY_B: "DOORWAY",
    FRB_TYPE_GATEWAY_C: "DOORWAY",
    FRB_TYPE_GATEWAY_D: "DOORWAY",
    FRB_TYPE_GATEWAY_END: "DOORWAY",
}

# Suit lookup for suit/COS types
FRB_TYPE_TO_SUIT: dict[int, str] = {
    FRB_TYPE_SPADE: "SPADE",
    FRB_TYPE_HEART: "HEART",
    FRB_TYPE_DIAMOND: "DIAMOND",
    FRB_TYPE_CLUB: "CLUB",
    FRB_TYPE_COS_SPADE: "SPADE",
    FRB_TYPE_COS_HEART: "HEART",
    FRB_TYPE_COS_DIAMOND: "DIAMOND",
    FRB_TYPE_COS_CLUB: "CLUB",
}

FRB_BACKSTREET_TYPES: set[int] = {
    FRB_TYPE_WARP_A, FRB_TYPE_WARP_B, FRB_TYPE_WARP_C,
    FRB_TYPE_WARP_D, FRB_TYPE_WARP_E,
}

FRB_DOORWAY_TYPES: set[int] = {
    FRB_TYPE_GATEWAY_A, FRB_TYPE_GATEWAY_B, FRB_TYPE_GATEWAY_C,
    FRB_TYPE_GATEWAY_D, FRB_TYPE_GATEWAY_END,
}

# Combined set for transport squares
FRB_TRANSPORT_TYPES = FRB_BACKSTREET_TYPES | FRB_DOORWAY_TYPES

# --- Data structures ---

@dataclass
class FrbWaypoint:
    from_id: int
    to_ids: list[int]


@dataclass
class FrbSquare:
    index: int
    frb_type: int
    x: int
    y: int
    waypoints: list[FrbWaypoint]
    district: int
    value: int
    price: int


@dataclass
class FrbBoard:
    initial_cash: int
    target_networth: int
    base_salary: int
    salary_increment: int
    max_dice_roll: int
    num_districts: int
    squares: list[FrbSquare]


# --- Parsing ---

def parse_frb(data: bytes) -> FrbBoard:
    """Parse a .frb binary file into an FrbBoard."""
    # Validate header
    if data[0:4] != HEADER_MAGIC:
        raise ValueError(f"Invalid magic: expected {HEADER_MAGIC}, got {data[0:4]}")
    if data[0x10:0x14] != HEADER_MAGIC:
        raise ValueError(f"Invalid second header magic at 0x10")

    # Board config at 0x20
    initial_cash = struct.unpack(">H", data[0x20:0x22])[0]
    target_networth = struct.unpack(">H", data[0x22:0x24])[0]
    base_salary = struct.unpack(">H", data[0x24:0x26])[0]
    salary_increment = struct.unpack(">H", data[0x26:0x28])[0]
    max_dice_roll = struct.unpack(">H", data[0x28:0x2A])[0]
    num_districts = 0  # computed from actual property data during conversion

    # Square section at 0x30
    if data[0x30:0x34] != SQUARE_SECTION_MAGIC:
        raise ValueError(f"Invalid square section magic at 0x30")
    num_squares = struct.unpack(">H", data[0x3C:0x3E])[0]

    squares: list[FrbSquare] = []
    for i in range(num_squares):
        offset = 0x40 + i * SQUARE_RECORD_SIZE
        rec = data[offset : offset + SQUARE_RECORD_SIZE]

        frb_type = struct.unpack(">H", rec[0:2])[0]
        x = struct.unpack(">h", rec[2:4])[0]
        y = struct.unpack(">h", rec[4:6])[0]

        # Waypoints: 4 entries of 4 bytes each
        waypoints: list[FrbWaypoint] = []
        for w in range(MAX_WAYPOINT_ENTRIES):
            wp_off = 8 + w * WAYPOINT_ENTRY_SIZE
            entry = rec[wp_off : wp_off + WAYPOINT_ENTRY_SIZE]
            if entry[0] == UNUSED_ID:
                break
            from_id = entry[0]
            to_ids = [b for b in entry[1:4] if b != UNUSED_ID]
            if to_ids:
                waypoints.append(FrbWaypoint(from_id=from_id, to_ids=to_ids))

        district = rec[24]
        value = struct.unpack(">H", rec[26:28])[0]
        price = struct.unpack(">H", rec[28:30])[0]

        squares.append(FrbSquare(
            index=i, frb_type=frb_type, x=x, y=y,
            waypoints=waypoints, district=district,
            value=value, price=price,
        ))

    return FrbBoard(
        initial_cash=initial_cash,
        target_networth=target_networth,
        base_salary=base_salary,
        salary_increment=salary_increment,
        max_dice_roll=max_dice_roll,
        num_districts=num_districts,
        squares=squares,
    )


# --- Conversion ---

def convert_to_json(frb: FrbBoard) -> dict:
    """Convert a parsed FRB board to our JSON board format."""
    # Filter to only squares that are on the playable board (have waypoints
    # or are connected to squares that do). Squares without waypoints and
    # with unrecognized types in the "palette" area are skipped.
    # But first: fail loudly on any truly unrecognized type.
    playable_squares: list[FrbSquare] = []

    for sq in frb.squares:
        if sq.frb_type not in FRB_TO_OUR_TYPE:
            raise ValueError(
                f"Unrecognized square type {sq.frb_type} (0x{sq.frb_type:02x}) "
                f"at index {sq.index}, position ({sq.x}, {sq.y}). "
                f"Add this type to FRB_TO_OUR_TYPE."
            )
        playable_squares.append(sq)

    # Only include squares that have waypoints (are part of the actual board path)
    # or are referenced by other squares' waypoints.
    connected_ids: set[int] = set()
    for sq in playable_squares:
        if sq.waypoints:
            connected_ids.add(sq.index)
            for wp in sq.waypoints:
                connected_ids.add(wp.from_id)
                connected_ids.update(wp.to_ids)

    board_squares = [sq for sq in playable_squares if sq.index in connected_ids]

    if not board_squares:
        raise ValueError("No connected squares found on the board")

    # Build old_id -> new_id mapping (re-index from 0)
    old_to_new: dict[int, int] = {}
    for new_id, sq in enumerate(board_squares):
        old_to_new[sq.index] = new_id

    # Compute position scaling: map to our 4-unit grid
    all_x = [sq.x for sq in board_squares]
    all_y = [sq.y for sq in board_squares]
    min_x, min_y = min(all_x), min(all_y)

    # Original coordinates use 64 units per square (verified from adjacent
    # squares in reference boards). Our system uses 4 units per square.
    # So: divide by 16 to convert (64/16 = 4).
    ORIG_TO_OURS = 16

    def to_pos(x: int, y: int) -> list[int]:
        return [(x - min_x) // ORIG_TO_OURS, (y - min_y) // ORIG_TO_OURS]

    # Backstreet/doorway destinations: the district field IS the destination
    # square index (old ID) directly.
    backstreet_dest: dict[int, int] = {}  # old_id -> old_dest_id
    doorway_dest: dict[int, int] = {}
    for sq in board_squares:
        if sq.frb_type in FRB_BACKSTREET_TYPES:
            backstreet_dest[sq.index] = sq.district
        elif sq.frb_type in FRB_DOORWAY_TYPES:
            doorway_dest[sq.index] = sq.district

    # Count districts from property squares
    districts_used: set[int] = set()
    for sq in board_squares:
        if sq.frb_type == FRB_TYPE_PROPERTY:
            districts_used.add(sq.district)

    # Build output squares
    out_squares: list[dict] = []
    for sq in board_squares:
        new_id = old_to_new[sq.index]
        our_type = FRB_TO_OUR_TYPE[sq.frb_type]

        entry: dict = {
            "id": new_id,
            "type": our_type,
            "position": to_pos(sq.x, sq.y),
        }

        # Suit parameter
        if sq.frb_type in FRB_TYPE_TO_SUIT:
            entry["suit"] = FRB_TYPE_TO_SUIT[sq.frb_type]

        # Shop/property data
        if sq.frb_type == FRB_TYPE_PROPERTY:
            entry["district"] = sq.district
            entry["base_value"] = sq.value
            entry["base_rent"] = sq.price

        # Backstreet destination
        if sq.index in backstreet_dest:
            entry["backstreet_destination"] = old_to_new[backstreet_dest[sq.index]]

        # Doorway destination
        if sq.index in doorway_dest:
            entry["doorway_destination"] = old_to_new[doorway_dest[sq.index]]

        # Vacant plot — value field is unset in base boards, hardcode to 250
        if sq.frb_type == FRB_TYPE_VACANT_PLOT:
            entry["district"] = sq.district
            entry["base_value"] = 250
            entry["base_rent"] = 0

        # Waypoints: remap IDs
        if sq.waypoints:
            wp_list = []
            for wp in sq.waypoints:
                if wp.from_id not in old_to_new:
                    continue  # from_id refers to a non-playable square, skip
                remapped_to = [old_to_new[tid] for tid in wp.to_ids if tid in old_to_new]
                if remapped_to:
                    wp_list.append({
                        "from_id": old_to_new[wp.from_id],
                        "to_ids": remapped_to,
                    })
            entry["waypoints"] = wp_list
        else:
            entry["waypoints"] = []

        out_squares.append(entry)

    board = {
        "name": "",
        "max_dice_roll": frb.max_dice_roll,
        "target_networth": frb.target_networth,
        "max_bankruptcies": 1,
        "num_districts": max(districts_used) + 1 if districts_used else 0,
        "starting_cash": frb.initial_cash,
        "num_players": 4,
        "promotion": {
            "base_salary": frb.base_salary,
            "salary_increment": frb.salary_increment,
            "shop_value_multiplier": 0.10,
            "comeback_multiplier": 0.10,
        },
        "squares": out_squares,
    }

    return board


# --- Main ---

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.frb> [output.json]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    data = input_path.read_bytes()
    frb = parse_frb(data)

    print(f"Parsed {len(frb.squares)} squares from {input_path.name}", file=sys.stderr)
    print(f"Board: cash={frb.initial_cash}, salary={frb.base_salary}+{frb.salary_increment}, "
          f"dice={frb.max_dice_roll}, districts={frb.num_districts}", file=sys.stderr)

    board = convert_to_json(frb)

    connected = [sq for sq in board["squares"] if sq.get("waypoints")]
    disconnected = [sq for sq in board["squares"] if not sq.get("waypoints")]
    print(f"Output: {len(board['squares'])} squares "
          f"({len(connected)} connected, {len(disconnected)} disconnected)", file=sys.stderr)

    output = json.dumps(board, indent=2)

    if output_path:
        output_path.write_text(output + "\n")
        print(f"Wrote {output_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
