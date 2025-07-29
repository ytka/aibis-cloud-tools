#!/bin/bash
# デバッグ用の読み上げスクリプト

set -e
set -x  # デバッグモード有効

# 設定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TTS_SCRIPT="${PROJECT_ROOT}/src/aivis-cloud-tts.py"

# .envファイルが存在する場合は読み込み
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    source "${PROJECT_ROOT}/.env"
fi

API_KEY="${AIVIS_API_KEY:-}"

echo "=== デバッグ情報 ==="
echo "SCRIPT_DIR: ${SCRIPT_DIR}"
echo "TTS_SCRIPT: ${TTS_SCRIPT}"
echo "API_KEY: ${API_KEY:0:20}... (先頭20文字)"
echo "引数: $@"
echo "==================="

# ファイル存在確認
if [[ ! -f "$1" ]]; then
    echo "エラー: ファイルが存在しません: $1"
    exit 1
fi

echo "ファイル情報:"
ls -la "$1"
echo "ファイル内容:"
cat "$1"
echo "文字数: $(wc -c < "$1")"
echo "==================="

# TTS コマンド実行
# デフォルトモデルがあれば使用
MODEL_ARGS=""
if [[ -n "${AIVIS_DEFAULT_MODEL_UUID:-}" ]]; then
    MODEL_ARGS="--model-uuid ${AIVIS_DEFAULT_MODEL_UUID}"
    echo "使用モデル: ${AIVIS_DEFAULT_MODEL_UUID}"
fi

if command -v uv &> /dev/null && [[ -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
    echo "UV環境で実行"
    AIVIS_API_KEY="$API_KEY" uv run --directory "${PROJECT_ROOT}" src/aivis-cloud-tts.py --text-file "$1" $MODEL_ARGS
else
    echo "直接Python実行"
    AIVIS_API_KEY="$API_KEY" python3 "${TTS_SCRIPT}" --text-file "$1" $MODEL_ARGS
fi