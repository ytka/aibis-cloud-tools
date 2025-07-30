#!/usr/bin/env python3
"""
AivisCloudTTSクラスのテスト

Test-Driven Development approach:
1. Given (条件): テストの前提条件
2. When (実行): テスト対象の処理
3. Then (結果): 期待される結果
"""

import pytest
import tempfile
import os
import subprocess
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aibis_cloud_tools.tts import AivisCloudTTS


class TestAivisCloudTTSInit:
    """AivisCloudTTSクラスの初期化テスト群"""

    def test_正常なAPIキーで初期化できる(self):
        """
        Given: 有効なAPIキー
        When: AivisCloudTTS()で初期化
        Then: インスタンスが正常に作成される
        """
        # Given
        api_key = "test-api-key-12345"
        
        # When
        client = AivisCloudTTS(api_key)
        
        # Then
        assert client.api_key == api_key
        assert client.base_url == "https://api.aivis-project.com/v1"
        assert client.headers["Authorization"] == f"Bearer {api_key}"
        assert client.headers["Content-Type"] == "application/json"

    def test_空のAPIキーでも初期化できる(self):
        """
        Given: 空のAPIキー
        When: AivisCloudTTS()で初期化
        Then: インスタンスが作成される（ただし認証エラーになる）
        """
        # Given
        api_key = ""
        
        # When
        client = AivisCloudTTS(api_key)
        
        # Then
        assert client.api_key == ""
        assert client.headers["Authorization"] == "Bearer "


class TestAivisCloudTTSListModels:
    """list_modelsメソッドのテスト群"""

    def test_正常なレスポンスでモデル一覧を取得できる(self):
        """
        Given: 正常なAPIレスポンス
        When: list_models()を実行
        Then: モデル一覧が返される
        """
        # Given
        mock_response = {
            "aivm_models": [
                {"aivm_model_uuid": "uuid1", "name": "Model1", "description": "Test model 1"},
                {"aivm_model_uuid": "uuid2", "name": "Model2", "description": "Test model 2"}
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = mock_response
            
            client = AivisCloudTTS("test-key")
            
            # When
            result = client.list_models(limit=5)
            
            # Then
            assert result == mock_response
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert "limit" in kwargs["params"]
            assert kwargs["params"]["limit"] == 5

    def test_HTTPエラーが適切に処理される(self):
        """
        Given: HTTPエラーが発生するAPI
        When: list_models()を実行
        Then: HTTPError例外が発生する
        """
        # Given
        with patch('requests.get') as mock_get:
            mock_get.return_value.raise_for_status.side_effect = Exception("HTTP Error")
            
            client = AivisCloudTTS("test-key")
            
            # When/Then
            with pytest.raises(Exception, match="HTTP Error"):
                client.list_models()


class TestAivisCloudTTSSynthesizeSpeech:
    """synthesize_speechメソッドのテスト群"""

    def test_正常な音声合成リクエスト(self):
        """
        Given: 正常なパラメータ
        When: synthesize_speech()を実行
        Then: 音声データが返される
        """
        # Given
        mock_audio_data = b"fake_audio_data"
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "audio/mpeg"}
            mock_response.iter_content.return_value = [mock_audio_data]
            mock_post.return_value = mock_response
            
            client = AivisCloudTTS("test-key")
            
            # When
            result = client.synthesize_speech(
                text="テストテキスト",
                model_uuid="test-model-uuid",
                volume=1.0
            )
            
            # Then
            assert result == mock_audio_data
            mock_post.assert_called_once()

    def test_JSONエラーレスポンスが適切に処理される(self):
        """
        Given: JSONエラーレスポンス
        When: synthesize_speech()を実行
        Then: 適切な例外が発生する
        """
        # Given
        error_json = b'{"status_code": 400, "detail": "Bad Request"}'
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.iter_content.return_value = [error_json]
            mock_post.return_value = mock_response
            
            client = AivisCloudTTS("test-key")
            
            # When/Then
            with pytest.raises(Exception, match="API Error: 400 - Bad Request"):
                client.synthesize_speech(
                    text="テストテキスト",
                    model_uuid="test-model-uuid"
                )

    def test_HTTPエラーステータスコードが適切に処理される(self):
        """
        Given: HTTP 401エラー
        When: synthesize_speech()を実行
        Then: カスタムエラーメッセージで例外が発生する
        """
        # Given
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_post.return_value = mock_response
            
            client = AivisCloudTTS("test-key")
            
            # When/Then
            with pytest.raises(Exception, match="認証エラー"):
                client.synthesize_speech(
                    text="テストテキスト",
                    model_uuid="test-model-uuid"
                )


class TestAivisCloudTTSPlayAudio:
    """play_audioメソッドのテスト群"""

    @patch('sys.platform', 'darwin')
    def test_macOSでafplayが呼び出される(self):
        """
        Given: macOS環境
        When: play_audio()を実行
        Then: afplayコマンドが呼び出される
        """
        # Given
        audio_data = b"fake_audio_data"
        
        with patch('subprocess.Popen') as mock_popen, \
             patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.unlink') as mock_unlink:
            
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.mp3"
            mock_process = Mock()
            mock_process.wait.return_value = None
            mock_popen.return_value = mock_process
            
            client = AivisCloudTTS("test-key")
            
            # When
            client.play_audio(audio_data, "mp3")
            
            # Then
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "afplay"
            assert "/tmp/test.mp3" in args

    @patch('sys.platform', 'linux')
    def test_Linuxでplayが呼び出される(self):
        """
        Given: Linux環境
        When: play_audio()を実行
        Then: playコマンドが呼び出される
        """
        # Given
        audio_data = b"fake_audio_data"
        
        with patch('subprocess.Popen') as mock_popen, \
             patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.unlink') as mock_unlink:
            
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.mp3"
            mock_process = Mock()
            mock_process.wait.return_value = None
            mock_popen.return_value = mock_process
            
            client = AivisCloudTTS("test-key")
            
            # When
            client.play_audio(audio_data, "mp3")
            
            # Then
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "play"

    @patch('sys.platform', 'win32')
    def test_WindowsでwinsoundPlaySoundが呼び出される(self):
        """
        Given: Windows環境
        When: play_audio()を実行
        Then: winsound.PlaySoundが呼び出される
        """
        # Given
        audio_data = b"fake_audio_data"
        
        # winsoundモジュールをモック
        mock_winsound = MagicMock()
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.unlink') as mock_unlink, \
             patch.dict('sys.modules', {'winsound': mock_winsound}):
            
            mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.mp3"
            
            client = AivisCloudTTS("test-key")
            
            # When
            client.play_audio(audio_data, "mp3")
            
            # Then
            mock_winsound.PlaySound.assert_called_once()

    def test_一時ファイルが適切にクリーンアップされる(self):
        """
        Given: 音声データ
        When: play_audio()を実行
        Then: 一時ファイルが削除される
        """
        # Given
        audio_data = b"fake_audio_data"
        temp_file_path = "/tmp/test.mp3"
        
        with patch('sys.platform', 'darwin'), \
             patch('subprocess.Popen') as mock_popen, \
             patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.unlink') as mock_unlink:
            
            mock_temp.return_value.__enter__.return_value.name = temp_file_path
            mock_process = Mock()
            mock_process.wait.return_value = None
            mock_popen.return_value = mock_process
            
            client = AivisCloudTTS("test-key")
            
            # When
            client.play_audio(audio_data, "mp3")
            
            # Then
            mock_unlink.assert_called_once_with(temp_file_path)


class TestAivisCloudTTSPlayAudioAsync:
    """play_audio_asyncメソッドのテスト群"""

    @patch('sys.platform', 'darwin')
    def test_非同期再生でプロセスオブジェクトが返される(self):
        """
        Given: macOS環境
        When: play_audio_async()を実行
        Then: プロセスオブジェクトと一時ファイルパスが返される
        """
        # Given
        audio_data = b"fake_audio_data"
        temp_file_path = "/tmp/test.mp3"
        
        with patch('subprocess.Popen') as mock_popen, \
             patch('tempfile.NamedTemporaryFile') as mock_temp:
            
            mock_temp.return_value.__enter__.return_value.name = temp_file_path
            mock_process = Mock()
            mock_popen.return_value = mock_process
            
            client = AivisCloudTTS("test-key")
            
            # When
            proc, file_path = client.play_audio_async(audio_data, "mp3")
            
            # Then
            assert proc == mock_process
            assert file_path == temp_file_path
            mock_popen.assert_called_once()

    @patch('sys.platform', 'win32')
    def test_Windows環境で疑似プロセスオブジェクトが返される(self):
        """
        Given: Windows環境
        When: play_audio_async()を実行
        Then: 疑似プロセスオブジェクトが返される
        """
        # Given
        audio_data = b"fake_audio_data"
        temp_file_path = "C:\\temp\\test.mp3"
        
        # winsoundモジュールをモック
        mock_winsound = MagicMock()
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('threading.Thread') as mock_thread, \
             patch.dict('sys.modules', {'winsound': mock_winsound}):
            
            mock_temp.return_value.__enter__.return_value.name = temp_file_path
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance
            
            client = AivisCloudTTS("test-key")
            
            # When
            proc, file_path = client.play_audio_async(audio_data, "mp3")
            
            # Then
            assert hasattr(proc, 'poll')
            assert hasattr(proc, 'wait')
            assert hasattr(proc, 'terminate')
            assert hasattr(proc, 'kill')
            assert file_path == temp_file_path

    def test_プロセス開始エラー時に一時ファイルが削除される(self):
        """
        Given: プロセス開始でエラーが発生
        When: play_audio_async()を実行
        Then: 一時ファイルが削除されて例外が発生する
        """
        # Given
        audio_data = b"fake_audio_data"
        temp_file_path = "/tmp/test.mp3"
        
        with patch('sys.platform', 'darwin'), \
             patch('subprocess.Popen') as mock_popen, \
             patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.unlink') as mock_unlink:
            
            mock_temp.return_value.__enter__.return_value.name = temp_file_path
            mock_popen.side_effect = Exception("Process start failed")
            
            client = AivisCloudTTS("test-key")
            
            # When/Then
            with pytest.raises(Exception, match="Process start failed"):
                client.play_audio_async(audio_data, "mp3")
            
            mock_unlink.assert_called_once_with(temp_file_path)


class TestAivisCloudTTSHandleHttpError:
    """_handle_http_errorメソッドのテスト群"""

    def test_401エラーで適切なメッセージが表示される(self):
        """
        Given: HTTP 401エラーレスポンス
        When: _handle_http_error()を実行
        Then: 認証エラーメッセージで例外が発生する
        """
        # Given
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        client = AivisCloudTTS("test-key")
        
        # When/Then
        with pytest.raises(Exception) as exc_info:
            client._handle_http_error(mock_response)
        
        assert "認証エラー" in str(exc_info.value)
        assert "401 Unauthorized" in str(exc_info.value)

    def test_503エラーで適切なメッセージが表示される(self):
        """
        Given: HTTP 503エラーレスポンス
        When: _handle_http_error()を実行
        Then: サービス障害メッセージで例外が発生する
        """
        # Given
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        
        client = AivisCloudTTS("test-key")
        
        # When/Then
        with pytest.raises(Exception) as exc_info:
            client._handle_http_error(mock_response)
        
        assert "503 Service Unavailable" in str(exc_info.value)
        assert "障害が発生" in str(exc_info.value)

    def test_未知のエラーコードで汎用メッセージが表示される(self):
        """
        Given: HTTP 999エラーレスポンス（未知のエラーコード）
        When: _handle_http_error()を実行
        Then: 汎用エラーメッセージで例外が発生する
        """
        # Given
        mock_response = Mock()
        mock_response.status_code = 999
        mock_response.text = "Unknown Error"
        
        client = AivisCloudTTS("test-key")
        
        # When/Then
        with pytest.raises(Exception) as exc_info:
            client._handle_http_error(mock_response)
        
        assert "HTTP 999" in str(exc_info.value)


if __name__ == "__main__":
    # テストを実行
    pytest.main([__file__, "-v"])