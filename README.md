# Aivis Cloud TTS Script

Aivis Cloud API を使用した音声合成・再生スクリプトです。uvパッケージマネージャーを使用して依存関係を自動管理し、Claude Desktopとの統合もサポートしています。

## 機能

- **音声合成**: テキストまたはテキストファイルから音声を生成
- **音声再生**: 生成した音声の自動再生（macOS/Linux/Windows対応）
- **ファイル保存**: 複数の音声フォーマットでの保存
- **モデル検索**: 利用可能な音声合成モデルの一覧表示
- **パラメータ調整**: 話速、感情表現、音量などの細かい制御
- **Model Context Protocol**: Claude Desktopとの統合対応

## 必要な環境

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー
- [Aivis Cloud API](https://aivis-project.com/cloud-api/) のAPIキー

## Aivis Cloud API について

**Aivis Cloud API** は、日本語に特化した高品質な音声合成APIサービスです。

### 特徴
- **高品質な日本語音声合成**: 自然で聞き取りやすい音声生成
- **多様な音声モデル**: 様々なキャラクターや話者の音声に対応
- **リアルタイム配信対応**: ストリーミング再生で低遅延を実現
- **豊富なパラメータ調整**: 話速、感情表現、音量などの細かな制御
- **複数フォーマット対応**: WAV、MP3、FLAC、AAC、Opusに対応

### サービス詳細
- **公式サイト**: [https://aivis-project.com/cloud-api/](https://aivis-project.com/cloud-api/)
- **API ドキュメント**: [https://api.aivis-project.com/v1/docs](https://api.aivis-project.com/v1/docs)
- **APIキー取得**: [https://hub.aivis-project.com/cloud-api/api-keys](https://hub.aivis-project.com/cloud-api/api-keys)
- **ダッシュボード**: [https://hub.aivis-project.com/](https://hub.aivis-project.com/)

詳しい音声サンプルや料金については、[公式サイト](https://aivis-project.com/cloud-api/)をご確認ください。

## セットアップ

### 1. uv のインストール

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. APIキーの設定

[Aivis Cloud API ダッシュボード](https://hub.aivis-project.com/cloud-api/api-keys) からAPIキーを取得し、以下のいずれかの方法で設定：

#### 方法1: .envファイルを使用（推奨）

```bash
# .env.example をコピーして .env ファイルを作成
cp .env.example .env

# .env ファイルでAPIキーを設定
echo "AIVIS_API_KEY=your_api_key_here" > .env
```

#### 方法2: 環境変数で設定

```bash
export AIVIS_API_KEY="your_api_key_here"
```

**注意**: `.env` ファイルは Git に含まれません（`.gitignore` で除外）。APIキーを安全に管理できます。

### 3. デフォルト音声モデルの設定（オプション）

`.env` ファイルでデフォルト音声モデルを指定できます：

```bash
# よく使うモデルを設定しておくと、毎回 -m オプションで指定する必要がありません
AIVIS_DEFAULT_MODEL_UUID=e9339137-2ae3-4d41-9394-fb757a7e61e6
```

**優先順位**: コマンドライン指定 > 環境変数 > APIデフォルト

## 使用方法

### say.py - メインTTSスクリプト

```bash
# テキストから音声合成（位置引数）
uv run scripts/say.py "こんにちは、世界！"

# テキストファイルから音声合成（-fオプション）
uv run scripts/say.py -f examples/sample.txt

# 音声ファイルとして保存
uv run scripts/say.py "こんにちは" --save-file output.mp3

# リアルタイムストリーミング再生
uv run scripts/say.py -f examples/sample.txt --realtime

# パラメータ調整
uv run scripts/say.py "感情豊かに話します" \
  --rate 1.2 \
  --intensity 1.5 \
  --volume 1.0 \
  --format mp3

# モデル一覧表示
uv run scripts/say.py --list-models

# 長いテキストの分割処理（3000文字単位）
uv run scripts/say.py -f examples/long_text.txt --max-chars 3000
```

### claude_code_speaker.py - Claude応答監視

Claude Codeの応答を自動監視・読み上げするスクリプト：

```bash
# uvで実行（推奨）
uv run scripts/claude_code_speaker.py

# 手動で依存関係をインストールして実行
pip install watchdog
python scripts/claude_code_speaker.py

# カスタム設定で実行
python scripts/claude_code_speaker.py --watch-dir ~/.claude/projects

# ヘルプ表示
uv run scripts/claude_code_speaker.py --help
```

### Claude Code応答監視

Claude Codeの応答を自動的に検出して読み上げる機能：

```bash
# uvで実行（推奨、依存関係自動管理）
uv run scripts/claude-code-speaker.py

# 手動で依存関係をインストールして実行
pip install watchdog
python scripts/claude-code-speaker.py

# 詳細なオプション
uv run scripts/claude-code-speaker.py --help
```

**機能**:
- Claude Codeの応答ファイル（.jsonl）をリアルタイム監視
- 新しい応答を検出すると自動的にAivis Cloud TTSで読み上げ
- ログファイル記録とmacOSシステム通知
- TTSスクリプトの自動検出
- 環境変数による設定（`.env`ファイル対応）

**環境変数**:
- `CLAUDE_WATCH_DIR`: Claude Codeの監視ディレクトリ

### mcp_server.py - MCPサーバー

```bash
# MCPサーバー起動
uv run scripts/mcp_server.py

# デバッグモード（詳細ログ出力）
MCP_DEBUG=true uv run scripts/mcp_server.py
```

### mcp tools との連携

```bash
# ツール一覧表示
mcp tools uv run --directory /path/to/project scripts/mcp_server.py

# 音声合成実行（単一テキスト）
mcp call speak --params '{"text":"こんにちは"}' uv run --directory /path/to/project scripts/mcp_server.py

# 音声合成実行（複数テキスト）
mcp call speak --params '{"speaks":[{"text":"こんにちは"},{"text":"さようなら"}]}' uv run --directory /path/to/project scripts/mcp_server.py
```

## MCPサーバーのパラメータ

### `speak` コマンド

- `text` (必須): 合成するテキスト
- `model_uuid` (オプション): 音声合成モデルのUUID
- `emotional_intensity` (オプション): 感情表現の強さ (0.0-2.0、デフォルト: 1.0)
- `volume` (オプション): 音量 (0.0-2.0、デフォルト: 1.0)
- `async_mode` (オプション): 非同期モード (true/false、デフォルト: false)

## Claude Desktop への組み込み

### 1. 設定ファイルを開く

```bash
# macOS
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows
notepad %APPDATA%\Claude\claude_desktop_config.json
```

### 2. MCP サーバー設定を追加

```json
{
  "mcpServers": {
    "aivis-tts": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "run",
        "--directory",
        "/path/to/your/project/directory",
        "scripts/mcp_server.py"
      ],
      "env": {
        "AIVIS_API_KEY": "your_actual_api_key_here"
      }
    }
  }
}
```

**注意点:**
- `command` はuvのフルパスを指定（`which uv` で確認）
- `/path/to/your/project/directory` を実際のプロジェクトディレクトリに変更
- APIキーを実際の値に変更

### 3. Claude Desktop を再起動

設定ファイルを保存後、Claude Desktop を再起動してください。

### 4. 使用方法

Claude Desktop で以下のように依頼できます：

```
「こんにちは、今日は良い天気ですね。」というテキストを音声で再生してください。
```

```
感情豊かに「おめでとうございます！」と言ってください。感情の強さは1.5に設定してください。
```

```
「お疲れ様でした」を非同期モードで再生してください。
```

## ファイル構成

```
aibis-cloud-tools/
├── aibis_cloud_tools/     # メインライブラリパッケージ
│   ├── __init__.py       # パッケージ初期化
│   ├── tts.py           # AivisCloudTTSクラス
│   └── utils.py         # ユーティリティ関数
├── scripts/              # 実行可能スクリプト
│   ├── say.py           # メインTTSスクリプト
│   ├── claude_code_speaker.py # Claude応答監視スクリプト
│   ├── mcp_server.py    # MCPサーバー
│   └── README.md        # スクリプト詳細説明
├── tests/               # テストスイート
│   ├── test_tts.py      # TTSクラステスト
│   ├── test_utils.py    # ユーティリティテスト
│   ├── test_claude_code_speaker.py # 監視スクリプトテスト
│   ├── test_mcp_server.py # MCPサーバーテスト
│   └── test_mcp.sh      # MCPサーバー手動テスト
├── examples/            # 使用例・サンプルファイル
│   └── sample.txt      # サンプルテキストファイル
├── .env.example        # 環境変数テンプレート
├── pyproject.toml      # uv設定ファイル・依存関係
├── uv.lock            # 依存関係ロックファイル
└── README.md          # このファイル
```

## 対応音声フォーマット

| フォーマット | 拡張子 | 特徴 |
|-------------|--------|------|
| WAV | .wav | 無圧縮・最高音質・大きなファイルサイズ |
| FLAC | .flac | 可逆圧縮・高音質・中程度のファイルサイズ |
| MP3 | .mp3 | 汎用性が高い・ストリーミング再生対応 |
| AAC | .aac | MP3より高効率・多くのデバイスで対応 |
| Opus | .ogg | 最高圧縮効率・低遅延 |

## 開発・テスト

### テストの実行

```bash
# 全テストの実行
python -m pytest tests/ -v

# 特定のテストファイルのみ実行
python -m pytest tests/test_tts.py -v

# カバレッジ付きでテスト実行
python -m pytest tests/ --cov=aibis_cloud_tools --cov-report=html

# テスト並列実行（高速化）
python -m pytest tests/ -n auto
```

### テスト構成

- **61個のテスト** で包括的にカバー
- **Given-When-Then** 構造でテスト記述
- **Mock** を使用した外部API呼び出しの分離
- **pytest** + **pytest-asyncio** でテストフレームワーク構成

### 依存関係管理

```bash
# 依存関係のインストール
uv sync

# 依存関係の追加
uv add package_name

# 開発用依存関係の追加  
uv add --dev package_name

# 依存関係の更新
uv lock --upgrade
```

### プロジェクト構造

- **aibis_cloud_tools/**: Pythonパッケージ（ライブラリコード）
- **scripts/**: 実行可能スクリプト（CLIツール）
- **tests/**: テストスイート（単体・統合テスト）

## トラブルシューティング

### 音声が再生されない場合

- **macOS**: `afplay` コマンドが利用可能か確認
- **Linux**: `play` または `aplay` がインストールされているか確認  
- **Windows**: 標準の音声再生機能を使用

### APIエラーが発生する場合

1. APIキーが正しく設定されているか確認
2. [Aivis Cloud API ダッシュボード](https://hub.aivis-project.com/) でクレジット残高を確認
3. 指定したモデルUUIDが存在するか `--list-models` で確認

### MCPサーバーのデバッグ

```bash
# 詳細なログ出力を有効にする
MCP_DEBUG=true uv run scripts/mcp_server.py
```

### テストが失敗する場合

```bash
# 依存関係の再インストール
uv sync --force

# テスト環境のクリーンアップ
rm -rf .pytest_cache __pycache__ tests/__pycache__

# 個別テストのデバッグ実行
python -m pytest tests/test_tts.py::TestAivisCloudTTSInit::test_正常なAPIキーで初期化できる -v -s
```

## 関連リンク

- [Aivis Cloud API 公式サイト](https://aivis-project.com/cloud-api/)
- [API ドキュメント](https://api.aivis-project.com/v1/docs)
- [Model Context Protocol](https://spec.modelcontextprotocol.io/)
- [uv ドキュメント](https://docs.astral.sh/uv/)