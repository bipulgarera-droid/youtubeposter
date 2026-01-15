#!/usr/bin/env python3
"""
Video Transcription Script
Gets transcript directly from YouTube using the Transcript API.
No audio download needed - fast and reliable.
"""

import os
import re
import json
import argparse
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

# Load environment variables
load_dotenv()


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


def get_transcript(video_id: str) -> dict:
    """
    Get transcript using YouTube Transcript API (new v1.2.3 syntax).
    Returns dict with text and metadata.
    """
    print(f"Fetching transcript for video: {video_id}...")
    
    # New API syntax (v1.2.3+)
    ytt_api = YouTubeTranscriptApi()
    
    try:
        # Fetch transcript - returns a FetchedTranscript object
        fetched_transcript = ytt_api.fetch(video_id)
        
        # Convert to raw data (list of dicts with text, start, duration)
        transcript_data = fetched_transcript.to_raw_data()
        
    except Exception as e:
        raise RuntimeError(f"Could not fetch transcript: {str(e)}")
    
    # Combine all text segments
    full_text = ' '.join([segment['text'] for segment in transcript_data])
    
    return {
        'text': full_text,
        'segments': transcript_data,
        'word_count': len(full_text.split())
    }


def transcribe_video(video_url: str, keep_audio: bool = False) -> dict:
    """
    Main transcription function.
    Uses YouTube Transcript API to fetch existing captions.
    """
    try:
        video_id = extract_video_id(video_url)
    except ValueError as e:
        return {'success': False, 'message': str(e)}
    
    try:
        result = get_transcript(video_id)
        
        print(f"Transcript fetched: {result['word_count']} words")
        
        return {
            'success': True,
            'video_id': video_id,
            'transcript': result['text'],
            'word_count': result['word_count'],
            'message': f"Transcript fetched successfully ({result['word_count']} words)"
        }
        
    except Exception as e:
        return {
            'success': False,
            'video_id': video_id,
            'message': f'Failed to get transcript: {str(e)}. This video may not have captions available.'
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get transcript from a YouTube video')
    parser.add_argument('url', help='YouTube video URL or ID')
    args = parser.parse_args()
    
    result = transcribe_video(args.url)
    print(json.dumps(result, indent=2))
