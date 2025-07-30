#!/usr/bin/env python3
"""
ユーティリティ関数のテスト

Test-Driven Development approach:
1. Given (条件): テストの前提条件
2. When (実行): テスト対象の処理
3. Then (結果): 期待される結果
"""

import pytest
import tempfile
import os
from pathlib import Path
import sys
from unittest.mock import patch

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aibis_cloud_tools.utils import (
    split_text_smart,
    clean_markdown_for_tts,
    load_env_file,
    get_default_model
)


class TestSplitTextSmart:
    """split_text_smart関数のテスト群"""

    def test_短いテキストは分割されない(self):
        """
        Given: 100文字の短いテキスト
        When: split_text_smart()を1000文字制限で実行
        Then: 1つのチャンクとして返される
        """
        # Given
        short_text = "これは短いテキストです。" * 10  # 約100文字
        max_chars = 1000
        
        # When
        result = split_text_smart(short_text, max_chars)
        
        # Then
        assert len(result) == 1
        assert result[0] == short_text

    def test_長いテキストは適切に分割される(self):
        """
        Given: 3000文字の長いテキスト
        When: split_text_smart()を1000文字制限で実行
        Then: 複数のチャンクに分割される
        """
        # Given
        long_text = "これは長いテキストです。" * 250  # 約3000文字
        max_chars = 1000
        
        # When
        result = split_text_smart(long_text, max_chars)
        
        # Then
        assert len(result) > 1
        assert all(len(chunk) <= max_chars for chunk in result)
        assert "".join(result) == long_text  # 元のテキストが完全に復元される

    def test_改行で適切に分割される(self):
        """
        Given: 改行を含むテキスト
        When: split_text_smart()を実行
        Then: 改行位置で分割される
        """
        # Given
        text_with_newlines = "第1段落です。\n\n第2段落です。\n\n第3段落です。"
        max_chars = 20
        
        # When
        result = split_text_smart(text_with_newlines, max_chars)
        
        # Then
        assert len(result) >= 2
        assert all(len(chunk) <= max_chars for chunk in result)
        
    def test_句読点で適切に分割される(self):
        """
        Given: 句読点を含む長いテキスト
        When: split_text_smart()を実行
        Then: 句読点位置で分割される
        """
        # Given
        text_with_punctuation = "これは第一文です。これは第二文です。これは第三文です。"
        max_chars = 15
        
        # When
        result = split_text_smart(text_with_punctuation, max_chars)
        
        # Then
        assert len(result) >= 2
        assert all(len(chunk) <= max_chars for chunk in result)

    def test_空文字列は空リストを返す(self):
        """
        Given: 空文字列
        When: split_text_smart()を実行
        Then: 空リストが返される
        """
        # Given
        empty_text = ""
        max_chars = 100
        
        # When
        result = split_text_smart(empty_text, max_chars)
        
        # Then
        assert result == []

    def test_max_chars_1の場合(self):
        """
        Given: 5文字のテキストとmax_chars=1
        When: split_text_smart()を実行
        Then: 各文字が個別のチャンクになる
        """
        # Given
        text = "あいうえお"
        max_chars = 1
        
        # When
        result = split_text_smart(text, max_chars)
        
        # Then
        assert len(result) == 5
        assert result == ["あ", "い", "う", "え", "お"]


class TestCleanMarkdownForTts:
    """clean_markdown_for_tts関数のテスト群"""

    def test_マークダウン記法が削除される(self):
        """
        Given: マークダウン記法を含むテキスト
        When: clean_markdown_for_tts()を実行
        Then: マークダウン記法が削除される
        """
        # Given
        markdown_text = "# 見出し\n**太字**と*斜体*と`コード`"
        
        # When
        result = clean_markdown_for_tts(markdown_text)
        
        # Then
        assert "#" not in result
        assert "**" not in result
        assert "*" not in result
        assert "`" not in result
        assert "見出し" in result
        assert "太字" in result
        assert "斜体" in result
        assert "コード" in result

    def test_空文字列は空文字列を返す(self):
        """
        Given: 空文字列
        When: clean_markdown_for_tts()を実行
        Then: 空文字列が返される
        """
        # Given
        empty_text = ""
        
        # When
        result = clean_markdown_for_tts(empty_text)
        
        # Then
        assert result == ""

    def test_通常のテキストはそのまま返される(self):
        """
        Given: マークダウン記法を含まない通常のテキスト
        When: clean_markdown_for_tts()を実行
        Then: 元のテキストがそのまま返される
        """
        # Given
        normal_text = "これは普通のテキストです。"
        
        # When
        result = clean_markdown_for_tts(normal_text)
        
        # Then
        assert result == normal_text


class TestLoadEnvFile:
    """load_env_file関数のテスト群"""

    def test_env_fileが存在しない場合は何もしない(self):
        """
        Given: .envファイルが存在しない環境
        When: load_env_file()を実行
        Then: 例外が発生せず正常に終了する
        """
        # Given (一時ディレクトリで実行)
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # When
                load_env_file()  # 例外が発生しないことを確認
                
                # Then
                # 例外が発生しなければOK
                assert True
                
            finally:
                os.chdir(original_cwd)

    def test_env_fileが存在する場合は環境変数が設定される(self):
        """
        Given: TEST_KEY=test_valueを含む.envファイル
        When: load_env_file()を実行
        Then: 環境変数TEST_KEYがtest_valueに設定される
        """
        # Given
        # load_env_file()の実装を直接テスト（project_rootに.envを配置）
        original_env_test = os.environ.get("TEST_KEY_FOR_TESTING")
        original_env_another = os.environ.get("ANOTHER_KEY_FOR_TESTING")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("TEST_KEY_FOR_TESTING=test_value\nANOTHER_KEY_FOR_TESTING=another_value")
            
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # When
                with patch('aibis_cloud_tools.utils.Path') as mock_path:
                    # プロジェクトルートを一時ディレクトリに設定
                    mock_path.return_value = Path(temp_dir)
                    load_env_file()
                
                # Then
                assert os.environ.get("TEST_KEY_FOR_TESTING") == "test_value"
                assert os.environ.get("ANOTHER_KEY_FOR_TESTING") == "another_value"
                
            finally:
                os.chdir(original_cwd)
                # 環境変数をクリーンアップ
                if original_env_test is None:
                    os.environ.pop("TEST_KEY_FOR_TESTING", None)
                else:
                    os.environ["TEST_KEY_FOR_TESTING"] = original_env_test
                    
                if original_env_another is None:
                    os.environ.pop("ANOTHER_KEY_FOR_TESTING", None)
                else:
                    os.environ["ANOTHER_KEY_FOR_TESTING"] = original_env_another


class TestGetDefaultModel:
    """get_default_model関数のテスト群"""

    def test_デフォルトモデルUUIDが返される(self):
        """
        Given: 特に条件なし
        When: get_default_model()を実行
        Then: 有効なUUID形式の文字列が返される
        """
        # Given/When
        result = get_default_model()
        
        # Then
        assert isinstance(result, str)
        assert len(result) > 0
        # UUID形式の簡単なチェック（ハイフンで区切られた形式）
        parts = result.split("-")
        assert len(parts) == 5  # UUID形式: 8-4-4-4-12

    def test_毎回同じ値が返される(self):
        """
        Given: 複数回の関数呼び出し
        When: get_default_model()を複数回実行
        Then: 常に同じ値が返される
        """
        # Given/When
        result1 = get_default_model()
        result2 = get_default_model()
        result3 = get_default_model()
        
        # Then
        assert result1 == result2 == result3


if __name__ == "__main__":
    # テストを実行
    pytest.main([__file__, "-v"])