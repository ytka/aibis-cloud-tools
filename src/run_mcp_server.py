#!/usr/bin/env python3
"""
Aivis Cloud TTS MCP Server using official MCP framework
"""

import asyncio
import os
import signal
import subprocess
import tempfile
import sys
from typing import Optional, Any

import requests
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types


# TTS functions
def get_headers() -> dict:
    """Get API headers"""
    api_key = os.getenv("AIVIS_API_KEY", "")
    if not api_key:
        raise ValueError("AIVIS_API_KEY environment variable is required")
    
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def synthesize_speech(
    text: str, 
    model_uuid: Optional[str] = None, 
    emotional_intensity: float = 1.0, 
    volume: float = 1.0
) -> bytes:
    """Synthesize speech from text"""
    url = "https://api.aivis-project.com/v1/tts/synthesize"
    default_model_uuid = "a59cb814-0083-4369-8542-f51a29e72af7"
    
    payload = {
        "model_uuid": model_uuid or default_model_uuid,
        "text": text,
        "use_ssml": True,
        "output_format": "mp3",
        "emotional_intensity": emotional_intensity,
        "volume": volume
    }
    
    response = requests.post(url, headers=get_headers(), json=payload, stream=True, timeout=30)
    response.raise_for_status()
    
    audio_data = b""
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            audio_data += chunk
    
    # Validate audio data
    if len(audio_data) == 0:
        raise ValueError("Received empty audio data from API")
    
    # Check if it looks like valid audio data (MP3 should start with specific bytes)
    if not audio_data.startswith(b'\xff\xfb') and not audio_data.startswith(b'\xff\xf3') and not audio_data.startswith(b'ID3'):
        raise ValueError(f"Audio data doesn't appear to be valid MP3 format (starts with: {audio_data[:10].hex()})")
    
    return audio_data


def play_audio(audio_data: bytes) -> dict:
    """Play audio synchronously"""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_file.write(audio_data)
        temp_file_path = temp_file.name
    
    try:
        if sys.platform == "darwin":
            # macOS - use afplay with better error handling
            result = subprocess.run(
                ["afplay", temp_file_path], 
                check=False,  # Don't raise exception immediately
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                # Try to get more details about the error
                error_msg = f"afplay failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                if result.stdout:
                    error_msg += f" (stdout: {result.stdout.strip()})"
                
                # Check if file exists and has content
                file_size = os.path.getsize(temp_file_path) if os.path.exists(temp_file_path) else 0
                error_msg += f" (audio file size: {file_size} bytes)"
                
                raise subprocess.CalledProcessError(result.returncode, "afplay", error_msg)
                
        elif sys.platform == "linux":
            try:
                result = subprocess.run(["play", temp_file_path], check=False, capture_output=True, text=True)
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, "play", result.stderr)
            except FileNotFoundError:
                result = subprocess.run(["aplay", temp_file_path], check=False, capture_output=True, text=True)
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, "aplay", result.stderr)
                    
        elif sys.platform == "win32":
            import winsound
            winsound.PlaySound(temp_file_path, winsound.SND_FILENAME)
        
        return {"status": "completed", "message": "Audio playback completed"}
    
    except Exception as e:
        # Return error details instead of raising
        return {
            "status": "error", 
            "message": f"Audio playback failed: {str(e)}",
            "audio_size": len(audio_data),
            "temp_file": temp_file_path
        }
    
    finally:
        try:
            os.unlink(temp_file_path)
        except OSError:
            pass


# MCP Server setup
server = Server("aivis-tts")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="speak",
            description="Synthesize and play single or multiple texts sequentially using Aivis Cloud TTS API",
            inputSchema={
                "type": "object",
                "properties": {
                    # Single text mode (backward compatibility)
                    "text": {
                        "type": "string",
                        "description": "Single text to synthesize and play"
                    },
                    "model_uuid": {
                        "type": "string",
                        "description": "Voice model UUID for single text (optional)"
                    },
                    "emotional_intensity": {
                        "type": "number",
                        "description": "Emotional intensity for single text (0.0-2.0)",
                        "minimum": 0.0,
                        "maximum": 2.0
                    },
                    "volume": {
                        "type": "number",
                        "description": "Volume level for single text (0.0-2.0)",
                        "minimum": 0.0,
                        "maximum": 2.0
                    },
                    # Multiple texts mode - flexible array
                    "speaks": {
                        "type": "array",
                        "description": "Array of speech segments to be played sequentially",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Text to synthesize"
                                },
                                "model_uuid": {
                                    "type": "string",
                                    "description": "Voice model UUID (optional)"
                                },
                                "emotional_intensity": {
                                    "type": "number",
                                    "description": "Emotional intensity (0.0-2.0)",
                                    "minimum": 0.0,
                                    "maximum": 2.0
                                },
                                "volume": {
                                    "type": "number",
                                    "description": "Volume level (0.0-2.0)",
                                    "minimum": 0.0,
                                    "maximum": 2.0
                                }
                            },
                            "required": ["text"]
                        },
                        "minItems": 1
                    }
                },
                "anyOf": [
                    {"required": ["text"]},
                    {"required": ["speaks"]}
                ]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle tool calls"""
    if name == "speak":
        try:
            # Check for single text mode (backward compatibility)
            if "text" in arguments:
                speech_segments = [{
                    "text": arguments.get("text", ""),
                    "model_uuid": arguments.get("model_uuid"),
                    "emotional_intensity": arguments.get("emotional_intensity", 1.0),
                    "volume": arguments.get("volume", 1.0)
                }]
            elif "speaks" in arguments:
                # Multiple speech mode - use speaks array
                speech_segments = []
                for segment in arguments["speaks"]:
                    speech_segments.append({
                        "text": segment.get("text", ""),
                        "model_uuid": segment.get("model_uuid"),
                        "emotional_intensity": segment.get("emotional_intensity", 1.0),
                        "volume": segment.get("volume", 1.0)
                    })
            else:
                speech_segments = []
            
            if not speech_segments:
                raise ValueError("No text provided in any speak parameter")
            
            # Process each speech segment sequentially
            results = []
            total_audio_size = 0
            
            for i, segment in enumerate(speech_segments, 1):
                if not segment["text"]:
                    continue
                
                # Synthesize and play audio for this segment
                audio_data = synthesize_speech(
                    segment["text"], 
                    segment["model_uuid"], 
                    segment["emotional_intensity"], 
                    segment["volume"]
                )
                play_result = play_audio(audio_data)
                
                segment_result = {
                    "segment": i,
                    "text": segment["text"],
                    "audio_size": len(audio_data),
                    "playback_result": play_result
                }
                results.append(segment_result)
                total_audio_size += len(audio_data)
            
            final_result = {
                "success": True,
                "message": f"Successfully synthesized and played {len(results)} speech segments totaling {total_audio_size} bytes",
                "segments_count": len(results),
                "total_audio_size": total_audio_size,
                "segments": results
            }
            
            return [types.TextContent(type="text", text=str(final_result))]
        
        except Exception as e:
            error_result = {"success": False, "error": str(e)}
            return [types.TextContent(type="text", text=str(error_result))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Main entry point"""
    # メイン実行時のみシグナル処理を設定
    def graceful_shutdown(signum, frame):
        print(f"\n🛑 シグナル {signum} を受信、MCP Server正常終了中...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, graceful_shutdown)   # Ctrl-C
    signal.signal(signal.SIGTERM, graceful_shutdown)  # 終了シグナル
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="aivis-tts",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 MCP Server終了")
        sys.exit(0)