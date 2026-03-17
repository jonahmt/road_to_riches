#!/usr/bin/env bash
# Launch Road to Riches
#
# Usage:
#   ./play.sh                              # Local TUI, test board, 2 players
#   ./play.sh local boards/big.json 4      # Custom board, 4 players
#   ./play.sh server                       # Start WebSocket game server
#   ./play.sh client                       # Connect TUI to running server
#   ./play.sh server --port 9000 --debug   # Custom port with debug logging
#   ./play.sh text                         # Text mode (stdin/stdout)

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

exec python -m road_to_riches.main "$@"
