#!/usr/bin/env python3
"""
Step-by-Step Pipeline - Pauses after each step for user approval via Telegram.
Uses Supabase storage to serve intermediate outputs.
"""
import os
import sys
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import asyncio
import httpx

load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.job_queue import set_job_status, JobStatus, get_redis_connection
from execution.storage_helper import upload_file, upload_text, upload_json

# Base directories
TMP_DIR = Path(__file__).parent.parent / '.tmp'

# Telegram config
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Step states
STEP_PENDING = 'pending'
STEP_RUNNING = 'running'
STEP_AWAITING_APPROVAL = 'awaiting_approval'
STEP_APPROVED = 'approved'
STEP_REJECTED = 'rejected'
STEP_COMPLETED = 'completed'


def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None) -> bool:
    """Send a message to Telegram."""
    if not BOT_TOKEN:
        print("⚠️ No TELEGRAM_BOT_TOKEN")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = httpx.post(url, json=payload, timeout=30)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")
        return False


def send_telegram_document(chat_id: int, file_path: str, caption: str = "") -> bool:
    """Send a document to Telegram."""
    if not BOT_TOKEN:
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id, 'caption': caption[:1024]}
            response = httpx.post(url, data=data, files=files, timeout=60)
            return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram document send failed: {e}")
        return False


def send_telegram_photo(chat_id: int, file_path: str, caption: str = "") -> bool:
    """Send a photo to Telegram."""
    if not BOT_TOKEN:
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'photo': f}
            data = {'chat_id': chat_id, 'caption': caption[:1024]}
            response = httpx.post(url, data=data, files=files, timeout=60)
            return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram photo send failed: {e}")
        return False


def get_approval_keyboard(job_id: str, step_name: str):
    """Create approval keyboard for a step."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve_{job_id}_{step_name}"},
                {"text": "🔄 Regenerate", "callback_data": f"regen_{job_id}_{step_name}"}
            ],
            [
                {"text": "❌ Cancel Pipeline", "callback_data": f"cancel_{job_id}"}
            ]
        ]
    }


def set_step_status(job_id: str, step_name: str, status: str, data: dict = None):
    """Store step status in Redis."""
    redis = get_redis_connection()
    key = f"step_status:{job_id}:{step_name}"
    value = {
        "status": status,
        "step_name": step_name,
        "updated_at": datetime.now().isoformat(),
        "data": data or {}
    }
    redis.set(key, json.dumps(value), ex=86400 * 7)  # 7 days


def get_step_status(job_id: str, step_name: str) -> dict:
    """Get step status from Redis."""
    redis = get_redis_connection()
    key = f"step_status:{job_id}:{step_name}"
    data = redis.get(key)
    if data:
        return json.loads(data)
    return {"status": STEP_PENDING}


def wait_for_approval(job_id: str, step_name: str, timeout: int = 3600) -> str:
    """
    Wait for user approval of a step.
    Returns: 'approved', 'rejected', or 'timeout'
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        step_status = get_step_status(job_id, step_name)
        status = step_status.get("status")
        
        if status == STEP_APPROVED:
            return "approved"
        elif status == STEP_REJECTED:
            return "rejected"
        
        time.sleep(2)  # Poll every 2 seconds
    
    return "timeout"


def run_step_by_step_pipeline(
    job_id: str,
    youtube_url: str,
    topic: Optional[str] = None,
    telegram_chat_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run pipeline with approval after each step.
    """
    try:
        # ===== STEP 1: Extract Video Info =====
        step_name = "video_info"
        set_job_status(job_id, JobStatus.RUNNING, 5, "Step 1: Extracting video info...")
        set_step_status(job_id, step_name, STEP_RUNNING)
        
        from execution.full_pipeline import extract_video_info
        video_info = extract_video_info(youtube_url)
        
        if not topic:
            topic = video_info['title']
        
        # Send for approval
        message = (
            f"📹 *Step 1: Video Info*\n\n"
            f"*Title:* {video_info['title'][:60]}...\n"
            f"*Channel:* {video_info.get('channel', 'Unknown')}\n"
            f"*Duration:* {video_info.get('duration', 0) // 60} min\n\n"
            f"*Topic for video:* {topic}\n\n"
            f"Approve to continue?"
        )
        
        set_step_status(job_id, step_name, STEP_AWAITING_APPROVAL, {"topic": topic})
        send_telegram_message(telegram_chat_id, message, get_approval_keyboard(job_id, step_name))
        
        # Wait for approval
        result = wait_for_approval(job_id, step_name)
        if result != "approved":
            set_job_status(job_id, JobStatus.FAILED, 5, f"Step 1 {result}")
            return {"error": f"Step 1: {result}"}
        
        set_step_status(job_id, step_name, STEP_COMPLETED)
        
        # ===== STEP 2: Transcription =====
        step_name = "transcribe"
        set_job_status(job_id, JobStatus.RUNNING, 15, "Step 2: Transcribing video...")
        set_step_status(job_id, step_name, STEP_RUNNING)
        
        from execution.transcribe_video import transcribe_video
        transcript_result = transcribe_video(youtube_url)
        transcript = transcript_result.get('transcript', '')
        
        word_count = len(transcript.split())
        
        # Upload transcript
        transcript_url = upload_text(transcript, job_id, "transcribe", "transcript.txt")
        
        message = (
            f"📝 *Step 2: Transcription Complete*\n\n"
            f"*Words:* {word_count}\n"
            f"*Duration estimate:* {word_count // 150} min\n\n"
            f"📄 [View Transcript]({transcript_url})\n\n"
            f"Approve to continue to research?"
        )
        
        set_step_status(job_id, step_name, STEP_AWAITING_APPROVAL, {"word_count": word_count, "url": transcript_url})
        send_telegram_message(telegram_chat_id, message, get_approval_keyboard(job_id, step_name))
        
        result = wait_for_approval(job_id, step_name)
        if result != "approved":
            set_job_status(job_id, JobStatus.FAILED, 15, f"Step 2 {result}")
            return {"error": f"Step 2: {result}"}
        
        set_step_status(job_id, step_name, STEP_COMPLETED)
        
        # ===== STEP 3: News Research =====
        step_name = "research"
        set_job_status(job_id, JobStatus.RUNNING, 25, "Step 3: Researching news...")
        set_step_status(job_id, step_name, STEP_RUNNING)
        
        from execution.search_news import search_news
        research_result = search_news(topic, num_articles=20, transcript=transcript, days_limit=3)
        articles = research_result.get('articles', []) if research_result else []
        
        # Upload articles list
        articles_url = upload_json({"articles": articles}, job_id, "research", "articles.json")
        
        # Format preview
        preview = "\n".join([f"• {a.get('title', '')[:50]}..." for a in articles[:5]])
        
        message = (
            f"🔍 *Step 3: Research Complete*\n\n"
            f"*Found:* {len(articles)} articles\n\n"
            f"*Top articles:*\n{preview}\n\n"
            f"📄 [View All Articles]({articles_url})\n\n"
            f"Approve to generate script?"
        )
        
        set_step_status(job_id, step_name, STEP_AWAITING_APPROVAL, {"count": len(articles), "url": articles_url})
        send_telegram_message(telegram_chat_id, message, get_approval_keyboard(job_id, step_name))
        
        result = wait_for_approval(job_id, step_name)
        if result != "approved":
            set_job_status(job_id, JobStatus.FAILED, 25, f"Step 3 {result}")
            return {"error": f"Step 3: {result}"}
        
        set_step_status(job_id, step_name, STEP_COMPLETED)
        
        # ===== STEP 4: Script Generation =====
        step_name = "script"
        set_job_status(job_id, JobStatus.RUNNING, 35, "Step 4: Generating script...")
        set_step_status(job_id, step_name, STEP_RUNNING)
        
        # Combine research data
        research_data = f"REFERENCE TRANSCRIPT:\n{transcript}\n\nNEWS ARTICLES:\n"
        for article in articles[:15]:
            research_data += f"- {article.get('title', '')}: {article.get('snippet', '')}\n"
        
        from execution.generate_narrative_script import generate_narrative_script
        script_result = generate_narrative_script(
            research_data=research_data,
            topic=topic,
            target_minutes=15
        )
        script_text = script_result.get('full_script', '')
        script_chunks = script_result.get('chunks', [])
        
        # Upload script
        script_url = upload_text(script_text, job_id, "script", "script.txt")
        
        word_count = len(script_text.split())
        
        message = (
            f"📜 *Step 4: Script Generated*\n\n"
            f"*Words:* {word_count}\n"
            f"*Chunks:* {len(script_chunks)}\n"
            f"*Estimated duration:* {word_count // 150} min\n\n"
            f"📄 [Download Script]({script_url})\n\n"
            f"Approve to generate AI images?"
        )
        
        set_step_status(job_id, step_name, STEP_AWAITING_APPROVAL, {"word_count": word_count, "chunks": len(script_chunks), "url": script_url})
        send_telegram_message(telegram_chat_id, message, get_approval_keyboard(job_id, step_name))
        
        result = wait_for_approval(job_id, step_name)
        if result != "approved":
            set_job_status(job_id, JobStatus.FAILED, 35, f"Step 4 {result}")
            return {"error": f"Step 4: {result}"}
        
        set_step_status(job_id, step_name, STEP_COMPLETED)
        
        # ===== STEP 5: AI Images =====
        step_name = "images"
        set_job_status(job_id, JobStatus.RUNNING, 50, f"Step 5: Generating {len(script_chunks)} images...")
        set_step_status(job_id, step_name, STEP_RUNNING)
        
        from execution.generate_ai_images import generate_all_images
        image_results = generate_all_images(script_text, str(TMP_DIR / 'screenshots'))
        
        # Upload first 3 images as preview
        screenshots_dir = TMP_DIR / 'screenshots'
        image_urls = []
        for i in range(min(3, len(list(screenshots_dir.glob('*.png'))))):
            img_path = screenshots_dir / f"screenshot_{i+1:04d}.png"
            if img_path.exists():
                url = upload_file(str(img_path), job_id, "images", f"image_{i+1}.png")
                image_urls.append(url)
                # Send photo to Telegram
                send_telegram_photo(telegram_chat_id, str(img_path), f"Image {i+1}/{len(script_chunks)}")
        
        message = (
            f"🖼️ *Step 5: Images Generated*\n\n"
            f"*Total images:* {len(script_chunks)}\n"
            f"*Previews sent above*\n\n"
            f"Approve to generate audio?"
        )
        
        set_step_status(job_id, step_name, STEP_AWAITING_APPROVAL, {"count": len(script_chunks), "preview_urls": image_urls})
        send_telegram_message(telegram_chat_id, message, get_approval_keyboard(job_id, step_name))
        
        result = wait_for_approval(job_id, step_name)
        if result != "approved":
            set_job_status(job_id, JobStatus.FAILED, 50, f"Step 5 {result}")
            return {"error": f"Step 5: {result}"}
        
        set_step_status(job_id, step_name, STEP_COMPLETED)
        
        # ===== STEP 6: Audio Generation =====
        step_name = "audio"
        set_job_status(job_id, JobStatus.RUNNING, 65, "Step 6: Generating audio...")
        set_step_status(job_id, step_name, STEP_RUNNING)
        
        from execution.full_pipeline import generate_all_audio
        audio_results = generate_all_audio(script_chunks)
        
        # Upload sample audio
        audio_dir = TMP_DIR / 'audio'
        sample_audio = audio_dir / "chunk_0000.mp3"
        audio_url = None
        if sample_audio.exists():
            audio_url = upload_file(str(sample_audio), job_id, "audio", "sample_chunk_1.mp3")
        
        message = (
            f"🔊 *Step 6: Audio Generated*\n\n"
            f"*Total chunks:* {len(script_chunks)}\n\n"
            f"🎵 [Sample Audio]({audio_url})\n\n"
            f"Approve to stitch video?"
        )
        
        set_step_status(job_id, step_name, STEP_AWAITING_APPROVAL, {"sample_url": audio_url})
        send_telegram_message(telegram_chat_id, message, get_approval_keyboard(job_id, step_name))
        
        result = wait_for_approval(job_id, step_name)
        if result != "approved":
            set_job_status(job_id, JobStatus.FAILED, 65, f"Step 6 {result}")
            return {"error": f"Step 6: {result}"}
        
        set_step_status(job_id, step_name, STEP_COMPLETED)
        
        # ===== STEP 7: Video Stitching =====
        step_name = "video"
        set_job_status(job_id, JobStatus.RUNNING, 80, "Step 7: Stitching video + subtitles...")
        set_step_status(job_id, step_name, STEP_RUNNING)
        
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
        
        # Burn subtitles
        from execution.generate_subtitles import generate_subtitled_video
        subtitle_result = generate_subtitled_video(
            video_path=temp_video_path,
            audio_path=None,
            output_dir=str(TMP_DIR / 'final_videos')
        )
        
        if subtitle_result.get('success'):
            final_video_path = subtitle_result.get('subtitled_video', temp_video_path)
        else:
            final_video_path = temp_video_path
        
        # Rename to title
        import re
        import shutil
        safe_title = re.sub(r'[^\w\s-]', '', topic)[:100].strip().replace(' ', '_')
        final_video_dir = TMP_DIR / 'final_videos'
        final_video_dir.mkdir(parents=True, exist_ok=True)
        titled_video_path = final_video_dir / f"{safe_title}.mp4"
        
        if os.path.exists(final_video_path) and str(final_video_path) != str(titled_video_path):
            shutil.move(final_video_path, titled_video_path)
            final_video_path = str(titled_video_path)
        
        # Upload to storage
        video_url = upload_file(str(final_video_path), job_id, "video", f"{safe_title}.mp4")
        
        message = (
            f"🎬 *Step 7: Video Complete!*\n\n"
            f"*Title:* {topic[:60]}...\n"
            f"*File:* `{safe_title}.mp4`\n\n"
            f"📹 [Download Video]({video_url})\n\n"
            f"Finalize to upload to YouTube?"
        )
        
        set_step_status(job_id, step_name, STEP_AWAITING_APPROVAL, {"video_url": video_url, "path": str(final_video_path)})
        send_telegram_message(telegram_chat_id, message, get_approval_keyboard(job_id, step_name))
        
        result = wait_for_approval(job_id, step_name)
        if result != "approved":
            set_job_status(job_id, JobStatus.FAILED, 80, f"Step 7 {result}")
            # Still return video path even if not uploading
            return {"video_path": str(final_video_path), "video_url": video_url}
        
        set_step_status(job_id, step_name, STEP_COMPLETED)
        
        # ===== Complete =====
        set_job_status(job_id, JobStatus.COMPLETED, 100, "Pipeline complete!")
        
        send_telegram_message(
            telegram_chat_id,
            f"✅ *Pipeline Complete!*\n\n"
            f"📹 [Download Video]({video_url})\n\n"
            f"Your video is ready for upload!",
            None
        )
        
        return {
            "success": True,
            "video_path": str(final_video_path),
            "video_url": video_url,
            "topic": topic
        }
        
    except Exception as e:
        error_msg = f"Pipeline failed: {str(e)}\n{traceback.format_exc()}"
        set_job_status(job_id, JobStatus.FAILED, 0, error_msg)
        send_telegram_message(telegram_chat_id, f"❌ *Error:* {str(e)}", None)
        raise


if __name__ == "__main__":
    print("Step-by-step pipeline module loaded.")
