"""Simple stdin/stdout player input for testing the game loop."""

from __future__ import annotations

from road_to_riches.engine.game_loop import GameLog, PlayerInput
from road_to_riches.engine.property import current_rent, max_capital
from road_to_riches.models.game_state import GameState


class TextPlayerInput(PlayerInput):
    """Collects player input via stdin. Displays via stdout."""

    def choose_pre_roll_action(self, state: GameState, player_id: int, log: GameLog) -> str:
        player = state.get_player(player_id)
        self.notify(state, log)
        print(f"  Cash: {player.ready_cash}G | Level: {player.level}")
        print(f"  Suits: {_fmt_suits(player)}")
        has_stock = bool(player.owned_stock)
        has_shops = bool(player.owned_properties)
        options = "[R]oll"
        if has_stock:
            options += ", [S]ell Stock"
        if has_shops:
            options += ", [A]uction, Sell S[h]op"
        options += ", [B]uy Shop, [I]nfo"
        while True:
            choice = input(f"  > {options}: ").strip().upper()
            if choice in ("R", "ROLL"):
                return "roll"
            elif choice in ("S", "SELL") and has_stock:
                return "sell_stock"
            elif choice in ("A", "AUCTION") and has_shops:
                return "auction"
            elif choice in ("H",) and has_shops:
                return "sell_shop"
            elif choice in ("B", "BUY"):
                return "buy_shop"
            elif choice in ("I", "INFO"):
                self._show_info(state, player_id)
            else:
                print("  Invalid choice.")

    def choose_path(
        self, state: GameState, player_id: int, choices: list[int], log: GameLog
    ) -> int:
        self.notify(state, log)
        descs = []
        for sq_id in choices:
            sq = state.board.squares[sq_id]
            descs.append(f"{sq_id} ({sq.type.value})")
        print(f"  Choose path: {', '.join(descs)}")
        while True:
            try:
                choice = int(input("  > Square ID: ").strip())
                if choice in choices:
                    return choice
            except ValueError:
                pass
            print("  Invalid choice.")

    def choose_buy_shop(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        self.notify(state, log)
        sq = state.board.squares[square_id]
        player = state.get_player(player_id)
        print(f"  Buy shop at square {square_id} (district {sq.property_district})?")
        print(f"  Cost: {cost}G | Your cash: {player.ready_cash}G")
        choice = input("  > [Y]es / [N]o: ").strip().upper()
        return choice in ("Y", "YES")

    def choose_investment(
        self, state: GameState, player_id: int, investable: list[dict], log: GameLog
    ) -> tuple[int, int] | None:
        self.notify(state, log)
        player = state.get_player(player_id)
        print(f"  Invest in a shop? (Cash: {player.ready_cash}G)")
        for shop in investable:
            print(
                f"    Square {shop['square_id']}: "
                f"value={shop['current_value']}G, "
                f"max_cap={shop['max_capital']}G, "
                f"district={shop['district']}"
            )
        print("  Enter square ID and amount, or 'n' to skip.")
        choice = input("  > ").strip()
        if choice.lower() in ("n", "no", ""):
            return None
        try:
            parts = choice.split()
            sq_id = int(parts[0])
            amount = int(parts[1]) if len(parts) > 1 else player.ready_cash
            valid_ids = [s["square_id"] for s in investable]
            if sq_id in valid_ids:
                return (sq_id, amount)
        except (ValueError, IndexError):
            pass
        print("  Invalid input, skipping investment.")
        return None

    def choose_stock_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        self.notify(state, log)
        player = state.get_player(player_id)
        print(f"  Buy stock? (Cash: {player.ready_cash}G)")
        self._show_stock_table(state)
        print("  Enter district ID and quantity, or 'n' to skip.")
        choice = input("  > ").strip()
        if choice.lower() in ("n", "no", ""):
            return None
        try:
            parts = choice.split()
            district_id = int(parts[0])
            qty = int(parts[1]) if len(parts) > 1 else 1
            price = state.stock.get_price(district_id).current_price
            if qty * price <= player.ready_cash and qty > 0:
                return (district_id, qty)
            else:
                print("  Can't afford that many.")
        except (ValueError, IndexError):
            pass
        return None

    def choose_stock_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        self.notify(state, log)
        player = state.get_player(player_id)
        print("  Sell stock?")
        for d_id, qty in player.owned_stock.items():
            price = state.stock.get_price(d_id).current_price
            print(f"    District {d_id}: {qty} shares @ {price}G each")
        print("  Enter district ID and quantity, or 'n' to skip.")
        choice = input("  > ").strip()
        if choice.lower() in ("n", "no", ""):
            return None
        try:
            parts = choice.split()
            district_id = int(parts[0])
            qty = int(parts[1]) if len(parts) > 1 else player.owned_stock.get(district_id, 0)
            if qty > 0:
                return (district_id, qty)
        except (ValueError, IndexError):
            pass
        return None

    def choose_cannon_target(
        self, state: GameState, player_id: int, targets: list[dict], log: GameLog
    ) -> int:
        self.notify(state, log)
        print("  Cannon! Choose a player to warp to:")
        for t in targets:
            sq = state.board.squares[t["position"]]
            print(f"    Player {t['player_id']} at square {t['position']} ({sq.type.value})")
        while True:
            try:
                choice = int(input("  > Player ID: ").strip())
                valid_ids = [t["player_id"] for t in targets]
                if choice in valid_ids:
                    return choice
            except ValueError:
                pass
            print("  Invalid choice.")

    def choose_vacant_plot_type(
        self,
        state: GameState,
        player_id: int,
        square_id: int,
        options: list[str],
        log: GameLog,
    ) -> str:
        self.notify(state, log)
        print(f"  Choose development type for vacant plot {square_id}:")
        for i, opt in enumerate(options):
            print(f"    [{i + 1}] {opt}")
        while True:
            try:
                choice = int(input("  > ").strip())
                if 1 <= choice <= len(options):
                    return options[choice - 1]
            except ValueError:
                pass
            print("  Invalid choice.")

    def choose_forced_buyout(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        self.notify(state, log)
        player = state.get_player(player_id)
        print(f"  Force-buy square {square_id} for {cost}G? (Cash: {player.ready_cash}G)")
        choice = input("  > [Y]es / [N]o: ").strip().upper()
        return choice in ("Y", "YES")

    def choose_auction_bid(
        self,
        state: GameState,
        player_id: int,
        square_id: int,
        min_bid: int,
        log: GameLog,
    ) -> int | None:
        self.notify(state, log)
        player = state.get_player(player_id)
        sq = state.board.squares[square_id]
        print(f"  Player {player_id}: Bid on square {square_id} (value={sq.shop_current_value}G)?")
        print(f"  Minimum bid: {min_bid}G | Your cash: {player.ready_cash}G")
        choice = input("  > Bid amount or 'n': ").strip()
        if choice.lower() in ("n", "no", ""):
            return None
        try:
            bid = int(choice)
            if bid >= min_bid and bid <= player.ready_cash:
                return bid
            print("  Invalid bid.")
        except ValueError:
            pass
        return None

    def choose_shop_to_auction(self, state: GameState, player_id: int, log: GameLog) -> int | None:
        self.notify(state, log)
        player = state.get_player(player_id)
        print("  Choose a shop to auction:")
        for sq_id in player.owned_properties:
            sq = state.board.squares[sq_id]
            print(
                f"    Square {sq_id}: value={sq.shop_current_value}G, "
                f"district={sq.property_district}"
            )
        choice = input("  > Square ID or 'n': ").strip()
        if choice.lower() in ("n", "no", ""):
            return None
        try:
            sq_id = int(choice)
            if sq_id in player.owned_properties:
                return sq_id
        except ValueError:
            pass
        print("  Invalid choice.")
        return None

    def choose_shop_to_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        self.notify(state, log)
        print("  Buy a shop from another player.")
        print("  Other players' shops:")
        for p in state.active_players:
            if p.player_id == player_id:
                continue
            for sq_id in p.owned_properties:
                sq = state.board.squares[sq_id]
                print(
                    f"    P{p.player_id} sq{sq_id}: "
                    f"value={sq.shop_current_value}G, "
                    f"district={sq.property_district}"
                )
        print("  Enter: player_id square_id offer_price, or 'n'")
        choice = input("  > ").strip()
        if choice.lower() in ("n", "no", ""):
            return None
        try:
            parts = choice.split()
            target_pid = int(parts[0])
            sq_id = int(parts[1])
            price = int(parts[2])
            return (target_pid, sq_id, price)
        except (ValueError, IndexError):
            pass
        print("  Invalid input.")
        return None

    def choose_shop_to_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        self.notify(state, log)
        player = state.get_player(player_id)
        print("  Sell one of your shops to another player.")
        for sq_id in player.owned_properties:
            sq = state.board.squares[sq_id]
            print(
                f"    Square {sq_id}: value={sq.shop_current_value}G, "
                f"district={sq.property_district}"
            )
        print("  Enter: target_player_id square_id asking_price, or 'n'")
        choice = input("  > ").strip()
        if choice.lower() in ("n", "no", ""):
            return None
        try:
            parts = choice.split()
            target_pid = int(parts[0])
            sq_id = int(parts[1])
            price = int(parts[2])
            if sq_id in player.owned_properties:
                return (target_pid, sq_id, price)
        except (ValueError, IndexError):
            pass
        print("  Invalid input.")
        return None

    def choose_accept_offer(
        self, state: GameState, player_id: int, offer: dict, log: GameLog
    ) -> str:
        self.notify(state, log)
        otype = offer["type"]
        sq_id = offer["square_id"]
        price = offer["price"]
        print(f"  Player {player_id}: {otype} offer for square {sq_id} at {price}G")
        choice = input("  > [A]ccept / [R]eject / [C]ounter: ").strip().upper()
        if choice in ("A", "ACCEPT"):
            return "accept"
        if choice in ("C", "COUNTER"):
            return "counter"
        return "reject"

    def choose_counter_price(
        self, state: GameState, player_id: int, original_price: int, log: GameLog
    ) -> int:
        self.notify(state, log)
        print(f"  Original price: {original_price}G. Enter counter-offer:")
        while True:
            try:
                return int(input("  > ").strip())
            except ValueError:
                print("  Invalid amount.")

    def choose_liquidation(
        self, state: GameState, player_id: int, options: dict, log: GameLog
    ) -> tuple[str, int]:
        self.notify(state, log)
        player = state.get_player(player_id)
        print(f"  Cash: {player.ready_cash}G (need to reach 0)")
        if options["shops"]:
            print("  Shops to sell (75% value):")
            for shop in options["shops"]:
                print(f"    [shop {shop['square_id']}] sell value: {shop['sell_value']}G")
        if options["stock"]:
            print("  Stock to sell:")
            for d_id, info in options["stock"].items():
                qty, val = info["quantity"], info["total_value"]
                print(f"    [stock {d_id}] {qty} shares, total: {val}G")
        while True:
            choice = input("  > sell shop <id> / sell stock <id>: ").strip().lower()
            parts = choice.split()
            try:
                if len(parts) >= 3 and parts[0] == "sell":
                    asset_type = parts[1]
                    asset_id = int(parts[2])
                    if asset_type in ("shop", "stock"):
                        return (asset_type, asset_id)
            except ValueError:
                pass
            print("  Invalid. Use: sell shop <id> or sell stock <id>")

    def notify(self, state: GameState, log: GameLog) -> None:
        for msg in log.messages:
            print(f"  [LOG] {msg}")
        log.clear()

    def _show_info(self, state: GameState, player_id: int) -> None:
        print("\n  === Game Info ===")
        print(f"  Target net worth: {state.board.target_networth}G")
        print(f"  Max dice roll: {state.board.max_dice_roll}")
        print()
        for p in state.players:
            if p.bankrupt:
                print(f"  Player {p.player_id}: BANKRUPT")
                continue
            nw = state.net_worth(p)
            marker = " <-- YOU" if p.player_id == player_id else ""
            print(
                f"  Player {p.player_id}: cash={p.ready_cash}G, "
                f"nw={nw}G, level={p.level}, "
                f"sq={p.position}, suits={_fmt_suits(p)}{marker}"
            )
            if p.owned_properties:
                for sq_id in p.owned_properties:
                    sq = state.board.squares[sq_id]
                    rent = current_rent(state.board, sq)
                    mc = max_capital(state.board, sq)
                    print(
                        f"    Shop sq{sq_id} d{sq.property_district}: "
                        f"val={sq.shop_current_value}, rent={rent}, max_cap={mc}"
                    )
        print()
        self._show_stock_table(state)
        print()

    def _show_stock_table(self, state: GameState) -> None:
        print("  Stock Market:")
        header = "  District | Price"
        for p in state.active_players:
            header += f" | P{p.player_id}"
        print(header)
        for sp in state.stock.stocks:
            row = f"       {sp.district_id}   |  {sp.current_price:3d} "
            for p in state.active_players:
                qty = p.owned_stock.get(sp.district_id, 0)
                row += f" | {qty:2d}"
            print(row)


def _fmt_suits(player) -> str:
    from road_to_riches.models.suit import Suit

    symbols = {
        Suit.SPADE: "S",
        Suit.HEART: "H",
        Suit.DIAMOND: "D",
        Suit.CLUB: "C",
        Suit.WILD: "W",
    }
    parts = []
    for suit, sym in symbols.items():
        count = player.suits.get(suit, 0)
        if count > 0:
            parts.append(sym if count == 1 else f"{sym}x{count}")
    return " ".join(parts) if parts else "none"
