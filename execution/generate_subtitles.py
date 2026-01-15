#!/usr/bin/env python3
"""
Subtitle Generation Script
Uses Groq (Distil-Whisper) for precise word-level transcription, then FFmpeg to burn styled subtitles.
Style: Bold white text with cyan highlight on the last word of each line.
"""

import os
import re
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# Check for API keys
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    print("⚠️ Warning: GROQ_API_KEY not set in environment. Subtitle generation will fail.")


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds * 1000) % 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_to_srt(audio_path: str) -> str:
    """
    Use Groq (Distil-Whisper) to transcribe audio with word-level precision.
    Constructs SRT enforcing max 4 words per line.
    """
    client = Groq(api_key=GROQ_API_KEY)
    
    print(f"🎤 Transcribing with Groq (Whisper Large V3 Turbo)...")
    
    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file.read()),
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )
    
    # Process word-level timestamps to build subtitles
    # Logic: Group words into chunks of max 4. 
    # Start time = start of first word. End time = end of last word.
    
    words = transcription.words
    srt_blocks = []
    
    current_chunk = []
    chunk_word_count = 0
    
    # Group words into lines
    for word_obj in words:
        word_text = word_obj['word'].strip()
        
        # Start new chunk if we hit limit (max 4 words)
        # Note: Groq might return punctuation attached to words, which is fine
        if chunk_word_count >= 4:
            srt_blocks.append(current_chunk)
            current_chunk = []
            chunk_word_count = 0
            
        current_chunk.append(word_obj)
        chunk_word_count += 1
        
    # Append last chunk
    if current_chunk:
        srt_blocks.append(current_chunk)
    
    # Build SRT content
    srt_output = []
    for i, block in enumerate(srt_blocks, 1):
        if not block:
            continue
            
        start_time = format_timestamp(block[0]['start'])
        end_time = format_timestamp(block[-1]['end'])
        
        # Construct text line
        text = ' '.join(w['word'].strip() for w in block)
        
        srt_output.append(f"{i}")
        srt_output.append(f"{start_time} --> {end_time}")
        srt_output.append(text)
        srt_output.append("") # Empty line after each block
        
    final_srt = '\n'.join(srt_output)
    print(f"✅ Transcription complete. Generated {len(srt_blocks)} subtitle lines.")
    return final_srt


def srt_to_ass_with_highlights(srt_content: str) -> str:
    """
    Convert SRT to ASS format with styled subtitles.
    Highlights the LAST word of each subtitle in cyan.
    """
    
    # ASS header with styles matching YouTube-style captions
    # Style: Arial Black, Size 72, White text, Black outline (4px), Shadow (2px), Bottom Center
    ass_header = """[Script Info]
Title: Auto-Generated Subtitles
ScriptType: v4.00+
PlayDepth: 0
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,10,10,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    events = []
    
    # Robust SRT parsing using regex
    pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n((?:(?!\n\d+\n\d{2}:\d{2}:\d{2}).)+)'
    
    matches = re.findall(pattern, srt_content, re.DOTALL)
    
    print(f"  📊 Found {len(matches)} subtitle entries...")
    
    for sub_num, start_ts, end_ts, text_block in matches:
        # Parse timestamps
        start_match = re.match(r'(\d{2}:\d{2}:\d{2})[,.](\d{3})', start_ts)
        end_match = re.match(r'(\d{2}:\d{2}:\d{2})[,.](\d{3})', end_ts)
        
        if not start_match or not end_match:
            continue
        
        start_time = f"{start_match.group(1)}.{start_match.group(2)[:2]}"
        end_time = f"{end_match.group(1)}.{end_match.group(2)[:2]}"
        
        # Clean up text
        text = ' '.join(text_block.strip().split('\n'))
        text = ' '.join(text.split())
        
        # Force ALL CAPS for impact
        text = text.upper()
        
        # Apply highlight to last word
        # ASS color format is &HBBGGRR& (Blue, Green, Red)
        # Cyan = Blue(FF) + Green(FF) + Red(00) -> &HFFFF00&
        # Previous &H00FFFF& was Red(FF) + Green(FF) = Yellow
        
        words = text.split()
        if words:
            if len(words) > 1:
                styled_text = ' '.join(words[:-1]) + ' {\\c&HFFFF00&}' + words[-1] + '{\\c&HFFFFFF&}'
            else:
                styled_text = '{\\c&HFFFF00&}' + words[0] + '{\\c&HFFFFFF&}'
        else:
            styled_text = text
        
        events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{styled_text}")
    
    return ass_header + '\n'.join(events) + '\n'


def burn_subtitles(video_path: str, ass_path: str, output_path: str) -> bool:
    """Use FFmpeg to burn ASS subtitles into video."""
    print(f"🔥 Burning subtitles into video...")
    
    escaped_ass = ass_path.replace('\\', '/').replace(':', '\\:')
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"ass='{escaped_ass}'",
        '-c:a', 'copy',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '18',
        output_path
    ]
    
    print(f"  Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print(f"✅ Subtitled video saved: {output_path}")
            return True
        else:
            print(f"❌ FFmpeg error: {result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def generate_subtitled_video(video_path: str, audio_path: str = None, output_dir: str = None) -> dict:
    """Main function: Generate subtitles and burn into video."""
    video_path = Path(video_path)
    
    if not video_path.exists():
        return {'success': False, 'error': f'Video not found: {video_path}'}
    
    if output_dir:
        output_dir = Path(output_dir)
    else:
        output_dir = video_path.parent
    
    output_dir.mkdir(exist_ok=True)
    
    # Needs AUDIO for Groq, so extract it
    if not audio_path:
        audio_path = output_dir / f"{video_path.stem}_groq.mp3"
        print(f"🎵 Extracting audio for Groq...")
        extract_cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-vn', '-acodec', 'libmp3lame',
            '-q:a', '2',
            str(audio_path)
        ]
        subprocess.run(extract_cmd, capture_output=True)
    
    try:
        # Step 1: Transcribe using Groq (Audio -> SRT)
        srt_content = transcribe_to_srt(str(audio_path))
        
        # Save SRT
        srt_path = output_dir / f"{video_path.stem}.srt"
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        # Step 2: Convert to styled ASS
        ass_content = srt_to_ass_with_highlights(srt_content)
        ass_path = output_dir / f"{video_path.stem}.ass"
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
        
        # Step 3: Burn subtitles into video
        output_video = output_dir / f"{video_path.stem}_subtitled.mp4"
        success = burn_subtitles(str(video_path), str(ass_path), str(output_video))
        
        if success:
            return {
                'success': True,
                'srt_path': str(srt_path),
                'ass_path': str(ass_path),
                'subtitled_video': str(output_video),
                'message': 'Subtitles generated (Groq) and burned successfully'
            }
        else:
            return {'success': False, 'error': 'FFmpeg burn failed'}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', '-v', required=True)
    parser.add_argument('--audio', '-a')
    parser.add_argument('--output-dir', '-o')
    args = parser.parse_args()
    
    print(json.dumps(generate_subtitled_video(
        args.video, args.audio, args.output_dir
    ), indent=2))
