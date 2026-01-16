#!/usr/bin/env python3
"""
Full Pipeline - Complete video generation from YouTube URL or news.
Chains all steps: Transcribe → Research → Script → Images → Audio → Stitch → SRT
"""
import os
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.job_queue import set_job_status, JobStatus

# Base directory for temporary files
TMP_DIR = Path(__file__).parent.parent / '.tmp'


def extract_video_info(youtube_url: str) -> Dict[str, Any]:
    """
    Extract video metadata from YouTube URL.
    
    Returns:
        Dict with title, description, tags, duration, etc.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return {
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'tags': info.get('tags', []),
            'duration': info.get('duration', 0),
            'channel': info.get('channel', ''),
            'view_count': info.get('view_count', 0),
            'upload_date': info.get('upload_date', ''),
        }


def run_full_pipeline(
    job_id: str,
    youtube_url: str,
    topic: Optional[str] = None,
    telegram_chat_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run the complete video generation pipeline.
    
    Args:
        job_id: Job ID for status tracking
        youtube_url: YouTube video URL to use as reference
        topic: Optional topic override (defaults to video title)
        telegram_chat_id: Optional Telegram chat ID for notifications
    
    Returns:
        Dict with paths to generated files
    """
    try:
        set_job_status(job_id, JobStatus.RUNNING, 5, "Extracting video information...")
        
        # Step 1: Extract video info
        video_info = extract_video_info(youtube_url)
        if not topic:
            topic = video_info['title']
        
        set_job_status(job_id, JobStatus.RUNNING, 10, f"Topic: {topic[:50]}... Transcribing video...")
        
        # Step 2: Transcribe video
        from execution.transcribe_video import transcribe_video
        transcript_result = transcribe_video(youtube_url)
        transcript = transcript_result.get('transcript', '') if transcript_result else ''
        
        set_job_status(job_id, JobStatus.RUNNING, 20, "Running news research...")
        
        # Step 3: News research
        from execution.search_news import search_news
        research_result = search_news(topic, num_articles=20, transcript=transcript)
        research_articles = research_result.get('articles', []) if research_result else []
        
        # Combine research data
        research_data = f"REFERENCE TRANSCRIPT:\n{transcript}\n\n"
        research_data += "NEWS ARTICLES:\n"
        for article in research_articles[:15]:
            research_data += f"- {article.get('title', '')}: {article.get('snippet', '')}\n"
        
        set_job_status(job_id, JobStatus.RUNNING, 30, "Generating narrative script...")
        
        # Step 4: Generate script
        from execution.generate_narrative_script import generate_narrative_script
        script_result = generate_narrative_script(
            research_data=research_data,
            topic=topic,
            target_minutes=15
        )
        script_text = script_result.get('full_script', '')
        script_chunks = script_result.get('chunks', [])
        
        set_job_status(job_id, JobStatus.RUNNING, 45, f"Generating {len(script_chunks)} AI images...")
        
        # Step 5: Generate AI images
        from execution.generate_ai_images import generate_all_images
        image_results = generate_all_images(script_chunks, topic)
        
        set_job_status(job_id, JobStatus.RUNNING, 65, "Generating audio for all chunks...")
        
        # Step 6: Generate audio
        audio_results = generate_all_audio(script_chunks)
        
        set_job_status(job_id, JobStatus.RUNNING, 80, "Stitching final video...")
        
        # Step 7: Stitch video
        from execution.generate_video import build_video_from_chunks
        
        # Prepare chunks with paths
        chunks_with_paths = []
        for i, chunk in enumerate(script_chunks):
            chunk_data = {
                'id': i,
                'text': chunk.get('text', ''),
                'audio_path': str(TMP_DIR / 'audio' / f'chunk_{i:04d}.mp3'),
                'screenshot_path': str(TMP_DIR / 'screenshots' / f'screenshot_{i+1:04d}.png')
            }
            chunks_with_paths.append(chunk_data)
        
        video_result = build_video_from_chunks(chunks_with_paths)
        temp_video_path = video_result.get('output_path')
        
        if not temp_video_path:
            raise Exception("Video stitching failed")
        
        set_job_status(job_id, JobStatus.RUNNING, 88, "Burning subtitles...")
        
        # Step 8: Generate subtitles and burn into video
        from execution.generate_subtitles import generate_subtitled_video
        subtitle_result = generate_subtitled_video(
            video_path=temp_video_path,
            audio_path=None,  # Will extract audio from video
            output_dir=str(TMP_DIR / 'final_videos')
        )
        
        if subtitle_result.get('success'):
            video_path = subtitle_result.get('subtitled_video', temp_video_path)
            srt_path = subtitle_result.get('srt_path')
        else:
            print(f"⚠️ Subtitle generation failed: {subtitle_result.get('error')}")
            video_path = temp_video_path
            srt_path = None
        
        set_job_status(job_id, JobStatus.RUNNING, 92, "Renaming video file...")
        
        # Step 8.5: Rename video file to title (for YouTube algorithm)
        import re
        safe_title = re.sub(r'[^\w\s-]', '', topic or video_info['title'])[:100]
        safe_title = safe_title.strip().replace(' ', '_')
        
        final_video_dir = TMP_DIR / 'final_videos'
        final_video_dir.mkdir(parents=True, exist_ok=True)
        final_video_path = final_video_dir / f"{safe_title}.mp4"
        
        if os.path.exists(video_path) and str(video_path) != str(final_video_path):
            import shutil
            shutil.move(video_path, final_video_path)
            video_path = str(final_video_path)
        
        set_job_status(job_id, JobStatus.RUNNING, 94, "Generating timestamps...")
        
        # Step 8.6: Generate timestamps from SRT
        timestamps_text = ""
        if srt_path and os.path.exists(str(srt_path)):
            from execution.generate_timestamps import generate_timestamps_from_srt
            timestamp_result = generate_timestamps_from_srt(str(srt_path), num_chapters=10)
            if timestamp_result.get('success'):
                timestamps_text = timestamp_result.get('formatted', '')
                print(f"✅ Generated {len(timestamp_result.get('chapters', []))} chapter timestamps")
        
        set_job_status(job_id, JobStatus.RUNNING, 96, "Generating metadata...")
        
        # Step 9: Generate metadata with timestamps
        from execution.generate_metadata import generate_full_metadata
        metadata = generate_full_metadata(
            original_title=video_info['title'],
            original_description=video_info.get('description', ''),
            original_tags=video_info.get('tags', []),
            topic=topic,
            script_text=script_text,
            timestamps_text=timestamps_text
        )
        
        # Final result
        result = {
            'video_path': str(video_path) if video_path else None,
            'srt_path': str(srt_path) if srt_path else None,
            'metadata': metadata,
            'timestamps': timestamps_text,
            'topic': topic,
            'title': topic or video_info['title'],
            'original_title': video_info['title'],
            'chunk_count': len(script_chunks),
            'word_count': len(script_text.split()),
            'completed_at': datetime.now().isoformat()
        }
        
        set_job_status(job_id, JobStatus.COMPLETED, 100, "Pipeline complete!", result)
        
        # Send Telegram notification if chat_id provided
        if telegram_chat_id:
            send_telegram_notification(telegram_chat_id, job_id, result)
        
        return result
        
    except Exception as e:
        error_msg = f"Pipeline failed: {str(e)}\n{traceback.format_exc()}"
        set_job_status(job_id, JobStatus.FAILED, 0, error_msg)
        
        if telegram_chat_id:
            send_telegram_error(telegram_chat_id, job_id, str(e))
        
        raise


def run_news_pipeline(
    job_id: str,
    news_url: str,
    topic: str,
    telegram_chat_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run pipeline based on a news article instead of YouTube reference.
    Does deep research on the topic and generates original content.
    """
    try:
        set_job_status(job_id, JobStatus.RUNNING, 5, "Fetching news article...")
        
        # Step 1: Fetch news article content
        import requests
        from bs4 import BeautifulSoup
        
        response = requests.get(news_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract article text
        article_text = ' '.join([p.get_text() for p in soup.find_all('p')])[:5000]
        
        set_job_status(job_id, JobStatus.RUNNING, 15, "Running deep research on topic...")
        
        # Step 2: Deep research
        from execution.search_news import search_news_for_topic
        research_articles = search_news_for_topic(topic, max_results=25)
        
        # Combine research
        research_data = f"ORIGINAL NEWS ARTICLE:\n{article_text}\n\n"
        research_data += "ADDITIONAL RESEARCH:\n"
        for article in research_articles[:20]:
            research_data += f"- {article.get('title', '')}: {article.get('snippet', '')}\n"
        
        set_job_status(job_id, JobStatus.RUNNING, 30, "Generating narrative script...")
        
        # Continue with standard pipeline from step 4 onwards
        from execution.generate_narrative_script import generate_narrative_script
        script_result = generate_narrative_script(
            research_data=research_data,
            topic=topic,
            target_minutes=15
        )
        script_text = script_result.get('full_script', '')
        script_chunks = script_result.get('chunks', [])
        
        # Steps 5-9 same as full pipeline
        set_job_status(job_id, JobStatus.RUNNING, 45, f"Generating {len(script_chunks)} AI images...")
        from execution.generate_ai_images import generate_all_images
        generate_all_images(script_chunks, topic)
        
        set_job_status(job_id, JobStatus.RUNNING, 65, "Generating audio...")
        generate_all_audio(script_chunks)
        
        set_job_status(job_id, JobStatus.RUNNING, 80, "Stitching video...")
        from execution.generate_video import generate_video
        video_path = generate_video()
        
        set_job_status(job_id, JobStatus.RUNNING, 90, "Generating subtitles...")
        from execution.generate_srt import generate_srt
        srt_path = generate_srt()
        
        # Generate metadata from scratch
        metadata = {
            'title': generate_title_from_topic(topic),
            'description': generate_description(script_text, topic),
            'tags': generate_tags(topic)
        }
        
        result = {
            'video_path': str(video_path) if video_path else None,
            'srt_path': str(srt_path) if srt_path else None,
            'metadata': metadata,
            'topic': topic,
            'source_url': news_url,
            'completed_at': datetime.now().isoformat()
        }
        
        set_job_status(job_id, JobStatus.COMPLETED, 100, "News pipeline complete!", result)
        
        if telegram_chat_id:
            send_telegram_notification(telegram_chat_id, job_id, result)
        
        return result
        
    except Exception as e:
        error_msg = f"News pipeline failed: {str(e)}"
        set_job_status(job_id, JobStatus.FAILED, 0, error_msg)
        if telegram_chat_id:
            send_telegram_error(telegram_chat_id, job_id, str(e))
        raise


def generate_all_audio(chunks: list) -> list:
    """Generate audio for all script chunks."""
    import requests
    import base64
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    audio_dir = TMP_DIR / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    for i, chunk in enumerate(chunks):
        text = chunk.get('text', '')
        if not text:
            continue
        
        # Clean text for TTS
        import re
        text = re.sub(r'https?://\S+', '', text)
        text = text.replace('\n', ' ').strip()
        
        if not text:
            continue
        
        # Call Google TTS API
        url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={GEMINI_API_KEY}"
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-US",
                "name": "en-US-Chirp3-HD-Charon"
            },
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": 24000
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                audio_content = base64.b64decode(response.json()['audioContent'])
                audio_path = audio_dir / f"chunk_{i}.wav"
                with open(audio_path, 'wb') as f:
                    f.write(audio_content)
                results.append({'index': i, 'path': str(audio_path)})
        except Exception as e:
            print(f"Audio generation failed for chunk {i}: {e}")
    
    return results


def generate_metadata(video_info: Dict, script_text: str, topic: str) -> Dict:
    """Generate optimized metadata based on original video and script."""
    import google.generativeai as genai
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    
    original_title = video_info.get('title', '')
    original_description = video_info.get('description', '')[:1000]
    original_tags = video_info.get('tags', [])[:20]
    
    prompt = f"""Generate YouTube metadata based on this video:

ORIGINAL TITLE: {original_title}
TOPIC: {topic}
SCRIPT EXCERPT: {script_text[:2000]}

Generate:
1. NEW TITLE: Similar to original but change 2-3 words (keep SEO keywords)
2. DESCRIPTION: 2-3 sentences from the hook, then key points, then disclaimer
3. TAGS: 10-15 relevant tags

Return as JSON:
{{"title": "...", "description": "...", "tags": ["tag1", "tag2", ...]}}"""
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        
        # Parse JSON from response
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"Metadata generation failed: {e}")
    
    # Fallback
    return {
        'title': original_title,
        'description': script_text[:500],
        'tags': original_tags
    }


def generate_title_from_topic(topic: str) -> str:
    """Generate a video title from topic."""
    return topic


def generate_description(script_text: str, topic: str) -> str:
    """Generate video description."""
    # Use first 500 chars of script as description base
    return script_text[:500] + "\n\n#" + topic.replace(' ', '')


def generate_tags(topic: str) -> list:
    """Generate tags from topic."""
    words = topic.lower().split()
    return words[:15]


def send_telegram_notification(chat_id: int, job_id: str, result: Dict):
    """Send completion notification via Telegram."""
    import requests
    
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not BOT_TOKEN:
        return
    
    message = f"""✅ Video Generation Complete!

📹 Job: {job_id}
📝 Topic: {result.get('topic', 'N/A')[:50]}
⏱️ Chunks: {result.get('chunk_count', 0)}
📊 Words: {result.get('word_count', 0)}

Your video is ready for review."""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    })


def send_telegram_error(chat_id: int, job_id: str, error: str):
    """Send error notification via Telegram."""
    import requests
    
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not BOT_TOKEN:
        return
    
    message = f"""❌ Video Generation Failed

📹 Job: {job_id}
⚠️ Error: {error[:200]}

Please check the logs for details."""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        'chat_id': chat_id,
        'text': message
    })


if __name__ == "__main__":
    # Test with a sample URL
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"Testing with: {test_url}")
    info = extract_video_info(test_url)
    print(f"Title: {info['title']}")
