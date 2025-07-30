#!/usr/bin/env python3
"""
Claude Code応答監視スクリプト（Aivis Cloud TTS統合版）
新しいClaude応答が検出されたときにAivis Cloud TTSで読み上げる
"""

import json
import time
import subprocess
import shlex
import os
import sys
import signal
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aibis_cloud_tools import AivisCloudTTS, load_env_file, clean_markdown_for_tts, get_default_model

class ClaudeResponseWatcher(FileSystemEventHandler):
    def __init__(self, watch_dir, tts_script_path=None):
        self.watch_dir = Path(watch_dir).expanduser()
        self.processed_lines = {}  # ファイルごとの処理済み行数
        
        # TTSプロセス管理
        self.current_tts_process = None
        self.process_lock = threading.Lock()
        self.is_playing = False
        
        # クリーンアップ管理
        self._cleanup_done = False
        self._cleanup_lock = threading.Lock()
        
        # TTS設定
        self.use_direct_tts = True  # 直接ライブラリを使用
        self.tts_script_path = self._find_tts_script(tts_script_path)  # フォールバック用
        self.tts_client = None
        
        # 既存ファイルの行数を初期化
        self._initialize_processed_lines()
        
        # ESCキー監視を開始
        self._start_esc_monitor()
    
    def _find_tts_script(self, custom_path=None):
        """TTSスクリプトのパスを自動検出または設定（フォールバック用）"""
        if custom_path:
            script_path = Path(custom_path).expanduser()
            if script_path.exists():
                return str(script_path)
        
        # プロジェクト内の相対パスで検索
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        
        # say.pyを直接検索
        possible_paths = [
            script_dir / "say.py",                        # 同じディレクトリ
            project_root / "scripts" / "say.py",          # プロジェクトルート/scripts/
        ]
        
        for tts_script in possible_paths:
            if tts_script.exists():
                return str(tts_script)
        
        return None
    
    def _kill_current_tts(self):
        """現在のTTS再生を停止（子プロセスも含めて確実に終了）"""
        with self.process_lock:
            # ライブラリ使用時の処理
            if self.current_tts_process == "library_thread":
                print("🛑 ライブラリTTS再生をキャンセルしています...")
                self.is_playing = False
                self.current_tts_process = None
                print("🛑 ライブラリTTS再生をキャンセルしました")
                return
            
            # 従来のプロセス終了処理
            if self.current_tts_process and hasattr(self.current_tts_process, 'poll') and self.current_tts_process.poll() is None:
                try:
                    if sys.platform == "win32":
                        # Windows: プロセスを終了
                        self.current_tts_process.terminate()
                        try:
                            self.current_tts_process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            self.current_tts_process.kill()
                    else:
                        # Unix系: プロセスグループ全体を終了（uv runとその子プロセスを確実に終了）
                        try:
                            import signal
                            pgid = os.getpgid(self.current_tts_process.pid)
                            os.killpg(pgid, signal.SIGTERM)
                            try:
                                self.current_tts_process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                os.killpg(pgid, signal.SIGKILL)
                        except (OSError, ProcessLookupError):
                            # プロセスグループがない場合は通常の終了を試行
                            self.current_tts_process.terminate()
                            try:
                                self.current_tts_process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                self.current_tts_process.kill()
                    
                    print("🛑 前の音声再生をキャンセルしました")
                    self.is_playing = False
                    
                except (ProcessLookupError, OSError) as e:
                    # プロセスが既に終了している場合
                    pass
                except Exception as e:
                    print(f"⚠️  音声キャンセルエラー: {e}")
                    
                self.current_tts_process = None
    
    def _start_esc_monitor(self):
        """ESCキー監視を開始（表示崩れなし）"""
        if sys.stdin.isatty():
            try:
                monitor_thread = threading.Thread(target=self._esc_monitor, daemon=True)
                monitor_thread.start()
                print("⌨️  ESCキーで音声をキャンセルできます")
            except Exception:
                # エラー時は静かに無効化
                pass
    
    def _esc_monitor(self):
        """ESCキー監視（最適化版）"""
        try:
            import select
            import termios
            
            # 設定を保存
            old_settings = termios.tcgetattr(sys.stdin)
            
            try:
                # 最小限の設定変更でrawモードに近づける
                new_settings = old_settings[:]
                new_settings[3] &= ~(termios.ICANON | termios.ECHO)  # カノニカル＆エコー無効
                new_settings[6][termios.VMIN] = 1     # 最低1文字
                new_settings[6][termios.VTIME] = 0    # タイムアウトなし
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
                
                while True:
                    # 入力待機（短時間タイムアウト）
                    if select.select([sys.stdin], [], [], 0.3)[0]:
                        try:
                            char = sys.stdin.read(1)
                            if char and ord(char) == 27:  # ESC = 0x1b = 27
                                # エコーを手動で復元して出力
                                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                                if self.is_playing:
                                    print("\n⌨️  ESCキー検出 - 音声をキャンセル中...")
                                    sys.stdout.flush()
                                    self._kill_current_tts()
                                else:
                                    print("\n⌨️  ESCキー検出（再生中ではありません）")
                                    sys.stdout.flush()
                                # 設定を再適用
                                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
                                
                        except (OSError, IOError, ValueError):
                            continue
                        except (EOFError, KeyboardInterrupt):
                            break
                            
            finally:
                # 必ず元の設定に復元
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                        
        except (ImportError, OSError):
            # termios等が利用できない環境
            pass
        except Exception:
            # その他のエラーで静かに終了
            pass
    
    def _initialize_processed_lines(self):
        """既存のJSONLファイルの行数を記録（起動時の重複処理を防ぐ）"""
        for jsonl_file in self.watch_dir.glob('**/*.jsonl'):
            try:
                with open(jsonl_file, 'r') as f:
                    self.processed_lines[str(jsonl_file)] = len(f.readlines())
            except Exception as e:
                print(f"⚠️  初期化エラー {jsonl_file}: {e}")
    
    def on_modified(self, event):
        if event.src_path.endswith('.jsonl'):
            self.process_new_lines(event.src_path)
    
    def on_created(self, event):
        if event.src_path.endswith('.jsonl'):
            # 新しいファイルが作成された場合
            self.processed_lines[event.src_path] = 0
            self.process_new_lines(event.src_path)
    
    def process_new_lines(self, file_path):
        file_path = Path(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"❌ ファイル読み込みエラー {file_path}: {e}")
            return
        
        # 前回処理済み行数を取得
        last_processed = self.processed_lines.get(str(file_path), 0)
        new_lines = lines[last_processed:]
        
        for line in new_lines:
            if line.strip():
                try:
                    data = json.loads(line)
                    # Claudeの応答のみ処理
                    if data.get('type') == 'assistant':
                        self.handle_claude_response(data, file_path)
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON解析エラー: {e}")
                    continue
        
        # 処理済み行数を更新
        self.processed_lines[str(file_path)] = len(lines)
    
    def handle_claude_response(self, data, file_path):
        """Claudeの応答が検出されたときの処理"""
        try:
            # 📝 content[0]['text'] の存在をチェック
            if not self._has_valid_text_content(data):
                print(f"⏭️  content[0]['text']が存在しないため、スキップします")
                return
            
            # 安全にcontentを取得
            content = data['message']['content'][0]['text']
            timestamp = data.get('timestamp', 'N/A')
            session_id = data.get('sessionId', 'N/A')
            
            print(f"\n🤖 Claude応答検出!")
            print(f"📅 時刻: {timestamp}")
            print(f"📁 ファイル: {file_path.name}")
            print(f"💬 内容: {content[:100]}{'...' if len(content) > 100 else ''}")
            print("-" * 50)
            
            # ここで任意のコマンドを実行
            self.execute_custom_command(content, timestamp, session_id)
            
        except Exception as e:
            print(f"❌ Claude応答処理エラー: {e}")
    
    def _has_valid_text_content(self, data):
        """content[0]['text']が存在するかチェック"""
        try:
            # messageキーの存在確認
            if 'message' not in data:
                return False
            
            # contentキーの存在確認
            if 'content' not in data['message']:
                return False
            
            # contentがリストで、最初の要素が存在するか確認
            content = data['message']['content']
            if not isinstance(content, list) or len(content) == 0:
                return False
            
            # 最初の要素にtextキーがあるか確認
            first_item = content[0]
            if not isinstance(first_item, dict) or 'text' not in first_item:
                return False
            
            return True
            
        except Exception:
            return False
    
    def execute_custom_command(self, content, timestamp, session_id):
        """カスタムコマンドの実行（Aivis Cloud TTS読み上げ版）"""
        try:
            # 前の音声再生をキャンセル
            if self.is_playing:
                print("🛑 前の音声再生をキャンセルしています...")
                self._kill_current_tts()
            
            # ログファイルに記録
            log_file = Path.home() / "claude-responses.log"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"🤖 Claude応答検出: {timestamp}\n")
                f.write(f"内容: {content}\n")
                f.write("-" * 50 + "\n")
            
            print(f"✅ ログに記録: {log_file}")
            
            # 🔊 Aivis Cloud TTSで読み上げ
            try:
                # 長すぎる場合は最初の2000文字のみ読み上げ（より安全なサイズ）
                max_length = 2000
                truncated_content = content[:max_length] if len(content) > max_length else content
                
                # Markdown記法をクリーニング
                read_content = clean_markdown_for_tts(truncated_content)
                
                # 直接TTSライブラリを使用
                if self._use_direct_tts():
                    self._play_with_library(read_content)
                elif self.tts_script_path:
                    self._play_with_script(read_content)
                else:
                    print("⚠️  TTSが設定されていないため、読み上げをスキップします")
                    self._send_notification("Claude応答を検出しました（TTS未設定）")
                    
            except Exception as tts_error:
                print(f"⚠️  TTS読み上げエラー: {tts_error}")
                self.is_playing = False
                self._send_notification("TTS読み上げに失敗しました")
                
        except Exception as e:
            print(f"❌ コマンド実行エラー: {e}")
            self.is_playing = False
    
    def _use_direct_tts(self):
        """直接TTSライブラリを使用できるかチェック"""
        try:
            api_key = os.getenv("AIVIS_API_KEY")
            return api_key is not None
        except:
            return False
    
    def _get_tts_client(self):
        """TTSクライアントを取得（キャッシュ付き）"""
        if self.tts_client is None:
            api_key = os.getenv("AIVIS_API_KEY")
            if not api_key:
                raise ValueError("AIVIS_API_KEY environment variable is required")
            self.tts_client = AivisCloudTTS(api_key)
        return self.tts_client
    
    def _play_with_library(self, text):
        """ライブラリを直接使用して音声再生"""
        with self.process_lock:
            self.is_playing = True
            # スレッドオブジェクトを current_tts_process として保存
            # これにより _kill_current_tts() で適切に停止できる
            self.current_tts_process = "library_thread"
        
        print(f"🔊 Aivis Cloud TTS（ライブラリ）で読み上げ開始: {text[:50]}...")
        
        def play_audio_thread():
            try:
                # 開始時に再度チェック（キャンセルされていないか）
                with self.process_lock:
                    if not self.is_playing:
                        return
                
                client = self._get_tts_client()
                print(f"🔊 音声合成中... ({len(text)}文字)")
                
                # キャンセルチェック
                with self.process_lock:
                    if not self.is_playing:
                        return
                
                audio_data = client.synthesize_speech(
                    text=text,
                    model_uuid=get_default_model(),
                    volume=1.0
                )
                
                # キャンセルチェック
                with self.process_lock:
                    if not self.is_playing:
                        return
                
                print(f"🎵 音声再生中... ({len(audio_data)} bytes)")
                temp_file = client.play_audio(audio_data)
                
                # 再生完了後の最終チェック
                with self.process_lock:
                    if self.is_playing:  # まだキャンセルされていない場合のみ完了メッセージ
                        if temp_file:
                            print(f"💾 音声ファイル: {temp_file}")
                        print("✅ 音声再生が完了しました")
                        
            except Exception as e:
                print(f"⚠️  ライブラリTTSエラー: {e}")
            finally:
                with self.process_lock:
                    self.is_playing = False
                    self.current_tts_process = None
        
        # バックグラウンドで再生
        audio_thread = threading.Thread(target=play_audio_thread, daemon=True)
        # スレッドオブジェクトを保存（将来的な拡張用）
        with self.process_lock:
            self.current_audio_thread = audio_thread
        audio_thread.start()
    
    def _play_with_script(self, text):
        """スクリプト経由で音声再生（フォールバック）"""
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        
        cmd = [
            "uv", "run", 
            "--directory", str(project_root),
            self.tts_script_path,
            "--text", text
        ]
        
        # 環境変数をコピー
        env = os.environ.copy()
        
        # プロセス管理情報を更新
        with self.process_lock:
            self.is_playing = True
            
            # 新しいプロセスグループで実行（子プロセスを確実に終了させるため）
            if sys.platform == "win32":
                # Windows: CREATE_NEW_PROCESS_GROUP フラグを使用
                self.current_tts_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    env=env
                )
            else:
                # Unix系: 新しいプロセスグループを作成
                self.current_tts_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid,
                    env=env
                )
        
        print(f"🔊 Aivis Cloud TTS（スクリプト）で読み上げ開始: {text[:50]}...")
        print(f"🔧 実行コマンド: {' '.join(shlex.quote(arg) for arg in cmd)}")
        if sys.stdin.isatty():
            print("⌨️  ESCキーでキャンセル可能")
        
        # バックグラウンドでプロセス完了を監視
        threading.Thread(target=self._monitor_tts_process, daemon=True).start()
    
    def _monitor_tts_process(self):
        """TTSプロセスの完了を監視するバックグラウンドスレッド"""
        try:
            if self.current_tts_process:
                # プロセスの完了を待機
                self.current_tts_process.wait()
                
                # プロセス管理状態をクリア
                with self.process_lock:
                    self.is_playing = False
                    self.current_tts_process = None
                
                print("✅ 音声再生が完了しました")
                
        except Exception as e:
            print(f"⚠️  プロセス監視エラー: {e}")
            with self.process_lock:
                self.is_playing = False
                self.current_tts_process = None
    
    
    def cleanup(self):
        """後処理 - 現在のTTSプロセスを停止"""
        with self._cleanup_lock:
            if self._cleanup_done:
                return
            self._cleanup_done = True
        
        print("🧹 TTSプロセスをクリーンアップ中...")
        self._kill_current_tts()
    
    def _send_notification(self, message):
        """通知メッセージを標準エラー出力に送信"""
        print(f"🔔 {message}", file=sys.stderr, flush=True)


def main():
    """メイン関数"""
    import argparse
    import signal
    
    # .envファイルを読み込み
    load_env_file()
    
    parser = argparse.ArgumentParser(
        description="Claude Code応答監視スクリプト（Aivis Cloud TTS統合版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python claude_code_speaker.py                                           # デフォルト設定で実行
  python claude_code_speaker.py --tts-script ./scripts/say.py             # カスタムTTSスクリプト指定
  python claude_code_speaker.py --watch-dir ~/.claude/sessions            # カスタム監視ディレクトリ指定

環境変数での設定:
  export CLAUDE_WATCH_DIR="~/.claude/projects"                            # 監視ディレクトリ
  python claude_code_speaker.py                                           # 環境変数で設定して実行
        """
    )
    
    # OS別のデフォルト監視ディレクトリ
    def get_default_watch_dir():
        if sys.platform == "win32":
            # Windows: %APPDATA%/Claude/projects
            return os.path.expandvars("%APPDATA%/Claude/projects")
        else:
            # Unix/Mac: ~/.claude/projects
            return "~/.claude/projects"
    
    # デフォルト監視ディレクトリ（環境変数 > OS別デフォルトの優先順位）
    default_watch_dir = os.getenv("CLAUDE_WATCH_DIR", get_default_watch_dir())
    
    parser.add_argument(
        "--watch-dir", 
        default=default_watch_dir,
        help=f"監視するディレクトリ（環境変数: CLAUDE_WATCH_DIR、デフォルト: {default_watch_dir}）"
    )
    
    # デフォルトTTSスクリプト（自動検出）
    default_tts_script = None
    
    parser.add_argument(
        "--tts-script",
        default=default_tts_script,
        help="使用するTTSスクリプトのパス（フォールバック用、通常はライブラリを直接使用）"
    )
    
    args = parser.parse_args()
    
    # 監視ディレクトリの確認
    watch_path = Path(args.watch_dir).expanduser()
    
    if not watch_path.exists():
        print(f"❌ ディレクトリが見つかりません: {watch_path}")
        print("💡 --watch-dir オプションで正しいClaude Codeのプロジェクトディレクトリを指定してください")
        return 1
    
    # イベントハンドラーの初期化
    event_handler = ClaudeResponseWatcher(args.watch_dir, args.tts_script)
    
    # メイン実行時のみシグナル処理を設定
    def graceful_shutdown(signum, frame):
        print(f"\n🛑 シグナル {signum} を受信、正常終了中...")
        event_handler.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, graceful_shutdown)   # Ctrl-C
    signal.signal(signal.SIGTERM, graceful_shutdown)  # 終了シグナル
    
    # TTS設定の確認
    if event_handler._use_direct_tts():
        print("🔊 TTS: ライブラリ直接使用（推奨）")
    elif event_handler.tts_script_path:
        print(f"🔊 TTSスクリプト（フォールバック）: {event_handler.tts_script_path}")
    else:
        print("⚠️  TTSが設定されていません。通知のみ行います。")
        print("💡 AIVIS_API_KEY環境変数を設定するか、--tts-script オプションでsay.pyのパスを指定してください")
    
    print(f"👁️  Claude応答監視を開始します...")
    print(f"📂 監視ディレクトリ: {watch_path}")
    print(f"📝 ログファイル: {Path.home() / 'claude-responses.log'}")
    print("🛑 停止するには Ctrl+C を押してください")
    print("=" * 60)
    
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 監視を停止しています...")
        observer.stop()
    
    observer.join()
    print("✅ 監視を停止しました")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())