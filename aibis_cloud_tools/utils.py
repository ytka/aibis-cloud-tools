#!/usr/bin/env python3
"""
共通ユーティリティ関数
"""

import os
import re
from pathlib import Path


def load_env_file():
    """プロジェクトルートの.envファイルを読み込む"""
    # lib/utils.pyから見たプロジェクトルート
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


def split_text_smart(text, max_chars=2000):
    """テキストを賢く分割する（文章境界を考慮）"""
    if not text:  # 空文字列チェックを追加
        return []
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # 文単位で分割（。！？で終わる文を優先）
    sentences = []
    temp_sentence = ""
    
    for char in text:
        temp_sentence += char
        if char in '。！？\n':
            sentences.append(temp_sentence.strip())
            temp_sentence = ""
    
    # 残りがあれば追加
    if temp_sentence.strip():
        sentences.append(temp_sentence.strip())
    
    # 文をチャンクに結合
    for sentence in sentences:
        # 文が長すぎる場合は強制分割
        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # 長すぎる文を強制分割
            while len(sentence) > max_chars:
                chunks.append(sentence[:max_chars])
                sentence = sentence[max_chars:]
            
            if sentence:
                current_chunk = sentence
        
        # 文を追加してもmax_charsを超えない場合
        elif len(current_chunk + sentence) <= max_chars:
            current_chunk += sentence
        
        # 超える場合は現在のチャンクを確定して新しいチャンクを開始
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
    
    # 最後のチャンクを追加
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def get_default_model():
    """デフォルトの音声合成モデルUUIDを返す"""
    # openapi.json の例で使用されているモデル
    return "a59cb814-0083-4369-8542-f51a29e72af7"


def clean_markdown_for_tts(text):
    """Markdown記法をTTS読み上げ用にクリーニング"""
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