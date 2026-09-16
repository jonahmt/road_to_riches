"""Contract tests for real-engine AI branching, fairness and strategic decisions."""

import copy
import random

import pytest

from road_to_riches.ai.lab.policies import Lab
from road_to_riches.ai.lab.runner import LabInput, match
from road_to_riches.ai.lab.simulation import DecisionContext, PlanningGameLoop
from road_to_riches.ai.lab.strategy import StrategicPolicy, route_distance
from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.events.turn_events import InitBuyShopEvent, TurnEvent
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.models.square_type import SquareType
from road_to_riches.protocol import InputRequest
from road_to_riches.protocol import InputRequestType as T

BOARD = "boards/conversion_tests/trodain/trodain.json"


def setup_loop():
    lab = Lab(["strategic"] * 4, seed=4)
    loop = PlanningGameLoop(GameConfig(BOARD, starting_player_index=0), LabInput(lab))
    loop.lab = lab
    return loop, lab


def test_victory_route_ignores_missing_suits():
    loop, _ = setup_loop()
    state = loop.state
    p = state.players[0]
    p.ready_cash = state.board.target_networth
    p.position = 0
    p.suits.clear()
    assert route_distance(state, 0) == 0
    p.ready_cash = 1200
    assert route_distance(state, 0) > 0


def test_fair_sale_accepted_bad_sale_rejected():
    loop, _ = setup_loop()
    state = loop.state
    sq = next(s for s in state.board.squares if s.type == SquareType.SHOP)
    sq.property_owner = 0
    state.players[0].owned_properties.append(sq.id)
    policy = StrategicPolicy(0)
    offer = {"type": "buy", "buyer_id": 1, "seller_id": 0, "square_id": sq.id, "price": 1800}
    assert policy.choose(state, InputRequest(T.ACCEPT_OFFER, 0, {"offer": offer})) == "accept"
    offer["price"] = 1
    assert policy.choose(state, InputRequest(T.ACCEPT_OFFER, 0, {"offer": offer})) in (
        "reject",
        "counter",
    )


def test_branch_applies_candidate_and_preserves_live_state_rng_and_queue():
    loop, lab = setup_loop()
    sq = next(s for s in loop.state.board.squares if s.type == SquareType.SHOP)
    event = InitBuyShopEvent(player_id=0, square_id=sq.id, cost=sq.shop_current_value)
    event.execute(loop.state)
    loop.pipeline.enqueue(TurnEvent(player_id=1))
    req = InputRequest(
        T.BUY_SHOP,
        0,
        {
            "square_id": sq.id,
            "cost": sq.shop_current_value,
            "cash": loop.state.players[0].ready_cash,
        },
    )
    before = game_state_to_dict(loop.state)
    rng = random.getstate()
    context = DecisionContext(loop, event, lab.policies, rng)
    bought, _ = context.rollout(req, True, 221, turns=0)
    passed, _ = context.rollout(req, False, 221, turns=0)
    # Dispatch enqueues the transaction; execute the next event to compare it.
    # A zero-turn horizon stops before processing the pending BuyShopEvent.
    assert bought.players[0].ready_cash == passed.players[0].ready_cash
    bought, _ = context.rollout(req, True, 221, turns=1)
    passed, _ = context.rollout(req, False, 221, turns=1)
    assert bought.board.squares[sq.id].property_owner == 0
    assert passed.board.squares[sq.id].property_owner != 0
    assert game_state_to_dict(loop.state) == before
    assert random.getstate() == rng
    assert loop.pipeline.pending == 1


def test_future_deck_order_does_not_change_branch():
    loop, lab = setup_loop()
    event = TurnEvent(player_id=0)
    context = DecisionContext(loop, event, lab.policies, random.getstate())
    req = InputRequest(T.PRE_ROLL, 0)
    first, _ = context.rollout(req, "roll", 532, turns=4)
    loop.state.venture_deck.remaining.reverse()
    random.seed(800)  # Live random state is irrelevant to a sampled future.
    second, _ = context.rollout(req, "roll", 532, turns=4)
    assert game_state_to_dict(first) == game_state_to_dict(second)


def test_search_cannot_mutate_candidate_or_policy_memory():
    loop, lab = setup_loop()
    context = DecisionContext(loop, TurnEvent(player_id=0), lab.policies, random.getstate())
    before = copy.deepcopy(lab.policies[0].deal_attempted)
    context.rollout(InputRequest(T.PRE_ROLL, 0), "roll", 68, turns=4)
    assert lab.policies[0].deal_attempted == before


def test_seeded_full_match_reproducibility_and_real_victory():
    names = ["basic", "strategic", "rollout", "strategic"]
    a = match(BOARD, names, 5, target=2500, samples=1, horizon=2)
    b = match(BOARD, names, 5, target=2500, samples=1, horizon=2)
    assert a["finished"] and b["finished"]
    assert a["final"] == b["final"]
    assert [(d["prompt"], d["action"]) for d in a["decisions"]] == [
        (d["prompt"], d["action"]) for d in b["decisions"]
    ]
    assert any(d["search"] for d in a["decisions"] if d["profile"] == "rollout")


def test_missing_learned_checkpoint_fails_clearly():
    with pytest.raises(ValueError, match="checkpoint"):
        Lab(["learned"] * 4)


def test_trained_checkpoint_runs_policy_and_value_and_changes_search():
    from pathlib import Path

    from road_to_riches.ai.lab.network import Network
    from road_to_riches.ai.lab.strategy import features

    model = Network.load(
        Path(__file__).parents[1] / "src/road_to_riches/ai/lab/checkpoints/trained.json"
    )
    loop, _ = setup_loop()
    from road_to_riches.ai.lab.graph import graph_input

    prediction = model.value(features(loop.state, 0), graph_input(loop.state, 0))
    assert 0 < prediction < 1
    result = match(
        BOARD,
        ["basic", "strategic", "rollout", "learned"],
        90000,
        target=2500,
        model=model,
        samples=1,
        horizon=2,
    )
    assert result["finished"]
    assert any(d["search"] for d in result["decisions"] if d["profile"] == "learned")


def test_branch_replay_uses_prior_observed_inputs_inside_negotiation():
    from road_to_riches.events.turn_events import InitBuyShopOfferEvent

    loop, lab = setup_loop()
    sq = next(s for s in loop.state.board.squares if s.type == SquareType.SHOP)
    sq.property_owner = 1
    loop.state.players[1].owned_properties.append(sq.id)
    event = InitBuyShopOfferEvent(player_id=0)
    loop.pipeline.enqueue(TurnEvent(player_id=0))
    price = 150
    context = DecisionContext(
        loop,
        event,
        lab.policies,
        random.getstate(),
        prefix=[(0, T.CHOOSE_SHOP_BUY, (1, sq.id, price))],
    )
    req = InputRequest(
        T.ACCEPT_OFFER,
        1,
        {
            "offer": {
                "type": "buy",
                "buyer_id": 0,
                "seller_id": 1,
                "square_id": sq.id,
                "price": price,
            }
        },
    )
    accepted, _ = context.rollout(req, "accept", 440, turns=1)
    rejected, _ = context.rollout(req, "reject", 440, turns=1)
    assert accepted.board.squares[sq.id].property_owner == 0
    assert rejected.board.squares[sq.id].property_owner == 1
    assert loop.state.board.squares[sq.id].property_owner == 1


def test_hypothetical_arrival_collects_the_last_missing_suit():
    from road_to_riches.models.suit import Suit

    loop, _ = setup_loop()
    p = loop.state.players[0]
    heart = next(
        s for s in loop.state.board.squares if s.type == SquareType.SUIT and s.suit == Suit.HEART
    )
    p.suits = {Suit.SPADE: 1, Suit.DIAMOND: 1, Suit.CLUB: 1}
    arrival_distance = route_distance(loop.state, 0, heart.id, None)
    p.suits[Suit.HEART] = 1
    assert arrival_distance == route_distance(loop.state, 0, heart.id, None)


def test_real_socket_game_uses_all_three_policies_without_changing_human_control():
    import asyncio
    import socket
    from pathlib import Path

    import websockets

    from road_to_riches.ai.basic.client import BasicAIClient
    from road_to_riches.ai.lab.live import LabServer
    from road_to_riches.ai.lab.network import Network
    from road_to_riches.models.serialize import game_state_from_dict
    from road_to_riches.protocol import decode, encode, msg_identify, msg_presentation_ack

    async def run():
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", 0))
            except PermissionError:
                pytest.skip("localhost sockets unavailable")
            port = probe.getsockname()[1]
        peers = []

        async def presenter(pid):
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(encode(msg_identify(pid, game_id="default")))
                async for raw in ws:
                    msg = decode(raw)
                    if msg["msg"] == "presentation_request" and msg["player_id"] == pid:
                        await ws.send(
                            encode(msg_presentation_ack(msg["request_id"], pid, "default"))
                        )
                    elif msg["msg"] == "game_over":
                        return

        class TestServer(LabServer):
            def _spawn_ai_clients(self, session, host, port):
                peers.extend(asyncio.create_task(presenter(pid)) for pid in range(1, 4))

        model = Network.load(
            Path(__file__).parents[1] / "src/road_to_riches/ai/lab/checkpoints/trained.json"
        )
        server = TestServer(
            GameConfig(BOARD, starting_player_index=0),
            ["human", "strategic", "rollout", "learned"],
            model,
            target=10000,
        )
        service = asyncio.create_task(server.serve("127.0.0.1", port))
        human = BasicAIClient(0, delay=0, presentation_delay=0)
        try:
            for _ in range(100):
                try:
                    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
                    break
                except OSError:
                    await asyncio.sleep(0.01)
            else:
                raise AssertionError("server never started")
            async with ws:
                turns = 0
                async for raw in ws:
                    msg = decode(raw)
                    if msg["msg"] == "state_sync":
                        human.state = game_state_from_dict(msg["state"])
                    elif msg["msg"] == "input_request" and msg["player_id"] == 0:
                        req = InputRequest(T(msg["type"]), 0, msg.get("data", {}))
                        if req.type == T.PRE_ROLL:
                            turns += 1
                            if turns >= 4:
                                # Stop at a safe known human decision after three complete rounds.
                                server._default_session.game_loop.game_over = True
                        await ws.send(encode(human.response_message(req, game_id="default")))
                    elif msg["msg"] == "presentation_request" and msg["player_id"] == 0:
                        await ws.send(encode(msg_presentation_ack(msg["request_id"], 0, "default")))
                    elif msg["msg"] == "game_over":
                        break
            await asyncio.wait_for(service, 5)
            assert turns >= 4
            assert {d["profile"] for d in server.lab.trace} == {"strategic", "rollout", "learned"}
            assert all(d["player"] != 0 for d in server.lab.trace)
            assert any(d["search"] for d in server.lab.trace if d["profile"] == "learned")
        finally:
            service.cancel()
            for task in peers:
                task.cancel()
            await asyncio.gather(service, *peers, return_exceptions=True)

    asyncio.run(asyncio.wait_for(run(), 60))


def test_replay_includes_actual_victory_state_not_only_previous_turn():
    result = match(BOARD, ["strategic"] * 4, 4, target=2500, replay=True)
    last = result["frames"][-1]
    assert result["finished"] and last["terminal"]
    assert last["state"] == result["final"]
    assert last["decision_count"] == len(result["decisions"])
    assert last["turn"] == result["turns"]


def test_graph_encoder_is_permutation_invariant_and_responds_to_connections():
    from pathlib import Path

    from road_to_riches.ai.lab.graph import graph_input
    from road_to_riches.ai.lab.network import Network
    from road_to_riches.ai.lab.strategy import features

    model = Network.load(
        Path(__file__).parents[1] / "src/road_to_riches/ai/lab/checkpoints/trained.json"
    )
    if not model.uses_graph:
        pytest.skip("MLP checkpoint selected")
    loop, _ = setup_loop()
    x = features(loop.state, 0)
    nodes, pool = graph_input(loop.state, 0)
    original = model.value(x, (nodes, pool))
    reversed_graph = (list(reversed(nodes)), [list(reversed(row)) for row in pool])
    assert model.value(x, reversed_graph) == pytest.approx(original, abs=1e-12)
    # Remove neighbor messages while retaining every node's own attributes.
    disconnected = ([row[:12] + [0.0] * 12 for row in nodes], pool)
    assert abs(model.value(x, disconnected) - original) > 1e-8


def test_graph_training_and_portable_inference_agree():
    np = pytest.importorskip("numpy")
    from road_to_riches.ai.lab.graph import graph_input
    from road_to_riches.ai.lab.network import Network
    from road_to_riches.ai.lab.training import fit_mlp

    loop, _ = setup_loop()
    graph = graph_input(loop.state, 0)
    x = [[0.2] * 20] * 32
    head, loss = fit_mlp(x, [1.0] * 32, seed=1, epochs=20, graphs=[graph] * 32)
    assert loss[-1] < loss[0]
    assert max(abs(v) for v in head["graph"]["b"]) > 0.001
    model = Network({"version": 1, "state_dim": 20, "value": head, "policy": head})
    nodes, pooling = map(np.asarray, graph)
    embedded = np.tanh(nodes @ np.array(head["graph"]["w"]).T + head["graph"]["b"])
    pooled = (pooling @ embedded).reshape(-1)
    all_x = np.concatenate([x[0], pooled])
    hidden = np.tanh(all_x @ np.array(head["w1"]).T + head["b1"])
    expected = 1 / (1 + np.exp(-(hidden @ head["w2"] + head["b2"])))
    assert model.value(x[0], graph) == pytest.approx(float(expected), abs=1e-10)
