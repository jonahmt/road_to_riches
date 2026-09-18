"""Versioned transparent policy checkpoints; no neural inference or rule changes."""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PolicyParameters:
    reserve: float = 1.0
    synergy: float = 1.0
    rent_risk: float = 1.0
    rival_stock: float = 0.6
    rent_growth: float = 0.12
    external_growth: float = 0.15
    offer_premium: float = 1.08
    trade_margin: float = 30.0
    leaf: tuple = (2.4, 0.7, 0.3, 1.0, 0.2, 0.4, 0.55, 2.0, 0.9)

    def __post_init__(self):
        if len(self.leaf) != 9:
            raise ValueError("Nine leaf weights required")
        for value in [getattr(self, k) for k in BOUNDS] + list(self.leaf):
            if not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError("Policy weights must be finite and nonnegative")
        for key, (lo, hi) in BOUNDS.items():
            if not lo <= getattr(self, key) <= hi:
                raise ValueError(f"Out-of-range policy parameter: {key}")
        if any(v > 8 for v in self.leaf):
            raise ValueError("Leaf weights exceed safe range")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data.get("version") != 1 or data.get("kind") != "strategic_parameters":
            raise ValueError("Unsupported policy checkpoint")
        return cls(**{**data["parameters"], "leaf": tuple(data["parameters"]["leaf"])})

    def save(self, path, **metadata):
        Path(path).write_text(
            json.dumps(
                {
                    "version": 1,
                    "kind": "strategic_parameters",
                    "parameters": asdict(self),
                    **metadata,
                },
                indent=2,
            )
        )


BOUNDS = {
    "reserve": (0.2, 2.5),
    "synergy": (0.2, 2.5),
    "rent_risk": (0.2, 3.0),
    "rival_stock": (0.0, 1.5),
    "rent_growth": (0.01, 0.5),
    "external_growth": (0.01, 0.8),
    "offer_premium": (1.0, 1.3),
    "trade_margin": (0.0, 150.0),
}
DEFAULT_PARAMETERS = PolicyParameters()
