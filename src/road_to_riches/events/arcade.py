"""Experimental, server-owned suit reels with a separate start and result."""

import random
from dataclasses import dataclass, field

from road_to_riches.events.event import GameEvent
from road_to_riches.events.game_events import PresentationBarrierEvent
from road_to_riches.events.registry import register_event
from road_to_riches.models.game_state import GameState

SUITS = ("SPADE", "HEART", "DIAMOND", "CLUB")


def arcade_prize(reels: list[str], level: int) -> int:
    if len(reels) != 3 or any(s not in SUITS for s in reels):
        raise ValueError("Arcade requires three standard suits")
    distinct = len(set(reels))
    return level * (50 if distinct == 1 else 10 if distinct == 2 else 0)


@register_event
@dataclass
class ArcadeEvent(GameEvent):
    player_id: int

    def execute(self, state: GameState) -> list[GameEvent]:
        level = state.get_player(self.player_id).level
        return [
            PresentationBarrierEvent(
                player_id=self.player_id,
                presentation_type="arcade_intro",
                data={"level": level, "pair_prize": 10 * level, "triple_prize": 50 * level},
            ),
            ArcadeSpinEvent(player_id=self.player_id),
        ]


@register_event
@dataclass
class ArcadeSpinEvent(GameEvent):
    player_id: int
    reels: list[str] = field(default_factory=list)

    def execute(self, state: GameState) -> list[GameEvent]:
        if not self.reels:
            self.reels = [random.choice(SUITS) for _ in range(3)]
        player = state.get_player(self.player_id)
        amount = arcade_prize(self.reels, player.level)
        player.ready_cash += amount
        # No intermediate cash log/notify: the result owns its complete reveal.
        return [
            PresentationBarrierEvent(
                player_id=self.player_id,
                presentation_type="arcade_result",
                data={"reels": list(self.reels), "amount": amount, "level": player.level},
            )
        ]
