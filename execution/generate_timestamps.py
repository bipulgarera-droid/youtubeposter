#!/usr/bin/env python3
"""
Generate YouTube Timestamps (Chapters) from SRT file.
Creates chapter markers based on content segments using AI.
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def parse_srt(srt_path: str) -> List[Dict]:
    """
    Parse an SRT file into a list of subtitle entries.
    
    Returns:
        List of dicts with: index, start_time, end_time, text
    """
    if not os.path.exists(srt_path):
        print(f"⚠️ SRT file not found: {srt_path}")
        return []
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by double newline (subtitle blocks)
    blocks = re.split(r'\n\n+', content.strip())
    
    entries = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            try:
                index = int(lines[0])
                time_match = re.match(
                    r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})',
                    lines[1]
                )
                if time_match:
                    text = ' '.join(lines[2:])
                    entries.append({
                        'index': index,
                        'start_time': time_match.group(1),
                        'end_time': time_match.group(2),
                        'text': text
                    })
            except ValueError:
                continue
    
    return entries


def srt_time_to_seconds(srt_time: str) -> float:
    """Convert SRT time format (HH:MM:SS,mmm) to seconds."""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', srt_time)
    if match:
        h, m, s, ms = map(int, match.groups())
        return h * 3600 + m * 60 + s + ms / 1000
    return 0


def seconds_to_youtube_time(seconds: float) -> str:
    """Convert seconds to YouTube timestamp format (M:SS or H:MM:SS)."""
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}:{m:02d}:{s:02d}"


def generate_chapter_titles(srt_entries: List[Dict], num_chapters: int = 10) -> List[Dict]:
    """
    Use AI to generate chapter titles based on SRT content.
    Divides video into logical chapters based on content shifts.
    
    Args:
        srt_entries: Parsed SRT entries
        num_chapters: Target number of chapters (8-12 recommended)
    
    Returns:
        List of dicts with: time (YouTube format), title, seconds
    """
    if not srt_entries:
        return []
    
    # Get full transcript with timestamps
    full_text = ""
    for entry in srt_entries:
        seconds = srt_time_to_seconds(entry['start_time'])
        time_str = seconds_to_youtube_time(seconds)
        full_text += f"[{time_str}] {entry['text']}\n"
    
    # Limit text for API
    full_text = full_text[:15000]
    
    prompt = f"""Analyze this video transcript and create {num_chapters} chapter timestamps.

TRANSCRIPT:
{full_text}

RULES:
1. Create exactly {num_chapters} chapters
2. First chapter MUST start at 0:00
3. Each chapter title should be 3-7 words, descriptive but concise
4. Identify natural topic shifts/transitions
5. Space chapters roughly evenly, minimum 1 minute apart
6. Use title case for chapter names
7. Make titles engaging and click-worthy

OUTPUT FORMAT (exactly like this, no extra text):
0:00 - Introduction: [Topic Hook]
1:45 - [Chapter Title]
3:12 - [Chapter Title]
...

TIMESTAMPS:"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        
        # Parse response
        chapters = []
        lines = response.text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Match pattern: "0:00 - Title" or "1:23:45 - Title"
            match = re.match(r'^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*(.+)$', line)
            if match:
                time_str = match.group(1)
                title = match.group(2).strip()
                
                # Convert to seconds for sorting
                parts = time_str.split(':')
                if len(parts) == 2:
                    seconds = int(parts[0]) * 60 + int(parts[1])
                else:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                
                chapters.append({
                    'time': time_str,
                    'title': title,
                    'seconds': seconds
                })
        
        # Sort by time
        chapters.sort(key=lambda x: x['seconds'])
        
        # Ensure first chapter is 0:00
        if chapters and chapters[0]['seconds'] != 0:
            chapters.insert(0, {
                'time': '0:00',
                'title': 'Introduction',
                'seconds': 0
            })
        
        return chapters
        
    except Exception as e:
        print(f"❌ Chapter generation failed: {e}")
        return []


def format_timestamps_for_description(chapters: List[Dict]) -> str:
    """Format chapters as YouTube description timestamps."""
    if not chapters:
        return ""
    
    lines = ["TIMESTAMPS:"]
    for chapter in chapters:
        lines.append(f"{chapter['time']} - {chapter['title']}")
    
    return "\n".join(lines)


def generate_timestamps_from_srt(srt_path: str, num_chapters: int = 10) -> Dict:
    """
    Main function: Generate timestamps from SRT file.
    
    Args:
        srt_path: Path to SRT file
        num_chapters: Target number of chapters
    
    Returns:
        Dict with chapters list and formatted string
    """
    print(f"📑 Parsing SRT: {srt_path}")
    entries = parse_srt(srt_path)
    
    if not entries:
        return {'chapters': [], 'formatted': '', 'success': False}
    
    print(f"   Found {len(entries)} subtitle entries")
    
    print(f"🧠 Generating {num_chapters} chapter titles...")
    chapters = generate_chapter_titles(entries, num_chapters)
    
    if not chapters:
        return {'chapters': [], 'formatted': '', 'success': False}
    
    print(f"✅ Generated {len(chapters)} chapters:")
    for ch in chapters:
        print(f"   {ch['time']} - {ch['title']}")
    
    formatted = format_timestamps_for_description(chapters)
    
    return {
        'chapters': chapters,
        'formatted': formatted,
        'success': True
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        srt_file = sys.argv[1]
    else:
        # Test with a sample SRT
        srt_file = ".tmp/final_videos/test.srt"
    
    result = generate_timestamps_from_srt(srt_file)
    
    if result['success']:
        print("\n" + "="*50)
        print("FORMATTED FOR DESCRIPTION:")
        print("="*50)
        print(result['formatted'])
