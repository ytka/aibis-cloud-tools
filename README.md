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

### 対応音声モデル例
- **mai**: 標準的な女性の声（推奨）
- **ずんだもん**: 人気キャラクターの声
- **老当主**: 渋い男性の声
- **若い男**: 爽やかな男性の声

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
AIVIS_DEFAULT_MODEL_UUID=e9339137-2ae3-4d41-9394-fb757a7e61e6  # mai
```

**利用可能なモデル例**:
- **mai**: `e9339137-2ae3-4d41-9394-fb757a7e61e6` (デフォルト推奨)
- **ずんだもん**: `b7be910e-d703-4b3d-80e4-02d1426d21d0`
- **老当主**: `5d804388-665e-4174-ab60-53d448c0d7eb`
- **若い男**: `6d11c6c2-f4a4-4435-887e-23dd60f8b8dd`

**優先順位**: コマンドライン指定 > 環境変数 > APIデフォルト

## 使用方法

### TTS スクリプト

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

### シェルスクリプト

便利なシェルスクリプトが用意されています：

```bash
# 簡単な音声合成
scripts/speak.sh "こんにちは"
scripts/speak.sh examples/sample.txt

# 長いテキストの分割読み上げ
scripts/speak_long.sh examples/sample.txt

# デバッグ用スクリプト
scripts/debug_speak.sh examples/sample.txt

# Claude Code応答監視（自動読み上げ）
python scripts/claude-code-speaker.py

# uvで実行（推奨）
uv run scripts/claude-code-speaker.py

# カスタム設定で実行
python scripts/claude-code-speaker.py --tts-script scripts/speak.sh --watch-dir ~/.claude/projects
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

### MCPサーバー

```bash
# MCPサーバー起動
uv run src/run_mcp_server.py

# デバッグモード（詳細ログ出力）
MCP_DEBUG=true uv run src/run_mcp_server.py
```

### mcp tools との連携

```bash
# ツール一覧表示
mcp tools uv run --directory /path/to/project src/run_mcp_server.py

# 音声合成実行（同期モード）
mcp call speak --params '{"text":"こんにちは"}' uv run --directory /path/to/project src/run_mcp_server.py

# 音声合成実行（非同期モード）
mcp call speak --params '{"text":"こんにちは","async_mode":true}' uv run --directory /path/to/project src/run_mcp_server.py
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
        "src/run_mcp_server.py"
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
├── src/                    # メインソースコード
│   ├── aivis-cloud-tts.py # メイン TTS スクリプト
│   └── run_mcp_server.py  # MCP サーバー（公式フレームワーク使用）
├── scripts/               # シェルスクリプト群
│   ├── speak.sh          # 簡単読み上げスクリプト
│   ├── speak_long.sh     # 長文分割読み上げスクリプト
│   ├── debug_speak.sh    # デバッグ用スクリプト
│   ├── claude-code-speaker.py # Claude Code応答監視スクリプト
│   └── README.md         # スクリプトの詳細説明
├── examples/              # 使用例・サンプルファイル
│   └── sample.txt        # サンプルテキストファイル
├── tests/                 # テストファイル
│   └── test_mcp.sh       # MCPサーバーテストスクリプト
├── docs/                  # ドキュメント
├── tmp/                   # 一時ファイル
├── .env.example          # 環境変数テンプレート
├── pyproject.toml        # uv 設定ファイル
└── README.md             # このファイル
```

## 対応音声フォーマット

| フォーマット | 拡張子 | 特徴 |
|-------------|--------|------|
| WAV | .wav | 無圧縮・最高音質・大きなファイルサイズ |
| FLAC | .flac | 可逆圧縮・高音質・中程度のファイルサイズ |
| MP3 | .mp3 | 汎用性が高い・ストリーミング再生対応 |
| AAC | .aac | MP3より高効率・多くのデバイスで対応 |
| Opus | .ogg | 最高圧縮効率・低遅延 |

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
MCP_DEBUG=true uv run run_mcp_server.py
```

## 関連リンク

- [Aivis Cloud API 公式サイト](https://aivis-project.com/cloud-api/)
- [API ドキュメント](https://api.aivis-project.com/v1/docs)
- [Model Context Protocol](https://spec.modelcontextprotocol.io/)
- [uv ドキュメント](https://docs.astral.sh/uv/)