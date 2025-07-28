#!/bin/bash
# Aivis Cloud TTS 簡単読み上げスクリプト

set -e

# 色付き出力用の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 設定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TTS_SCRIPT="${SCRIPT_DIR}/aivis-cloud-tts.py"

# .envファイルが存在する場合は読み込み
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    source "${SCRIPT_DIR}/.env"
fi

API_KEY="${AIVIS_API_KEY:-}"

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

# ヘルプ表示
show_help() {
    echo -e "${BLUE}Aivis Cloud TTS 簡単読み上げスクリプト${NC}"
    echo -e "Usage: $0 [オプション] <テキストまたはファイル>"
    echo ""
    echo "基本的な使用方法:"
    echo "  $0 \"こんにちは\"                    # テキストを直接読み上げ"
    echo "  $0 example.txt                      # ファイルを読み上げ"
    echo "  $0 -f example.txt                   # -f オプションでファイル指定"
    echo ""
    echo "オプション:"
    echo "  -h, --help                          このヘルプを表示"
    echo "  -f, --file                          入力をファイルとして扱う"
    echo "  -s, --save FILE                     音声ファイルを保存"
    echo "  -r, --rate RATE                     話速 (0.5-2.0、デフォルト: 1.0)"
    echo "  -i, --intensity INTENSITY           感情表現の強さ (0.0-2.0、デフォルト: 1.0)"
    echo "  -v, --volume VOLUME                 音量 (0.0-2.0、デフォルト: 1.0)"
    echo "  -m, --model MODEL_UUID              音声モデルのUUID"
    echo "  --format FORMAT                     出力フォーマット (wav|mp3|flac|aac|opus)"
    echo "  --no-play                           再生せずに保存のみ"
    echo "  --list-models                       利用可能なモデル一覧を表示"
    echo "  --realtime                          リアルタイムストリーミング再生"
    echo ""
    echo "環境変数:"
    echo "  AIVIS_API_KEY                       Aivis Cloud APIキー"
    echo ""
    echo "使用例:"
    echo "  $0 \"今日は良い天気ですね\""
    echo "  $0 -f README.md -s output.mp3"
    echo "  $0 \"こんにちは\" -r 1.2 -i 1.5 -v 0.8"
    echo "  $0 --list-models"
}

# パラメータ解析
parse_args() {
    local text=""
    local is_file=false
    local save_file=""
    local rate="1.0"
    local intensity="1.0"
    local volume="1.0"
    local model_uuid=""
    local format="mp3"
    local no_play=false
    local list_models=false
    local realtime=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -f|--file)
                is_file=true
                shift
                ;;
            -s|--save)
                save_file="$2"
                shift 2
                ;;
            -r|--rate)
                rate="$2"
                shift 2
                ;;
            -i|--intensity)
                intensity="$2"
                shift 2
                ;;
            -v|--volume)
                volume="$2"
                shift 2
                ;;
            -m|--model)
                model_uuid="$2"
                shift 2
                ;;
            --format)
                format="$2"
                shift 2
                ;;
            --no-play)
                no_play=true
                shift
                ;;
            --list-models)
                list_models=true
                shift
                ;;
            --realtime)
                realtime=true
                shift
                ;;
            -*)
                log_error "不明なオプション: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$text" ]]; then
                    text="$1"
                else
                    log_error "複数のテキスト/ファイルが指定されました"
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # モデル一覧表示
    if [[ "$list_models" == true ]]; then
        run_tts_command --list-models
        exit 0
    fi
    
    # テキストまたはファイルの確認
    if [[ -z "$text" ]]; then
        log_error "テキストまたはファイルを指定してください"
        show_help
        exit 1
    fi
    
    # ファイル存在確認（ファイルモードまたは.で始まらないファイル名）
    if [[ "$is_file" == true ]] || [[ -f "$text" && "$text" != .* ]]; then
        if [[ ! -f "$text" ]]; then
            log_error "ファイルが見つかりません: $text"
            exit 1
        fi
        is_file=true
    fi
    
    # TTS実行
    execute_tts "$text" "$is_file" "$save_file" "$rate" "$intensity" "$volume" "$model_uuid" "$format" "$no_play" "$realtime"
}

# TTS コマンド実行（リトライ機能付き）
run_tts_command_with_retry() {
    local max_retries=3
    local base_delay=2
    local retry_count=0
    
    while [[ $retry_count -lt $max_retries ]]; do
        local exit_code
        local temp_output=$(mktemp)
        local temp_error=$(mktemp)
        
        # TTS実行
        if command -v uv &> /dev/null && [[ -f "${SCRIPT_DIR}/pyproject.toml" ]]; then
            # UV環境で実行
            AIVIS_API_KEY="$API_KEY" uv run --directory "${SCRIPT_DIR}" aivis-cloud-tts.py "$@" > "$temp_output" 2> "$temp_error"
            exit_code=$?
        else
            # 直接実行
            AIVIS_API_KEY="$API_KEY" python3 "${TTS_SCRIPT}" "$@" > "$temp_output" 2> "$temp_error"
            exit_code=$?
        fi
        
        # 成功時
        if [[ $exit_code -eq 0 ]]; then
            cat "$temp_output"
            rm -f "$temp_output" "$temp_error"
            return 0
        fi
        
        # エラー内容確認
        local error_content=$(cat "$temp_error")
        
        # 429エラー（Rate Limit）チェック
        if echo "$error_content" | grep -q "HTTP 429\|Too Many Requests\|Rate limit"; then
            ((retry_count++))
            if [[ $retry_count -lt $max_retries ]]; then
                local delay=$((base_delay * retry_count))
                log_warning "レート制限に達しました。${delay}秒後にリトライします... (${retry_count}/${max_retries})"
                sleep "$delay"
                rm -f "$temp_output" "$temp_error"
                continue
            else
                log_error "レート制限により最大リトライ回数に達しました"
            fi
        fi
        
        # その他のエラー
        cat "$temp_error" >&2
        rm -f "$temp_output" "$temp_error"
        return $exit_code
    done
    
    return 1
}

# TTS コマンド実行（後方互換用）
run_tts_command() {
    if command -v uv &> /dev/null && [[ -f "${SCRIPT_DIR}/pyproject.toml" ]]; then
        # UV環境で実行
        uv run --directory "${SCRIPT_DIR}" aivis-cloud-tts.py "$@"
    else
        # 直接実行
        python3 "${TTS_SCRIPT}" "$@"
    fi
}

# TTS実行
execute_tts() {
    local text="$1"
    local is_file="$2"
    local save_file="$3"
    local rate="$4"
    local intensity="$5"
    local volume="$6"
    local model_uuid="$7"
    local format="$8"
    local no_play="$9"
    local realtime="${10}"
    
    # APIキーチェック
    if [[ -z "$API_KEY" ]]; then
        log_error "AIVIS_API_KEY 環境変数が設定されていません"
        echo "以下のように設定してください:"
        echo "export AIVIS_API_KEY=\"your_api_key_here\""
        exit 1
    fi
    
    # コマンド構築
    local cmd_args=()
    
    if [[ "$is_file" == true ]]; then
        cmd_args+=(--text-file "$text")
        log_info "ファイルを読み上げ: $text"
    else
        cmd_args+=(--text "$text")
        log_info "テキストを読み上げ: $text"
    fi
    
    # オプション追加
    [[ -n "$save_file" ]] && cmd_args+=(--save-file "$save_file")
    [[ "$rate" != "1.0" ]] && cmd_args+=(--rate "$rate")
    [[ "$intensity" != "1.0" ]] && cmd_args+=(--intensity "$intensity")
    [[ "$volume" != "1.0" ]] && cmd_args+=(--volume "$volume")
    [[ -n "$model_uuid" ]] && cmd_args+=(--model-uuid "$model_uuid")
    [[ "$format" != "mp3" ]] && cmd_args+=(--format "$format")
    [[ "$no_play" == true ]] && cmd_args+=(--no-play)
    [[ "$realtime" == true ]] && cmd_args+=(--realtime)
    
    # APIキー設定して実行（リトライ機能付き）
    log_info "音声合成を開始..."
    if run_tts_command_with_retry "${cmd_args[@]}"; then
        log_success "完了しました"
        [[ -n "$save_file" ]] && log_success "音声ファイルを保存: $save_file"
    else
        log_error "音声合成に失敗しました"
        exit 1
    fi
}

# メイン実行
main() {
    # 引数がない場合はヘルプを表示
    if [[ $# -eq 0 ]]; then
        show_help
        exit 1
    fi
    
    # TTSスクリプトの存在確認
    if [[ ! -f "$TTS_SCRIPT" ]]; then
        log_error "TTSスクリプトが見つかりません: $TTS_SCRIPT"
        exit 1
    fi
    
    # 引数解析と実行
    parse_args "$@"
}

# スクリプト実行
main "$@"