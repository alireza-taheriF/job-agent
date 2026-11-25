#!/usr/bin/env bash
# Run the bot + scheduler from the project venv.
cd "$(dirname "$0")"
exec .venv/bin/python main.py "$@"
