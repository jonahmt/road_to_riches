"""Integration tests for the core game engine."""

from __future__ import annotations

import random

from road_to_riches.board import load_board
from road_to_riches.engine.bankruptcy import (
    BankruptcyEvent,
    SellShopToBankEvent,
    check_bankruptcy,
    check_victory,
    needs_liquidation,
)
from road_to_riches.engine.property import current_rent, max_capital
from road_to_riches.engine.square_handler import PlayerAction, handle_land, handle_pass
from road_to_riches.events.turn_events import (
    MoveEvent,
    PassActionEvent,
    RollEvent,
    TurnEvent,
    WillMoveEvent,
)
from road_to_riches.events.game_events import (
    AuctionSellEvent,
    BuyShopEvent,
    BuyStockEvent,
    BuyVacantPlotEvent,
    CollectSuitEvent,
    ForcedBuyoutEvent,
    InvestInShopEvent,
    PayCheckpointTollEvent,
    PayTaxEvent,
    PromotionEvent,
    RaiseCheckpointTollEvent,
    RenovatePropertyEvent,
    RotateSuitEvent,
    ScriptEvent,
    SellStockEvent,
    TaxOfficeOwnerBonusEvent,
    TransferPropertyEvent,
    WarpEvent,
)
from road_to_riches.events.pipeline import EventPipeline
from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit


def _make_game() -> tuple[GameState, EventPipeline]:
    board, stock = load_board("boards/test_board.json")
    players = [PlayerState(player_id=i, position=0, ready_cash=1500) for i in range(4)]
    game = GameState(board=board, stock=stock, players=players)
    pipeline = EventPipeline()
    return game, pipeline


class TestBuyShop:
    def test_buy_shop_transfers_ownership(self):
        game, _ = _make_game()
        sq = game.board.squares[1]
        assert sq.property_owner is None

        BuyShopEvent(player_id=0, square_id=1).execute(game)

        assert sq.property_owner == 0
        assert 1 in game.players[0].owned_properties
        assert game.players[0].ready_cash == 1500 - sq.shop_base_value

    def test_buy_shop_updates_stock_value(self):
        game, _ = _make_game()
        old_price = game.stock.get_price(0).value_component
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        # Stock value shouldn't change since current_value == base_value
        assert game.stock.get_price(0).value_component == old_price


class TestRent:
    def test_rent_basic(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)

        rent = current_rent(game.board, game.board.squares[1])
        assert rent == 30  # base rent, 1 owned in 3-shop district

    def test_rent_increases_with_district_ownership(self):
        game, _ = _make_game()
        # Buy all 3 shops in district 0 (ids: 1, 2, 4)
        for sq_id in [1, 2, 4]:
            BuyShopEvent(player_id=0, square_id=sq_id).execute(game)

        rent_sq1 = current_rent(game.board, game.board.squares[1])
        # 3 of 3 owned: multiplier is 3.75
        assert rent_sq1 == 112  # int(3.75 * 30)


class TestInvestment:
    def test_invest_increases_value(self):
        game, _ = _make_game()
        # Buy 2 shops in district 0 to get max_cap > 0 (LUT gives higher multiplier)
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=0, square_id=2).execute(game)
        mc = max_capital(game.board, game.board.squares[1])
        assert mc > 0

        InvestInShopEvent(player_id=0, square_id=1, amount=100).execute(game)
        invested = min(100, mc)

        assert game.board.squares[1].shop_current_value == 200 + invested

    def test_invest_capped_at_max_capital(self):
        game, _ = _make_game()
        # Buy 2 shops so max_cap > 0
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=0, square_id=2).execute(game)

        mc = max_capital(game.board, game.board.squares[1])
        assert mc > 0
        InvestInShopEvent(player_id=0, square_id=1, amount=99999).execute(game)

        assert game.board.squares[1].shop_current_value == 200 + mc

    def test_invest_updates_stock_price(self):
        game, _ = _make_game()
        # Buy 2 shops so investment is possible
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=0, square_id=2).execute(game)
        old_stock = game.stock.get_price(0).value_component

        mc = max_capital(game.board, game.board.squares[1])
        assert mc > 0
        InvestInShopEvent(player_id=0, square_id=1, amount=100).execute(game)
        new_stock = game.stock.get_price(0).value_component
        assert new_stock > old_stock


class TestStock:
    def test_buy_stock(self):
        game, _ = _make_game()
        price = game.stock.get_price(0).current_price
        BuyStockEvent(player_id=0, district_id=0, quantity=5).execute(game)

        assert game.players[0].owned_stock[0] == 5
        assert game.players[0].ready_cash == 1500 - 5 * price

    def test_sell_stock(self):
        game, _ = _make_game()
        BuyStockEvent(player_id=0, district_id=0, quantity=10).execute(game)
        cash_after_buy = game.players[0].ready_cash

        price = game.stock.get_price(0).current_price
        SellStockEvent(player_id=0, district_id=0, quantity=5).execute(game)

        assert game.players[0].owned_stock[0] == 5
        assert game.players[0].ready_cash == cash_after_buy + 5 * price

    def test_buy_10_stock_creates_pending_fluctuation(self):
        game, _ = _make_game()
        BuyStockEvent(player_id=0, district_id=0, quantity=10).execute(game)
        assert game.stock.get_price(0).pending_fluctuation > 0

    def test_buy_under_10_no_fluctuation(self):
        game, _ = _make_game()
        BuyStockEvent(player_id=0, district_id=0, quantity=9).execute(game)
        assert game.stock.get_price(0).pending_fluctuation == 0


class TestPromotion:
    def test_suit_collection(self):
        game, _ = _make_game()
        CollectSuitEvent(player_id=0, suit=Suit.SPADE.value).execute(game)
        assert game.players[0].suits[Suit.SPADE] == 1

    def test_duplicate_suit_not_added(self):
        game, _ = _make_game()
        CollectSuitEvent(player_id=0, suit=Suit.SPADE.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.SPADE.value).execute(game)
        assert game.players[0].suits[Suit.SPADE] == 1

    def test_wild_card_stacks(self):
        game, _ = _make_game()
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)
        assert game.players[0].suits[Suit.WILD] == 2

    def test_promotion_bonus(self):
        game, _ = _make_game()
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
            CollectSuitEvent(player_id=0, suit=suit.value).execute(game)
        assert game.players[0].has_all_suits

        PromotionEvent(player_id=0).execute(game)

        assert game.players[0].level == 2
        assert len(game.players[0].suits) == 0  # suits cleared
        # Base salary (250) + level bonus (150 * 1) = 400
        assert game.players[0].ready_cash == 1500 + 400

    def test_promotion_keeps_excess_wilds(self):
        game, _ = _make_game()
        # 4 real suits + 1 wild -> 1 wild leftover
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
            CollectSuitEvent(player_id=0, suit=suit.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)

        PromotionEvent(player_id=0).execute(game)

        assert game.players[0].suits == {Suit.WILD: 1}

    def test_promotion_wild_substitutes_and_keeps_excess(self):
        game, _ = _make_game()
        # 3 real suits + 2 wilds -> 1 wild leftover (1 wild used as substitute)
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND]:
            CollectSuitEvent(player_id=0, suit=suit.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)

        PromotionEvent(player_id=0).execute(game)

        assert game.players[0].suits == {Suit.WILD: 1}

    def test_promotion_wild_exact_substitution(self):
        game, _ = _make_game()
        # 3 real suits + 1 wild -> nothing left (wild used as substitute)
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND]:
            CollectSuitEvent(player_id=0, suit=suit.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)

        PromotionEvent(player_id=0).execute(game)

        assert len(game.players[0].suits) == 0


def _run_movement(game: GameState, pipeline: EventPipeline, player_id: int, roll: int) -> None:
    """Run movement events choosing the first path each step, auto-confirm stop."""
    from road_to_riches.board.pathfinding import get_next_squares

    remaining = roll
    while remaining > 0:
        player = game.get_player(player_id)
        choices = get_next_squares(game.board, player.position, player.from_square)
        if not choices:
            break

        from_sq = player.position
        target_sq = game.board.squares[choices[0]]
        step_cost = 0 if target_sq.type == SquareType.DOORWAY else 1

        # Move
        move_evt = MoveEvent(player_id=player_id, from_sq=from_sq, to_sq=choices[0])
        move_evt.execute(game)

        # Pass action
        pass_evt = PassActionEvent(player_id=player_id, square_id=choices[0])
        pass_evt.execute(game)
        result = pass_evt.get_result()
        if result is not None:
            for auto_event in result.auto_events:
                auto_event.execute(game)

        remaining -= step_cost


class TestTurnLifecycle:
    def test_full_turn_cycle(self):
        random.seed(99)
        game, pipeline = _make_game()

        # TurnEvent
        turn_event = TurnEvent(player_id=0)
        turn_event.execute(game)
        assert game.current_player.player_id == 0

        # RollEvent
        roll_event = RollEvent(player_id=0)
        roll_event.execute(game)
        roll = roll_event.get_result()
        assert 1 <= roll <= 6

        # Movement
        _run_movement(game, pipeline, 0, roll)

        # Player should have moved
        assert game.players[0].position != 0

    def test_suit_collected_during_pass(self):
        random.seed(42)  # rolls 6, passes square 3 (spade suit)
        game, pipeline = _make_game()

        roll_event = RollEvent(player_id=0)
        roll_event.execute(game)
        roll = roll_event.get_result()

        _run_movement(game, pipeline, 0, roll)

        assert Suit.SPADE in game.players[0].suits


class TestBankruptcyAndVictory:
    def test_bankruptcy_detection(self):
        game, _ = _make_game()
        game.players[0].ready_cash = -100
        # Net worth = -100 (no assets), so bankrupt
        assert check_bankruptcy(game, 0)

    def test_no_bankruptcy_with_assets(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        game.players[0].ready_cash = -100
        # Net worth = -100 + 200 (shop) = 100, not bankrupt
        assert not check_bankruptcy(game, 0)

    def test_bankruptcy_event_removes_player(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BankruptcyEvent(player_id=0).execute(game)

        assert game.players[0].bankrupt
        assert len(game.players[0].owned_properties) == 0
        assert len(game.players[0].owned_stock) == 0
        assert game.board.squares[1].property_owner is None

    def test_sell_shop_to_bank(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        cash_before = game.players[0].ready_cash
        SellShopToBankEvent(player_id=0, square_id=1).execute(game)

        assert 1 not in game.players[0].owned_properties
        assert game.board.squares[1].property_owner is None
        assert game.players[0].ready_cash == cash_before + int(200 * 0.75)

    def test_needs_liquidation(self):
        game, _ = _make_game()
        assert not needs_liquidation(game, 0)
        game.players[0].ready_cash = -1
        assert needs_liquidation(game, 0)

    def test_victory_requires_bank_square(self):
        game, _ = _make_game()
        game.players[0].ready_cash = 20000
        # Player is at position 0 (bank)
        assert check_victory(game, 0)

    def test_victory_fails_if_not_at_bank(self):
        game, _ = _make_game()
        game.players[0].ready_cash = 20000
        game.players[0].position = 5  # not bank
        assert not check_victory(game, 0)

    def test_victory_fails_if_below_target(self):
        game, _ = _make_game()
        # 1500 cash, target is 10000
        assert not check_victory(game, 0)


class TestP1SquareTypes:
    def test_change_of_suit_pass_collects_and_rotates(self):
        game, _ = _make_game()
        # Repurpose an existing square in the test board for this test
        sq = game.board.squares[3]  # suit square on test board
        original_type = sq.type
        sq.type = SquareType.CHANGE_OF_SUIT
        sq.suit = Suit.SPADE

        result = handle_pass(game, 0, sq)
        assert len(result.auto_events) == 2
        assert isinstance(result.auto_events[0], CollectSuitEvent)
        assert result.auto_events[0].suit == Suit.SPADE
        assert isinstance(result.auto_events[1], RotateSuitEvent)

        for e in result.auto_events:
            e.execute(game)
        assert game.players[0].suits[Suit.SPADE] == 1
        assert sq.suit == Suit.HEART

        sq.type = original_type

    def test_change_of_suit_full_rotation(self):
        assert Suit.SPADE.next() == Suit.HEART
        assert Suit.HEART.next() == Suit.DIAMOND
        assert Suit.DIAMOND.next() == Suit.CLUB
        assert Suit.CLUB.next() == Suit.SPADE

    def test_suit_yourself_grants_wild(self):
        game, _ = _make_game()
        sq = SquareInfo(id=99, position=(0, 0), type=SquareType.SUIT_YOURSELF)
        result = handle_pass(game, 0, sq)
        assert len(result.auto_events) == 1
        assert isinstance(result.auto_events[0], CollectSuitEvent)
        assert result.auto_events[0].suit == Suit.WILD.value
        result.auto_events[0].execute(game)
        assert game.players[0].suits[Suit.WILD] == 1

    def test_backstreet_land_warps(self):
        game, _ = _make_game()
        sq = SquareInfo(
            id=99, position=(0, 0), type=SquareType.BACKSTREET, backstreet_destination=5
        )
        result = handle_land(game, 0, sq)
        assert len(result.auto_events) == 1
        assert isinstance(result.auto_events[0], WarpEvent)
        assert result.auto_events[0].target_square_id == 5
        result.auto_events[0].execute(game)
        assert game.players[0].position == 5

    def test_doorway_pass_warps(self):
        game, _ = _make_game()
        sq = SquareInfo(id=99, position=(0, 0), type=SquareType.DOORWAY, doorway_destination=10)
        result = handle_pass(game, 0, sq)
        assert len(result.auto_events) == 1
        assert isinstance(result.auto_events[0], WarpEvent)
        assert result.auto_events[0].target_square_id == 10

    def test_cannon_land_offers_targets(self):
        game, _ = _make_game()
        game.players[1].position = 7
        game.players[2].position = 12
        sq = SquareInfo(id=99, position=(0, 0), type=SquareType.CANNON)
        result = handle_land(game, 0, sq)

        assert PlayerAction.CHOOSE_CANNON_TARGET in result.available_actions
        targets = result.info["cannon_targets"]
        target_pids = [t["player_id"] for t in targets]
        assert 1 in target_pids
        assert 2 in target_pids
        assert 0 not in target_pids  # self excluded

    def test_warp_event(self):
        game, _ = _make_game()
        game.players[0].position = 3
        WarpEvent(player_id=0, target_square_id=15).execute(game)
        assert game.players[0].position == 15


class TestVacantPlots:
    def test_buy_vacant_plot_as_checkpoint(self):
        game, _ = _make_game()
        # Use an existing square and make it a vacant plot
        sq = game.board.squares[5]
        sq.type = SquareType.VACANT_PLOT
        sq.shop_base_value = 200
        sq.shop_current_value = 200
        sq.property_district = 0

        BuyVacantPlotEvent(player_id=0, square_id=5, development_type="VP_CHECKPOINT").execute(game)

        assert sq.property_owner == 0
        assert sq.type == SquareType.VP_CHECKPOINT
        assert sq.checkpoint_toll == 10
        assert game.players[0].ready_cash == 1500 - 200

    def test_buy_vacant_plot_as_tax_office(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VACANT_PLOT
        sq.shop_base_value = 200
        sq.shop_current_value = 200
        sq.property_district = 0

        BuyVacantPlotEvent(player_id=0, square_id=5, development_type="VP_TAX_OFFICE").execute(game)

        assert sq.type == SquareType.VP_TAX_OFFICE
        assert sq.checkpoint_toll == 0

    def test_checkpoint_toll_payment(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_CHECKPOINT
        sq.property_owner = 0
        sq.checkpoint_toll = 30

        PayCheckpointTollEvent(payer_id=1, owner_id=0, square_id=5).execute(game)

        # Player 1 pays 30, owner gets 30, toll increases to 40
        assert game.players[1].ready_cash == 1500 - 30
        assert game.players[0].ready_cash == 1500 + 30
        assert sq.checkpoint_toll == 40

    def test_checkpoint_raise_toll(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_CHECKPOINT
        sq.checkpoint_toll = 20

        RaiseCheckpointTollEvent(square_id=5).execute(game)
        assert sq.checkpoint_toll == 30

    def test_checkpoint_pass_handler_owner(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_CHECKPOINT
        sq.property_owner = 0
        sq.checkpoint_toll = 20

        result = handle_pass(game, 0, sq)
        assert len(result.auto_events) == 1
        assert isinstance(result.auto_events[0], RaiseCheckpointTollEvent)

    def test_checkpoint_pass_handler_other(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_CHECKPOINT
        sq.property_owner = 0
        sq.checkpoint_toll = 20

        result = handle_pass(game, 1, sq)
        assert len(result.auto_events) == 1
        assert isinstance(result.auto_events[0], PayCheckpointTollEvent)

    def test_tax_office_other_player(self):
        game, _ = _make_game()
        # Set specific net worths
        game.players[1].ready_cash = 2000

        PayTaxEvent(payer_id=1, owner_id=0, square_id=0).execute(game)

        # 4% of player 1's net worth (2000) = 80
        assert game.players[1].ready_cash == 2000 - 80
        assert game.players[0].ready_cash == 1500 + 80

    def test_tax_office_owner_bonus(self):
        game, _ = _make_game()
        game.players[0].ready_cash = 3000

        TaxOfficeOwnerBonusEvent(player_id=0).execute(game)

        # 4% of 3000 = 120
        assert game.players[0].ready_cash == 3000 + 120


class TestShopExchanges:
    def test_forced_buyout(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        # sq1 has base value 200, current value 200
        p1_cash = game.players[1].ready_cash

        ForcedBuyoutEvent(buyer_id=1, square_id=1).execute(game)

        # Buyer pays 5x = 1000, owner gets 3x = 600, 2x to bank
        assert game.players[1].ready_cash == p1_cash - 1000
        assert 1 in game.players[1].owned_properties
        assert 1 not in game.players[0].owned_properties
        assert game.board.squares[1].property_owner == 1
        # Owner got 3x = 600 (on top of buying at 200)
        assert game.players[0].ready_cash == (1500 - 200) + 600

    def test_transfer_property(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)

        TransferPropertyEvent(from_player_id=0, to_player_id=1, square_id=1, price=300).execute(
            game
        )

        assert game.board.squares[1].property_owner == 1
        assert 1 in game.players[1].owned_properties
        assert 1 not in game.players[0].owned_properties
        assert game.players[1].ready_cash == 1500 - 300
        assert game.players[0].ready_cash == (1500 - 200) + 300

    def test_auction_with_winner(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        p0_cash = game.players[0].ready_cash

        AuctionSellEvent(seller_id=0, square_id=1, winner_id=1, winning_bid=500).execute(game)

        assert game.board.squares[1].property_owner == 1
        assert 1 in game.players[1].owned_properties
        assert 1 not in game.players[0].owned_properties
        assert game.players[0].ready_cash == p0_cash + 500
        assert game.players[1].ready_cash == 1500 - 500

    def test_auction_no_bids(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        p0_cash = game.players[0].ready_cash

        AuctionSellEvent(seller_id=0, square_id=1, winner_id=None, winning_bid=0).execute(game)

        # No bids: seller gets base value (200), shop becomes unowned
        assert game.board.squares[1].property_owner is None
        assert 1 not in game.players[0].owned_properties
        assert game.players[0].ready_cash == p0_cash + 200

    def test_forced_buyout_offered_on_rent(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        # Give player 1 enough cash for 5x buyout (1000)
        game.players[1].ready_cash = 5000

        result = handle_land(game, 1, game.board.squares[1])

        assert PlayerAction.FORCED_BUYOUT in result.available_actions
        assert result.info["buyout_cost"] == 1000

    def test_forced_buyout_not_offered_if_too_poor(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        # Player 1 can't afford buyout after rent
        game.players[1].ready_cash = 100

        result = handle_land(game, 1, game.board.squares[1])

        assert PlayerAction.FORCED_BUYOUT not in result.available_actions


class TestRenovation:
    def test_renovate_checkpoint_to_tax_office(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_CHECKPOINT
        sq.property_owner = 0
        sq.property_district = 0
        sq.shop_base_value = 200
        sq.shop_current_value = 300
        sq.checkpoint_toll = 40
        game.players[0].owned_properties.append(5)
        game.players[0].ready_cash = 1000

        RenovatePropertyEvent(player_id=0, square_id=5, new_type="VP_TAX_OFFICE").execute(game)

        assert sq.type == SquareType.VP_TAX_OFFICE
        assert sq.checkpoint_toll == 0
        assert sq.shop_current_value == 200  # Reset to base
        # Refund 75% of 300 = 225, cost 200 => net +25
        assert game.players[0].ready_cash == 1025

    def test_renovate_tax_office_to_checkpoint(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_TAX_OFFICE
        sq.property_owner = 0
        sq.property_district = 0
        sq.shop_base_value = 200
        sq.shop_current_value = 200
        game.players[0].owned_properties.append(5)
        game.players[0].ready_cash = 1000

        RenovatePropertyEvent(player_id=0, square_id=5, new_type="VP_CHECKPOINT").execute(game)

        assert sq.type == SquareType.VP_CHECKPOINT
        assert sq.checkpoint_toll == 10
        # Refund 75% of 200 = 150, cost 200 => net -50
        assert game.players[0].ready_cash == 950

    def test_renovate_action_offered_on_owner_checkpoint_land(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_CHECKPOINT
        sq.property_owner = 0
        sq.checkpoint_toll = 20

        result = handle_land(game, 0, sq)

        assert PlayerAction.RENOVATE in result.available_actions
        assert "VP_TAX_OFFICE" in result.info["renovate_options"]

    def test_renovate_action_offered_on_owner_tax_office_land(self):
        game, _ = _make_game()
        sq = game.board.squares[5]
        sq.type = SquareType.VP_TAX_OFFICE
        sq.property_owner = 0

        result = handle_land(game, 0, sq)

        assert PlayerAction.RENOVATE in result.available_actions
        assert "VP_CHECKPOINT" in result.info["renovate_options"]


class TestTrade:
    def test_trade_shops_swap(self):
        """Two players swap shops via TransferPropertyEvent (no gold)."""
        game, _ = _make_game()
        # Player 0 owns sq 1, player 1 owns sq 4
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=1, square_id=4).execute(game)
        p0_cash_after = game.players[0].ready_cash
        p1_cash_after = game.players[1].ready_cash

        # Transfer sq 1 from P0 to P1 (price=0)
        TransferPropertyEvent(from_player_id=0, to_player_id=1, square_id=1, price=0).execute(game)
        # Transfer sq 4 from P1 to P0 (price=0)
        TransferPropertyEvent(from_player_id=1, to_player_id=0, square_id=4, price=0).execute(game)

        assert 1 in game.players[1].owned_properties
        assert 4 in game.players[0].owned_properties
        assert 1 not in game.players[0].owned_properties
        assert 4 not in game.players[1].owned_properties
        # No gold exchanged
        assert game.players[0].ready_cash == p0_cash_after
        assert game.players[1].ready_cash == p1_cash_after

    def test_trade_with_gold(self):
        """Trade with gold offset: P0 gives shop + gold for P1's shop."""
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=1, square_id=4).execute(game)
        p0_cash = game.players[0].ready_cash
        p1_cash = game.players[1].ready_cash

        # Swap shops + P0 gives 100G
        TransferPropertyEvent(from_player_id=0, to_player_id=1, square_id=1, price=0).execute(game)
        TransferPropertyEvent(from_player_id=1, to_player_id=0, square_id=4, price=0).execute(game)
        # Gold transfer
        game.players[0].ready_cash -= 100
        game.players[1].ready_cash += 100

        assert game.players[0].ready_cash == p0_cash - 100
        assert game.players[1].ready_cash == p1_cash + 100


class TestScriptEvent:
    def test_venture_placeholder_script(self):
        """ScriptEvent executes a Python script that modifies game state."""
        import os

        game, _ = _make_game()
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "scripts",
            "venture_placeholder.py",
        )
        event = ScriptEvent(player_id=0, script_path=script_path)
        event.execute(game)

        assert game.players[0].ready_cash == 1600  # 1500 + 100
        msg = event.get_result()
        assert "100G" in msg
        assert "Player 0" in msg

    def test_venture_card_on_suit_square(self):
        """Landing on a Suit square should trigger venture_card flag."""
        game, _ = _make_game()
        # Square 3 is a Suit square in test_board
        sq = game.board.squares[3]
        assert sq.type == SquareType.SUIT

        result = handle_land(game, 0, sq)
        assert result.info.get("venture_card") is True

    def test_venture_card_on_venture_square(self):
        """Landing on a Venture square should trigger venture_card flag."""
        game, _ = _make_game()
        sq = game.board.squares[5]
        assert sq.type == SquareType.VENTURE

        result = handle_land(game, 0, sq)
        assert result.info.get("venture_card") is True
