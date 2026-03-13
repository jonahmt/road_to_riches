from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StockPrice:
    district_id: int
    value_component: int
    fluctuation_component: int = 0

    @property
    def current_price(self) -> int:
        return self.value_component + self.fluctuation_component


@dataclass
class StockState:
    stocks: list[StockPrice]
    """Indexed by district id."""

    def get_price(self, district_id: int) -> StockPrice:
        return self.stocks[district_id]
