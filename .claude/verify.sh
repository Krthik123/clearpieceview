#!/usr/bin/env bash
# One command to verify this project. Used by hooks, CI and people.
cd "$(dirname "$0")/.." && exec python3 .harness/harness.py check --full
