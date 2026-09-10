"""Board-authored layouts change geometry/routes while preserving square identity."""

import math
from copy import deepcopy

FIELDS = {"id", "position", "waypoints", "switch_next_state"}


def build_layouts(data: dict) -> dict[int, dict]:
    definitions = data.get("layouts", [])
    if not definitions:
        if any(s["type"] == "SWITCH" for s in data["squares"]):
            raise ValueError(
                "Switch boards require alternate layouts and switch_next_state targets"
            )
        return {}
    base = [{k: deepcopy(v) for k, v in s.items() if k in FIELDS} for s in data["squares"]]
    layouts = {0: {"name": data.get("layout_name", "Original layout"), "squares": base}}
    for definition in definitions:
        layout_id = definition.get("id")
        if type(layout_id) is not int or layout_id <= 0 or layout_id in layouts:
            raise ValueError(
                "Alternate layout IDs must be distinct positive integers (0 is original)"
            )
        squares = deepcopy(base)
        seen = set()
        for override in definition.get("squares", []):
            square_id = override.get("id")
            if type(square_id) is not int or square_id not in range(len(base)) or square_id in seen:
                raise ValueError("Layout overrides require distinct existing square IDs")
            if set(override) - FIELDS:
                raise ValueError("Layouts may change only positions, waypoints and switch targets")
            seen.add(square_id)
            squares[square_id].update(deepcopy(override))
        layouts[layout_id] = {
            "name": definition.get("name", f"Layout {layout_id}"),
            "squares": squares,
        }
    for layout in layouts.values():
        for s in layout["squares"]:
            pos = s.get("position", [])
            if len(pos) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in pos
            ):
                raise ValueError("Layout positions require two finite numbers")
            if not s.get("waypoints"):
                raise ValueError("Every layout square requires a route")
            for wp in s["waypoints"]:
                if wp.get("from_id") is not None and wp["from_id"] not in range(len(base)):
                    raise ValueError("Layout waypoint references a missing source")
                if not wp.get("to_ids") or any(
                    type(i) is not int or i not in range(len(base)) for i in wp["to_ids"]
                ):
                    raise ValueError("Layout waypoint references a missing destination")
            if (
                data["squares"][s["id"]]["type"] == "SWITCH"
                and s.get("switch_next_state") not in layouts
            ):
                raise ValueError("Every switch needs a valid target in every layout")
    return layouts
