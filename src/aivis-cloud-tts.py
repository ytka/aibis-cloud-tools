#!/usr/bin/env python3
"""
Aivis Cloud API を使用した音声合成・再生スクリプト
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
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
        
        # 詳細なHTTPエラーハンドリング
        if response.status_code != 200:
            self._handle_http_error(response)
            response.raise_for_status()  # 例外を発生させる

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
        
        # 詳細なHTTPエラーハンドリング
        if response.status_code != 200:
            self._handle_http_error(response)
            response.raise_for_status()  # 例外を発生させる

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
            # 32KBバッファリング改善：十分なデータが蓄積されてからafplayを開始
            MIN_BUFFER_SIZE = 32 * 1024  # 32KB - MP3ヘッダー + 音声データの完整性を確保
            
            with open(temp_file_path, "wb") as f:
                chunk_count = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        audio_data += chunk
                        f.write(chunk)
                        f.flush()  # 即座にディスクに書き込み
                        chunk_count += 1
                        
                        # 32KB以上のデータが蓄積されたらafplayを開始
                        if len(audio_data) >= MIN_BUFFER_SIZE and not audio_player:
                            print(f"十分なデータを受信（{len(audio_data)} bytes >= {MIN_BUFFER_SIZE} bytes）、afplayを開始...")
                            try:
                                audio_player = subprocess.Popen(
                                    ["afplay", temp_file_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                )
                                print("afplayプロセスを開始しました（音声冒頭飛び対策済み）")
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
                except subprocess.TimeoutExpired:
                    print(f"afplayがタイムアウトしました ({estimated_duration:.1f}秒)、強制終了します")
                    audio_player.terminate()
                    try:
                        audio_player.wait(timeout=5)  # 強制終了の完了を5秒待機
                    except subprocess.TimeoutExpired:
                        audio_player.kill()  # さらに強制終了
                        print("afplayを強制終了しました")
                except KeyboardInterrupt:
                    print("\n🛑 音声再生を中断しています...")
                    audio_player.terminate()
                    try:
                        audio_player.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        audio_player.kill()
                    raise
                except Exception as e:
                    print(f"リアルタイム再生の終了処理でエラー: {e}")
                finally:
                    # 一時ファイル削除
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.unlink(temp_file_path)
                            print("一時ファイルを削除しました")
                        except OSError:
                            pass

        # 通常の保存処理
        if save_file and not enable_realtime_play:
            with open(save_file, "wb") as f:
                f.write(audio_data)
            print(f"ファイルを保存しました: {save_file}")

        return audio_data

    def _handle_http_error(self, response):
        """HTTPエラーの詳細処理"""
        status_code = response.status_code
        
        if status_code == 503:
            print("🚨 Aivis Cloud APIで障害が発生しています (503 Service Unavailable)")
            print("しばらく時間を置いてから再度お試しください")
        elif status_code == 429:
            print("⏱️ API制限に達しました (429 Too Many Requests)")
            print("少し時間を置いてから再度お試しください")
        elif status_code == 401:
            print("🔑 認証エラー (401 Unauthorized)")
            print("AIVIS_API_KEY環境変数を確認してください")
        elif status_code == 400:
            print("📝 リクエストエラー (400 Bad Request)")
            print("テキスト内容やパラメータを確認してください")
        elif status_code == 500:
            print("🔥 サーバー内部エラー (500 Internal Server Error)")
            print("Aivis Cloud側で問題が発生している可能性があります")
        else:
            print(f"❌ API エラーが発生しました: HTTP {status_code}")
        
        # エラーレスポンスの詳細があれば表示
        try:
            error_detail = response.text
            if error_detail:
                print(f"詳細: {error_detail}")
        except:
            pass

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
                proc = subprocess.Popen(["afplay", temp_file_path])
                proc.wait()  # 完了を待つ
            # Linuxの場合はplayやaplayを試行
            elif sys.platform == "linux":
                try:
                    proc = subprocess.Popen(["play", temp_file_path])
                    proc.wait()
                except FileNotFoundError:
                    proc = subprocess.Popen(["aplay", temp_file_path])
                    proc.wait()
            # Windowsの場合
            elif sys.platform == "win32":
                import winsound
                winsound.PlaySound(temp_file_path, winsound.SND_FILENAME)
            else:
                print(f"音声ファイルが保存されました: {temp_file_path}")
                print("手動で再生してください")
                return temp_file_path
        except KeyboardInterrupt:
            print("\n🛑 音声再生を中断しています...")
            if 'proc' in locals() and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            raise
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass

        return None


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


def split_text_smart(text, max_chars=2000):
    """テキストを賢く分割する（文章境界を考慮）"""
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
            
            # 分割間の一時停止（最後のチャンクでない場合）
            if i < len(text_chunks) and args.split_pause > 0:
                print(f"⏸️  {args.split_pause}秒間一時停止...")
                import time
                time.sleep(args.split_pause)

        # 全チャンクの音声データをファイル保存（非リアルタイム時のみ）
        if args.save_file and not args.realtime and total_audio_data:
            with open(args.save_file, "wb") as f:
                f.write(total_audio_data)
            print(f"音声ファイルを保存しました: {args.save_file} ({len(total_audio_data)} bytes)")

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