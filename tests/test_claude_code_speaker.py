#!/usr/bin/env python3
"""
claude_code_speaker.pyの統合テスト

Test-Driven Development approach:
1. Given (条件): テストの前提条件
2. When (実行): テスト対象の処理
3. Then (結果): 期待される結果
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.claude_code_speaker import ClaudeResponseWatcher


class TestClaudeResponseWatcherInit:
    """ClaudeResponseWatcherクラスの初期化テスト群"""

    def test_正常な監視ディレクトリで初期化できる(self):
        """
        Given: 存在する監視ディレクトリ
        When: ClaudeResponseWatcher()で初期化
        Then: インスタンスが正常に作成される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            
            # When
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
            
            # Then
            assert watcher.watch_dir == Path(temp_dir).expanduser()
            assert watcher.api_key == "test-key"
            assert watcher.processed_lines == {}
            assert watcher.current_tts_process is None

    def test_APIキーなしでも初期化できる(self):
        """
        Given: AIVIS_API_KEYが設定されていない環境
        When: ClaudeResponseWatcher()で初期化
        Then: api_keyがNoneでインスタンスが作成される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            
            # When
            with patch.dict(os.environ, {}, clear=True):
                watcher = ClaudeResponseWatcher(temp_dir)
            
            # Then
            assert watcher.api_key is None

    def test_定数が適切に設定される(self):
        """
        Given: ClaudeResponseWatcherクラス
        When: クラス定数を確認
        Then: 適切な値が設定されている
        """
        # Given/When/Then
        assert ClaudeResponseWatcher.MAX_TEXT_LENGTH == 3000
        assert ClaudeResponseWatcher.CANCEL_CHECK_INTERVAL == 0.1
        assert ClaudeResponseWatcher.PROCESS_TERMINATION_TIMEOUT == 2
        assert ClaudeResponseWatcher.ESC_KEY_TIMEOUT == 0.3
        assert ClaudeResponseWatcher.SPLIT_PAUSE == 0.5


class TestClaudeResponseWatcherProcessNewLines:
    """process_new_linesメソッドのテスト群"""

    def test_新しい行が適切に処理される(self):
        """
        Given: Claude応答を含むJSONLファイル
        When: process_new_lines()を実行
        Then: 新しい行のみが処理される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl_file = Path(temp_dir) / "test.jsonl"
            
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                # 初期化後にファイルを作成して追加行をシミュレート
                claude_response = {
                    "type": "assistant",
                    "message": {
                        "content": [{"text": "これはテスト応答です。"}]
                    },
                    "timestamp": "2024-01-01T00:00:00Z"
                }
                
                jsonl_file.write_text(json.dumps(claude_response) + "\n")
                
                with patch.object(watcher, 'handle_claude_response') as mock_handle:
                    
                    # When
                    watcher.process_new_lines(str(jsonl_file))
                    
                    # Then
                    mock_handle.assert_called_once()
                    args = mock_handle.call_args[0]
                    assert args[0] == claude_response

    def test_無効なJSONは無視される(self):
        """
        Given: 無効なJSONを含むファイル
        When: process_new_lines()を実行
        Then: 無効な行はスキップされエラーにならない
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl_file = Path(temp_dir) / "test.jsonl"
            jsonl_file.write_text("invalid json\n")
            
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                # When/Then（例外が発生しないことを確認）
                watcher.process_new_lines(str(jsonl_file))

    def test_非assistant_typeの行はスキップされる(self):
        """
        Given: assistant以外のtypeを持つJSON行
        When: process_new_lines()を実行
        Then: その行は処理されない
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl_file = Path(temp_dir) / "test.jsonl"
            
            user_message = {
                "type": "user",
                "message": {"content": [{"text": "ユーザーメッセージ"}]}
            }
            
            jsonl_file.write_text(json.dumps(user_message) + "\n")
            
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                with patch.object(watcher, 'handle_claude_response') as mock_handle:
                    
                    # When
                    watcher.process_new_lines(str(jsonl_file))
                    
                    # Then
                    mock_handle.assert_not_called()


class TestClaudeResponseWatcherHandleClaudeResponse:
    """handle_claude_responseメソッドのテスト群"""

    def test_有効なClaude応答が処理される(self):
        """
        Given: 有効なClaude応答データ
        When: handle_claude_response()を実行
        Then: TTS処理が呼び出される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            claude_data = {
                "message": {
                    "content": [{"text": "これはテスト応答です。"}]
                },
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                with patch.object(watcher, 'handle_claude_response_tts') as mock_tts:
                    
                    # When
                    watcher.handle_claude_response(claude_data, Path("test.jsonl"))
                    
                    # Then
                    mock_tts.assert_called_once_with(
                        "これはテスト応答です。",
                        "2024-01-01T00:00:00Z"
                    )

    def test_無効なcontentの応答はスキップされる(self):
        """
        Given: content[0]['text']が存在しない応答データ
        When: handle_claude_response()を実行
        Then: TTS処理は呼び出されない
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_data = {
                "message": {
                    "content": [{"type": "image"}]  # textキーがない
                },
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                with patch.object(watcher, 'handle_claude_response_tts') as mock_tts:
                    
                    # When
                    watcher.handle_claude_response(invalid_data, Path("test.jsonl"))
                    
                    # Then
                    mock_tts.assert_not_called()


class TestClaudeResponseWatcherHandleClaudeResponseTts:
    """handle_claude_response_ttsメソッドのテスト群"""

    def test_短いテキストは単一チャンクで処理される(self):
        """
        Given: 3000文字以下の短いテキスト
        When: handle_claude_response_tts()を実行
        Then: 1つのチャンクとして処理される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            short_text = "これは短いテスト文です。"
            
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                with patch.object(watcher, '_play_with_library_sync') as mock_play:
                    
                    # When
                    watcher.handle_claude_response_tts(short_text, "2024-01-01T00:00:00Z")
                    
                    # Then
                    mock_play.assert_called_once()

    def test_長いテキストは複数チャンクで処理される(self):
        """
        Given: 3000文字を超える長いテキスト
        When: handle_claude_response_tts()を実行
        Then: 複数のチャンクに分割されて順次処理される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            long_text = "これは長いテスト文です。" * 300  # 約3600文字
            
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                with patch.object(watcher, '_play_with_library_sync') as mock_play, \
                     patch('time.sleep') as mock_sleep:
                    
                    # When
                    watcher.handle_claude_response_tts(long_text, "2024-01-01T00:00:00Z")
                    
                    # Then
                    assert mock_play.call_count > 1  # 複数回呼び出される
                    mock_sleep.assert_called()  # チャンク間の待機が発生

    def test_APIキーなしではスキップされる(self):
        """
        Given: AIVIS_API_KEYが設定されていない環境
        When: handle_claude_response_tts()を実行
        Then: TTS処理はスキップされる
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            test_text = "テストテキスト"
            
            with patch.dict(os.environ, {}, clear=True):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                with patch.object(watcher, '_play_with_library_sync') as mock_play:
                    
                    # When
                    watcher.handle_claude_response_tts(test_text, "2024-01-01T00:00:00Z")
                    
                    # Then
                    mock_play.assert_not_called()


class TestClaudeResponseWatcherProcessManagement:
    """プロセス管理関連のテスト群"""

    def test_has_active_tts_process_正常なプロセス(self):
        """
        Given: アクティブなTTSプロセス
        When: _has_active_tts_process()を実行
        Then: Trueが返される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                mock_process = Mock()
                mock_process.poll.return_value = None  # まだ実行中
                watcher.current_tts_process = mock_process
                
                # When
                result = watcher._has_active_tts_process()
                
                # Then
                assert result is True

    def test_has_active_tts_process_終了したプロセス(self):
        """
        Given: 既に終了したTTSプロセス
        When: _has_active_tts_process()を実行
        Then: Falseが返される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                mock_process = Mock()
                mock_process.poll.return_value = 0  # 終了済み
                watcher.current_tts_process = mock_process
                
                # When
                result = watcher._has_active_tts_process()
                
                # Then
                assert result is False

    def test_kill_current_tts_正常終了(self):
        """
        Given: アクティブなTTSプロセス
        When: _kill_current_tts()を実行
        Then: プロセスが正常に終了される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                mock_process = Mock()
                mock_process.poll.return_value = None  # アクティブ
                mock_process.wait.return_value = None
                watcher.current_tts_process = mock_process
                
                # When
                watcher._kill_current_tts()
                
                # Then
                mock_process.terminate.assert_called_once()
                mock_process.wait.assert_called_once_with(timeout=2)
                assert watcher.current_tts_process is None

    def test_kill_current_tts_強制終了(self):
        """
        Given: 通常終了しないTTSプロセス
        When: _kill_current_tts()を実行
        Then: プロセスが強制終了される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                mock_process = Mock()
                mock_process.poll.return_value = None  # アクティブ
                # timeoutで例外を発生させる
                from subprocess import TimeoutExpired
                mock_process.wait.side_effect = TimeoutExpired("test", 2)
                watcher.current_tts_process = mock_process
                
                # When
                watcher._kill_current_tts()
                
                # Then
                mock_process.terminate.assert_called_once()
                mock_process.kill.assert_called_once()
                assert watcher.current_tts_process is None


class TestClaudeResponseWatcherFileSystemEvents:
    """ファイルシステムイベント処理のテスト群"""

    def test_on_modified_jsonlファイル(self):
        """
        Given: .jsonlファイルの変更イベント
        When: on_modified()を実行
        Then: process_new_lines()が呼び出される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                from watchdog.events import FileModifiedEvent
                event = FileModifiedEvent("/path/to/test.jsonl")
                
                with patch.object(watcher, 'process_new_lines') as mock_process:
                    
                    # When
                    watcher.on_modified(event)
                    
                    # Then
                    mock_process.assert_called_once_with("/path/to/test.jsonl")

    def test_on_modified_非jsonlファイル(self):
        """
        Given: .jsonl以外のファイルの変更イベント
        When: on_modified()を実行
        Then: process_new_lines()は呼び出されない
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                from watchdog.events import FileModifiedEvent
                event = FileModifiedEvent("/path/to/test.txt")
                
                with patch.object(watcher, 'process_new_lines') as mock_process:
                    
                    # When
                    watcher.on_modified(event)
                    
                    # Then
                    mock_process.assert_not_called()

    def test_on_created_jsonlファイル(self):
        """
        Given: 新しい.jsonlファイルの作成イベント
        When: on_created()を実行
        Then: processed_linesが初期化されprocess_new_lines()が呼び出される
        """
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AIVIS_API_KEY": "test-key"}):
                watcher = ClaudeResponseWatcher(temp_dir)
                
                from watchdog.events import FileCreatedEvent
                event = FileCreatedEvent("/path/to/new.jsonl")
                
                with patch.object(watcher, 'process_new_lines') as mock_process:
                    
                    # When
                    watcher.on_created(event)
                    
                    # Then
                    assert watcher.processed_lines["/path/to/new.jsonl"] == 0
                    mock_process.assert_called_once_with("/path/to/new.jsonl")


if __name__ == "__main__":
    # テストを実行
    pytest.main([__file__, "-v"])