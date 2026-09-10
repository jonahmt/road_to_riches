"""Switch changes only layout-owned fields, never the shops' financial state."""

from dataclasses import dataclass

from road_to_riches.board.pathfinding import get_next_squares
from road_to_riches.events.event import GameEvent
from road_to_riches.events.game_events import PresentationBarrierEvent
from road_to_riches.events.registry import register_event
from road_to_riches.models.board_state import Waypoint
from road_to_riches.models.game_state import GameState


@register_event
@dataclass
class SwitchLayoutEvent(GameEvent):
    player_id: int
    square_id: int

    def execute(self, state: GameState) -> list[GameEvent]:
        board = state.board
        target = board.squares[self.square_id].switch_next_state
        layout = board.layouts.get(target)
        if layout is None:
            # Legacy saves predate authored layouts. Explain rather than crash.
            return [
                PresentationBarrierEvent(
                    player_id=self.player_id,
                    presentation_type="board_layout_changed",
                    data={
                        "message": "This board has no alternate layout configured.",
                        "square_id": self.square_id,
                    },
                )
            ]
        previous = board.current_layout
        for definition in layout["squares"]:
            square = board.squares[definition["id"]]
            square.position = tuple(definition["position"])
            square.waypoints = [
                Waypoint(from_id=w.get("from_id"), to_ids=list(w["to_ids"]))
                for w in definition["waypoints"]
            ]
            square.switch_next_state = definition.get("switch_next_state")
        board.current_layout = target
        for player in state.players:
            if not get_next_squares(board, player.position, player.from_square):
                player.from_square = None
        return [
            PresentationBarrierEvent(
                player_id=self.player_id,
                presentation_type="board_layout_changed",
                data={
                    "from_layout": previous,
                    "to_layout": target,
                    "name": layout["name"],
                    "square_id": self.square_id,
                    "message": "The board has changed. Follow the new routes!",
                },
            )
        ]
