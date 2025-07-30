#!/usr/bin/env python3
"""
Aivis Cloud TTS クライアントライブラリ
"""

import json
import os
import subprocess
import sys
import tempfile
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
        content_type = response.headers.get('Content-Type', 'unknown')
        
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
        content_type = response.headers.get('Content-Type', 'unknown')

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
            except Exception as e:
                enable_realtime_play = False
                temp_file_path = None

        # ストリーミング受信と書き込み
        
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
                            try:
                                audio_player = subprocess.Popen(
                                    ["afplay", temp_file_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                )
                            except Exception as e:
                                # afplayの開始に失敗した場合はリアルタイム再生を無効化
                                enable_realtime_play = False
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

        # データ受信完了

        # リアルタイム再生の終了を待つ
        if audio_player:
            if no_wait:
                # バックグラウンド再生の場合は一時ファイルを残す（注意：手動削除が必要）
                pass
            else:
                # 音声の長さを推定（MP3の場合、おおよその計算）
                # 128kbps MP3の場合: 1秒 ≈ 16KB、安全のため余裕をもたせる
                estimated_duration = max(30, (len(audio_data) / 16000) * 1.5 + 10)  # 最低30秒、余裕をもって1.5倍+10秒
                
                try:
                    return_code = audio_player.wait(timeout=estimated_duration)
                except subprocess.TimeoutExpired:
                    audio_player.terminate()
                    try:
                        audio_player.wait(timeout=5)  # 強制終了の完了を5秒待機
                    except subprocess.TimeoutExpired:
                        audio_player.kill()  # さらに強制終了
                except KeyboardInterrupt:
                    audio_player.terminate()
                    try:
                        audio_player.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        audio_player.kill()
                    raise
                except Exception as e:
                    # リアルタイム再生の終了処理でエラーが発生した場合
                    pass
                finally:
                    # 一時ファイル削除
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.unlink(temp_file_path)
                        except OSError:
                            pass

        # 通常の保存処理
        if save_file and not enable_realtime_play:
            with open(save_file, "wb") as f:
                f.write(audio_data)

        return audio_data

    def _handle_http_error(self, response):
        """HTTPエラーの詳細処理"""
        status_code = response.status_code
        
        error_messages = {
            503: "Aivis Cloud APIで障害が発生しています (503 Service Unavailable)。しばらく時間を置いてから再度お試しください。",
            429: "API制限に達しました (429 Too Many Requests)。少し時間を置いてから再度お試しください。",
            401: "認証エラー (401 Unauthorized)。AIVIS_API_KEY環境変数を確認してください。",
            400: "リクエストエラー (400 Bad Request)。テキスト内容やパラメータを確認してください。",
            500: "サーバー内部エラー (500 Internal Server Error)。Aivis Cloud側で問題が発生している可能性があります。"
        }
        
        base_message = error_messages.get(status_code, f"API エラーが発生しました: HTTP {status_code}")
        
        # エラーレスポンスの詳細を取得
        error_detail = ""
        try:
            error_detail = response.text
        except:
            pass
        
        # カスタム例外として投げる
        full_message = base_message
        if error_detail:
            full_message += f" 詳細: {error_detail}"
        
        raise Exception(full_message)

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
                # サポートされていないプラットフォームの場合は一時ファイルパスを返す
                return temp_file_path
        except KeyboardInterrupt:
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