# app/services/audio_service.py
import openai
import os
from typing import Dict, Any
from pathlib import Path

class AudioTranscriptionService:
    """Service for audio transcription using OpenAI Whisper API"""
    
    def __init__(self, api_key: str):
        openai.api_key = api_key
    
    async def transcribe_audio(self, audio_file_path: str, language: str = "ro") -> str:
        """
        Transcribe audio file using OpenAI Whisper API.
        
        Args:
            audio_file_path: Path to audio file
            language: Language code (ro for Romanian)
        
        Returns:
            Transcribed text
        """
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="text"
                )
            return transcript
        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")
    
    async def transcribe_with_timestamps(
        self, 
        audio_file_path: str, 
        language: str = "ro"
    ) -> Dict[str, Any]:
        """
        Transcribe with word-level timestamps for future real-time streaming.
        
        Args:
            audio_file_path: Path to audio file
            language: Language code (ro for Romanian)
        
        Returns:
            Dict with transcript and timestamps
        """
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",  # Includes timestamps
                    timestamp_granularities=["word"]  # For future streaming
                )
            return {
                "text": transcript.text,
                "segments": transcript.segments if hasattr(transcript, 'segments') else [],
                "language": transcript.language,
                "duration": transcript.duration if hasattr(transcript, 'duration') else None
            }
        except Exception as e:
            raise Exception(f"Transcription with timestamps failed: {str(e)}")