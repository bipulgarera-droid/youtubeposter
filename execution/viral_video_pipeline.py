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
from execution.generate_audio import generate_audio_from_script, generate_all_audio
from execution.generate_ai_images import generate_images_for_script, split_script_to_chunks
from execution.generate_video import build_video_from_chunks
from execution.youtube_upload import upload_video

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
    
    def checkpoint_path(self) -> str:
        """Get checkpoint file path for this video."""
        from pathlib import Path
        checkpoint_dir = Path(".tmp/viral_pipeline")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return str(checkpoint_dir / f"{self.video_id}_checkpoint.json")
    
    def save_checkpoint(self, step: str):
        """Save current state to checkpoint file."""
        import json
        self.data["last_completed_step"] = step
        try:
            with open(self.checkpoint_path(), 'w') as f:
                json.dump(self.data, f, indent=2, default=str)
            print(f"      💾 Checkpoint saved: {step}")
        except Exception as e:
            print(f"      ⚠️ Checkpoint save failed: {e}")
    
    def load_checkpoint(self) -> bool:
        """Load checkpoint if exists. Returns True if loaded."""
        import json
        from pathlib import Path
        try:
            checkpoint_file = Path(self.checkpoint_path())
            if checkpoint_file.exists():
                with open(checkpoint_file) as f:
                    self.data = json.load(f)
                print(f"      📂 Checkpoint loaded: {self.data.get('last_completed_step', 'unknown')}")
                return True
        except Exception as e:
            print(f"      ⚠️ Checkpoint load failed: {e}")
        return False
    
    def clear_checkpoint(self):
        """Remove checkpoint file after successful completion."""
        from pathlib import Path
        try:
            Path(self.checkpoint_path()).unlink(missing_ok=True)
        except:
            pass
    
    async def run(self, resume: bool = True) -> Dict:
        """Execute the full pipeline with checkpointing."""
        try:
            # Try to load checkpoint
            last_step = None
            if resume and self.load_checkpoint():
                last_step = self.data.get("last_completed_step")
                await self.log(f"📂 Resuming from checkpoint: {last_step}")
            
            steps = [
                ("fetch_video_info", "📊 Fetching original video details...", self.fetch_video_info),
                ("transcribe", "📝 Transcribing video...", self.transcribe),
                ("research", "🔍 Researching to make it 30% better...", self.research),
                ("generate_script", "✍️ Writing improved script...", self.generate_improved_script),
                ("generate_metadata", "📋 Creating similar title/description/tags...", self.generate_metadata),
                ("analyze_thumbnail", "🖼️ Analyzing thumbnail elements...", self.analyze_thumbnail),
                ("generate_audio", "🎙️ Generating voiceover...", self.generate_audio),
                ("generate_images", "🎨 Creating visuals...", self.generate_images),
                ("create_video", "🎬 Stitching video...", self.create_video),
                ("upload", "📤 Uploading to YouTube...", self.upload),
            ]
            
            # Find starting point
            start_idx = 0
            if last_step:
                for i, (step_name, _, _) in enumerate(steps):
                    if step_name == last_step:
                        start_idx = i + 1  # Start from NEXT step
                        break
            
            # Execute steps
            for step_name, step_msg, step_func in steps[start_idx:]:
                await self.log(step_msg)
                await step_func()
                self.save_checkpoint(step_name)
            
            await self.log(f"✅ Video uploaded! URL: {self.data.get('upload_result', {}).get('url', 'N/A')}")
            self.clear_checkpoint()
            
            return {
                "success": True,
                "video_url": self.data.get("upload_result", {}).get("url"),
                "data": self.data
            }
            
        except Exception as e:
            await self.log(f"❌ Pipeline failed: {str(e)}")
            await self.log(f"💡 Use the same video to resume from checkpoint")
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
        from pathlib import Path
        output_dir = Path(".tmp/viral_pipeline")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        result = generate_all_audio(self.data["script"], str(output_dir))
        self.data["audio_result"] = result
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
        # Build chunks structure for video builder
        from pathlib import Path
        
        audio_result = self.data.get("audio_result", {})
        audio_files = audio_result.get("audio_files", [])
        
        images_dir = Path(".tmp/viral_pipeline/images")
        image_files = sorted(images_dir.glob("*.png")) if images_dir.exists() else []
        
        chunks = []
        script_chunks = split_script_to_chunks(self.data["script"])
        
        for i, chunk_text in enumerate(script_chunks):
            audio_file = audio_files[i] if i < len(audio_files) else None
            image_file = image_files[i] if i < len(image_files) else None
            
            chunks.append({
                "id": i,
                "text": chunk_text,
                "audio_path": audio_file.get("path") if audio_file else None,
                "screenshot_path": str(image_file) if image_file else None
            })
        
        result = build_video_from_chunks(chunks)
        if result.get("success"):
            self.data["output_path"] = result.get("output_path", ".tmp/final_videos/final_video.mp4")
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
