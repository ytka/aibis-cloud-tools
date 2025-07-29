#!/bin/bash
# Aivis Cloud TTS ラッパー

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run "${SCRIPT_DIR}/../src/aivis-cloud-tts.py" "$@"