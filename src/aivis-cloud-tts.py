#!/usr/bin/env python3
"""
Aivis Cloud API を使用した音声合成・再生スクリプト
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from typing import Optional
import requests


class AivisCloudTTS:
    """Aivis Cloud TTS クライアント"""

    def __init__(self, api_key: str):
        """
        Aivis Cloud TTS クライアントを初期化

        Args:
            api_key: Aivis Cloud API の API キー
        """
        self.api_key = api_key
        self.base_url = "https://api.aivis-project.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def list_models(self, limit: int = 10) -> dict:
        """
        利用可能な音声合成モデルを取得

        Args:
            limit: 取得するモデル数

        Returns:
            モデル検索結果
        """
        url = f"{self.base_url}/aivm-models/search"
        params = {"limit": limit, "sort": "download"}

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def synthesize_speech(
        self,
        text: str,
        model_uuid: str,
        speaker_uuid: Optional[str] = None,
        style_name: Optional[str] = None,
        output_format: str = "mp3",
        speaking_rate: float = 1.0,
        emotional_intensity: float = 1.0,
        volume: float = 1.0
    ) -> bytes:
        """
        テキストから音声を合成

        Args:
            text: 合成するテキスト
            model_uuid: 音声合成モデルのUUID
            speaker_uuid: 話者のUUID（オプション）
            style_name: スタイル名（オプション）
            output_format: 出力形式（wav, mp3, flac, aac, opus）
            speaking_rate: 話速（0.5-2.0）
            emotional_intensity: 感情表現の強さ（0.0-2.0）
            volume: 音量（0.0-2.0）

        Returns:
            合成された音声データ
        """
        url = f"{self.base_url}/tts/synthesize"

        payload = {
            "model_uuid": model_uuid,
            "use_ssml": True,
            "text": text,
            "output_format": output_format,
            #"speaking_rate": speaking_rate,
            # "emotional_intensity": emotional_intensity,
            "volume": volume
        }

        if speaker_uuid:
            payload["speaker_uuid"] = speaker_uuid

        if style_name:
            payload["style_name"] = style_name

        response = requests.post(url, headers=self.headers, json=payload, stream=True)
        response.raise_for_status()

        # レスポンスヘッダーを確認（デバッグ用）
        if 'Content-Type' in response.headers:
            print(f"Response Content-Type: {response.headers['Content-Type']}")
        
        # ストリーミングレスポンスを読み込み
        audio_data = b""
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                audio_data += chunk

        # JSON エラーレスポンスかチェック
        if audio_data.startswith(b'{'):
            try:
                error_data = json.loads(audio_data.decode('utf-8'))
                if 'status_code' in error_data and 'detail' in error_data:
                    raise Exception(f"API Error: {error_data['status_code']} - {error_data['detail']}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # JSON でない場合は通常の音声データとして処理

        return audio_data

    def synthesize_and_stream(
        self,
        text: str,
        model_uuid: str,
        speaker_uuid: Optional[str] = None,
        style_name: Optional[str] = None,
        output_format: str = "mp3",
        speaking_rate: float = 1.0,
        emotional_intensity: float = 1.0,
        volume: float = 1.0,
        save_file: Optional[str] = None,
        enable_realtime_play: bool = True,
        no_wait: bool = False
    ) -> bytes:
        """
        テキストから音声を合成し、リアルタイム再生

        Args:
            text: 合成するテキスト
            model_uuid: 音声合成モデルのUUID
            speaker_uuid: 話者のUUID（オプション）
            style_name: スタイル名（オプション）
            output_format: 出力形式（wav, mp3, flac, aac, opus）
            speaking_rate: 話速（0.5-2.0）
            emotional_intensity: 感情表現の強さ（0.0-2.0）
            volume: 音量（0.0-2.0）
            save_file: 保存先ファイルパス
            enable_realtime_play: リアルタイム再生を有効にするか
            no_wait: 音声再生の終了を待たない

        Returns:
            合成された音声データ
        """
        url = f"{self.base_url}/tts/synthesize"

        payload = {
            "model_uuid": model_uuid,
            "use_ssml": True,
            "text": text,
            "output_format": output_format,
            "speaking_rate": speaking_rate,
            "emotional_intensity": emotional_intensity,
            "volume": volume
        }

        if speaker_uuid:
            payload["speaker_uuid"] = speaker_uuid

        if style_name:
            payload["style_name"] = style_name

        response = requests.post(url, headers=self.headers, json=payload, stream=True)
        response.raise_for_status()

        # レスポンスヘッダーを確認
        if 'Content-Type' in response.headers:
            print(f"Response Content-Type: {response.headers['Content-Type']}")

        # リアルタイム再生用の準備
        audio_data = b""
        audio_player = None
        temp_file_path = None
        
        if enable_realtime_play and output_format == "mp3" and sys.platform == "darwin":
            # macOSでMP3のリアルタイム再生を試行
            try:
                file_extension = "mp3"
                temp_file = tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False)
                temp_file_path = temp_file.name
                temp_file.close()
                print(f"一時ファイルを作成: {temp_file_path}")
                
                print("リアルタイム再生を準備中...")
            except Exception as e:
                print(f"リアルタイム再生の準備に失敗: {e}")
                enable_realtime_play = False
                temp_file_path = None

        # ストリーミング受信と書き込み
        print(f"ストリーミング受信開始 (realtime: {enable_realtime_play})")
        
        if enable_realtime_play and temp_file_path:
            # リアルタイム再生用の書き込み
            with open(temp_file_path, "wb") as f:
                chunk_count = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        audio_data += chunk
                        f.write(chunk)
                        f.flush()  # 即座にディスクに書き込み
                        chunk_count += 1
                        
                        # 最初のチャンクを受信したらafplayを開始
                        if chunk_count == 1 and not audio_player:
                            print("最初のチャンクを受信、afplayを開始...")
                            try:
                                audio_player = subprocess.Popen(
                                    ["afplay", temp_file_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                )
                                print("afplayプロセスを開始しました")
                            except Exception as e:
                                print(f"afplayの開始に失敗: {e}")
                        
                        if chunk_count % 10 == 0:
                            print(f"受信チャンク数: {chunk_count}, データサイズ: {len(audio_data)} bytes")
        else:
            # 通常の書き込み
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    audio_data += chunk
                    if save_file:
                        # 保存ファイルがある場合は後で書き込み
                        pass

        # JSON エラーレスポンスかチェック
        if audio_data.startswith(b'{'):
            try:
                error_data = json.loads(audio_data.decode('utf-8'))
                if 'status_code' in error_data and 'detail' in error_data:
                    raise Exception(f"API Error: {error_data['status_code']} - {error_data['detail']}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        print(f"データ受信完了: {len(audio_data)} bytes")

        # リアルタイム再生の終了を待つ
        if audio_player:
            if no_wait:
                print("バックグラウンドで音声を再生中です...")
                print(f"一時ファイル: {temp_file_path}")
                print("注意: 一時ファイルは手動で削除してください")
            else:
                # 音声の長さを推定（MP3の場合、おおよその計算）
                # 128kbps MP3の場合: 1秒 ≈ 16KB、安全のため余裕をもたせる
                estimated_duration = max(30, (len(audio_data) / 16000) * 1.5 + 10)  # 最低30秒、余裕をもって1.5倍+10秒
                print(f"afplayの終了を待機中... (推定時間: {estimated_duration:.1f}秒)")
                
                try:
                    return_code = audio_player.wait(timeout=estimated_duration)
                    print(f"afplayが終了しました (return code: {return_code})")
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)  # 一時ファイル削除
                        print("一時ファイルを削除しました")
                except subprocess.TimeoutExpired:
                    print(f"afplayがタイムアウトしました ({estimated_duration:.1f}秒)、強制終了します")
                    audio_player.terminate()
                    try:
                        audio_player.wait(timeout=5)  # 強制終了の完了を5秒待機
                    except subprocess.TimeoutExpired:
                        audio_player.kill()  # さらに強制終了
                        print("afplayを強制終了しました")
                except Exception as e:
                    print(f"リアルタイム再生の終了処理でエラー: {e}")

        # 通常の保存処理
        if save_file and not enable_realtime_play:
            with open(save_file, "wb") as f:
                f.write(audio_data)
            print(f"ファイルを保存しました: {save_file}")

        return audio_data

    def play_audio(self, audio_data: bytes, output_format: str = "mp3"):
        """
        音声データを再生

        Args:
            audio_data: 音声データ
            output_format: 音声形式
        """
        # 一時ファイルに音声データを保存
        file_extension = output_format
        if output_format == "opus":
            file_extension = "ogg"

        with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name

        try:
            # macOSの場合はafplayを使用
            if sys.platform == "darwin":
                subprocess.run(["afplay", temp_file_path], check=True)
            # Linuxの場合はplayやaplayを試行
            elif sys.platform == "linux":
                try:
                    subprocess.run(["play", temp_file_path], check=True)
                except FileNotFoundError:
                    subprocess.run(["aplay", temp_file_path], check=True)
            # Windowsの場合
            elif sys.platform == "win32":
                import winsound
                winsound.PlaySound(temp_file_path, winsound.SND_FILENAME)
            else:
                print(f"音声ファイルが保存されました: {temp_file_path}")
                print("手動で再生してください")
                return temp_file_path
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass

        return None


def get_default_model():
    """デフォルトの音声合成モデルUUIDを返す"""
    # openapi.json の例で使用されているモデル
    return "a59cb814-0083-4369-8542-f51a29e72af7"


def main():
    """メイン関数"""
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
        
        # 音声合成
        print("音声を合成中...")
        
        if args.realtime and not args.no_play:
            # リアルタイムストリーミング再生
            audio_data = client.synthesize_and_stream(
                text=text_content,
                model_uuid=args.model_uuid,
                speaker_uuid=args.speaker_uuid,
                style_name=args.style_name,
                output_format=args.format,
                speaking_rate=args.rate,
                emotional_intensity=args.intensity,
                volume=args.volume,
                save_file=args.save_file,
                enable_realtime_play=True,
                no_wait=args.no_wait
            )
        else:
            # 従来の方式（全データ受信後に再生）
            audio_data = client.synthesize_speech(
                text=text_content,
                model_uuid=args.model_uuid,
                speaker_uuid=args.speaker_uuid,
                style_name=args.style_name,
                output_format=args.format,
                speaking_rate=args.rate,
                emotional_intensity=args.intensity,
                volume=args.volume
            )

            print(f"音声データを取得しました（{len(audio_data)} bytes）")

            # ファイル保存
            if args.save_file:
                with open(args.save_file, "wb") as f:
                    f.write(audio_data)
                print(f"音声ファイルを保存しました: {args.save_file}")

            # 音声再生
            if not args.no_play:
                print("音声を再生中...")
                temp_file = client.play_audio(audio_data, args.format)
                if temp_file:
                    print(f"音声ファイル: {temp_file}")

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