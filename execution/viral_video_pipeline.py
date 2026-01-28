#!/usr/bin/env python3
"""
Viral Video Cloning Pipeline
Creates an improved version of a viral video to appear in suggested videos.

Flow:
1. Get video info (title, desc, tags, thumbnail)
2. Transcribe the video
3. Research deeper using transcript + news
4. Generate 30% better script
5. Generate similar title/desc/tags
6. Generate thumbnail with similar elements
7. Create full video and upload
"""

import os
import asyncio
from typing import Dict, Optional, Callable
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Import existing modules
from execution.youtube_video_info import get_video_details
from execution.transcribe_video import transcribe_video
from execution.research_agent import deep_research, format_research_for_script
from execution.generate_script import generate_script
from execution.generate_audio import generate_audio
from execution.generate_ai_images import generate_images_for_script
from execution.generate_video import create_video
from execution.youtube_upload import upload_video
from execution.storage_helper import upload_to_supabase, get_supabase_url

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class ViralVideoPipeline:
    """Pipeline to clone and improve a viral video."""
    
    def __init__(self, video_id: str, send_message: Callable = None):
        self.video_id = video_id
        self.send_message = send_message or print
        self.data = {
            "video_id": video_id,
            "original": {},
            "transcript": "",
            "research": {},
            "script": "",
            "title": "",
            "description": "",
            "tags": [],
            "thumbnail_analysis": {},
            "output_path": ""
        }
    
    async def log(self, message: str):
        """Send progress message."""
        if asyncio.iscoroutinefunction(self.send_message):
            await self.send_message(message)
        else:
            self.send_message(message)
    
    async def run(self) -> Dict:
        """Execute the full pipeline."""
        try:
            # Step 1: Get original video info
            await self.log("📊 Fetching original video details...")
            await self.fetch_video_info()
            
            # Step 2: Transcribe
            await self.log("📝 Transcribing video...")
            await self.transcribe()
            
            # Step 3: Research deeper
            await self.log("🔍 Researching to make it 30% better...")
            await self.research()
            
            # Step 4: Generate improved script
            await self.log("✍️ Writing improved script...")
            await self.generate_improved_script()
            
            # Step 5: Generate similar metadata
            await self.log("📋 Creating similar title/description/tags...")
            await self.generate_metadata()
            
            # Step 6: Analyze thumbnail
            await self.log("🖼️ Analyzing thumbnail elements...")
            await self.analyze_thumbnail()
            
            # Step 7: Generate audio
            await self.log("🎙️ Generating voiceover...")
            audio_result = await self.generate_audio()
            
            # Step 8: Generate images
            await self.log("🎨 Creating visuals...")
            images_result = await self.generate_images()
            
            # Step 9: Create video
            await self.log("🎬 Stitching video...")
            video_result = await self.create_video()
            
            # Step 10: Upload to YouTube
            await self.log("📤 Uploading to YouTube...")
            upload_result = await self.upload()
            
            await self.log(f"✅ Video uploaded! URL: {upload_result.get('url', 'N/A')}")
            
            return {
                "success": True,
                "video_url": upload_result.get("url"),
                "data": self.data
            }
            
        except Exception as e:
            await self.log(f"❌ Pipeline failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def fetch_video_info(self):
        """Get original video's title, description, tags, thumbnail."""
        info = get_video_details(self.video_id)
        if not info.get("success"):
            raise Exception(f"Could not fetch video info: {info.get('error')}")
        
        self.data["original"] = {
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "tags": info.get("tags", []),
            "thumbnail_url": info.get("thumbnails", {}).get("high", {}).get("url", ""),
            "channel": info.get("channelTitle", ""),
            "views": info.get("viewCount", 0)
        }
    
    async def transcribe(self):
        """Get transcript of the original video."""
        result = transcribe_video(f"https://youtube.com/watch?v={self.video_id}")
        if not result.get("success"):
            raise Exception(f"Transcription failed: {result.get('message')}")
        
        self.data["transcript"] = result.get("transcript", "")
    
    async def research(self):
        """Research deeper using transcript as context."""
        # Extract topic from original title
        topic = self.data["original"]["title"]
        
        # Use deep_research with transcript as additional source
        research = deep_research(
            topic=topic,
            country=None,
            source_article={
                "title": self.data["original"]["title"],
                "snippet": self.data["transcript"][:2000]  # First 2000 chars as context
            }
        )
        
        self.data["research"] = research
        self.data["research_formatted"] = format_research_for_script(research)
    
    async def generate_improved_script(self):
        """Generate a script that's 30% more detailed and engaging."""
        # Prepare articles from research
        articles = []
        for news in self.data["research"].get("recent_news", []):
            articles.append({
                "title": news.get("title", ""),
                "content": news.get("content", news.get("snippet", "")),
                "source": news.get("source", "")
            })
        
        # Generate script with "improve" mode hint
        result = generate_script(
            topic=self.data["original"]["title"],
            articles=articles,
            transcript=self.data["transcript"],
            word_count=5000,  # Longer than average for more depth
            channel_focus="Empire Finance",
            script_mode="improve"  # This signals to make it better
        )
        
        if not result.get("success"):
            raise Exception(f"Script generation failed: {result.get('message')}")
        
        self.data["script"] = result.get("script", {}).get("raw_text", "")
    
    async def generate_metadata(self):
        """Generate similar title, description, and merge tags."""
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        original_title = self.data["original"]["title"]
        original_desc = self.data["original"]["description"]
        original_tags = self.data["original"]["tags"]
        
        # Generate similar title (80% same structure)
        title_prompt = f"""Rewrite this YouTube title to be 80% similar but unique enough to avoid duplicate detection.
Keep the same structure, hook words, and topic. Change 2-3 words maximum.

Original: {original_title}

Rules:
- Keep the same emotional hook (DESTROYED, TRUTH, etc.)
- Keep the same topic keywords
- Change word order slightly or use synonyms
- Must feel like the same video at first glance
- Max 70 characters

Return ONLY the new title, nothing else."""

        title_response = model.generate_content(title_prompt)
        self.data["title"] = title_response.text.strip().strip('"')
        
        # Generate similar description
        desc_prompt = f"""Rewrite this YouTube description to be similar but unique.
Keep the first 2 sentences almost identical (change 1-2 words).
Add Empire Finance branding at the end.

Original first 500 chars:
{original_desc[:500]}

Return the new description (max 500 chars), nothing else."""

        desc_response = model.generate_content(desc_prompt)
        self.data["description"] = desc_response.text.strip()
        
        # Merge tags (remove vague ones)
        vague_tags = {"video", "youtube", "2024", "2025", "2026", "new", "latest", "trending"}
        good_original_tags = [t for t in original_tags if t.lower() not in vague_tags][:15]
        
        our_tags = ["empire finance", "economy explained", "financial news", "economic analysis"]
        
        self.data["tags"] = list(set(good_original_tags + our_tags))[:20]
    
    async def analyze_thumbnail(self):
        """Analyze what works in the original thumbnail."""
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        prompt = f"""Analyze what makes this thumbnail effective for a viral video.
Title: {self.data["original"]["title"]}
Thumbnail URL: {self.data["original"]["thumbnail_url"]}

Return a JSON object with:
- "main_text": the big text overlay (if any)
- "text_color": dominant text color
- "emotion": facial expression shown (shocked, worried, angry, etc.)
- "key_elements": list of visual elements that grab attention
- "background_color": dominant background color

Return ONLY valid JSON."""

        try:
            response = model.generate_content(prompt)
            import json
            self.data["thumbnail_analysis"] = json.loads(response.text)
        except:
            self.data["thumbnail_analysis"] = {
                "main_text": self.data["title"][:30],
                "emotion": "worried",
                "key_elements": ["face", "text overlay"]
            }
    
    async def generate_audio(self):
        """Generate voiceover from script."""
        result = generate_audio(self.data["script"], output_dir=".tmp/viral_pipeline")
        return result
    
    async def generate_images(self):
        """Generate AI images for the video."""
        result = generate_images_for_script(
            self.data["script"],
            output_dir=".tmp/viral_pipeline/images"
        )
        return result
    
    async def create_video(self):
        """Stitch audio + images into video."""
        result = create_video(
            audio_path=".tmp/viral_pipeline/audio.mp3",
            images_dir=".tmp/viral_pipeline/images",
            output_path=".tmp/viral_pipeline/output.mp4"
        )
        self.data["output_path"] = ".tmp/viral_pipeline/output.mp4"
        return result
    
    async def upload(self):
        """Upload to YouTube with cloned metadata."""
        result = upload_video(
            video_path=self.data["output_path"],
            title=self.data["title"],
            description=self.data["description"],
            tags=self.data["tags"],
            category_id="22"  # People & Blogs
        )
        return result


async def run_viral_pipeline(video_id: str, send_message: Callable = None) -> Dict:
    """Convenience function to run the pipeline."""
    pipeline = ViralVideoPipeline(video_id, send_message)
    return await pipeline.run()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python viral_video_pipeline.py <video_id>")
        sys.exit(1)
    
    video_id = sys.argv[1]
    result = asyncio.run(run_viral_pipeline(video_id))
    print(result)
