#!/usr/bin/env bash
# Launch Road to Riches
#
# Usage:
#   ./play.sh                     # TUI, solo board, 1 player
#   ./play.sh --text              # Text mode (stdin/stdout)
#   ./play.sh boards/test_board.json 4   # Custom board, 4 players
#   ./play.sh --text boards/solo_board.json 1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: No virtual environment found. Run: python -m venv venv && pip install -e ."
    exit 1
fi

# Defaults
MODE=""
BOARD="boards/solo_board.json"
PLAYERS="1"

# Parse args
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--text" ] || [ "$arg" = "--tui" ]; then
        MODE="$arg"
    else
        ARGS+=("$arg")
    fi
done

if [ ${#ARGS[@]} -ge 1 ]; then
    BOARD="${ARGS[0]}"
fi
if [ ${#ARGS[@]} -ge 2 ]; then
    PLAYERS="${ARGS[1]}"
fi

echo "═══════════════════════════════════════"
echo "  ROAD TO RICHES"
echo "  Board:   $BOARD"
echo "  Players: $PLAYERS"
echo "  Mode:    ${MODE:---tui}"
echo "═══════════════════════════════════════"
echo ""

exec python -m road_to_riches.main $MODE "$BOARD" "$PLAYERS"
