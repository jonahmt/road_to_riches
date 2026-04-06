"""Entry point for running a Road to Riches game."""

from __future__ import annotations

import argparse
import logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Road to Riches")
    parser.add_argument(
        "mode",
        nargs="?",
        default="local",
        choices=["local", "server", "client", "text"],
        help="Run mode (default: local)",
    )
    parser.add_argument(
        "board", nargs="?", default="boards/test_board.json", help="Board file path",
    )
    parser.add_argument("players", nargs="?", type=int, default=4,
                        help="Number of players (local/text mode)")
    parser.add_argument("--humans", type=int, default=1,
                        help="Number of human players (server mode)")
    parser.add_argument("--ai", type=int, default=3,
                        help="Number of AI players (server mode)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(name)s] %(levelname)s %(message)s",
        )

    if args.mode == "server":
        from road_to_riches.server.server import run_server

        run_server(
            board_path=args.board,
            num_humans=args.humans,
            num_ai=args.ai,
            host=args.host,
            port=args.port,
            debug=args.debug,
        )

    elif args.mode == "client":
        from road_to_riches.client.tui_app import run_tui_client

        uri = f"ws://{args.host}:{args.port}"
        run_tui_client(uri=uri)

    elif args.mode == "local":
        from road_to_riches.client.tui_app import run_tui

        run_tui(args.board, args.players)

    else:  # text
        from road_to_riches.client.text_input import TextPlayerInput
        from road_to_riches.engine.game_loop import GameConfig, GameLoop

        config = GameConfig(
            board_path=args.board,
            num_players=args.players,
            starting_cash=1500,
        )
        player_input = TextPlayerInput()
        game = GameLoop(config, player_input)

        print("=" * 60)
        print("  ROAD TO RICHES")
        print("=" * 60)
        print(f"  Board: {args.board}")
        print(f"  Players: {args.players}")
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
