"""Budgeted rollout and neural-guided variants over the same candidate set."""

from __future__ import annotations

import random
import time

from road_to_riches.ai.lab.graph import graph_input
from road_to_riches.ai.lab.network import candidate_features
from road_to_riches.ai.lab.strategy import StrategicPolicy, evaluate, features
from road_to_riches.protocol import InputRequestType as T

SEARCH_TYPES = {
    T.CHOOSE_PATH,
    T.BUY_SHOP,
    T.INVEST,
    T.BUY_STOCK,
    T.AUCTION_BID,
    T.CHOOSE_ANY_SQUARE,
    T.CANNON_TARGET,
    T.ACCEPT_OFFER,
    T.TRADE,
    T.CHOOSE_SHOP_BUY,
    T.FORCED_BUYOUT,
}


class RolloutPolicy(StrategicPolicy):
    name = "rollout"

    def __init__(self, pid, *, samples=2, horizon=4, width=3, model=None, seed=0):
        super().__init__(pid)
        if samples < 1 or horizon < 1 or width < 2:
            raise ValueError("Search requires positive samples/horizon and width >= 2")
        self.samples, self.horizon, self.width = samples, horizon, width
        self.model = model
        self.rng = random.Random(seed + pid * 100003)
        self.last_search = []

    def choose(self, state, req, context=None):
        candidates = self.candidates(state, req)
        self.last_candidates = candidates
        self.last_search = []
        chosen = candidates[0].action
        if context is not None and req.type in SEARCH_TYPES and len(candidates) > 1:
            shortlist = candidates[: self.width]
            # Keep the neutral option available even when the heuristic likes
            # several monetary candidates. The search can explicitly decline.
            neutral = next(
                (
                    c
                    for c in candidates
                    if c.action is None or c.action is False or c.action == "reject"
                ),
                None,
            )
            if neutral is not None and neutral not in shortlist:
                shortlist[-1] = neutral
            seeds = [self.rng.randrange(2**31) for _ in range(self.samples)]
            best = -float("inf")
            for c in shortlist:
                total = 0
                for seed in seeds:
                    outcome, winner = context.rollout(req, c.action, seed, self.horizon)
                    value = evaluate(outcome, self.pid, winner)
                    if self.model is not None and winner is None:
                        # Learned value complements the short rollout; terminal
                        # results always dominate any network estimate.
                        value += 2 * self.model.value(
                            features(outcome, self.pid),
                            graph_input(outcome, self.pid) if self.model.uses_graph else None,
                        )
                    total += value
                score = total / len(seeds)
                # Tiny prior breaks exact ties; it cannot swamp rollout outcomes.
                score += 0.001 * c.score
                self.last_search.append({"action": c.action, "score": score, "reason": c.reason})
                if score > best:
                    best, chosen = score, c.action
        self.record(req, chosen)
        return chosen


class LearnedPolicy(RolloutPolicy):
    name = "learned"

    def candidates(self, state, req):
        candidates = super().candidates(state, req)
        if self.model is not None and len(candidates) > 1:
            base = features(state, self.pid)
            graph = graph_input(state, self.pid) if self.model.uses_graph else None
            ranked = [
                (self.model.policy(base, candidate_features(state, req, c), graph), i, c)
                for i, c in enumerate(candidates)
            ]
            candidates = [c for _, _, c in sorted(ranked, key=lambda row: (-row[0], row[1]))]
        return candidates


class Lab:
    def __init__(self, profiles, *, model=None, seed=0, samples=2, horizon=4, width=3):
        from road_to_riches.ai.basic.client import BasicAIClient

        self.policies = []
        for pid, name in enumerate(profiles):
            if name == "basic":
                p = BasicAIClient(pid, delay=0, presentation_delay=0)
            elif name in ("strategic", "human"):
                p = StrategicPolicy(pid)
            elif name in ("rollout", "learned"):
                cls = LearnedPolicy if name == "learned" else RolloutPolicy
                if name == "learned" and model is None:
                    raise ValueError("learned profile requires a trained checkpoint")
                p = cls(
                    pid,
                    samples=samples,
                    horizon=horizon,
                    width=width,
                    model=model if name == "learned" else None,
                    seed=seed,
                )
            else:
                raise ValueError(f"Unknown AI profile: {name}")
            self.policies.append(p)
        self.profiles = profiles
        self.context = None
        self.trace = []
        self.rng = random.Random(seed + 991)
        self.on_decision = None

    def decide(self, state, req):
        p = self.policies[req.player_id]
        start = time.perf_counter()
        # Policy tie-breaking cannot consume the game's dice/deck RNG stream.
        game_rng = random.getstate()
        random.setstate(self.rng.getstate())
        try:
            if self.profiles[req.player_id] == "basic":
                p.state = state
                action = p.decide(req)
            else:
                action = p.choose(state, req, self.context)
            self.rng.setstate(random.getstate())
        finally:
            random.setstate(game_rng)
        if self.context is not None:
            self.context.prefix.append((req.player_id, req.type, action))
        record = {
            "player": req.player_id,
            "profile": self.profiles[req.player_id],
            "prompt": req.type.value,
            "action": action,
            "ms": (time.perf_counter() - start) * 1000,
            "search": getattr(p, "last_search", []),
        }
        self.trace.append(record)
        if self.on_decision:
            self.on_decision(state, req, p, record)
        return action
