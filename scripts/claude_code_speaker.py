#!/usr/bin/env python3
"""
Claude Code応答監視スクリプト（Aivis Cloud TTS統合版）
新しいClaude応答が検出されたときにAivis Cloud TTSで読み上げる
"""

import json
import time
import subprocess
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

from aibis_cloud_tools import AivisCloudTTS, load_env_file, clean_markdown_for_tts, get_default_model, split_text_smart

class ClaudeResponseWatcher(FileSystemEventHandler):
    # 設定定数
    MAX_TEXT_LENGTH = 3000                  # テキスト分割の単位（文字数）
    CANCEL_CHECK_INTERVAL = 0.1            # キャンセルチェック間隔（秒）
    PROCESS_TERMINATION_TIMEOUT = 2        # プロセス終了タイムアウト（秒）
    ESC_KEY_TIMEOUT = 0.3                  # ESCキー監視タイムアウト（秒）
    SPLIT_PAUSE = 0.5                      # 分割間の一時停止秒数
    
    def __init__(self, watch_dir):
        self.watch_dir = Path(watch_dir).expanduser()
        self.processed_lines = {}  # ファイルごとの処理済み行数
        
        # TTSプロセス管理
        self.current_tts_process = None
        self.process_lock = threading.Lock()
        
        # クリーンアップ管理
        self._cleanup_done = False
        self._cleanup_lock = threading.Lock()
        
        # TTS設定（初期化時にAPIキーをチェック）
        self.api_key = os.getenv("AIVIS_API_KEY")
        self.tts_client = None
        
        # 既存ファイルの行数を初期化
        self._initialize_processed_lines()
        
        # ESCキー監視を開始
        self._start_esc_monitor()
    
    
    def _has_active_tts_process(self):
        """アクティブなTTSプロセスが存在するかチェック"""
        return (self.current_tts_process and 
                hasattr(self.current_tts_process, 'poll') and 
                self.current_tts_process.poll() is None)
    
    def _kill_current_tts(self):
        """現在のTTSプロセスを終了（個別プロセスのみ）"""
        with self.process_lock:
            if self._has_active_tts_process() and self.current_tts_process is not None:
                print("🛑 TTS再生をキャンセルしています...")
                try:
                    # プロセスグループではなく、個別プロセスのみを終了
                    self.current_tts_process.terminate()
                    try:
                        self.current_tts_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.current_tts_process.kill()
                    
                    print("🛑 音声再生をキャンセルしました")
                    
                except (ProcessLookupError, OSError):
                    # プロセスが既に終了している場合
                    pass
                except (PermissionError, subprocess.SubprocessError) as e:
                    print(f"⚠️  音声キャンセルエラー: {e}")
                except Exception as e:
                    print(f"⚠️  予期しないキャンセルエラー: {e}")
                    
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
            from contextlib import contextmanager
            
            @contextmanager
            def raw_terminal():
                """ターミナル設定の確実な復元を保証するcontext manager"""
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    # 最小限の設定変更でrawモードに近づける
                    new_settings = old_settings[:]
                    new_settings[3] &= ~(termios.ICANON | termios.ECHO)  # カノニカル＆エコー無効
                    new_settings[6][termios.VMIN] = 1     # 最低1文字
                    new_settings[6][termios.VTIME] = 0    # タイムアウトなし
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
                    yield old_settings
                finally:
                    # 設定を確実に復元
                    try:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    except:
                        pass  # 復元に失敗してもプログラムは継続
            
            with raw_terminal():
                while True:
                    # 入力待機（短時間タイムアウト）
                    if select.select([sys.stdin], [], [], self.ESC_KEY_TIMEOUT)[0]:
                        try:
                            char = sys.stdin.read(1)
                            if char and ord(char) == 27:  # ESC = 0x1b = 27
                                if self._has_active_tts_process():
                                    print("\n⌨️  ESCキー検出 - 音声をキャンセル中...")
                                    sys.stdout.flush()
                                    self._kill_current_tts()
                                else:
                                    print("\n⌨️  ESCキー検出（再生中ではありません）")
                                    sys.stdout.flush()
                                
                        except (OSError, IOError, ValueError):
                            # 入力読み取りエラーは継続
                            continue
                        except (EOFError, KeyboardInterrupt):
                            # 終了シグナルでループを抜ける
                            break
                        
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
                # メモリ効率的な行数カウント
                line_count = 0
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line_count, _ in enumerate(f, 1):
                        pass  # 行数のみカウント
                self.processed_lines[str(jsonl_file)] = line_count
            except (IOError, OSError, PermissionError) as e:
                print(f"⚠️  ファイル読み取りエラー {jsonl_file}: {e}")
            except Exception as e:
                print(f"⚠️  予期しない初期化エラー {jsonl_file}: {e}")
    
    def on_modified(self, event):
        if str(event.src_path).endswith('.jsonl'):
            self.process_new_lines(event.src_path)
    
    def on_created(self, event):
        if str(event.src_path).endswith('.jsonl'):
            # 新しいファイルが作成された場合
            self.processed_lines[event.src_path] = 0
            self.process_new_lines(event.src_path)
    
    def process_new_lines(self, file_path):
        """新しい行を処理してClaude応答を検出（メモリ効率版）"""
        try:
            file_path = Path(file_path)
            file_key = str(file_path)
            
            # 前回処理した行数を取得
            last_processed = self.processed_lines.get(file_key, 0)
            current_line_num = 0
            
            # ファイルを行単位で読み込み（メモリ効率）
            with open(file_path, 'r', encoding='utf-8') as f:
                for current_line_num, line in enumerate(f, 1):
                    # 新しい行のみ処理
                    if current_line_num > last_processed:
                        line = line.strip()
                        if line:  # 空行をスキップ
                            try:
                                data = json.loads(line)
                                # Claudeの応答のみ処理
                                if data.get('type') == 'assistant':
                                    self.handle_claude_response(data, file_path)
                            except json.JSONDecodeError as e:
                                print(f"⚠️  JSON解析エラー: {e}")
                                continue
            
            # 処理済み行数を更新
            self.processed_lines[file_key] = current_line_num
            
        except (IOError, OSError, PermissionError) as e:
            print(f"❌ ファイル読み込みエラー {file_path}: {e}")
        except Exception as e:
            print(f"❌ 予期しない処理エラー {file_path}: {e}")
    
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
            
            # Claude応答の音声読み上げ処理
            self.handle_claude_response_tts(content, timestamp)
            
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
    
    def handle_claude_response_tts(self, content, timestamp):
        """Claude応答の音声読み上げ処理"""
        try:
            # 前の音声再生をキャンセル（プロセス存在チェック）
            if self._has_active_tts_process():
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
                # APIキーの確認（初期化時にチェック済み）
                if not self.api_key:
                    print("⚠️  AIVIS_API_KEYが設定されていないため、読み上げをスキップします")
                    self._send_notification("Claude応答を検出しました（API KEY未設定）")
                    return
                
                # 長いテキストを分割して処理
                text_chunks = split_text_smart(content, self.MAX_TEXT_LENGTH)
                
                if len(text_chunks) > 1:
                    print(f"📝 テキストを{len(text_chunks)}個のチャンクに分割しました（{self.MAX_TEXT_LENGTH}文字単位）")
                
                # 各チャンクを順次読み上げ（同期実行）
                for i, chunk_text in enumerate(text_chunks, 1):
                    # Markdown記法をクリーニング
                    read_content = clean_markdown_for_tts(chunk_text)
                    
                    print(f"🔊 [{i}/{len(text_chunks)}] チャンク読み上げ中... ({len(chunk_text)}文字)")
                    
                    # TTSライブラリで同期読み上げ（前の再生が完了してから次へ）
                    self._play_with_library_sync(read_content)
                    
                    # 最後のチャンクでない場合は短時間待機
                    if i < len(text_chunks):
                        print(f"⏸️  {self.SPLIT_PAUSE}秒間一時停止...")
                        time.sleep(self.SPLIT_PAUSE)
                    
            except Exception as tts_error:
                print(f"⚠️  TTS読み上げエラー: {tts_error}")
                self._send_notification("TTS読み上げに失敗しました")
                
        except Exception as e:
            print(f"❌ コマンド実行エラー: {e}")
    
    
    def _get_tts_client(self):
        """TTSクライアントを取得（キャッシュ付き）"""
        if self.tts_client is None:
            if not self.api_key:
                raise ValueError("AIVIS_API_KEY environment variable is required")
            self.tts_client = AivisCloudTTS(self.api_key)
        return self.tts_client
    
    def _play_with_library(self, text):
        """ライブラリの非同期再生機能を使用して音声再生（単一チャンク用）"""
        print(f"🔊 Aivis Cloud TTS（ライブラリ）で読み上げ開始: {text[:50]}...")
        
        def play_audio_thread():
            temp_file_path = None
            proc = None
            
            def cleanup_temp_file():
                """一時ファイルの確実なクリーンアップ"""
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except (OSError, PermissionError):
                        # ファイル削除エラーは無視して継続
                        pass
            
            try:
                client = self._get_tts_client()
                print(f"🔊 音声合成中... ({len(text)}文字)")
                
                audio_data = client.synthesize_speech(
                    text=text,
                    model_uuid=get_default_model(),
                    volume=1.0
                )
                
                print(f"🎵 音声再生中... ({len(audio_data)} bytes)")
                
                # 非同期再生でプロセスオブジェクトを取得
                proc, temp_file_path = client.play_audio_async(audio_data)
                
                with self.process_lock:
                    self.current_tts_process = proc
                
                # プロセスの完了を監視（キャンセル可能）
                should_continue = True
                while should_continue:
                    if proc.poll() is not None:
                        # プロセス完了
                        break
                    
                    # キャンセルチェック（原子的操作）
                    with self.process_lock:
                        should_continue = (self.current_tts_process == proc)
                    
                    if not should_continue:
                        # 別のプロセスに置き換えられた（キャンセルされた）場合
                        if proc.poll() is None:
                            proc.terminate()
                            try:
                                proc.wait(timeout=self.PROCESS_TERMINATION_TIMEOUT)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                        # キャンセル時も一時ファイルをクリーンアップ
                        cleanup_temp_file()
                        return
                    
                    # 短時間待機
                    import time
                    time.sleep(self.CANCEL_CHECK_INTERVAL)
                
                # 再生完了
                print(f"💾 音声ファイル: {temp_file_path}")
                print("✅ 音声再生が完了しました")
                        
            except Exception as e:
                print(f"⚠️  ライブラリTTSエラー: {e}")
            finally:
                # 一時ファイルのクリーンアップ
                cleanup_temp_file()
                
                with self.process_lock:
                    if self.current_tts_process == proc:
                        self.current_tts_process = None
        
        # バックグラウンドで再生
        audio_thread = threading.Thread(target=play_audio_thread, daemon=True)
        audio_thread.start()
    
    def _play_with_library_sync(self, text):
        """ライブラリの同期再生機能を使用して音声再生（マルチチャンク用）"""
        print(f"🔊 Aivis Cloud TTS（同期）で読み上げ開始: {text[:50]}...")
        
        temp_file_path = None
        proc = None
        
        def cleanup_temp_file():
            """一時ファイルの確実なクリーンアップ"""
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except (OSError, PermissionError):
                    # ファイル削除エラーは無視して継続
                    pass
        
        try:
            client = self._get_tts_client()
            print(f"🔊 音声合成中... ({len(text)}文字)")
            
            audio_data = client.synthesize_speech(
                text=text,
                model_uuid=get_default_model(),
                volume=1.0
            )
            
            print(f"🎵 音声再生中... ({len(audio_data)} bytes)")
            
            # 非同期再生でプロセスオブジェクトを取得
            proc, temp_file_path = client.play_audio_async(audio_data)
            
            with self.process_lock:
                self.current_tts_process = proc
            
            # プロセスの完了を同期的に待機（キャンセル可能）
            should_continue = True
            while should_continue:
                if proc.poll() is not None:
                    # プロセス完了
                    break
                
                # キャンセルチェック（原子的操作）
                with self.process_lock:
                    should_continue = (self.current_tts_process == proc)
                
                if not should_continue:
                    # 別のプロセスに置き換えられた（キャンセルされた）場合
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=self.PROCESS_TERMINATION_TIMEOUT)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                    # キャンセル時も一時ファイルをクリーンアップ
                    cleanup_temp_file()
                    return
                
                # 短時間待機
                time.sleep(self.CANCEL_CHECK_INTERVAL)
            
            # 再生完了
            print(f"💾 音声ファイル: {temp_file_path}")
            print("✅ 音声再生が完了しました")
                    
        except Exception as e:
            print(f"⚠️  ライブラリTTSエラー: {e}")
        finally:
            # 一時ファイルのクリーンアップ
            cleanup_temp_file()
            
            with self.process_lock:
                if self.current_tts_process == proc:
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
    
    
    args = parser.parse_args()
    
    # 監視ディレクトリの確認
    watch_path = Path(args.watch_dir).expanduser()
    
    if not watch_path.exists():
        print(f"❌ ディレクトリが見つかりません: {watch_path}")
        print("💡 --watch-dir オプションで正しいClaude Codeのプロジェクトディレクトリを指定してください")
        return 1
    
    # イベントハンドラーの初期化
    event_handler = ClaudeResponseWatcher(args.watch_dir)
    
    # メイン実行時のみシグナル処理を設定
    def graceful_shutdown(signum, _):
        print(f"\n🛑 シグナル {signum} を受信、正常終了中...")
        event_handler.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, graceful_shutdown)   # Ctrl-C
    signal.signal(signal.SIGTERM, graceful_shutdown)  # 終了シグナル
    
    # TTS設定の確認
    if event_handler.api_key:
        print("🔊 TTS: Aivis Cloud ライブラリ使用")
    else:
        print("⚠️  TTSが設定されていません。通知のみ行います。")
        print("💡 AIVIS_API_KEY環境変数を設定してください")
    
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