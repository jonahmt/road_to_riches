"""Entry point for running a Road to Riches game."""

from __future__ import annotations

import sys

from road_to_riches.client.text_input import TextPlayerInput
from road_to_riches.engine.game_loop import GameConfig, GameLoop


def main() -> None:
    board_path = sys.argv[1] if len(sys.argv) > 1 else "boards/test_board.json"
    num_players = int(sys.argv[2]) if len(sys.argv) > 2 else 4

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
