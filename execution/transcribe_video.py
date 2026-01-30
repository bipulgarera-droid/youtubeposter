#!/usr/bin/env python3
"""
Video Transcription Script
Uses Groq Whisper API with yt-dlp audio download.
Falls back to YouTube Transcript API for videos with existing captions.
"""

import os
import re
import json
import argparse
import tempfile
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    # If already just an ID
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def download_audio(video_id: str, output_path: str) -> str:
    """Download audio from YouTube video using yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Use yt-dlp to download audio only
    # Added anti-bot bypass measures
    cmd = [
        "yt-dlp",
        "-x",  # Extract audio
        "--audio-format", "mp3",
        "--audio-quality", "5",  # Medium quality (smaller file)
        "-o", output_path,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        # Bypass "Sign in to confirm you're not a bot"
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "--extractor-args", "youtube:player_client=android",
        url
    ]

    # Check for cookies.txt in acceptable locations
    cookies_path = None
    if os.path.exists("cookies.txt"):
        cookies_path = "cookies.txt"
    elif os.path.exists("../cookies.txt"):
        cookies_path = "../cookies.txt"
    
    if cookies_path:
        cmd.extend(["--cookies", cookies_path])
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to download audio: {e.stderr.decode()}")


def transcribe_with_groq(audio_path: str) -> str:
    """Transcribe audio using Groq Whisper API."""
    from groq import Groq
    
    client = Groq(api_key=GROQ_API_KEY)
    
    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), audio_file.read()),
            model="whisper-large-v3",
            response_format="text"
        )
    
    return transcription


def try_youtube_transcript_api(video_id: str) -> dict:
    """Try to get transcript from YouTube's built-in captions (Manual OR Auto-Generated)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Instantiate the API (Required for v1.2.4+)
        yt_api = YouTubeTranscriptApi()
        
        # Method 1: Robust 'list' (Finds manual or auto-generated)
        try:
            transcript_list = yt_api.list(video_id)
            
            # Try to find English (manual or auto)
            # This is robust: looks for 'en', 'en-US', etc.
            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            
            # Fetch the actual data
            transcript_data = transcript.fetch()
            
            full_text = ' '.join([segment['text'] for segment in transcript_data])
            return {
                'success': True,
                'text': full_text,
                'method': 'youtube_captions_robust'
            }
            
        except Exception as e:
            # Fallback to simple fetch if listing fails
            print(f"  (Robust transcript fetch failed: {e}, trying simple fetch...)")
            pass

        # Method 2: Simple fetch (Legacy)
        # Note: In new API this is api.fetch(video_id)
        fetched_transcript = yt_api.fetch(video_id)
        # It usually returns the list of dicts directly
        full_text = ' '.join([segment['text'] for segment in fetched_transcript])
        
        return {
            'success': True,
            'text': full_text,
            'method': 'youtube_captions_simple'
        }
    except Exception as e:
        print(f"  (All YouTube caption methods failed: {e})")
        return {'success': False}


def get_transcript(video_id: str) -> dict:
    """
    Get transcript using Groq Whisper API.
    Downloads audio with yt-dlp, then transcribes with Groq.
    """
    print(f"Fetching transcript for video: {video_id}...")
    
    # First try YouTube's built-in captions (fastest, no API cost)
    yt_result = try_youtube_transcript_api(video_id)
    if yt_result.get('success'):
        print("  ✓ Got transcript from YouTube captions")
        return {
            'text': yt_result['text'],
            'word_count': len(yt_result['text'].split()),
            'method': 'youtube_captions'
        }
    
    print("  → YouTube captions unavailable, using Groq Whisper...")
    
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set - cannot transcribe via Whisper")
    
    # Download audio to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, f"{video_id}.mp3")
        
        print("  → Downloading audio...")
        download_audio(video_id, audio_path)
        
        # Check file size (Groq limit is 25MB)
        file_size = os.path.getsize(audio_path)
        if file_size > 25 * 1024 * 1024:
            raise RuntimeError(f"Audio file too large ({file_size / 1024 / 1024:.1f}MB). Groq limit is 25MB.")
        
        print(f"  → Transcribing with Groq Whisper ({file_size / 1024 / 1024:.1f}MB)...")
        transcript_text = transcribe_with_groq(audio_path)
    
    return {
        'text': transcript_text,
        'word_count': len(transcript_text.split()),
        'method': 'groq_whisper'
    }


def transcribe_video(video_url: str, keep_audio: bool = False) -> dict:
    """
    Main transcription function.
    Uses YouTube Transcript API first, falls back to Groq Whisper.
    """
    try:
        video_id = extract_video_id(video_url)
    except ValueError as e:
        return {'success': False, 'message': str(e)}
    
    try:
        result = get_transcript(video_id)
        
        print(f"  ✓ Transcript fetched: {result['word_count']} words (via {result['method']})")
        
        return {
            'success': True,
            'video_id': video_id,
            'transcript': result['text'],
            'word_count': result['word_count'],
            'method': result['method'],
            'message': f"Transcript fetched successfully ({result['word_count']} words)"
        }
        
    except Exception as e:
        return {
            'success': False,
            'video_id': video_id,
            'message': f'Failed to get transcript: {str(e)}'
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get transcript from a YouTube video')
    parser.add_argument('url', help='YouTube video URL or ID')
    args = parser.parse_args()
    
    result = transcribe_video(args.url)
    print(json.dumps(result, indent=2))
