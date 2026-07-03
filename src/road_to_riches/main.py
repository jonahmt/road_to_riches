"""Entry point for running a Road to Riches game."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

DEFAULT_BOARD = "boards/test_board.json"
DEFAULT_PLAYERS = 4


@dataclass(frozen=True)
class ParsedRunConfig:
    mode: str
    board: str
    players: int
    humans: int
    ai: int
    ai_delay: float
    host: str
    port: int
    log_lines: int | None
    diagnostic_log: str | None
    lobby: bool
    debug: bool
    resume: str | None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Road to Riches")
    parser.add_argument(
        "mode",
        nargs="?",
        default="local",
        choices=["local", "server", "client", "text"],
        help="Run mode (default: local)",
    )
    parser.add_argument(
        "board_arg",
        nargs="?",
        help="Legacy board file path positional. Prefer --board.",
    )
    parser.add_argument(
        "players_arg",
        nargs="?",
        type=int,
        help="Legacy player count positional. Prefer --players.",
    )
    parser.add_argument(
        "--board",
        dest="board_flag",
        default=None,
        help="Board file path (local/server/text modes)",
    )
    parser.add_argument(
        "--players",
        dest="players_flag",
        type=int,
        default=None,
        help="Number of players (local/text modes)",
    )
    parser.add_argument(
        "--humans", type=int, default=1, help="Number of human players (server mode)"
    )
    parser.add_argument("--ai", type=int, default=3, help="Number of AI players (server mode)")
    parser.add_argument(
        "--ai-delay",
        type=float,
        default=1.0,
        help="AI response delay in seconds (server mode, default 1.0)",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--log-lines",
        type=int,
        default=None,
        help="Max log lines kept in the TUI (local/client mode). Default: unlimited (entire game).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and dev commands",
    )
    parser.add_argument(
        "--lobby",
        action="store_true",
        help=(
            "Run server without an automatic default game; "
            "clients create/join games over sockets."
        ),
    )
    parser.add_argument(
        "--diagnostic-log",
        default=None,
        metavar="PATH",
        help="Write append-only backend diagnostic JSONL to PATH",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="latest",
        default=None,
        metavar="SAVE",
        help="Resume from SAVE, defaulting to the most recent save",
    )
    return parser


def _resolve_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> ParsedRunConfig:
    if args.board_flag is not None and args.board_arg is not None:
        parser.error("Use either positional board or --board, not both.")
    if args.players_flag is not None and args.players_arg is not None:
        parser.error("Use either positional players or --players, not both.")

    if args.mode in {"client", "text"} and args.resume is not None:
        parser.error("--resume is only supported for local and server modes.")
    if args.lobby and args.mode != "server":
        parser.error("--lobby is only supported in server mode.")
    if args.lobby and args.resume is not None:
        parser.error("--lobby cannot be combined with --resume.")

    if args.resume is not None and (
        args.board_arg is not None
        or args.players_arg is not None
        or args.board_flag is not None
        or args.players_flag is not None
    ):
        parser.error("--resume loads the board and player count from the save file.")

    if args.mode == "client":
        if (
            args.board_arg is not None
            or args.players_arg is not None
            or args.board_flag is not None
        ):
            parser.error("client mode does not accept board or player arguments.")
        if args.players_flag is not None:
            parser.error("client mode does not accept --players.")
        if args.diagnostic_log is not None:
            parser.error("--diagnostic-log is only supported by backend modes.")

    board_arg = args.board_arg
    players_arg = args.players_arg
    if (
        args.mode in {"local", "text"}
        and args.board_flag is None
        and args.players_flag is None
        and args.players_arg is None
        and args.board_arg is not None
        and args.board_arg.isdecimal()
    ):
        players_arg = int(args.board_arg)
        board_arg = None

    board = args.board_flag or board_arg or DEFAULT_BOARD
    players = args.players_flag if args.players_flag is not None else players_arg
    if players is None:
        players = DEFAULT_PLAYERS

    return ParsedRunConfig(
        mode=args.mode,
        board=board,
        players=players,
        humans=args.humans,
        ai=args.ai,
        ai_delay=args.ai_delay,
        host=args.host,
        port=args.port,
        log_lines=args.log_lines,
        diagnostic_log=args.diagnostic_log,
        lobby=args.lobby,
        debug=args.debug,
        resume=args.resume,
    )


def parse_run_config(argv: list[str] | None = None) -> ParsedRunConfig:
    parser = _build_parser()
    return _resolve_args(parser, parser.parse_args(argv))


def main() -> None:
    args = parse_run_config()

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
            ai_delay=args.ai_delay,
            host=args.host,
            port=args.port,
            debug=args.debug,
            resume=args.resume,
            diagnostic_log_path=args.diagnostic_log,
            lobby=args.lobby,
        )

    elif args.mode == "client":
        from road_to_riches.client.tui_app import run_tui_client

        uri = f"ws://{args.host}:{args.port}"
        run_tui_client(uri=uri, log_lines=args.log_lines, debug_mode=args.debug)

    elif args.mode == "local":
        from road_to_riches.client.tui_app import run_tui

        run_tui(
            args.board,
            args.players,
            log_lines=args.log_lines,
            resume=args.resume,
            diagnostic_log_path=args.diagnostic_log,
            debug_mode=args.debug,
        )

    else:  # text
        from road_to_riches.client.text_input import TextPlayerInput
        from road_to_riches.engine.game_loop import GameConfig, GameLoop

        config = GameConfig(
            board_path=args.board,
            num_players=args.players,
            diagnostic_log_path=args.diagnostic_log,
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
