# Scripts Directory

このディレクトリには、Aivis Cloud TTSプロジェクトの各種スクリプトが含まれています。

## 音声合成スクリプト

### speak.sh
基本的な音声合成スクリプト。

```bash
# 基本的な使用方法
./speak.sh "こんにちは"
./speak.sh ../examples/sample.txt

# オプション付き
./speak.sh "こんにちは" -m e9339137-2ae3-4d41-9394-fb757a7e61e6 -i 1.5
```

### speak_long.sh
長いテキストを分割して読み上げるスクリプト。

```bash
# 長いテキストファイルの読み上げ
./speak_long.sh ../examples/sample.txt

# オプション付き
./speak_long.sh -c 1500 -p 2 ../examples/sample.txt
```

### debug_speak.sh
デバッグ用の音声合成スクリプト。詳細な情報を表示します。

```bash
./debug_speak.sh ../examples/sample.txt
```

## Claude Code連携スクリプト

### claude-code-speaker.py
Claude Codeの応答を監視し、自動的にAivis Cloud TTSで読み上げるスクリプト。

```bash
# uvで実行（推奨、依存関係自動管理）
uv run claude-code-speaker.py

# 基本実行（自動検出）
python claude-code-speaker.py

# カスタム設定
python claude-code-speaker.py --tts-script ./speak.sh --watch-dir ~/.claude/projects

# ヘルプ表示
uv run claude-code-speaker.py --help
```

#### 機能
- Claude Codeの応答ファイル（.jsonl）を監視
- 新しい応答を検出すると自動的にTTSで読み上げ
- **自動音声キャンセル**: 新しいイベント発生時に前の音声を自動キャンセル
- **ESCキーキャンセル**: ESCキー押下で音声再生を即座に停止（表示崩れなし）
- ログファイルに記録
- エラー通知表示

#### 依存関係
```bash
# uvを使用する場合（推奨）- 自動的に依存関係が管理されます
uv run claude-code-speaker.py

# 手動でインストールする場合
pip install watchdog
```

#### 環境変数設定
`.env`ファイルまたはシェル環境変数で設定：

```bash
# .envファイルで設定（推奨）
CLAUDE_WATCH_DIR=~/.claude/projects
CLAUDE_TTS_SCRIPT=~/source/aibis-cloud-tools/scripts/speak.sh

# シェル環境変数で設定
export CLAUDE_WATCH_DIR="~/.claude/projects"
export CLAUDE_TTS_SCRIPT="~/source/aibis-cloud-tools/scripts/speak.sh"
```

## 共通の環境変数

すべてのスクリプトは、プロジェクトルートの`.env`ファイルから環境変数を読み込みます：

- `AIVIS_API_KEY`: Aivis Cloud APIキー
- `AIVIS_DEFAULT_MODEL_UUID`: デフォルト音声モデルUUID

## パス構造

scripts/内のスクリプトは、以下の相対パス構造を前提としています：

```
aibis-cloud-tools/
├── scripts/          # このディレクトリ
│   ├── speak.sh      # ../src/aivis-cloud-tts.py を参照
│   └── ...
├── src/              # メインソースコード
├── examples/         # サンプルファイル
└── .env             # 環境変数ファイル
```