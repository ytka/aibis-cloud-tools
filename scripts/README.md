# Scripts Directory

このディレクトリには、Aivis Cloud TTSプロジェクトの実行可能スクリプトが含まれています。

## メインスクリプト

### say.py - 音声合成メインスクリプト

高機能な音声合成スクリプト。位置引数とオプション引数をサポート。

```bash
# 基本的な使用方法（位置引数）
uv run scripts/say.py "こんにちは、世界！"

# ファイルから読み込み（-fオプション）
uv run scripts/say.py -f ../examples/sample.txt

# 詳細なオプション指定
uv run scripts/say.py "こんにちは" \
  --model e9339137-2ae3-4d41-9394-fb757a7e61e6 \
  --intensity 1.5 \
  --volume 1.0 \
  --format mp3 \
  --save-file output.mp3

# 長いテキストの分割処理（3000文字単位）
uv run scripts/say.py -f ../examples/long_text.txt --max-chars 3000

# 利用可能モデルの一覧表示
uv run scripts/say.py --list-models
```

#### 主な機能
- **位置引数**: テキストを直接指定
- **ファイル読み込み**: `-f`オプションでテキストファイルから読み込み
- **長文分割**: 3000文字単位での自動分割
- **音声保存**: 複数フォーマット対応（MP3、WAV、FLAC等）
- **リアルタイム再生**: ストリーミング対応
- **モデル選択**: 多様な音声モデルに対応

### claude_code_speaker.py - Claude応答監視スクリプト

Claude Codeの応答を監視し、自動的にAivis Cloud TTSで読み上げるスクリプト。

```bash
# uvで実行（推奨、依存関係自動管理）
uv run scripts/claude_code_speaker.py

# 基本実行
python scripts/claude_code_speaker.py

# カスタム監視ディレクトリ指定
python scripts/claude_code_speaker.py --watch-dir ~/.claude/projects

# ヘルプ表示
uv run scripts/claude_code_speaker.py --help
```

#### 主な機能
- **リアルタイム監視**: Claude Codeの応答ファイル（.jsonl）を監視
- **自動読み上げ**: 新しい応答を検出すると自動的にTTSで読み上げ
- **音声キャンセル**: 新しいイベント発生時に前の音声を自動キャンセル
- **ESCキー対応**: ESCキー押下で音声再生を即座に停止
- **長文分割**: 3000文字単位で自動分割処理
- **ログ記録**: ホームディレクトリにログファイル記録
- **クロスプラットフォーム**: Windows/macOS/Linux対応

#### 依存関係
```bash
# uvを使用する場合（推奨）- 自動的に依存関係が管理されます
uv run scripts/claude_code_speaker.py

# 手動でインストールする場合
pip install watchdog
```

#### 環境変数設定
`.env`ファイルまたはシェル環境変数で設定：

```bash
# .envファイルで設定（推奨）
CLAUDE_WATCH_DIR=~/.claude/projects
AIVIS_API_KEY=your_api_key_here

# シェル環境変数で設定
export CLAUDE_WATCH_DIR="~/.claude/projects"
export AIVIS_API_KEY="your_api_key_here"
```

### mcp_server.py - MCPサーバー

Model Context Protocol (MCP) サーバー実装。Claude Desktopと統合して音声合成機能を提供。

```bash
# MCPサーバー起動
uv run scripts/mcp_server.py

# デバッグモード（詳細ログ出力）
MCP_DEBUG=true uv run scripts/mcp_server.py
```

#### 対応ツール
- **speak**: 単一テキストまたは複数テキストの順次音声合成・再生

#### 使用例（mcp toolsとの連携）
```bash
# ツール一覧表示
mcp tools uv run --directory /path/to/project scripts/mcp_server.py

# 単一テキスト音声合成
mcp call speak --params '{"text":"こんにちは"}' uv run --directory /path/to/project scripts/mcp_server.py

# 複数テキスト順次再生
mcp call speak --params '{"speaks":[{"text":"こんにちは"},{"text":"さようなら"}]}' uv run --directory /path/to/project scripts/mcp_server.py

# パラメータ付き音声合成
mcp call speak --params '{"text":"こんにちは","emotional_intensity":1.5,"volume":0.8}' uv run --directory /path/to/project scripts/mcp_server.py
```

#### 主な機能
- **単一・複数テキスト対応**: 柔軟な入力形式
- **長文自動分割**: 3000文字単位での分割処理
- **パラメータ調整**: 感情表現・音量等の細かい制御
- **エラーハンドリング**: 詳細なエラー情報とレスポンス
- **一時ファイル管理**: 自動クリーンアップ機能

## 共通設定・環境変数

すべてのスクリプトは、プロジェクトルートの`.env`ファイルから環境変数を読み込みます：

### 必須環境変数
- `AIVIS_API_KEY`: Aivis Cloud APIキー

### オプション環境変数
- `AIVIS_DEFAULT_MODEL_UUID`: デフォルト音声モデルUUID（未指定時はAPIデフォルト）
- `CLAUDE_WATCH_DIR`: Claude Code監視ディレクトリ（claude_code_speaker.py用）

### .envファイル例
```bash
# Aivis Cloud API設定
AIVIS_API_KEY=your_api_key_here
AIVIS_DEFAULT_MODEL_UUID=e9339137-2ae3-4d41-9394-fb757a7e61e6

# Claude Code連携設定
CLAUDE_WATCH_DIR=~/.claude/projects
```

## プロジェクト構造

scripts/内のスクリプトは、以下のプロジェクト構造を前提としています：

```
aibis-cloud-tools/
├── aibis_cloud_tools/    # メインライブラリパッケージ
│   ├── tts.py           # AivisCloudTTSクラス
│   └── utils.py         # ユーティリティ関数
├── scripts/             # このディレクトリ（実行可能スクリプト）
│   ├── say.py           # メイン音声合成スクリプト
│   ├── claude_code_speaker.py # Claude応答監視
│   └── mcp_server.py    # MCPサーバー
├── tests/               # テストスイート
├── examples/            # サンプルファイル
└── .env                # 環境変数ファイル
```

## テスト・開発

### テスト実行
```bash
# 全テスト実行
python -m pytest tests/ -v

# スクリプト関連のテストのみ
python -m pytest tests/test_claude_code_speaker.py tests/test_mcp_server.py -v
```

### 開発時の依存関係管理
```bash
# uvで依存関係を自動管理
uv sync

# 新しい依存関係を追加
uv add package_name
```