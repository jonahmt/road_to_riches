"""Visual readiness must neither race the owner nor impersonate a decision."""

import copy
import threading
import time

from road_to_riches.board import load_board
from road_to_riches.events.game_events import PayRentEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.server.presentation_pacer import PresentationPacer, state_beat


def state():
    board, stock = load_board("boards/test_board.json")
    return GameState(
        board=board,
        stock=stock,
        players=[PlayerState(player_id=i, position=0, ready_cash=1000) for i in range(2)],
    )


def wait_until(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(0.005)


def test_visual_driver_and_decision_owner_are_independent_gates():
    browser, ai, stranger = object(), object(), object()
    messages = []
    pacer = PresentationPacer(messages.append, {0: browser, 1: ai}, "game")
    pacer.register(stranger, True)
    assert not pacer.enabled
    pacer.register(browser, True)
    before = game_state_to_dict(state())
    pacer.published = copy.deepcopy(before)
    after = copy.deepcopy(before)
    after["players"][1]["ready_cash"] += 120
    owner = threading.Event()
    worker = threading.Thread(
        target=lambda: pacer.run(
            after, "lucky_roll_result", {}, 1, request_id="roll", confirmation=owner
        )
    )
    worker.start()
    try:
        wait_until(lambda: pacer.pending is not None)
        beat = messages[0]
        assert beat["before"]["players"][1]["ready_cash"] == 1000
        assert beat["after"]["players"][1]["ready_cash"] == 1120
        assert beat["driver_player_id"] == 0
        owner.set()  # An AI's early acknowledgment cannot truncate the browser.
        pacer.acknowledge(stranger, "roll", beat["generation"])
        pacer.acknowledge(browser, "old-roll", beat["generation"])
        worker.join(0.05)
        assert worker.is_alive()
        assert pacer.published == before
        pacer.acknowledge(browser, "roll", beat["generation"])
        worker.join(1)
        assert not worker.is_alive()
        assert pacer.published == after
        assert messages[-1]["msg"] == "presentation_resolved"
    finally:
        owner.set()
        pacer.ready.set()
        worker.join(2)


def test_background_driver_reassignment_rejects_old_lease():
    first, second = object(), object()
    messages = []
    pacer = PresentationPacer(messages.append, {0: first, 1: second}, "game")
    pacer.register(first, True)
    pacer.register(second, True)
    worker = threading.Thread(
        target=lambda: pacer.run(game_state_to_dict(state()), "turn_started", {}, 0)
    )
    worker.start()
    try:
        wait_until(lambda: pacer.pending is not None)
        initial = pacer.snapshot()
        pacer.register(first, False)
        wait_until(lambda: pacer.driver is second)
        assert pacer.generation > initial["generation"]
        pacer.acknowledge(first, initial["request_id"], initial["generation"])
        assert not pacer.ready.is_set()
        pacer.acknowledge(second, initial["request_id"], pacer.generation)
        worker.join(1)
        assert not worker.is_alive()
    finally:
        pacer.ready.set()
        worker.join(2)


def test_renderer_timeout_never_consumes_human_reading_or_confirms_a_choice():
    browser = object()
    pacer = PresentationPacer(lambda _: None, {0: browser}, "game")
    pacer.render_timeout = 0.15
    pacer.register(browser, True)
    owner = threading.Event()
    worker = threading.Thread(
        target=lambda: pacer.run(
            game_state_to_dict(state()), "rent_payment", {}, 0, confirmation=owner
        )
    )
    worker.start()
    try:
        wait_until(lambda: pacer.pending is not None)
        worker.join(0.2)
        assert worker.is_alive()
        assert not owner.is_set()
        owner.set()
        worker.join(0.04)
        assert worker.is_alive()  # The confirmed panel still gets its exit animation.
        pacer.acknowledge(browser, pacer.pending["request_id"], pacer.generation)
        worker.join(1)
        assert not worker.is_alive()
    finally:
        owner.set()
        pacer.ready.set()
        worker.join(2)


def test_authoritative_endpoint_classification_preserves_movement_and_undo():
    before = game_state_to_dict(state())
    moved = copy.deepcopy(before)
    moved["players"][0]["position"] = 1
    assert state_beat(before, moved)[0] == "piece_moved"
    assert state_beat(moved, before)[0] == "piece_moved"
    suited = copy.deepcopy(moved)
    suited["players"][0]["suits"] = {"SPADE": 1}
    assert state_beat(moved, suited) == (
        "suit_collected",
        {"player_id": 0, "square_id": 1, "suit": "SPADE"},
    )
    assert before["players"][0]["position"] == 0


def test_rent_intermediate_cash_is_captured_before_actual_dividends():
    game = state()
    shop = next(square for square in game.board.squares if square.shop_base_value)
    shop.property_owner = 1
    game.players[1].owned_properties = [shop.id]
    game.players[0].owned_stock[shop.property_district] = 100
    rent = PayRentEvent(0, 1, shop.id)
    rent.execute(game)
    facts = rent.presentation_data()
    assert facts["rent_cash"][0] == 1000 - facts["rent_amount"]
    assert facts["rent_cash"][1] == 1000 + facts["rent_amount"]
    assert game.players[0].ready_cash == facts["rent_cash"][0] + facts["dividends"][0]["amount"]


def test_tile_rotation_and_path_bookkeeping_do_not_add_foreground_pauses():
    before = game_state_to_dict(state())
    after = copy.deepcopy(before)
    after["board"]["squares"][0]["suit"] = "HEART"
    after["players"][0]["from_square"] = 4
    assert state_beat(before, after) is None
    after["players"][0]["ready_cash"] -= 100
    assert state_beat(before, after)[0] == "state_changed"
