"""Entry point for running a Road to Riches game."""

from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    mode = "tui"

    if "--text" in args:
        mode = "text"
        args.remove("--text")
    elif "--tui" in args:
        args.remove("--tui")

    board_path = args[0] if args else "boards/test_board.json"
    num_players = int(args[1]) if len(args) > 1 else 4

    if mode == "tui":
        from road_to_riches.client.tui_app import run_tui

        run_tui(board_path, num_players)
    else:
        from road_to_riches.client.text_input import TextPlayerInput
        from road_to_riches.engine.game_loop import GameConfig, GameLoop

        config = GameConfig(
            board_path=board_path,
            num_players=num_players,
            starting_cash=1500,
        )
        player_input = TextPlayerInput()
        game = GameLoop(config, player_input)

        print("=" * 60)
        print("  ROAD TO RICHES")
        print("=" * 60)
        print(f"  Board: {board_path}")
        print(f"  Players: {num_players}")
        print(f"  Target: {game.state.board.target_networth}G")
        print("=" * 60)
        print()

        winner = game.run()

        print()
        print("=" * 60)
        if winner is not None:
            print(f"  Winner: Player {winner}!")
        else:
            print("  No winner.")
        print()
        print("  Final standings:")
        ranked = sorted(
            game.state.players,
            key=lambda p: game.state.net_worth(p),
            reverse=True,
        )
        for i, p in enumerate(ranked):
            nw = game.state.net_worth(p)
            status = " (BANKRUPT)" if p.bankrupt else ""
            print(f"  {i + 1}. Player {p.player_id}: {nw}G{status}")
        print("=" * 60)


if __name__ == "__main__":
    main()
