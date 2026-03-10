from __future__ import annotations  
from dataclasses import dataclass

@dataclass
class StockState:
  stocks: list[StockPrice] # should be indexed by district id

@dataclass 
class StockPrice:
  district_id: int
  value_component: int # the "value price" of the stock (based on property value)
  fluctuation_component: int # the "additonal price" modification to the stock. starts at 0 and changes based on buy/sell and events.
  
  @property
  def current_price(self) -> int:
    return self.value_component + self.fluctuation_component
