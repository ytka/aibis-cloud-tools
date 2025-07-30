#!/usr/bin/env python3
"""
Aivis Cloud API を使用した音声合成・再生 CLI
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from lib import AivisCloudTTS, load_env_file, split_text_smart, get_default_model


def main():
    """メイン関数"""
    # .envファイルを読み込み
    load_env_file()
    
    # メイン実行時のみシグナル処理を設定
    def graceful_shutdown(signum, frame):
        print(f"\n🛑 シグナル {signum} を受信、正常終了中...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, graceful_shutdown)   # Ctrl-C
    signal.signal(signal.SIGTERM, graceful_shutdown)  # 終了シグナル
    
    parser = argparse.ArgumentParser(description="Aivis Cloud API を使用した音声合成・再生")

    # テキスト入力（どちらか必須）
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", "-t", help="合成するテキスト")
    text_group.add_argument("--text-file", "-tf", help="テキストファイルのパス")
    
    parser.add_argument("--api-key", "-k", help="API キー（環境変数 AIVIS_API_KEY からも取得可能）")

    # オプション引数
    parser.add_argument("--model-uuid", "-m", default=get_default_model(),
                       help=f"音声合成モデルのUUID（デフォルト: {get_default_model()}）")
    parser.add_argument("--speaker-uuid", "-s", help="話者のUUID")
    parser.add_argument("--style-name", "-n", help="スタイル名（例: Happy, Sad）")
    parser.add_argument("--format", "-f", default="mp3",
                       choices=["wav", "mp3", "flac", "aac", "opus"],
                       help="出力音声形式（デフォルト: mp3）")
    parser.add_argument("--rate", "-r", type=float, default=1.0,
                       help="話速（0.5-2.0、デフォルト: 1.0）")
    parser.add_argument("--intensity", "-i", type=float, default=1.0,
                       help="感情表現の強さ（0.0-2.0、デフォルト: 1.0）")
    parser.add_argument("--volume", "-v", type=float, default=1.0,
                       help="音量（0.0-2.0、デフォルト: 1.0）")
    parser.add_argument("--save-file", "-o", help="音声ファイルの保存先パス")
    parser.add_argument("--no-play", action="store_true", help="音声を再生しない")
    parser.add_argument("--realtime", action="store_true", help="リアルタイムストリーミング再生を有効にする")
    parser.add_argument("--no-wait", action="store_true", help="音声再生の終了を待たない（バックグラウンド再生）")
    
    # 長いテキスト分割オプション
    parser.add_argument("--max-chars", type=int, default=2000,
                       help="長いテキストの分割単位（デフォルト: 2000文字）")
    parser.add_argument("--split-pause", type=float, default=0,
                       help="分割間の一時停止秒数（デフォルト: 0秒）")
    parser.add_argument("--list-models", action="store_true", help="利用可能なモデル一覧を表示")

    args = parser.parse_args()

    # API キーの取得
    api_key = args.api_key or os.getenv("AIVIS_API_KEY")
    if not api_key:
        print("エラー: API キーが指定されていません")
        print("--api-key オプションで指定するか、環境変数 AIVIS_API_KEY を設定してください")
        sys.exit(1)

    try:
        client = AivisCloudTTS(api_key)

        # テキストの取得
        if args.text_file:
            try:
                with open(args.text_file, 'r', encoding='utf-8') as f:
                    text_content = f.read().strip()
                if not text_content:
                    print("エラー: テキストファイルが空です")
                    sys.exit(1)
                print(f"テキストファイル '{args.text_file}' を読み込みました")
            except FileNotFoundError:
                print(f"エラー: テキストファイル '{args.text_file}' が見つかりません")
                sys.exit(1)
            except UnicodeDecodeError:
                print(f"エラー: テキストファイル '{args.text_file}' の文字エンコーディングが不正です")
                sys.exit(1)
        else:
            text_content = args.text
        
        # 長いテキストの分割処理
        text_chunks = split_text_smart(text_content, args.max_chars)
        
        if len(text_chunks) > 1:
            print(f"📝 テキストを{len(text_chunks)}個のチャンクに分割しました（{args.max_chars}文字単位）")
            if args.split_pause > 0:
                print(f"⏸️  分割間隔: {args.split_pause}秒")

        # モデル一覧表示
        if args.list_models:
            print("利用可能な音声合成モデル:")
            models = client.list_models(limit=20)
            for model in models["aivm_models"]:
                print(f"  UUID: {model['aivm_model_uuid']}")
                print(f"  名前: {model['name']}")
                print(f"  説明: {model['description']}")
                print(f"  話者数: {len(model['speakers'])}")
                print()
            return

        # テキスト内容を表示（デバッグ用）
        print(f"合成対象テキスト（{len(text_content)}文字）:")
        print(f"「{text_content[:100]}{'...' if len(text_content) > 100 else ''}」")
        
        # 音声合成（チャンク処理）
        print("音声を合成中...")
        
        # チャンクごとに処理
        total_audio_data = b""
        for i, chunk_text in enumerate(text_chunks, 1):
            print(f"🔊 [{i}/{len(text_chunks)}] チャンク処理中... ({len(chunk_text)}文字)")
            
            if args.realtime and not args.no_play:
                # リアルタイムストリーミング再生
                print(f"🔊 [{i}/{len(text_chunks)}] リアルタイム再生中...")
                audio_data = client.synthesize_and_stream(
                    text=chunk_text,
                    model_uuid=args.model_uuid,
                    speaker_uuid=args.speaker_uuid,
                    style_name=args.style_name,
                    output_format=args.format,
                    speaking_rate=args.rate,
                    emotional_intensity=args.intensity,
                    volume=args.volume,
                    save_file=None,  # チャンクごとの保存は無効
                    enable_realtime_play=True,
                    no_wait=args.no_wait
                )
                print(f"✅ リアルタイム再生完了（{len(audio_data)} bytes）")
            else:
                # 従来の方式（全データ受信後に再生）
                audio_data = client.synthesize_speech(
                    text=chunk_text,
                    model_uuid=args.model_uuid,
                    speaker_uuid=args.speaker_uuid,
                    style_name=args.style_name,
                    output_format=args.format,
                    speaking_rate=args.rate,
                    emotional_intensity=args.intensity,
                    volume=args.volume
                )

                print(f"チャンク音声データを取得しました（{len(audio_data)} bytes）")
                total_audio_data += audio_data

                # 音声再生
                if not args.no_play:
                    print(f"🎵 [{i}/{len(text_chunks)}] 音声を再生中...")
                    temp_file = client.play_audio(audio_data, args.format)
                    if temp_file:
                        print(f"音声ファイル: {temp_file}")
                    print(f"✅ 音声再生完了")
            
            # 分割間の一時停止（最後のチャンクでない場合）
            if i < len(text_chunks) and args.split_pause > 0:
                print(f"⏸️  {args.split_pause}秒間一時停止...")
                time.sleep(args.split_pause)

        # 全チャンクの音声データをファイル保存（非リアルタイム時のみ）
        if args.save_file and not args.realtime and total_audio_data:
            with open(args.save_file, "wb") as f:
                f.write(total_audio_data)
            print(f"💾 音声ファイルを保存しました: {args.save_file} ({len(total_audio_data)} bytes)")

        print("完了")

    except requests.exceptions.HTTPError as e:
        print(f"API エラー: {e}")
        if e.response.status_code == 401:
            print("API キーが無効です")
        elif e.response.status_code == 402:
            print("クレジット残高が不足しています")
        elif e.response.status_code == 404:
            print("指定されたモデルUUIDが見つかりません")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ネットワークエラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()