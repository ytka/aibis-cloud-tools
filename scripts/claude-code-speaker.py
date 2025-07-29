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
import atexit
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
        
        # TTSスクリプトのパスを設定
        self.tts_script_path = self._find_tts_script(tts_script_path)
        
        # 既存ファイルの行数を初期化
        self._initialize_processed_lines()
        
        # ESCキー監視を開始
        self._start_esc_monitor()
        
        # プロセスクリーンアップのシグナルハンドラー登録
        self._setup_signal_handlers()
    
    def _find_tts_script(self, custom_path=None):
        """TTSスクリプトのパスを自動検出または設定"""
        if custom_path:
            script_path = Path(custom_path).expanduser()
            if script_path.exists():
                return str(script_path)
        
        # プロジェクト内の相対パスで検索
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        
        # aivis-cloud-tts.pyを直接検索
        possible_paths = [
            project_root / "src" / "aivis-cloud-tts.py",  # プロジェクトルート/src/
            script_dir / "aivis-cloud-tts.py",            # 同じディレクトリ
            project_root / "aivis-cloud-tts.py",          # プロジェクトルート直下
        ]
        
        for tts_script in possible_paths:
            if tts_script.exists():
                return str(tts_script)
        
        print("⚠️  aivis-cloud-tts.pyが見つかりません。--tts-script オプションで指定してください。")
        return None
    
    def _kill_current_tts(self):
        """現在のTTS再生を停止"""
        with self.process_lock:
            if self.current_tts_process and self.current_tts_process.poll() is None:
                try:
                    if sys.platform == "win32":
                        # Windows: プロセスを終了
                        self.current_tts_process.terminate()
                        try:
                            self.current_tts_process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            self.current_tts_process.kill()
                    else:
                        # Unix系: プロセスグループ全体を終了
                        pgid = os.getpgid(self.current_tts_process.pid)
                        os.killpg(pgid, signal.SIGTERM)
                        try:
                            self.current_tts_process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            os.killpg(pgid, signal.SIGKILL)
                    
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
            if self.tts_script_path:
                try:
                    # 長すぎる場合は最初の2000文字のみ読み上げ（より安全なサイズ）
                    max_length = 2000
                    truncated_content = content[:max_length] if len(content) > max_length else content
                    
                    # Markdown記法をクリーニング
                    read_content = self._clean_markdown_for_tts(truncated_content)
                    
                    # aivis-cloud-tts.pyを直接実行（uv runで）
                    script_dir = Path(__file__).parent
                    project_root = script_dir.parent
                    
                    cmd = [
                        "uv", "run", 
                        "--directory", str(project_root),
                        self.tts_script_path,
                        "--text", read_content
                    ]
                    
                    # 環境変数をコピー
                    env = os.environ.copy()
                    
                    # プロセス管理情報を更新
                    with self.process_lock:
                        self.is_playing = True
                        
                        # 子プロセスを親と同じプロセスグループで実行
                        self.current_tts_process = subprocess.Popen(
                            cmd, 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL,
                            env=env
                        )
                    
                    print(f"🔊 Aivis Cloud TTSで読み上げ開始: {read_content[:50]}...")
                    print(f"🔧 実行コマンド: {' '.join(shlex.quote(arg) for arg in cmd)}")
                    if sys.stdin.isatty():
                        print("⌨️  ESCキーでキャンセル可能")
                    
                    # バックグラウンドでプロセス完了を監視
                    threading.Thread(target=self._monitor_tts_process, daemon=True).start()
                    
                except Exception as tts_error:
                    print(f"⚠️  TTS読み上げエラー: {tts_error}")
                    self.is_playing = False
                    self._send_notification("TTS読み上げに失敗しました")
            else:
                print("⚠️  TTSスクリプトが設定されていないため、読み上げをスキップします")
                self._send_notification("Claude応答を検出しました（TTS未設定）")
                
        except Exception as e:
            print(f"❌ コマンド実行エラー: {e}")
            self.is_playing = False
    
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
    
    def _clean_markdown_for_tts(self, text):
        """Markdown記法をTTS読み上げ用にクリーニング"""
        import re
        
        # ヘッダー記号の処理（# ## ### など）
        text = re.sub(r'^#{1,6}\s*(.+)$', r'\1', text, flags=re.MULTILINE)
        
        # 強調記号の削除
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'__(.*?)__', r'\1', text)      # __bold__
        text = re.sub(r'(?<!\*)\*([^\*\n]+?)\*(?!\*)', r'\1', text)  # *italic* (not part of **)
        text = re.sub(r'(?<!_)_([^_\n]+?)_(?!_)', r'\1', text)        # _italic_ (not part of __)
        
        # コードブロックの処理（先に処理）
        text = re.sub(r'```[\s\S]*?```', 'コード例', text)  # ```code blocks```
        text = re.sub(r'`([^`\n]*)`', r'\1', text)      # `inline code`
        
        # リンク記法の処理
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)  # [text](url) → text
        
        # リスト記号の処理
        text = re.sub(r'^[\s]*[-\*\+]\s*(.+)$', r'・\1', text, flags=re.MULTILINE)
        
        # 引用記号の削除
        text = re.sub(r'^>\s*(.+)$', r'\1', text, flags=re.MULTILINE)
        
        # テーブル区切りの処理
        text = text.replace('|', '、')
        
        # 複数の改行を整理
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 特殊文字の処理
        text = text.replace('---', '区切り線')
        text = text.replace('***', '区切り線')
        
        return text.strip()
    
    def _setup_signal_handlers(self):
        """プロセスクリーンアップ用のシグナルハンドラーを設定"""
        def cleanup_handler(signum, frame):
            # 安全な出力（標準エラー使用、reentrant call回避）
            try:
                sys.stderr.write(f"\n🛑 シグナル {signum} を受信、プロセスをクリーンアップ中...\n")
                sys.stderr.flush()
            except:
                pass  # 出力エラーを無視
            
            self._cleanup_all_processes()
            # スレッドシャットダウン中のsys.exit()を避けるため、os._exit()を使用
            os._exit(0)
        
        def cleanup_atexit():
            # atexitでは重複チェックのみ実行
            if not self._cleanup_done:
                try:
                    sys.stderr.write("🧹 終了時クリーンアップを実行中...\n")
                    sys.stderr.flush()
                except:
                    pass
                self._cleanup_all_processes()
        
        # シグナルハンドラー登録
        signal.signal(signal.SIGINT, cleanup_handler)   # Ctrl-C
        signal.signal(signal.SIGTERM, cleanup_handler)  # 終了シグナル
        
        # プロセス終了時のクリーンアップ
        atexit.register(cleanup_atexit)
        
        print("🔧 プロセスクリーンアップハンドラーを設定しました")
    
    def _cleanup_all_processes(self):
        """全ての子プロセスをクリーンアップ（重複実行防止付き）"""
        with self._cleanup_lock:
            # 既にクリーンアップ済みの場合はスキップ
            if self._cleanup_done:
                return
            
            self._cleanup_done = True
        
        try:
            # 現在のTTSプロセスを終了
            if hasattr(self, 'current_tts_process') and self.current_tts_process:
                try:
                    sys.stderr.write("🎵 TTSプロセスを終了中...\n")
                    sys.stderr.flush()
                except:
                    pass
                self._kill_current_tts()
            
            # プロセスグループ全体を終了（uv runの子プロセスも含む）
            try:
                # 現在のプロセスグループIDを取得
                pgid = os.getpgid(os.getpid())
                try:
                    sys.stderr.write(f"📋 プロセスグループ {pgid} を終了中...\n")
                    sys.stderr.flush()
                except:
                    pass
                
                # プロセスグループ全体にSIGTERMを送信
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass  # プロセスが既に存在しない場合は無視
                
                # 少し待機してからSIGKILLで強制終了
                time.sleep(0.5)  # 短縮して応答性向上
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass  # 既に終了している場合は無視
                    
            except Exception:
                # プロセスグループ操作のエラーは静かに無視
                pass
            
            try:
                sys.stderr.write("✅ プロセスクリーンアップ完了\n")
                sys.stderr.flush()
            except:
                pass
            
        except Exception:
            # 全てのエラーを静かに無視（シグナルハンドラー内での安全性確保）
            pass
    
    def _send_notification(self, message):
        """通知メッセージを標準エラー出力に送信"""
        print(f"🔔 {message}", file=sys.stderr, flush=True)

def load_env_file():
    """プロジェクトルートの.envファイルを読み込む"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_file = project_root / ".env"
    
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # 環境変数が未設定の場合のみ設定
                        if key.strip() not in os.environ:
                            os.environ[key.strip()] = value.strip()
        except Exception as e:
            print(f"⚠️  .envファイル読み込みエラー: {e}")

def main():
    """メイン関数"""
    import argparse
    
    # .envファイルを読み込み
    load_env_file()
    
    parser = argparse.ArgumentParser(
        description="Claude Code応答監視スクリプト（Aivis Cloud TTS統合版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python claude-code-speaker.py                                           # デフォルト設定で実行
  python claude-code-speaker.py --tts-script ./src/aivis-cloud-tts.py     # カスタムTTSスクリプト指定
  python claude-code-speaker.py --watch-dir ~/.claude/sessions            # カスタム監視ディレクトリ指定

環境変数での設定:
  export CLAUDE_WATCH_DIR="~/.claude/projects"                            # 監視ディレクトリ
  python claude-code-speaker.py                                           # 環境変数で設定して実行
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
        help="使用するTTSスクリプトのパス（省略時は自動検出）"
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
    
    # TTSスクリプトの確認
    if event_handler.tts_script_path:
        print(f"🔊 TTSスクリプト: {event_handler.tts_script_path}")
    else:
        print("⚠️  TTSスクリプトが見つかりません。通知のみ行います。")
        print("💡 --tts-script オプションでaivis-cloud-tts.pyのパスを指定してください")
    
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