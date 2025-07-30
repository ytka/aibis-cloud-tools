#!/usr/bin/env python3
"""
mcp_server.pyのテスト

Test-Driven Development approach:
1. Given (条件): テストの前提条件
2. When (実行): テスト対象の処理
3. Then (結果): 期待される結果
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.mcp_server import (
    get_tts_client,
    handle_list_tools,
    handle_call_tool
)


class TestGetTtsClient:
    """get_tts_client関数のテスト群"""

    def test_正常なAPIキーでクライアントが作成される(self):
        """
        Given: 有効なAIVIS_API_KEY環境変数
        When: get_tts_client()を実行
        Then: AivisCloudTTSインスタンスが返される
        """
        # Given
        with patch.dict(os.environ, {"AIVIS_API_KEY": "test-api-key"}):
            
            # When
            client = get_tts_client()
            
            # Then
            assert client is not None
            assert client.api_key == "test-api-key"

    def test_APIキーがない場合は例外が発生する(self):
        """
        Given: AIVIS_API_KEY環境変数が設定されていない
        When: get_tts_client()を実行
        Then: ValueError例外が発生する
        """
        # Given
        with patch.dict(os.environ, {}, clear=True):
            
            # When/Then
            with pytest.raises(ValueError, match="AIVIS_API_KEY environment variable is required"):
                get_tts_client()

    def test_空のAPIキーの場合は例外が発生する(self):
        """
        Given: 空のAIVIS_API_KEY環境変数
        When: get_tts_client()を実行
        Then: ValueError例外が発生する
        """
        # Given
        with patch.dict(os.environ, {"AIVIS_API_KEY": ""}):
            
            # When/Then
            with pytest.raises(ValueError, match="AIVIS_API_KEY environment variable is required"):
                get_tts_client()


class TestHandleListTools:
    """handle_list_tools関数のテスト群"""

    @pytest.mark.asyncio
    async def test_speak_toolが返される(self):
        """
        Given: 特に条件なし
        When: handle_list_tools()を実行
        Then: speakツールの定義が返される
        """
        # Given/When
        tools = await handle_list_tools()
        
        # Then
        assert len(tools) == 1
        assert tools[0].name == "speak"
        assert "text" in tools[0].inputSchema["properties"]
        assert "speaks" in tools[0].inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_tool_schemaが適切に定義される(self):
        """
        Given: 特に条件なし
        When: handle_list_tools()を実行
        Then: ツールスキーマが適切に定義されている
        """
        # Given/When
        tools = await handle_list_tools()
        tool = tools[0]
        
        # Then
        # 単一テキストモード
        assert "text" in tool.inputSchema["properties"]
        assert "model_uuid" in tool.inputSchema["properties"]
        assert "emotional_intensity" in tool.inputSchema["properties"]
        assert "volume" in tool.inputSchema["properties"]
        
        # 複数テキストモード
        assert "speaks" in tool.inputSchema["properties"]
        speaks_schema = tool.inputSchema["properties"]["speaks"]
        assert speaks_schema["type"] == "array"
        assert "text" in speaks_schema["items"]["properties"]
        
        # anyOf制約
        assert "anyOf" in tool.inputSchema
        assert {"required": ["text"]} in tool.inputSchema["anyOf"]
        assert {"required": ["speaks"]} in tool.inputSchema["anyOf"]


class TestHandleCallTool:
    """handle_call_tool関数のテスト群"""

    @pytest.mark.asyncio
    async def test_単一テキストモードが正常に処理される(self):
        """
        Given: 単一テキストのspeakリクエスト
        When: handle_call_tool()を実行
        Then: 音声合成と再生が実行され成功結果が返される
        """
        # Given
        arguments = {
            "text": "テストテキスト",
            "model_uuid": "test-model-uuid",
            "emotional_intensity": 1.5,
            "volume": 0.8
        }
        
        mock_audio_data = b"fake_audio_data"
        mock_proc = Mock()
        mock_proc.wait.return_value = None
        
        with patch('scripts.mcp_server.get_tts_client') as mock_get_client, \
             patch('scripts.mcp_server.get_default_model') as mock_get_model, \
             patch('scripts.mcp_server.split_text_smart') as mock_split, \
             patch('os.path.exists') as mock_exists, \
             patch('os.unlink') as mock_unlink:
            
            mock_client = Mock()
            mock_client.synthesize_speech.return_value = mock_audio_data
            mock_client.play_audio_async.return_value = (mock_proc, "/tmp/test.mp3")
            mock_get_client.return_value = mock_client
            mock_get_model.return_value = "default-model-uuid"
            mock_split.return_value = ["テストテキスト"]  # 単一チャンク
            mock_exists.return_value = True
            
            # When
            result = await handle_call_tool("speak", arguments)
            
            # Then
            assert len(result) == 1
            result_text = result[0].text
            result_data = eval(result_text)  # 簡易的なJSON解析
            
            assert result_data["success"] is True
            assert result_data["segments_count"] == 1
            assert result_data["total_audio_size"] == len(mock_audio_data)
            
            # モックが適切に呼び出されたことを確認
            mock_client.synthesize_speech.assert_called_once_with(
                text="テストテキスト",
                model_uuid="test-model-uuid",
                emotional_intensity=1.5,
                volume=0.8
            )

    @pytest.mark.asyncio
    async def test_複数テキストモードが正常に処理される(self):
        """
        Given: 複数テキストのspeakリクエスト
        When: handle_call_tool()を実行
        Then: 各セグメントが順次処理され成功結果が返される
        """
        # Given
        arguments = {
            "speaks": [
                {"text": "第1テキスト", "volume": 1.0},
                {"text": "第2テキスト", "volume": 0.5}
            ]
        }
        
        mock_audio_data1 = b"fake_audio_data1"
        mock_audio_data2 = b"fake_audio_data2"
        mock_proc = Mock()
        mock_proc.wait.return_value = None
        
        with patch('scripts.mcp_server.get_tts_client') as mock_get_client, \
             patch('scripts.mcp_server.get_default_model') as mock_get_model, \
             patch('scripts.mcp_server.split_text_smart') as mock_split, \
             patch('os.path.exists') as mock_exists, \
             patch('os.unlink') as mock_unlink:
            
            mock_client = Mock()
            mock_client.synthesize_speech.side_effect = [mock_audio_data1, mock_audio_data2]
            mock_client.play_audio_async.return_value = (mock_proc, "/tmp/test.mp3")
            mock_get_client.return_value = mock_client
            mock_get_model.return_value = "default-model-uuid"
            mock_split.side_effect = [["第1テキスト"], ["第2テキスト"]]  # 各々単一チャンク
            mock_exists.return_value = True
            
            # When
            result = await handle_call_tool("speak", arguments)
            
            # Then
            assert len(result) == 1
            result_text = result[0].text
            result_data = eval(result_text)
            
            assert result_data["success"] is True
            assert result_data["segments_count"] == 2
            assert result_data["total_audio_size"] == len(mock_audio_data1) + len(mock_audio_data2)
            
            # 各セグメントが処理されたことを確認
            assert mock_client.synthesize_speech.call_count == 2

    @pytest.mark.asyncio
    async def test_長いテキストが分割処理される(self):
        """
        Given: 3000文字を超える長いテキスト
        When: handle_call_tool()を実行
        Then: テキストが分割され各チャンクが処理される
        """
        # Given
        long_text = "これは長いテキストです。" * 300  # 約3600文字
        arguments = {"text": long_text}
        
        mock_audio_data = b"fake_audio_data"
        mock_proc = Mock()
        mock_proc.wait.return_value = None
        
        with patch('scripts.mcp_server.get_tts_client') as mock_get_client, \
             patch('scripts.mcp_server.get_default_model') as mock_get_model, \
             patch('scripts.mcp_server.split_text_smart') as mock_split, \
             patch('os.path.exists') as mock_exists, \
             patch('os.unlink') as mock_unlink:
            
            mock_client = Mock()
            mock_client.synthesize_speech.return_value = mock_audio_data
            mock_client.play_audio_async.return_value = (mock_proc, "/tmp/test.mp3")
            mock_get_client.return_value = mock_client
            mock_get_model.return_value = "default-model-uuid"
            
            # 2つのチャンクに分割される
            chunk1 = long_text[:3000]
            chunk2 = long_text[3000:]
            mock_split.return_value = [chunk1, chunk2]
            mock_exists.return_value = True
            
            # When
            result = await handle_call_tool("speak", arguments)
            
            # Then
            result_text = result[0].text
            result_data = eval(result_text)
            
            assert result_data["success"] is True
            
            # 分割処理が呼び出されたことを確認
            mock_split.assert_called_once_with(long_text, 3000)
            
            # 各チャンクが処理されたことを確認
            assert mock_client.synthesize_speech.call_count == 2

    @pytest.mark.asyncio
    async def test_空のテキストはスキップされる(self):
        """
        Given: 空のテキストを含むspeakリクエスト
        When: handle_call_tool()を実行
        Then: 空のテキストはスキップされる
        """
        # Given
        arguments = {
            "speaks": [
                {"text": ""},  # 空のテキスト
                {"text": "有効なテキスト"}
            ]
        }
        
        mock_audio_data = b"fake_audio_data"
        mock_proc = Mock()
        mock_proc.wait.return_value = None
        
        with patch('scripts.mcp_server.get_tts_client') as mock_get_client, \
             patch('scripts.mcp_server.get_default_model') as mock_get_model, \
             patch('scripts.mcp_server.split_text_smart') as mock_split, \
             patch('os.path.exists') as mock_exists, \
             patch('os.unlink') as mock_unlink:
            
            mock_client = Mock()
            mock_client.synthesize_speech.return_value = mock_audio_data
            mock_client.play_audio_async.return_value = (mock_proc, "/tmp/test.mp3")
            mock_get_client.return_value = mock_client
            mock_get_model.return_value = "default-model-uuid"
            mock_split.return_value = ["有効なテキスト"]  # 空のテキストは除外される
            mock_exists.return_value = True
            
            # When
            result = await handle_call_tool("speak", arguments)
            
            # Then
            result_text = result[0].text
            result_data = eval(result_text)
            
            assert result_data["success"] is True
            assert result_data["segments_count"] == 1  # 空のセグメントは除外される
            
            # 1回だけ音声合成が呼び出される（空のテキストは除外）
            assert mock_client.synthesize_speech.call_count == 1

    @pytest.mark.asyncio
    async def test_音声再生エラーが適切に処理される(self):
        """
        Given: 音声再生でエラーが発生する状況
        When: handle_call_tool()を実行
        Then: エラー情報が結果に含まれる
        """
        # Given
        arguments = {"text": "テストテキスト"}
        
        mock_audio_data = b"fake_audio_data"
        mock_proc = Mock()
        mock_proc.wait.side_effect = Exception("Playback failed")
        
        with patch('scripts.mcp_server.get_tts_client') as mock_get_client, \
             patch('scripts.mcp_server.get_default_model') as mock_get_model, \
             patch('scripts.mcp_server.split_text_smart') as mock_split, \
             patch('os.path.exists') as mock_exists, \
             patch('os.unlink') as mock_unlink:
            
            mock_client = Mock()
            mock_client.synthesize_speech.return_value = mock_audio_data
            mock_client.play_audio_async.return_value = (mock_proc, "/tmp/test.mp3")
            mock_get_client.return_value = mock_client
            mock_get_model.return_value = "default-model-uuid"
            mock_split.return_value = ["テストテキスト"]
            mock_exists.return_value = True
            
            # When
            result = await handle_call_tool("speak", arguments)
            
            # Then
            result_text = result[0].text
            result_data = eval(result_text)
            
            assert result_data["success"] is True  # 全体としては成功
            segments = result_data["segments"]
            assert len(segments) == 1
            
            chunk_result = segments[0]["chunks"][0]
            assert chunk_result["playback_result"]["status"] == "error"
            assert "Playback failed" in chunk_result["playback_result"]["message"]

    @pytest.mark.asyncio
    async def test_unknown_toolで例外が発生する(self):
        """
        Given: 未知のツール名
        When: handle_call_tool()を実行
        Then: ValueError例外が発生する
        """
        # Given
        tool_name = "unknown_tool"
        arguments = {}
        
        # When/Then
        with pytest.raises(ValueError, match="Unknown tool: unknown_tool"):
            await handle_call_tool(tool_name, arguments)

    @pytest.mark.asyncio
    async def test_テキストなしのリクエストでエラーが発生する(self):
        """
        Given: textもspeaksも含まないリクエスト
        When: handle_call_tool()を実行
        Then: エラー結果が返される
        """
        # Given
        arguments = {}  # textもspeaksもない
        
        # When
        result = await handle_call_tool("speak", arguments)
        
        # Then
        assert len(result) == 1
        result_text = result[0].text
        result_data = eval(result_text)
        
        assert result_data["success"] is False
        assert "No text provided" in result_data["error"]

    @pytest.mark.asyncio
    async def test_一時ファイルが適切にクリーンアップされる(self):
        """
        Given: 正常な音声再生処理
        When: handle_call_tool()を実行
        Then: 一時ファイルが削除される
        """
        # Given
        arguments = {"text": "テストテキスト"}
        temp_file_path = "/tmp/test.mp3"
        
        mock_audio_data = b"fake_audio_data"
        mock_proc = Mock()
        mock_proc.wait.return_value = None
        
        with patch('scripts.mcp_server.get_tts_client') as mock_get_client, \
             patch('scripts.mcp_server.get_default_model') as mock_get_model, \
             patch('scripts.mcp_server.split_text_smart') as mock_split, \
             patch('os.path.exists') as mock_exists, \
             patch('os.unlink') as mock_unlink:
            
            mock_client = Mock()
            mock_client.synthesize_speech.return_value = mock_audio_data
            mock_client.play_audio_async.return_value = (mock_proc, temp_file_path)
            mock_get_client.return_value = mock_client
            mock_get_model.return_value = "default-model-uuid"
            mock_split.return_value = ["テストテキスト"]
            mock_exists.return_value = True
            
            # When
            await handle_call_tool("speak", arguments)
            
            # Then
            mock_unlink.assert_called_once_with(temp_file_path)


if __name__ == "__main__":
    # テストを実行
    pytest.main([__file__, "-v"])