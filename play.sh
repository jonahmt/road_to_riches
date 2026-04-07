#!/usr/bin/env bash
# Thin wrapper around play.py — activates the venv and forwards all flags.
# All logic lives in play.py; see `./play.sh --help`.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: No virtual environment found. Run: python -m venv venv && pip install -e ."
    exit 1
fi

exec python play.py "$@"
