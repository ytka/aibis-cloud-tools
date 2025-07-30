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
from pathlib import Path
from typing import Optional, Any

import requests
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aibis_cloud_tools import AivisCloudTTS, get_default_model, split_text_smart


# Initialize TTS client
def get_tts_client() -> AivisCloudTTS:
    """Get TTS client instance"""
    api_key = os.getenv("AIVIS_API_KEY", "")
    if not api_key:
        raise ValueError("AIVIS_API_KEY environment variable is required")
    return AivisCloudTTS(api_key)


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
                
                # 長いテキストの場合は分割処理
                text_chunks = split_text_smart(segment["text"], 3000)
                
                if len(text_chunks) > 1:
                    print(f"📝 セグメント{i}: テキストを{len(text_chunks)}個のチャンクに分割")
                
                # 各チャンクを順次処理
                chunk_results = []
                segment_audio_size = 0
                
                for chunk_idx, chunk_text in enumerate(text_chunks, 1):
                    # Synthesize and play audio for this chunk using AivisCloudTTS
                    tts_client = get_tts_client()
                    audio_data = tts_client.synthesize_speech(
                        text=chunk_text,
                        model_uuid=segment["model_uuid"] or get_default_model(),
                        emotional_intensity=segment["emotional_intensity"],
                        volume=segment["volume"]
                    )
                    
                    # Play audio using the TTS client (非同期再生)
                    try:
                        proc, temp_file = tts_client.play_audio_async(audio_data, "mp3")
                        try:
                            proc.wait()  # プロセス完了を待機
                            play_result = {"status": "completed", "message": f"Chunk {chunk_idx}/{len(text_chunks)} playback completed"}
                        except Exception as wait_error:
                            play_result = {
                                "status": "error", 
                                "message": f"Chunk {chunk_idx}/{len(text_chunks)} playback wait failed: {str(wait_error)}",
                                "audio_size": len(audio_data)
                            }
                        finally:
                            # 一時ファイルのクリーンアップ
                            if temp_file and os.path.exists(temp_file):
                                try:
                                    os.unlink(temp_file)
                                except OSError:
                                    pass
                    except Exception as e:
                        play_result = {
                            "status": "error", 
                            "message": f"Chunk {chunk_idx}/{len(text_chunks)} playback failed: {str(e)}",
                            "audio_size": len(audio_data)
                        }
                    
                    chunk_result = {
                        "chunk": chunk_idx,
                        "text": chunk_text,
                        "audio_size": len(audio_data),
                        "playback_result": play_result
                    }
                    chunk_results.append(chunk_result)
                    segment_audio_size += len(audio_data)
                
                segment_result = {
                    "segment": i,
                    "text": segment["text"],
                    "chunks_count": len(text_chunks),
                    "audio_size": segment_audio_size,
                    "chunks": chunk_results
                }
                results.append(segment_result)
                total_audio_size += segment_audio_size
            
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