#!/bin/bash
# 長いテキストファイル用の分割読み上げスクリプト

set -e

# 色付き出力用の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 設定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# .envファイルが存在する場合は読み込み
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    source "${PROJECT_ROOT}/.env"
fi

API_KEY="${AIVIS_API_KEY:-}"
MAX_CHARS=2000  # 1回あたりの最大文字数

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
    echo -e "${BLUE}長いテキストファイル用 分割読み上げスクリプト${NC}"
    echo -e "Usage: $0 [オプション] <ファイル>"
    echo ""
    echo "オプション:"
    echo "  -h, --help                このヘルプを表示"
    echo "  -c, --chars NUM           分割単位の文字数 (デフォルト: 2000)"
    echo "  -p, --pause SECONDS       分割間の一時停止秒数 (デフォルト: 5)"
    echo "  -s, --start NUM           開始セグメント番号 (デフォルト: 1)"
    echo "  -m, --model MODEL_UUID    音声モデルのUUID"
    echo "  -i, --intensity INTENSITY 感情表現の強さ (0.0-2.0、デフォルト: 1.0)"
    echo "  -v, --volume VOLUME       音量 (0.0-2.0、デフォルト: 1.0)"
    echo "  --dry-run                 分割のみ表示（実行しない）"
    echo ""
    echo "環境変数:"
    echo "  AIVIS_API_KEY             Aivis Cloud APIキー"
    echo ""
    echo "使用例:"
    echo "  $0 long_document.txt"
    echo "  $0 -c 1500 -p 2 article.txt"
    echo "  $0 -s 3 tmp/1.txt                   # 3番目のセグメントから開始"
    echo "  $0 -m model-uuid -i 1.5 -v 0.8 article.txt  # モデルと音声設定指定"
    echo "  $0 --dry-run tmp/1.txt"
}

# テキストを分割
split_text() {
    local file="$1"
    local max_chars="$2"
    local temp_dir=$(mktemp -d)
    
    log_info "テキストを${max_chars}文字ずつに分割中..."
    
    # Pythonで分割処理
    python3 << EOF
import sys
import re

def split_text_smartly(text, max_chars):
    # 段落で分割を試みる
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # 段落が長すぎる場合は文単位で分割
        if len(paragraph) > max_chars:
            sentences = re.split(r'[。！？]\s*', paragraph)
            for sentence in sentences:
                if not sentence.strip():
                    continue
                sentence = sentence.strip() + '。'
                
                if len(current_chunk) + len(sentence) > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = ""
                    
                    # 文が長すぎる場合は強制分割
                    if len(sentence) > max_chars:
                        for i in range(0, len(sentence), max_chars):
                            chunks.append(sentence[i:i+max_chars])
                    else:
                        current_chunk = sentence
                else:
                    current_chunk += sentence
        else:
            if len(current_chunk) + len(paragraph) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
            current_chunk += paragraph + "\n\n"
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

# ファイル読み込み
with open('$file', 'r', encoding='utf-8') as f:
    text = f.read()

# 分割
chunks = split_text_smartly(text, $max_chars)

# 一時ファイルに保存
for i, chunk in enumerate(chunks, 1):
    with open(f'$temp_dir/chunk_{i:03d}.txt', 'w', encoding='utf-8') as f:
        f.write(chunk)

print(f'{len(chunks)}')
EOF
    
    echo "$temp_dir"
}

# 分割読み上げ実行
execute_split_tts() {
    local file="$1"
    local max_chars="$2"
    local pause_seconds="$3"
    local start_segment="$4"
    local model_uuid="$5"
    local intensity="$6"
    local volume="$7"
    local dry_run="$8"
    
    # APIキーチェック
    if [[ -z "$API_KEY" ]] && [[ "$dry_run" != true ]]; then
        log_error "AIVIS_API_KEY 環境変数が設定されていません"
        exit 1
    fi
    
    # ファイル存在確認
    if [[ ! -f "$file" ]]; then
        log_error "ファイルが見つかりません: $file"
        exit 1
    fi
    
    # ファイル情報
    local total_chars=$(wc -c < "$file")
    log_info "ファイル: $file"
    log_info "総文字数: $total_chars"
    log_info "分割単位: $max_chars 文字"
    
    # テキスト分割
    local temp_dir_result=$(split_text "$file" "$max_chars")
    local temp_dir=$(echo "$temp_dir_result" | tail -1)
    local chunk_count=$(echo "$temp_dir_result" | head -1)
    
    log_info "分割数: $chunk_count"
    log_info "開始セグメント: $start_segment"
    
    # 開始セグメント番号の妥当性チェック
    if [[ $start_segment -lt 1 ]] || [[ $start_segment -gt $chunk_count ]]; then
        log_error "開始セグメント番号が無効です: $start_segment (有効範囲: 1-$chunk_count)"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    if [[ "$dry_run" == true ]]; then
        log_info "=== DRY RUN: 分割結果 ==="
        for i in $(seq 1 $chunk_count); do
            local chunk_file="$temp_dir/chunk_$(printf '%03d' $i).txt"
            local chunk_size=$(wc -c < "$chunk_file")
            local status_marker=""
            [[ $i -ge $start_segment ]] && status_marker=" [実行対象]"
            echo "[$i/$chunk_count] $chunk_size 文字$status_marker"
            echo "内容: $(head -c 100 "$chunk_file")..."
            echo ""
        done
        rm -rf "$temp_dir"
        return 0
    fi
    
    # 実際の読み上げ
    log_info "読み上げを開始します（セグメント $start_segment から $chunk_count まで）..."
    local success_count=0
    local total_segments=$((chunk_count - start_segment + 1))
    
    for i in $(seq $start_segment $chunk_count); do
        local chunk_file="$temp_dir/chunk_$(printf '%03d' $i).txt"
        local chunk_size=$(wc -c < "$chunk_file")
        
        log_info "[$i/$chunk_count] $chunk_size 文字を読み上げ中..."
        
        # リトライ機能付きで実行
        local retry_success=false
        local max_chunk_retries=3
        local chunk_retry_count=0
        
        # speak.shへのオプション構築
        local speak_args=("$chunk_file")
        
        # モデル指定: コマンドライン > 環境変数の優先順位
        local effective_model=""
        if [[ -n "$model_uuid" ]]; then
            effective_model="$model_uuid"
        elif [[ -n "${AIVIS_DEFAULT_MODEL_UUID:-}" ]]; then
            effective_model="${AIVIS_DEFAULT_MODEL_UUID}"
        fi
        [[ -n "$effective_model" ]] && speak_args+=(-m "$effective_model")
        
        [[ "$intensity" != "1.0" ]] && speak_args+=(-i "$intensity")
        [[ "$volume" != "1.0" ]] && speak_args+=(-v "$volume")
        
        while [[ $chunk_retry_count -lt $max_chunk_retries ]] && [[ "$retry_success" == false ]]; do
            if AIVIS_API_KEY="$API_KEY" "${SCRIPT_DIR}/speak.sh" "${speak_args[@]}"; then
                ((success_count++))
                log_success "[$i/$chunk_count] 完了"
                retry_success=true
            else
                ((chunk_retry_count++))
                if [[ $chunk_retry_count -lt $max_chunk_retries ]]; then
                    local chunk_delay=$((2 * chunk_retry_count))
                    log_warning "[$i/$chunk_count] 失敗。${chunk_delay}秒後にリトライします... (${chunk_retry_count}/${max_chunk_retries})"
                    sleep "$chunk_delay"
                else
                    log_error "[$i/$chunk_count] 最大リトライ回数に達しました"
                fi
            fi
        done
        
        # 最後でなければ一時停止
        if [[ $i -lt $chunk_count ]] && [[ $pause_seconds -gt 0 ]]; then
            log_info "${pause_seconds}秒間一時停止..."
            sleep "$pause_seconds"
        fi
    done
    
    # クリーンアップ
    rm -rf "$temp_dir"
    
    # 結果表示
    log_success "完了: $success_count/$total_segments セグメント（全体の $success_count/$chunk_count）"
    if [[ $success_count -eq $total_segments ]]; then
        log_success "指定された範囲の全セグメントが正常に読み上げられました"
    else
        log_warning "一部のセグメントで失敗が発生しました"
    fi
}

# メイン実行
main() {
    local file=""
    local max_chars=$MAX_CHARS
    local pause_seconds=5
    local start_segment=1
    local model_uuid=""
    local intensity="1.0"
    local volume="1.0"
    local dry_run=false
    
    # 引数解析
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -c|--chars)
                max_chars="$2"
                shift 2
                ;;
            -p|--pause)
                pause_seconds="$2"
                shift 2
                ;;
            -s|--start)
                start_segment="$2"
                shift 2
                ;;
            -m|--model)
                model_uuid="$2"
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
            --dry-run)
                dry_run=true
                shift
                ;;
            -*)
                log_error "不明なオプション: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$file" ]]; then
                    file="$1"
                else
                    log_error "複数のファイルが指定されました"
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # ファイル指定確認
    if [[ -z "$file" ]]; then
        log_error "ファイルを指定してください"
        show_help
        exit 1
    fi
    
    # 開始セグメント番号の妥当性チェック（基本的な数値チェック）
    if ! [[ "$start_segment" =~ ^[1-9][0-9]*$ ]]; then
        log_error "開始セグメント番号は正の整数である必要があります: $start_segment"
        exit 1
    fi
    
    # 実行
    execute_split_tts "$file" "$max_chars" "$pause_seconds" "$start_segment" "$model_uuid" "$intensity" "$volume" "$dry_run"
}

# スクリプト実行
main "$@"