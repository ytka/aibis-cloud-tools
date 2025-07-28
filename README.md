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
- Aivis Cloud API のAPIキー

## セットアップ

### 1. uv のインストール

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. APIキーの設定

[Aivis Cloud API ダッシュボード](https://hub.aivis-project.com/cloud-api/api-keys) からAPIキーを取得し、環境変数で設定：

```bash
export AIVIS_API_KEY="your_api_key_here"
```

## 使用方法

### TTS スクリプト

```bash
# テキストから音声合成
uv run aivis-cloud-tts.py --text "こんにちは、世界！"

# テキストファイルから音声合成
uv run aivis-cloud-tts.py --text-file example.txt

# 音声ファイルとして保存
uv run aivis-cloud-tts.py --text "こんにちは" --save-file output.mp3

# リアルタイムストリーミング再生
uv run aivis-cloud-tts.py --text-file example.txt --realtime

# パラメータ調整
uv run aivis-cloud-tts.py --text "感情豊かに話します" \
  --rate 1.2 \
  --intensity 1.5 \
  --volume 1.0 \
  --format mp3

# モデル一覧表示
uv run aivis-cloud-tts.py --list-models
```

### MCPサーバー

```bash
# MCPサーバー起動
uv run run_mcp_server.py

# デバッグモード（詳細ログ出力）
MCP_DEBUG=true uv run run_mcp_server.py
```

### mcp tools との連携

```bash
# ツール一覧表示
mcp tools uv run --directory /path/to/project run_mcp_server.py

# 音声合成実行（同期モード）
mcp call speak --params '{"text":"こんにちは"}' uv run --directory /path/to/project run_mcp_server.py

# 音声合成実行（非同期モード）
mcp call speak --params '{"text":"こんにちは","async_mode":true}' uv run --directory /path/to/project run_mcp_server.py
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
        "run_mcp_server.py"
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

- `aivis-cloud-tts.py`: メイン TTS スクリプト
- `run_mcp_server.py`: MCP サーバー（公式フレームワーク使用）
- `pyproject.toml`: uv 設定ファイル

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