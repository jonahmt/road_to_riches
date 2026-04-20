"""Tests for square_handler: handle_pass / handle_land effect dispatch."""

from __future__ import annotations

from road_to_riches.board import load_board
from road_to_riches.engine.square_handler import (
    PlayerAction,
    handle_land,
    handle_pass,
)
from road_to_riches.events.game_events import (
    CloseShopsEvent,
    CollectSuitEvent,
    GainCommissionEvent,
    PayCheckpointTollEvent,
    PayRentEvent,
    PayTaxEvent,
    PromotionEvent,
    RaiseCheckpointTollEvent,
    RotateSuitEvent,
    TaxOfficeOwnerBonusEvent,
    WarpEvent,
)
from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit


def _make_game() -> GameState:
    board, stock = load_board("boards/test_board.json")
    players = [PlayerState(player_id=i, position=0, ready_cash=1500) for i in range(4)]
    return GameState(board=board, stock=stock, players=players)


def _sq(sq_type: SquareType, sq_id: int = 99, **kwargs) -> SquareInfo:
    return SquareInfo(id=sq_id, position=(0, 0), type=sq_type, **kwargs)


# ---------------------------------------------------------------------------
# handle_pass
# ---------------------------------------------------------------------------


class TestPassBank:
    def test_bank_pass_offers_buy_stock(self):
        game = _make_game()
        res = handle_pass(game, 0, _sq(SquareType.BANK))
        assert PlayerAction.BUY_STOCK in res.available_actions
        assert not any(isinstance(e, PromotionEvent) for e in res.auto_events)

    def test_bank_pass_promotes_when_all_suits(self):
        game = _make_game()
        p = game.players[0]
        p.suits = {Suit.SPADE: 1, Suit.HEART: 1, Suit.DIAMOND: 1, Suit.CLUB: 1}
        res = handle_pass(game, 0, _sq(SquareType.BANK))
        assert any(isinstance(e, PromotionEvent) for e in res.auto_events)


class TestPassSuit:
    def test_suit_pass_collects(self):
        game = _make_game()
        res = handle_pass(game, 1, _sq(SquareType.SUIT, suit=Suit.HEART))
        collects = [e for e in res.auto_events if isinstance(e, CollectSuitEvent)]
        assert len(collects) == 1
        assert collects[0].suit == Suit.HEART

    def test_suit_pass_noop_when_no_suit(self):
        game = _make_game()
        res = handle_pass(game, 1, _sq(SquareType.SUIT, suit=None))
        assert res.auto_events == []


class TestPassChangeOfSuit:
    def test_collects_and_rotates(self):
        game = _make_game()
        res = handle_pass(game, 0, _sq(SquareType.CHANGE_OF_SUIT, sq_id=7, suit=Suit.CLUB))
        assert any(isinstance(e, CollectSuitEvent) for e in res.auto_events)
        rots = [e for e in res.auto_events if isinstance(e, RotateSuitEvent)]
        assert len(rots) == 1 and rots[0].square_id == 7

    def test_noop_when_suit_none(self):
        game = _make_game()
        res = handle_pass(game, 0, _sq(SquareType.CHANGE_OF_SUIT, suit=None))
        assert res.auto_events == []


class TestPassSuitYourself:
    def test_grants_wild(self):
        game = _make_game()
        res = handle_pass(game, 0, _sq(SquareType.SUIT_YOURSELF))
        collects = [e for e in res.auto_events if isinstance(e, CollectSuitEvent)]
        assert len(collects) == 1
        assert collects[0].suit == Suit.WILD.value


class TestPassDoorway:
    def test_warps_when_destination_set(self):
        game = _make_game()
        res = handle_pass(game, 0, _sq(SquareType.DOORWAY, doorway_destination=5))
        warps = [e for e in res.auto_events if isinstance(e, WarpEvent)]
        assert len(warps) == 1 and warps[0].target_square_id == 5
        assert res.info["warped_to"] == 5

    def test_noop_when_no_destination(self):
        game = _make_game()
        res = handle_pass(game, 0, _sq(SquareType.DOORWAY, doorway_destination=None))
        assert res.auto_events == []
        assert "warped_to" not in res.info


class TestPassCheckpoint:
    def test_owner_pass_raises_toll(self):
        game = _make_game()
        sq = _sq(SquareType.VP_CHECKPOINT, property_owner=0, checkpoint_toll=50)
        res = handle_pass(game, 0, sq)
        assert any(isinstance(e, RaiseCheckpointTollEvent) for e in res.auto_events)
        assert res.info["toll_raised"] is True

    def test_nonowner_pass_pays_toll(self):
        game = _make_game()
        sq = _sq(SquareType.VP_CHECKPOINT, property_owner=0, checkpoint_toll=50)
        res = handle_pass(game, 1, sq)
        pays = [e for e in res.auto_events if isinstance(e, PayCheckpointTollEvent)]
        assert len(pays) == 1
        assert pays[0].payer_id == 1 and pays[0].owner_id == 0
        assert res.info["toll"] == 50

    def test_unowned_checkpoint_pass_noop(self):
        game = _make_game()
        sq = _sq(SquareType.VP_CHECKPOINT, property_owner=None)
        res = handle_pass(game, 0, sq)
        assert res.auto_events == []


# ---------------------------------------------------------------------------
# handle_land
# ---------------------------------------------------------------------------


class TestLandBank:
    def test_can_win_flag_when_networth_sufficient(self):
        game = _make_game()
        game.players[0].ready_cash = 999_999
        res = handle_land(game, 0, _sq(SquareType.BANK))
        assert res.info.get("can_win") is True

    def test_no_can_win_below_threshold(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.BANK))
        assert "can_win" not in res.info


class TestLandShop:
    def test_unowned_shop_offers_buy(self):
        game = _make_game()
        sq = _sq(SquareType.SHOP, property_owner=None, shop_base_value=200)
        res = handle_land(game, 0, sq)
        assert PlayerAction.BUY_SHOP in res.available_actions
        assert res.info["cost"] == 200

    def test_own_shop_offers_invest(self):
        game = _make_game()
        # Borrow a real shop from the board so max_capital lookups work.
        shop = game.board.squares[1]
        shop.property_owner = 0
        shop.shop_current_value = shop.shop_base_value
        game.players[0].owned_properties.append(1)
        res = handle_land(game, 0, shop)
        assert PlayerAction.INVEST in res.available_actions
        assert "investable_shops" in res.info

    def test_opponent_shop_pays_rent(self):
        game = _make_game()
        shop = game.board.squares[1]
        shop.property_owner = 1
        shop.shop_current_value = shop.shop_base_value
        game.players[1].owned_properties.append(1)
        res = handle_land(game, 0, shop)
        assert any(isinstance(e, PayRentEvent) for e in res.auto_events)
        assert res.info["owner_id"] == 1
        assert "rent" in res.info

    def test_forced_buyout_offered_when_affordable(self):
        game = _make_game()
        shop = game.board.squares[1]
        shop.property_owner = 1
        shop.shop_current_value = 100  # 5x = 500, player has 1500
        game.players[1].owned_properties.append(1)
        res = handle_land(game, 0, shop)
        assert PlayerAction.FORCED_BUYOUT in res.available_actions
        assert res.info["buyout_cost"] == 500

    def test_forced_buyout_not_offered_when_unaffordable(self):
        game = _make_game()
        shop = game.board.squares[1]
        shop.property_owner = 1
        shop.shop_current_value = 10_000  # 5x = 50_000
        game.players[1].owned_properties.append(1)
        res = handle_land(game, 0, shop)
        assert PlayerAction.FORCED_BUYOUT not in res.available_actions


class TestLandVacantPlot:
    def test_unowned_affordable_offers_buy(self):
        game = _make_game()
        sq = _sq(SquareType.VACANT_PLOT, shop_base_value=200)
        res = handle_land(game, 0, sq)
        assert PlayerAction.BUY_VACANT_PLOT in res.available_actions
        assert res.info["cost"] == 200
        # Default options when list is empty:
        assert SquareType.VP_CHECKPOINT.value in res.info["options"]
        assert SquareType.VP_TAX_OFFICE.value in res.info["options"]

    def test_unowned_unaffordable_no_action(self):
        game = _make_game()
        game.players[0].ready_cash = 10
        sq = _sq(SquareType.VACANT_PLOT, shop_base_value=200)
        res = handle_land(game, 0, sq)
        assert PlayerAction.BUY_VACANT_PLOT not in res.available_actions

    def test_owned_vacant_plot_noop(self):
        game = _make_game()
        sq = _sq(SquareType.VACANT_PLOT, property_owner=1, shop_base_value=200)
        res = handle_land(game, 0, sq)
        assert res.available_actions == []
        assert res.auto_events == []

    def test_explicit_options_passed_through(self):
        game = _make_game()
        sq = _sq(
            SquareType.VACANT_PLOT,
            shop_base_value=200,
            vacant_plot_options=[SquareType.VP_CHECKPOINT],
        )
        res = handle_land(game, 0, sq)
        assert res.info["options"] == [SquareType.VP_CHECKPOINT.value]


class TestLandCheckpoint:
    def test_owner_land_raises_toll_and_offers_invest_renovate(self):
        game = _make_game()
        sq = _sq(SquareType.VP_CHECKPOINT, property_owner=0, checkpoint_toll=50)
        res = handle_land(game, 0, sq)
        assert any(isinstance(e, RaiseCheckpointTollEvent) for e in res.auto_events)
        assert PlayerAction.INVEST in res.available_actions
        assert PlayerAction.RENOVATE in res.available_actions
        assert res.info["renovate_options"] == [SquareType.VP_TAX_OFFICE.value]

    def test_nonowner_land_pays_toll(self):
        game = _make_game()
        sq = _sq(SquareType.VP_CHECKPOINT, property_owner=0, checkpoint_toll=50)
        res = handle_land(game, 1, sq)
        pays = [e for e in res.auto_events if isinstance(e, PayCheckpointTollEvent)]
        assert len(pays) == 1
        assert res.info["toll"] == 50


class TestLandTaxOffice:
    def test_owner_gets_bonus_and_renovate(self):
        game = _make_game()
        sq = _sq(SquareType.VP_TAX_OFFICE, property_owner=0)
        res = handle_land(game, 0, sq)
        assert any(isinstance(e, TaxOfficeOwnerBonusEvent) for e in res.auto_events)
        assert PlayerAction.RENOVATE in res.available_actions
        assert res.info["renovate_options"] == [SquareType.VP_CHECKPOINT.value]

    def test_nonowner_pays_tax(self):
        game = _make_game()
        sq = _sq(SquareType.VP_TAX_OFFICE, property_owner=0)
        res = handle_land(game, 1, sq)
        pays = [e for e in res.auto_events if isinstance(e, PayTaxEvent)]
        assert len(pays) == 1 and pays[0].payer_id == 1 and pays[0].owner_id == 0


class TestLandSimpleEffects:
    def test_take_a_break_closes_shops(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.TAKE_A_BREAK))
        assert any(isinstance(e, CloseShopsEvent) for e in res.auto_events)

    def test_boon_commission_20(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.BOON))
        evs = [e for e in res.auto_events if isinstance(e, GainCommissionEvent)]
        assert len(evs) == 1 and evs[0].percent == 20

    def test_boom_commission_50(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.BOOM))
        evs = [e for e in res.auto_events if isinstance(e, GainCommissionEvent)]
        assert len(evs) == 1 and evs[0].percent == 50

    def test_roll_on_sets_flag(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.ROLL_ON))
        assert res.info.get("roll_again") is True

    def test_stockbroker_offers_buy_stock(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.STOCKBROKER))
        assert PlayerAction.BUY_STOCK in res.available_actions

    def test_venture_land_flags_card(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.VENTURE))
        assert res.info.get("venture_card") is True

    def test_suit_land_flags_card(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.SUIT, suit=Suit.HEART))
        assert res.info.get("venture_card") is True

    def test_suit_yourself_land_flags_card(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.SUIT_YOURSELF))
        assert res.info.get("venture_card") is True

    def test_change_of_suit_land_flags_card(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.CHANGE_OF_SUIT, suit=Suit.CLUB))
        assert res.info.get("venture_card") is True


class TestLandWarps:
    def test_backstreet_warps(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.BACKSTREET, backstreet_destination=9))
        warps = [e for e in res.auto_events if isinstance(e, WarpEvent)]
        assert len(warps) == 1 and warps[0].target_square_id == 9
        assert res.info["warped_to"] == 9

    def test_backstreet_no_destination_noop(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.BACKSTREET, backstreet_destination=None))
        assert res.auto_events == []


class TestLandCannon:
    def test_offers_target_when_other_active_players(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.CANNON))
        assert PlayerAction.CHOOSE_CANNON_TARGET in res.available_actions
        targets = res.info["cannon_targets"]
        assert {t["player_id"] for t in targets} == {1, 2, 3}

    def test_no_action_when_alone(self):
        game = _make_game()
        for p in game.players[1:]:
            p.bankrupt = True
        res = handle_land(game, 0, _sq(SquareType.CANNON))
        assert PlayerAction.CHOOSE_CANNON_TARGET not in res.available_actions
        assert "cannon_targets" not in res.info


class TestLandUnimplemented:
    def test_switch_marked_unimplemented(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.SWITCH))
        assert res.info.get("unimplemented") == SquareType.SWITCH.value

    def test_arcade_marked_unimplemented(self):
        game = _make_game()
        res = handle_land(game, 0, _sq(SquareType.ARCADE))
        assert res.info.get("unimplemented") == SquareType.ARCADE.value
