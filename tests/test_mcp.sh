#!/bin/bash
# MCP CLI動作確認用テストスクリプト

set -e  # エラー時に停止

# 色付き出力用の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 設定
PROJECT_DIR="/Users/yutaka/source/aibis-coutd-api"
MCP_SERVER_CMD="/opt/homebrew/bin/uv run --directory ${PROJECT_DIR} run_mcp_server.py"
API_KEY="${AIVIS_API_KEY:-aivis_u1DFvX2IDbKh6UH6fDdKg5YEDKkZd8RY}"

# ヘルプ表示
show_help() {
    echo -e "${BLUE}MCP CLI テストスクリプト${NC}"
    echo -e "使用方法: $0 [オプション]"
    echo ""
    echo "オプション:"
    echo "  -h, --help     このヘルプを表示"
    echo "  --tools        ツール一覧のみテスト"
    echo "  --single       単一テキストのみテスト"
    echo "  --multi        複数テキストのみテスト"
    echo "  --all          全テストを実行（デフォルト）"
    echo ""
    echo "環境変数:"
    echo "  AIVIS_API_KEY  Aivis Cloud APIキー"
}

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# テスト実行関数
run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    log_info "テスト実行: ${test_name}"
    echo "コマンド: ${test_cmd}"
    echo "----------------------------------------"
    
    if eval "AIVIS_API_KEY=\"${API_KEY}\" timeout 30s ${test_cmd}"; then
        log_success "${test_name} - 成功"
        return 0
    else
        local exit_code=$?
        if [ $exit_code -eq 124 ]; then
            log_error "${test_name} - タイムアウト (30秒)"
        else
            log_error "${test_name} - 失敗 (終了コード: ${exit_code})"
        fi
        return $exit_code
    fi
}

# 1. ツール一覧テスト
test_tools_list() {
    log_info "=== ツール一覧テスト ==="
    run_test "mcp tools" "mcp tools ${MCP_SERVER_CMD}"
    echo ""
}

# 2. 単一テキスト音声合成テスト
test_single_text() {
    log_info "=== 単一テキスト音声合成テスト ==="
    
    # 基本テスト
    run_test "基本の単一テキスト" \
        "mcp call speak --params '{\"text\":\"こんにちは、MCPテストです\"}' ${MCP_SERVER_CMD}"
    echo ""
    
    # パラメータ付きテスト
    run_test "パラメータ付き単一テキスト" \
        "mcp call speak --params '{\"text\":\"感情豊かに話します\",\"emotional_intensity\":1.5,\"volume\":1.2}' ${MCP_SERVER_CMD}"
    echo ""
}

# 3. 複数テキスト音声合成テスト
test_multiple_texts() {
    log_info "=== 複数テキスト音声合成テスト ==="
    
    # 2つのテキスト
    run_test "2つのテキスト" \
        "mcp call speak --params '{\"speaks\":[{\"text\":\"最初のメッセージです\"},{\"text\":\"二番目のメッセージです\"}]}' ${MCP_SERVER_CMD}"
    echo ""
    
    # 異なるパラメータで3つのテキスト
    run_test "異なるパラメータで3つのテキスト" \
        "mcp call speak --params '{\"speaks\":[{\"text\":\"普通に話します\",\"emotional_intensity\":1.0},{\"text\":\"感情豊かに話します\",\"emotional_intensity\":1.8},{\"text\":\"静かに話します\",\"emotional_intensity\":0.8,\"volume\":0.7}]}' ${MCP_SERVER_CMD}"
    echo ""
    
    # 多数のテキスト（5つ）
    run_test "5つのテキスト" \
        "mcp call speak --params '{\"speaks\":[{\"text\":\"1番目\"},{\"text\":\"2番目\"},{\"text\":\"3番目\"},{\"text\":\"4番目\"},{\"text\":\"5番目\"}]}' ${MCP_SERVER_CMD}"
    echo ""
}

# 4. エラーケーステスト
test_error_cases() {
    log_info "=== エラーケーステスト ==="
    
    # 空のテキスト
    log_info "空のテキストテスト（エラーが期待される）"
    if AIVIS_API_KEY="${API_KEY}" timeout 10s mcp call speak --params '{"text":""}' ${MCP_SERVER_CMD} 2>/dev/null; then
        log_warning "空のテキストでもエラーにならなかった"
    else
        log_success "空のテキストで適切にエラーになった"
    fi
    echo ""
    
    # パラメータなし
    log_info "パラメータなしテスト（エラーが期待される）"
    if AIVIS_API_KEY="${API_KEY}" timeout 10s mcp call speak --params '{}' ${MCP_SERVER_CMD} 2>/dev/null; then
        log_warning "パラメータなしでもエラーにならなかった"
    else
        log_success "パラメータなしで適切にエラーになった"
    fi
    echo ""
}

# 5. 性能テスト
test_performance() {
    log_info "=== 性能テスト ==="
    
    log_info "短いテキストの処理時間測定"
    time AIVIS_API_KEY="${API_KEY}" mcp call speak --params '{"text":"短いテスト"}' ${MCP_SERVER_CMD} > /dev/null 2>&1 || true
    echo ""
    
    log_info "長いテキストの処理時間測定"
    local long_text="これは長いテキストのテストです。音声合成システムが長いテキストをどのように処理するかを確認しています。複数の文が含まれており、全体的な処理時間を測定することで性能を評価します。"
    time AIVIS_API_KEY="${API_KEY}" mcp call speak --params "{\"text\":\"${long_text}\"}" ${MCP_SERVER_CMD} > /dev/null 2>&1 || true
    echo ""
}

# メイン実行
main() {
    local run_tools=false
    local run_single=false
    local run_multi=false
    local run_all=true
    
    # 引数解析
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --tools)
                run_tools=true
                run_all=false
                ;;
            --single)
                run_single=true
                run_all=false
                ;;
            --multi)
                run_multi=true
                run_all=false
                ;;
            --all)
                run_all=true
                ;;
            *)
                log_error "不明なオプション: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done
    
    # 開始メッセージ
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  MCP CLI テストスクリプト${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    
    # 環境チェック
    log_info "環境チェック"
    echo "プロジェクトディレクトリ: ${PROJECT_DIR}"
    echo "MCPサーバーコマンド: ${MCP_SERVER_CMD}"
    echo "APIキー: ${API_KEY:0:20}... (先頭20文字)"
    echo ""
    
    # uv コマンドの存在確認
    if ! command -v /opt/homebrew/bin/uv &> /dev/null; then
        log_error "uv コマンドが見つかりません: /opt/homebrew/bin/uv"
        exit 1
    fi
    
    # mcp コマンドの存在確認とバージョン確認
    if ! command -v mcp &> /dev/null; then
        log_error "mcp コマンドが見つかりません"
        exit 1
    fi
    
    # MCPのバージョンとhelpを表示
    log_info "MCP バージョン情報:"
    mcp version || true
    echo "MCP パス: $(which mcp)"
    echo ""
    
    # テスト実行
    local failed_tests=0
    
    if [[ "$run_all" == true ]] || [[ "$run_tools" == true ]]; then
        test_tools_list || ((failed_tests++))
    fi
    
    if [[ "$run_all" == true ]] || [[ "$run_single" == true ]]; then
        test_single_text || ((failed_tests++))
    fi
    
    if [[ "$run_all" == true ]] || [[ "$run_multi" == true ]]; then
        test_multiple_texts || ((failed_tests++))
    fi
    
    if [[ "$run_all" == true ]]; then
        test_error_cases || ((failed_tests++))
        test_performance || ((failed_tests++))
    fi
    
    # 結果サマリー
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  テスト結果${NC}"
    echo -e "${BLUE}================================${NC}"
    
    if [[ $failed_tests -eq 0 ]]; then
        log_success "全てのテストが成功しました！"
        exit 0
    else
        log_error "${failed_tests} 個のテストが失敗しました"
        exit 1
    fi
}

# スクリプト実行
main "$@"