"""Spawn a Road to Riches server and connect the human TUI client.

The server auto-spawns AI subprocesses for each AI player. This script just
orchestrates: launch the server in the background, wait for it to listen,
then run the TUI client in the foreground. When the client exits (or this
script is interrupted), the server is terminated.

All configuration is via flags — no positional args:

    python play.py
    python play.py --ai_delay=0.25
    python play.py --board=boards/large_test_board.json --humans=1 --ai=3
    python play.py --debug
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Poll until the server accepts TCP connections, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch a Road to Riches game with AI opponents.",
    )
    parser.add_argument("--board", default="boards/test_board.json",
                        help="Board file path")
    parser.add_argument("--human_players", type=int, default=1,
                        help="Number of human players (0 = AI-only watch mode)")
    parser.add_argument("--ai_players", type=int, default=3,
                        help="Number of AI players")
    parser.add_argument("--ai_delay", type=float, default=1.0,
                        help="AI response delay in seconds (default 1.0)")
    parser.add_argument("--host", default="localhost",
                        help="Server host")
    parser.add_argument("--port", type=int, default=8765,
                        help="Server port")
    parser.add_argument("--log_lines", type=int, default=None,
                        help="Max log lines kept in the TUI scrollback. "
                             "Default: unlimited (entire game).")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging on server and client")
    parser.add_argument("--server_log", default="/tmp/road_to_riches_server.log",
                        help="File to write server stdout/stderr to")
    parser.add_argument("--startup_timeout", type=float, default=5.0,
                        help="Seconds to wait for the server to start listening")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from most recent save file")
    args = parser.parse_args()

    if args.resume:
        # Load save to determine actual game parameters
        sys.path.insert(0, "src")
        from road_to_riches.save import load_save
        result = load_save()
        if result is None:
            print("No save file found.", file=sys.stderr)
            sys.exit(1)
        _, saved_config = result
        board = saved_config.board_path
        num_players = saved_config.num_players
        human_players = min(args.human_players, num_players)
        ai_players = num_players - human_players
        # Warn if user passed flags that conflict with the save
        if args.board != parser.get_default("board") and args.board != board:
            print(f"Warning: --board ignored when resuming (save uses {board})")
        if args.ai_players != parser.get_default("ai_players") and args.ai_players != ai_players:
            print(f"Warning: --ai_players ignored when resuming (save has {num_players} total players)")
    else:
        board = args.board
        human_players = args.human_players
        ai_players = args.ai_players

    if human_players + ai_players < 1:
        print("Need at least one player.", file=sys.stderr)
        sys.exit(2)

    server_cmd = [
        sys.executable, "-m", "road_to_riches.main", "server",
        board,
        "--humans", str(human_players),
        "--ai", str(ai_players),
        "--ai-delay", str(args.ai_delay),
        "--host", args.host,
        "--port", str(args.port),
    ]
    if args.debug:
        server_cmd.append("--debug")
    if args.resume:
        server_cmd.append("--resume")

    print(f"Server log: {args.server_log}")
    log_file = open(args.server_log, "w")
    server = subprocess.Popen(server_cmd, stdout=log_file, stderr=subprocess.STDOUT)

    exit_code = 0
    try:
        if not _wait_for_port(args.host, args.port, timeout=args.startup_timeout):
            print(f"Server did not start listening on {args.host}:{args.port} "
                  f"within {args.startup_timeout}s — see {args.server_log}",
                  file=sys.stderr)
            sys.exit(1)

        if args.human_players == 0:
            # AI-only run: just wait for the server to finish.
            exit_code = server.wait()
        else:
            client_cmd = [
                sys.executable, "-m", "road_to_riches.main", "client",
                "--host", args.host,
                "--port", str(args.port),
            ]
            if args.log_lines is not None:
                client_cmd += ["--log-lines", str(args.log_lines)]
            if args.debug:
                client_cmd.append("--debug")

            client = subprocess.run(client_cmd)
            exit_code = client.returncode
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server.kill()
        log_file.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
