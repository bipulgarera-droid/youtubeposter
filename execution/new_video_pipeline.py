"""
New Video Pipeline - Research-first step-by-step video generation.

This is the primary pipeline with:
1. Trend scanning → Topic selection
2. Deep research
3. Script generation (4,500 words, 7 chapters)
4. Style selection
5. AI image generation
6. Video generation
7. Subtitles
8. Tags + metadata
9. Thumbnail
10. File renaming
11. YouTube upload

All steps require Telegram approval.
"""

import os
import sys
import json
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import pipeline components
from execution.trend_scanner import scan_trending_topics, get_evergreen_topics
from execution.research_agent import deep_research, format_research_for_script
from execution.style_selector import get_style_options, apply_style_to_prompt, DEFAULT_STYLE
from execution.file_renamer import rename_output_files, generate_topic_slug, extract_topic_from_title
from execution.generate_outline import generate_outline, format_outline_for_telegram, format_outline_for_script
from execution.job_queue import get_redis_connection


# Import existing generators (with try/except for missing modules)
try:
    from execution.generate_narrative_script import generate_narrative_script
except ImportError:
    generate_narrative_script = None

try:
    from execution.generate_ai_images import generate_images_for_script
except ImportError as e:
    print(f"⚠️ Failed to import generate_images_for_script: {e}")
    generate_images_for_script = None

try:
    from execution.generate_audio import generate_audio_from_script
except ImportError:
    generate_audio_from_script = None

try:
    from execution.generate_video import build_video_from_chunks
except ImportError:
    build_video_from_chunks = None

try:
    from execution.generate_subtitles import generate_subtitled_video
except ImportError:
    generate_subtitled_video = None

try:
    from execution.generate_thumbnail import generate_thumbnail
except ImportError:
    generate_thumbnail = None

try:
    from execution.generate_metadata import generate_full_metadata
except ImportError:
    generate_full_metadata = None

try:
    from execution.generate_timestamps import generate_timestamps_from_srt
except ImportError:
    generate_timestamps_from_srt = None

# Supabase storage for persisting outputs
try:
    from execution.storage_helper import (
        upload_file, upload_text, upload_state, download_file, 
        get_latest_job_with_assets, download_state, cleanup_old_jobs
    )
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    upload_file = None
    upload_text = None
    upload_state = None
    download_file = None
    get_latest_job_with_assets = None
    download_state = None
    cleanup_old_jobs = None



class NewVideoPipeline:
    """
    Orchestrates the research-first video generation pipeline.
    Each step waits for user approval via Telegram.
    """
    
    def __init__(self, chat_id: int, send_message_func, send_keyboard_func, bot=None, test_mode: bool = False):
        """
        Initialize pipeline.
        
        Args:
            chat_id: Telegram chat ID
            send_message_func: Async function to send messages
            send_keyboard_func: Async function to send keyboard options
            bot: Telegram bot instance for sending documents/photos
            test_mode: If True, generate shorter content for faster testing
        """
        self.chat_id = chat_id
        self.send_message = send_message_func
        self.send_keyboard = send_keyboard_func
        self.bot = bot  # For sending documents, photos, videos
        self.test_mode = test_mode
        
        # Redis key for persistence
        self.redis_key = f"pipeline_state:{chat_id}"
        
        # Pipeline state
        self.state = {
            "step": "init",
            "topic": None,
            "title": None,
            "research": None,
            "outline": None,
            "script": None,
            "style": DEFAULT_STYLE,
            "images": [],
            "audio_path": None,
            "video_path": None,
            "srt_path": None,
            "subtitled_video_path": None,
            "thumbnail_path": None,
            "tags": [],
            "description": None,
            "timestamps": None,
            "output_dir": None,
            "test_mode": test_mode
        }
        
        # Create output directory
        self.output_dir = f".tmp/pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        self.state["output_dir"] = self.output_dir
    
    def save_state(self):
        """Save current state to Redis for resume capability."""
        try:
            # Save content for persistence (essential for Railway ephemeral usage)
            save_data = {
                "step": self.state["step"],
                "topic": self.state["topic"],
                "title": self.state["title"],
                "style": self.state["style"],
                "output_dir": self.state["output_dir"],
                "test_mode": self.state.get("test_mode", False),
                "timestamp": datetime.now().isoformat(),
                
                # Save full CONTENT because local files are ephemeral
                "script": self.state.get("script"),
                "research": self.state.get("research"),
                "outline": self.state.get("outline"),
                "description": self.state.get("description"),
                
                # Save paths
                "script_path": self.state.get("script_path"),
                "video_path": self.state.get("video_path"),
                "srt_path": self.state.get("srt_path"),
                "subtitled_video_path": self.state.get("subtitled_video_path"),
                "thumbnail_path": self.state.get("thumbnail_path"),
            }
            redis = get_redis_connection()
            # Save to Redis with 7-day TTL
            redis.set(self.redis_key, json.dumps(save_data), ex=604800)
            print(f"State saved to Redis: step={self.state['step']}")
        except Exception as e:
            print(f"State save error: {e}")
    
    @classmethod
    def load_state(cls, chat_id: int) -> Optional[Dict]:
        """Load saved state for a chat ID from Redis."""
        try:
            redis = get_redis_connection()
            key = f"pipeline_state:{chat_id}"
            data = redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Error loading state: {e}")
        return None
    
    @classmethod
    def has_saved_state(cls, chat_id: int) -> bool:
        """Check if there's a saved state for this chat in Redis."""
        try:
            redis = get_redis_connection()
            key = f"pipeline_state:{chat_id}"
            return redis.exists(key) > 0
        except:
            return False
    
    def clear_state(self):
        """Clear saved state from Redis."""
        try:
            redis = get_redis_connection()
            redis.delete(self.redis_key)
            print("State cleared from Redis")
        except Exception as e:
            print(f"Error clearing state: {e}")
    
    async def resume(self):
        """Resume from saved state."""
        saved = self.load_state(self.chat_id)
        if not saved:
            await self.send_message("❌ No saved session found. Use /newvideo to start fresh.")
            return False
        
        # Restore state
        self.state["step"] = saved.get("step", "init")
        self.state["topic"] = saved.get("topic")
        self.state["title"] = saved.get("title")
        self.state["style"] = saved.get("style", DEFAULT_STYLE)
        self.state["output_dir"] = saved.get("output_dir", self.output_dir)
        self.test_mode = saved.get("test_mode", False)
        
        # Restore CONTENT (prioritize saved state)
        if saved.get("script"):
            self.state["script"] = saved["script"]
        elif saved.get("script_path") and os.path.exists(saved["script_path"]):
            # Fallback to file (backward compatibility)
            with open(saved["script_path"], "r") as f:
                self.state["script"] = f.read()

        if saved.get("research"):
            self.state["research"] = saved["research"]
        if saved.get("outline"):
            self.state["outline"] = saved["outline"]
        if saved.get("description"):
            self.state["description"] = saved["description"]
            
        # Restore paths
        self.state["script_path"] = saved.get("script_path")
        
        timestamp = saved.get("timestamp", "unknown")
        step = self.state["step"]
        title = self.state.get("title", "Unknown")
        
        await self.send_keyboard(
            f"📂 **Resume Session**\n\n"
            f"**Title:** {title}\n"
            f"**Step:** {step}\n"
            f"**Saved:** {timestamp}\n\n"
            f"Continue from this point?",
            [
                ("✅ Continue", f"newvideo_resume_{step}"),
                ("🔄 Start Fresh", "newvideo_start_fresh")
            ]
        )
        return True
    
    async def _resume_from_cloud_subtitled(self):
        """Resume from subtitled video in Supabase - skip to metadata step."""
        await self.send_message("☁️ Resuming from cloud storage (subtitled video)...")
        
        job_id = self.state.get("cloud_job_id")
        assets = self.state.get("cloud_assets", {})
        
        if not job_id or not assets.get("subtitled_video"):
            await self.send_message("❌ No subtitled video found in cloud storage.")
            await self.start()
            return
        
        # Try to download saved state
        if download_state:
            saved_state = download_state(job_id)
            if saved_state:
                # Restore key fields from saved state
                self.state["title"] = saved_state.get("title", "Resumed from Cloud")
                self.state["topic"] = saved_state.get("topic", "")
                self.state["script"] = saved_state.get("script", "")
                await self.send_message(f"📋 Restored state: {self.state.get('title', 'Unknown')}")
        
        # Download subtitled video to local
        self.supabase_job_id = job_id
        subtitled_storage_path = assets["subtitled_video"]
        local_subtitled_path = os.path.join(self.output_dir, "video_subtitled.mp4")
        
        if download_file and download_file(subtitled_storage_path, local_subtitled_path):
            self.state["subtitled_video_path"] = local_subtitled_path
            self.state["subtitled_video_url"] = f"https://fjbowxwqaegvpjyinnsa.supabase.co/storage/v1/object/public/youtube-pipeline/{subtitled_storage_path}"
            
            # Download SRT if available
            if assets.get("srt"):
                local_srt_path = os.path.join(self.output_dir, "video.srt")
                if download_file(assets["srt"], local_srt_path):
                    self.state["srt_path"] = local_srt_path
            
            await self.send_message("✅ Subtitled video downloaded. Proceeding to metadata generation...")
            await self._generate_metadata()
        else:
            await self.send_message("❌ Failed to download subtitled video from cloud storage.")
            await self.start()
    
    async def _resume_from_cloud_images(self):
        """Resume from images in Supabase - generate audio & video."""
        await self.send_message("☁️ Resuming from cloud storage (images)...")
        
        job_id = self.state.get("cloud_job_id")
        assets = self.state.get("cloud_assets", {})
        
        if not job_id or not assets.get("images"):
            await self.send_message("❌ No images found in cloud storage.")
            await self.start()
            return
        
        # Try to download saved state
        if download_state:
            saved_state = download_state(job_id)
            if saved_state:
                self.state["title"] = saved_state.get("title", "Resumed from Cloud")
                self.state["topic"] = saved_state.get("topic", "")
                self.state["script"] = saved_state.get("script", "")
                await self.send_message(f"📋 Restored state: {self.state.get('title', 'Unknown')}")
        
        # If no script from state.json, try to download script file
        if not self.state.get("script") and assets.get("script"):
            await self.send_message("📥 Downloading script from cloud...")
            script_local_path = os.path.join(self.output_dir, "script.txt")
            if download_file and download_file(assets["script"], script_local_path):
                with open(script_local_path, 'r') as f:
                    self.state["script"] = f.read()
                await self.send_message("✅ Script downloaded from cloud")
        
        # Last resort: try to get from Redis (current session)
        if not self.state.get("script"):
            redis_state = self.load_state(self.chat_id)
            if redis_state and redis_state.get("script"):
                self.state["script"] = redis_state["script"]
                self.state["title"] = redis_state.get("title", "Resumed")
                self.state["topic"] = redis_state.get("topic", "")
                await self.send_message("📋 Restored script from local session")
        
        if not self.state.get("script"):
            await self.send_message("❌ No script found. Cannot generate audio without script.")
            await self.start()
            return
        
        # Split script into chunks to match images
        try:
            from execution.generate_ai_images import split_script_to_chunks
            script_chunks = split_script_to_chunks(self.state["script"])
            await self.send_message(f"📝 Script split into {len(script_chunks)} chunks")
        except Exception as e:
            print(f"Failed to split script: {e}")
            script_chunks = []
        
        # Download all images to local
        self.supabase_job_id = job_id
        images_dir = os.path.join(self.output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        image_chunks = []
        for i, img_storage_path in enumerate(assets["images"]):
            local_img_path = os.path.join(images_dir, f"chunk_{i:03d}.png")
            if download_file and download_file(img_storage_path, local_img_path):
                # Get chunk text from script - use index to match
                chunk_text = script_chunks[i] if i < len(script_chunks) else ""
                image_chunks.append({
                    "success": True,
                    "path": local_img_path,
                    "index": i,
                    "chunk_text": chunk_text
                })
        
        if not image_chunks:
            await self.send_message("❌ Failed to download images from cloud storage.")
            await self.start()
            return
        
        # Count how many have text
        chunks_with_text = sum(1 for c in image_chunks if c.get("chunk_text"))
        await self.send_message(f"✅ Downloaded {len(image_chunks)} images. {chunks_with_text} have text for audio. Proceeding to video generation...")
        
        # Store images in state and proceed to video generation
        self.state["images"] = {"chunks": image_chunks}
        await self._generate_video()
    
    
    async def start(self):
        """Start the pipeline - ask to scan trends."""
        self.state["step"] = "ask_opportunity"
        
        options = [
            ("Yes - Scan News", "newvideo_scan_yes"),
            ("🌍 Search by Country", "newvideo_country"),
            ("No - I have a topic", "newvideo_scan_no"),
            ("Evergreen Topic", "newvideo_evergreen")
        ]
        
        # Add Resume button if saved state exists in Redis
        if self.has_saved_state(self.chat_id):
            options.insert(0, ("📂 Resume Previous Session", "newvideo_resume_start"))
        
        # Add Resume from Cloud option if Supabase has assets
        if STORAGE_AVAILABLE and get_latest_job_with_assets:
            try:
                job_id, assets = get_latest_job_with_assets()
                if job_id:
                    # Determine best resume point based on what exists
                    if assets.get('subtitled_video'):
                        resume_label = "☁️ Resume from Subtitled Video"
                        resume_action = "newvideo_resume_cloud_subtitled"
                    elif assets.get('images'):
                        resume_label = f"☁️ Resume from Images ({len(assets['images'])} images)"
                        resume_action = "newvideo_resume_cloud_images"
                    else:
                        resume_label = None
                        resume_action = None
                    
                    if resume_label:
                        # Store job info for later use
                        self.state["cloud_job_id"] = job_id
                        self.state["cloud_assets"] = assets
                        options.insert(1, (resume_label, resume_action))
            except Exception as e:
                print(f"Error checking Supabase assets: {e}")
            
        await self.send_keyboard(
            "🎬 **New Video Pipeline**\n\nShould I scan for trending opportunities?",
            options
        )
    
    async def handle_callback(self, callback_data: str, user_input: str = None) -> bool:
        """
        Handle user callback or input.
        
        Returns True if pipeline should continue.
        """
        step = self.state["step"]
        
        # Handle text input FIRST (before callback_data checks)
        if user_input and step == "waiting_topic_input":
            self.state["topic"] = user_input
            self.state["raw_topic"] = user_input
            await self._generate_title()
            return True
        
        if user_input and step == "waiting_country_input":
            await self._scan_by_country(user_input)
            return True
        
        # If no callback_data, nothing more to do
        if not callback_data:
            return True
        
        # Step 1: Scan for opportunities
        if callback_data == "newvideo_scan_yes":
            await self._scan_trends()
            return True
        
        elif callback_data == "newvideo_scan_no":
            self.state["step"] = "waiting_topic_input"
            await self.send_message("📝 Enter your topic:")
            return True
        
        elif callback_data == "newvideo_country":
            self.state["step"] = "waiting_country_input"
            await self.send_message("🌍 Enter a country name (e.g., Venezuela, France, UK):")
            return True
        
        elif callback_data == "newvideo_evergreen":
            await self._show_evergreen_topics()
            return True
        
        # Resume/Start Fresh handlers
        elif callback_data == "newvideo_start_fresh":
            self.clear_state()
            await self.start()
            return True
            
        elif callback_data == "newvideo_resume_start":
            await self.resume()
            return True
        
        elif callback_data.startswith("newvideo_resume_"):
            # Resume from saved step - continue to next action
            step = callback_data.replace("newvideo_resume_", "")
            
            # Handle cloud resume options
            if step == "cloud_subtitled":
                await self._resume_from_cloud_subtitled()
                return True
            elif step == "cloud_images":
                await self._resume_from_cloud_images()
                return True
            
            await self.send_message(f"▶️ Resuming from step: {step}")
            # Trigger appropriate next action based on step
            if step == "approving_title":
                await self._start_research()
            elif step == "approving_research":
                await self._generate_outline()
            elif step == "approving_outline":
                await self._generate_script()
            elif step == "approving_script":
                await self._select_style()
            elif step == "approving_images":
                await self._generate_video()
            elif step == "approving_video":
                await self._add_subtitles()
            elif step == "approving_subtitles":
                await self._generate_metadata()
            elif step == "approving_metadata":
                await self._generate_thumbnail()
            elif step == "approving_thumbnail":
                await self._prepare_upload()
            else:
                await self.send_message(f"Unknown step: {step}. Starting fresh.")
                await self.start()
            return True
        
        # Step 2: Topic selection
        elif callback_data.startswith("newvideo_topic_"):
            idx = int(callback_data.replace("newvideo_topic_", ""))
            await self._select_topic(idx)
            return True
        
        elif callback_data == "newvideo_topic_none":
            await self._show_evergreen_topics()
            return True
        
        # Step 3: Title approval
        elif callback_data == "newvideo_title_approve":
            await self._start_research()
            return True
        
        elif callback_data == "newvideo_title_regen":
            await self._regenerate_title()
            return True
        
        # Step 4: Research approval → Generate Outline
        elif callback_data == "newvideo_research_approve":
            await self._generate_outline()
            return True
        
        elif callback_data == "newvideo_research_regen":
            await self._regenerate_research()
            return True
        
        # Step 5: Outline approval → Generate Script
        elif callback_data == "newvideo_outline_approve":
            await self._generate_script()
            return True
        
        elif callback_data == "newvideo_outline_regen":
            await self._regenerate_outline()
            return True
        
        # Step 6: Script approval
        elif callback_data == "newvideo_script_approve":
            await self._select_style()
            return True
        
        elif callback_data == "newvideo_script_regen":
            await self._regenerate_script()
            return True
        
        # Step 6: Style selection
        elif callback_data.startswith("newvideo_style_"):
            style_id = callback_data.replace("newvideo_style_", "")
            await self._apply_style(style_id)
            return True
        
        # Step 7: Images approval
        elif callback_data == "newvideo_images_approve":
            await self._generate_video()
            return True
        
        elif callback_data == "newvideo_images_regen":
            await self._regenerate_images()
            return True
        
        # Step 8: Video approval
        elif callback_data == "newvideo_video_approve":
            await self._add_subtitles()
            return True
        
        elif callback_data == "newvideo_video_regen":
            await self._regenerate_video()
            return True
        
        # Step 9: Subtitles approval
        elif callback_data == "newvideo_subtitles_approve":
            await self._generate_metadata()
            return True
        
        elif callback_data == "newvideo_subtitles_regen":
            await self._regenerate_subtitles()
            return True
        
        # Step 10: Metadata approval
        elif callback_data == "newvideo_metadata_approve":
            await self._generate_thumbnail()
            return True
        
        elif callback_data == "newvideo_metadata_regen":
            await self._regenerate_metadata()
            return True
        
        # Step 10: Thumbnail approval
        elif callback_data == "newvideo_thumbnail_approve":
            await self._prepare_upload()
            return True
        
        elif callback_data == "newvideo_thumbnail_regen":
            await self._regenerate_thumbnail()
            return True
        
        # Step 11: Final upload confirmation
        elif callback_data == "newvideo_upload_confirm":
            await self._upload_to_youtube()
            return False  # Pipeline complete
        
        elif callback_data == "newvideo_upload_cancel":
            await self.send_message("❌ Upload cancelled. Files saved locally.")
            return False
        
        return True
    
    async def _scan_trends(self):
        """Scan news for trending topics."""
        await self.send_message("🔍 Scanning trending topics...")
        
        topics = scan_trending_topics("economics")
        
        if not topics:
            await self.send_message("No trending topics found. Showing evergreen options...")
            await self._show_evergreen_topics()
            return
        
        self.state["trending_topics"] = topics
        self.state["step"] = "choosing_topic"
        
        # Build keyboard
        options = [
            (f"📰 {t['suggested_topic'][:40]}", f"newvideo_topic_{i}")
            for i, t in enumerate(topics)
        ]
        options.append(("None of these", "newvideo_topic_none"))
        
        msg = "🔥 **Trending Topics:**\n\n"
        for i, t in enumerate(topics):
            msg += f"{i+1}. **{t['suggested_topic']}**\n"
            msg += f"   └ {t['headline'][:60]}...\n\n"
        
        await self.send_keyboard(msg, options)
    
    async def _scan_by_country(self, country: str):
        """Scan news for topics specific to a country."""
        await self.send_message(f"🌍 Searching news for **{country}**...")
        
        # Store country for later use in title regeneration
        self.state["country"] = country
        
        # Import the country-specific search
        from execution.trend_scanner import scan_by_country
        topics = scan_by_country(country)
        
        if not topics:
            await self.send_message(f"No trending topics found for {country}. Try a different country.")
            self.state["step"] = "waiting_country_input"
            return
        
        self.state["trending_topics"] = topics
        self.state["step"] = "choosing_topic"
        
        # Build keyboard
        options = [
            (f"📰 {t['suggested_topic'][:40]}", f"newvideo_topic_{i}")
            for i, t in enumerate(topics)
        ]
        options.append(("None of these", "newvideo_topic_none"))
        
        msg = f"🌍 **Topics for {country}:**\n\n"
        for i, t in enumerate(topics):
            msg += f"{i+1}. **{t['suggested_topic']}**\n"
            msg += f"   └ {t['headline'][:60]}...\n\n"
        
        await self.send_keyboard(msg, options)
    
    async def _show_evergreen_topics(self):
        """Show evergreen topic options."""
        topics = get_evergreen_topics()
        self.state["trending_topics"] = topics
        self.state["step"] = "choosing_topic"
        
        options = [
            (f"🌲 {t['suggested_topic'][:40]}", f"newvideo_topic_{i}")
            for i, t in enumerate(topics)
        ]
        
        msg = "🌲 **Evergreen Topics:**\n\n"
        for i, t in enumerate(topics):
            msg += f"{i+1}. **{t['suggested_topic']}**\n"
            msg += f"   └ {t['description']}\n\n"
        msg += "\nOr type your own topic."
        
        self.state["step"] = "waiting_topic_input"
        await self.send_keyboard(msg, options)
    
    async def _select_topic(self, idx: int):
        """Select a topic from the list."""
        topics = self.state.get("trending_topics", [])
        if idx < len(topics):
            self.state["topic"] = topics[idx].get("suggested_topic", "Unknown Topic")
            self.state["country"] = topics[idx].get("country")
        
        await self._generate_title()
    
    async def _generate_title(self):
        """Generate title options from topic."""
        topic = self.state["topic"]
        await self.send_message(f"✍️ Generating title for: **{topic}**...")
        
        # Use title_style.md patterns
        # For now, simple generation
        title = self._create_title_from_topic(topic)
        self.state["title"] = title
        self.state["step"] = "approving_title"
        self.save_state()  # Save for resume
        
        await self.send_keyboard(
            f"📌 **Proposed Title:**\n\n`{title}`\n\nApprove this title?",
            [
                ("✅ Approve", "newvideo_title_approve"),
                ("🔄 Regenerate", "newvideo_title_regen")
            ]
        )
    
    def _create_title_from_topic(self, topic: str) -> str:
        """
        Create title using title_style patterns.
        If topic already has parenthetical (e.g., from trend_scanner), return as-is.
        """
        # If already formatted with parenthetical, return as-is
        if '(' in topic and topic.strip().endswith(')'):
            return topic
        
        # Otherwise, wrap with appropriate pattern based on content
        topic_lower = topic.lower()
        
        if any(w in topic_lower for w in ["crisis", "collapse", "failing", "broken", "dying"]):
            return f"Why {topic}'s Economy is COLLAPSING (The Hidden Truth)"
        elif any(w in topic_lower for w in ["rich", "success", "boom", "miracle"]):
            return f"How {topic} Actually Got RICH (The Real Reason)"
        elif any(w in topic_lower for w in ["poor", "poorer", "decline"]):
            return f"Why {topic} is POORER Than You Think (The Economic Truth)"
        else:
            # Default: The REAL TRUTH pattern
            return f"The REAL TRUTH About {topic}'s Economy (Here's Why)"
    
    async def _regenerate_title(self):
        """Regenerate title with different pattern."""
        topic = self.state.get("raw_topic", self.state["topic"])
        country = self.state.get("country", "")
        
        # Get fresh patterns - never stack parentheticals
        import random
        if country:
            patterns = [
                f"The REAL TRUTH About {country}'s Economy (The Hidden Crisis)",
                f"Why {country}'s Economy is COLLAPSING (The 5 Fatal Wounds)",
                f"Why {country} Can't Grow (The Structural Trap)",
                f"The Slow DEATH of {country}'s Economy (And What Comes Next)",
                f"Why {country} is POORER Than You Think (The Economic Truth)",
            ]
        else:
            patterns = [
                f"The REAL TRUTH About {topic} (Here's Why)",
                f"Why {topic} is Worse Than You Think (The Hidden Truth)",
                f"The END of {topic} (And What Comes Next)",
            ]
        
        self.state["title"] = random.choice(patterns)
        
        await self.send_keyboard(
            f"📌 **New Title:**\n\n`{self.state['title']}`\n\nApprove?",
            [
                ("✅ Approve", "newvideo_title_approve"),
                ("🔄 Regenerate", "newvideo_title_regen")
            ]
        )
    
    async def _start_research(self):
        """Start deep research."""
        await self.send_message("🔬 Starting deep research...")
        self.state["step"] = "researching"
        
        research = deep_research(
            self.state["topic"],
            self.state.get("country")
        )
        self.state["research"] = research
        
        # Format summary for user (now using raw_facts)
        summary = research.get("raw_facts", research.get("summary", "Research complete."))
        
        # Truncate for display
        display_summary = summary[:1500] if len(summary) > 1500 else summary
        
        await self.send_keyboard(
            f"📚 **Research Facts:**\n\n{display_summary}...\n\nProceed to outline generation?",
            [
                ("✅ Approve Research", "newvideo_research_approve"),
                ("🔄 Regenerate", "newvideo_research_regen"),
                ("❌ Cancel", "newvideo_cancel")
            ]
        )
        self.state["step"] = "approving_research"
        self.save_state()  # Save for resume
    
    async def _regenerate_research(self):
        """Regenerate research."""
        await self.send_message("🔄 Regenerating research...")
        await self._start_research()
    
    async def _generate_outline(self):
        """Generate 7-chapter outline from research."""
        await self.send_message("📋 Generating outline (7 chapters)...")
        self.state["step"] = "generating_outline"
        
        result = generate_outline(
            title=self.state["title"],
            research=self.state["research"],
            country=self.state.get("country")
        )
        
        if not result.get("success"):
            await self.send_message(f"❌ Outline generation failed: {result.get('error', 'Unknown')}")
            return
        
        self.state["outline"] = result.get("outline", "")
        
        # Show outline for approval
        outline_text = format_outline_for_telegram(result)
        
        await self.send_keyboard(
            outline_text,
            [
                ("✅ Approve Outline", "newvideo_outline_approve"),
                ("🔄 Regenerate", "newvideo_outline_regen"),
                ("❌ Cancel", "newvideo_cancel")
            ]
        )
        self.state["step"] = "approving_outline"
        self.save_state()  # Save for resume
    
    async def _regenerate_outline(self):
        """Regenerate the outline with fresh approach."""
        await self.send_message("🔄 Regenerating outline...")
        await self._generate_outline()
    
    async def _generate_script(self):
        """Generate the video script."""
        await self.send_message("📝 Generating 4,500-word script (~30 min video)...")
        self.state["step"] = "generating_script"
        
        research_text = format_research_for_script(self.state["research"])
        
        # Include approved outline in the context
        outline_text = ""
        if self.state.get("outline"):
            outline_text = f"\n\n### APPROVED OUTLINE (follow this structure EXACTLY):\n{self.state['outline']}"
        
        full_context = research_text + outline_text
        
        try:
            # Check for test mode - topic starting with "TEST:" uses short script
            topic = self.state["title"]
            if self.state.get("test_mode") or (self.state.get("raw_topic", "").upper().startswith("TEST")):
                target_mins = 1  # ~150 words / ~6 images for quick testing
                self.state["test_mode"] = True
                await self.send_message("🧪 **TEST MODE**: Generating ultra-short ~150 word script (~6 images)")
            else:
                target_mins = 30  # 4500 words (150 words/min × 30 min)
            
            # Generate script using narrative engine (accepts research_data: str)
            result = generate_narrative_script(
                research_data=full_context,
                topic=topic,
                target_minutes=target_mins
            )
            
            if not result or not result.get("full_script"):
                await self.send_message("❌ Script generation failed. Try regenerating.")
                return
            
            script = result.get("full_script", "")
            word_count = result.get("total_words", len(script.split()))
            
            # Save to file
            script_path = os.path.join(self.output_dir, "script.txt")
            with open(script_path, "w") as f:
                f.write(script)
            
            self.state["script"] = script
            self.state["script_path"] = script_path
            
            # Show preview
            preview = script[:2000] if len(script) > 2000 else script
            
            # Send script as downloadable file
            try:
                with open(script_path, 'rb') as script_file:
                    await self.bot.send_document(
                        chat_id=self.chat_id,
                        document=script_file,
                        filename=f"script_{self.state['title'][:30].replace(' ', '_')}.txt",
                        caption="📄 Full script attached for easy copying"
                    )
            except Exception as e:
                print(f"Failed to send script file: {e}")
            
            # Upload script to Supabase storage
            if STORAGE_AVAILABLE and upload_file:
                # Use existing job_id or create new one
                if not hasattr(self, 'supabase_job_id') or not self.supabase_job_id:
                    self.supabase_job_id = f"video_{self.chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                try:
                    script_url = upload_file(
                        local_path=script_path,
                        job_id=self.supabase_job_id,
                        step_name='scripts',
                        filename=f"script.txt"
                    )
                    if script_url:
                        self.state['script_url'] = script_url
                        self.state['supabase_job_id'] = self.supabase_job_id
                        print(f"✅ Script uploaded to Supabase: {script_url}")
                except Exception as e:
                    print(f"Failed to upload script to Supabase: {e}")
            
            await self.send_keyboard(
                f"📜 **Script Generated**\n\n"
                f"**Word Count:** {word_count}\n"
                f"**Title:** {self.state['title']}\n\n"
                f"📄 Full script sent as file above.\n\n"
                f"Approve script?",
                [
                    ("✅ Approve Script", "newvideo_script_approve"),
                    ("🔄 Regenerate", "newvideo_script_regen")
                ]
            )
            self.state["step"] = "approving_script"
            self.save_state()  # Save for resume
        except Exception as e:
            await self.send_message(f"❌ Script generation error: {str(e)}\n\nUse the Regenerate button to retry.")
    
    async def _regenerate_script(self):
        """Regenerate script with different approach."""
        await self.send_message("🔄 Regenerating script...")
        await self._generate_script()
    
    async def _select_style(self):
        """Show style selection options."""
        self.state["step"] = "selecting_style"
        
        styles = get_style_options()
        options = [
            (f"🎨 {s['name']}", f"newvideo_style_{s['id']}")
            for s in styles
        ]
        
        msg = "🎨 Select Video Style:\n\n"
        for s in styles:
            # NO markdown to avoid parsing errors
            msg += f"- {s['name']}\n{s['description']}\n\n"
        
        await self.send_keyboard(msg, options)
    
    async def _apply_style(self, style_id: str):
        """Apply selected style and generate images."""
        self.state["style"] = style_id
        await self.send_message(f"🎨 Style selected: {style_id}\n\n⏳ Generating images...")
        
        # Validate script exists
        if not self.state.get("script"):
            await self.send_message("❌ Error: Narrative script is missing. The saved session may be incomplete. Please use /start to restart.")
            return

        # Generate images
        if not generate_images_for_script:
            await self.send_message("❌ Image generator module not loaded. Check server logs.")
            return

        images = generate_images_for_script(
            script=self.state["script"],
            output_dir=self.output_dir,
            style=style_id
        )
        self.state["images"] = images
        
        # Get actual counts from result dict
        total_chunks = images.get('total_chunks', 0)
        successful = images.get('successful', 0)
        failed = images.get('failed', 0)
        
        # Send sample images to Telegram (first 3)
        chunks_data = images.get('chunks', [])
        sent_previews = 0
        for chunk_result in chunks_data[:3]:  # First 3 as preview
            if chunk_result.get('success') and chunk_result.get('path'):
                try:
                    with open(chunk_result['path'], 'rb') as img_file:
                        await self.bot.send_photo(
                            chat_id=self.chat_id,
                            photo=img_file,
                            caption=f"Image {chunk_result.get('index', 0)+1}/{total_chunks}"
                        )
                        sent_previews += 1
                except Exception as e:
                    print(f"Failed to send preview image: {e}")
        
        # Upload images to Supabase storage for persistence
        if STORAGE_AVAILABLE and upload_file:
            job_id = f"video_{self.chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            uploaded_urls = []
            for chunk_result in chunks_data:
                if chunk_result.get('success') and chunk_result.get('path'):
                    try:
                        url = upload_file(
                            local_path=chunk_result['path'],
                            job_id=job_id,
                            step_name='images',
                            filename=f"chunk_{chunk_result.get('index', 0):03d}.png"
                        )
                        if url:
                            uploaded_urls.append(url)
                            chunk_result['supabase_url'] = url
                    except Exception as e:
                        print(f"Failed to upload image to Supabase: {e}")
            
            if uploaded_urls:
                print(f"✅ Uploaded {len(uploaded_urls)} images to Supabase")
                self.state['supabase_job_id'] = job_id
        
        status_msg = f"🖼️ **Image Generation Complete**\n\n"
        status_msg += f"✅ Generated: {successful}/{total_chunks} images\n"
        if failed > 0:
            status_msg += f"❌ Failed: {failed}\n"
        if sent_previews > 0:
            status_msg += f"📸 Previewed: {sent_previews} samples above\n"
        status_msg += f"\nApprove images?"
        
        await self.send_keyboard(
            status_msg,
            [
                ("✅ Approve Images", "newvideo_images_approve"),
                ("🔄 Regenerate", "newvideo_images_regen")
            ]
        )
        self.state["step"] = "approving_images"
        self.save_state()  # Save for resume
    
    async def _regenerate_images(self):
        """Regenerate images."""
        await self.send_message("🔄 Regenerating images...")
        await self._apply_style(self.state["style"])
    
    async def _generate_video(self):
        """Generate video from images and audio."""
        await self.send_message("🎬 Generating video...\n\n⏳ This involves generating audio for each chunk and assembling the video. This may take several minutes for longer scripts.")
        self.state["step"] = "generating_video"
        
        # Get image data from state - handle both old (list) and new (dict) formats
        images_data = self.state.get("images", {})
        
        # New format: dict with 'chunks' key
        if isinstance(images_data, dict):
            image_chunks = images_data.get("chunks", [])
        # Legacy format: images was stored as a list directly
        elif isinstance(images_data, list):
            image_chunks = images_data
        else:
            image_chunks = []
        
        if not image_chunks:
            await self.send_message("❌ No image data found. Please use /newvideo → Start Fresh to regenerate images with the new format.")
            return
        
        await self.send_message(f"📊 Processing {len(image_chunks)} chunks...")
        
        # Build chunk objects for video generation
        video_chunks = []
        audio_dir = os.path.join(self.output_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        for i, img_chunk in enumerate(image_chunks):
            chunk_text = img_chunk.get("chunk_text", "")
            screenshot_path = img_chunk.get("path") if img_chunk.get("success") else None
            
            # Generate audio for this chunk
            audio_path = os.path.join(audio_dir, f"chunk_{i:03d}.wav")
            
            try:
                audio_result = generate_audio_from_script(chunk_text, audio_path)
                if not audio_result.get("success"):
                    print(f"Audio generation failed for chunk {i}: {audio_result.get('error')}")
                    continue
            except Exception as e:
                print(f"Audio error chunk {i}: {e}")
                continue
            
            video_chunks.append({
                "id": i,
                "text": chunk_text,
                "audio_path": audio_path,
                "screenshot_path": screenshot_path
            })
            
            # Progress update every 20 chunks
            if (i + 1) % 20 == 0:
                await self.send_message(f"⏳ Processed {i + 1}/{len(image_chunks)} chunks...")
        
        if not video_chunks:
            await self.send_message("❌ Failed to generate audio for any chunks.")
            return
        
        await self.send_message(f"✅ Audio generated for {len(video_chunks)} chunks.\n\n🎬 Now assembling video...")
        
        # Progress tracking for video assembly
        progress_messages = []
        
        def video_progress_callback(current, total, message):
            """Callback for video assembly progress - stores messages for later sending"""
            progress_messages.append(message)
            print(message)  # Also log to console
        
        # Build video from chunks with progress tracking
        try:
            video_result = build_video_from_chunks(video_chunks, progress_callback=video_progress_callback)
            
            # Send buffered progress messages (can't await from sync callback)
            # Progress is logged to Railway console instead
            
            if not video_result.get("success"):
                await self.send_message(f"❌ Video assembly failed: {video_result.get('message')}")
                return
            
            video_path = video_result.get("output_path")
            duration = video_result.get("duration", 0)
            
            self.state["video_path"] = video_path
            
            # Note: We don't upload the pre-subtitle video to save storage
            # Only the final subtitled video gets uploaded to Supabase
            
            
            # Send video file to Telegram for preview (skip if too large)
            video_size_mb = os.path.getsize(video_path) / (1024 * 1024) if video_path and os.path.exists(video_path) else 0
            if video_size_mb > 45:
                await self.send_message(f"⚠️ Video is {video_size_mb:.1f}MB - too large for Telegram preview (limit 50MB). Video saved locally.")
            else:
                try:
                    with open(video_path, 'rb') as video_file:
                        await self.bot.send_video(
                            chat_id=self.chat_id,
                            video=video_file,
                            caption=f"🎬 Video preview ({duration/60:.1f} min)"
                        )
                except Exception as e:
                    print(f"Failed to send video preview: {e}")
                    await self.send_message(f"⚠️ Video preview failed: {str(e)[:100]}")
            
            await self.send_keyboard(
                f"🎬 **Video Generated**\n\n"
                f"Duration: {duration/60:.1f} minutes\n"
                f"Chunks: {len(video_chunks)}\n\n"
                f"Approve video?",
                [
                    ("✅ Approve Video", "newvideo_video_approve"),
                    ("🔄 Regenerate", "newvideo_video_regen")
                ]
            )
            self.state["step"] = "approving_video"
            self.save_state()
            
        except Exception as e:
            await self.send_message(f"❌ Video generation error: {str(e)}")
            print(f"Video generation exception: {e}")
    
    async def _add_subtitles(self):
        """Add subtitles to video."""
        await self.send_message("📝 Adding subtitles...")
        
        video_path = self.state.get("video_path")
        if not video_path:
            await self.send_message("❌ Video path not found in state. Cannot add subtitles.")
            return
        
        try:
            result = generate_subtitled_video(
                video_path=video_path,
                audio_path=None  # Let it extract audio from video
            )
            
            if not result.get("success"):
                await self.send_message(f"❌ Subtitle generation failed: {result.get('error', 'Unknown error')}")
                return
            
            subtitled_path = result.get("subtitled_video")
            srt_result_path = result.get("srt_path")
            
            # Validate subtitled video path
            if not subtitled_path or not os.path.exists(subtitled_path):
                await self.send_message(f"❌ Subtitled video file not created. FFmpeg may have failed.")
                print(f"DEBUG: subtitled_video from result = {subtitled_path}")
                return
            
            self.state["subtitled_video_path"] = subtitled_path
            self.state["srt_path"] = srt_result_path
            
            srt_path = self.state.get("srt_path")
            
            # Upload subtitled video and SRT to Supabase for persistence
            if STORAGE_AVAILABLE:
                try:
                    if subtitled_path and os.path.exists(subtitled_path):
                        subtitled_url = upload_file(
                            local_path=subtitled_path,
                            job_id=self.supabase_job_id,
                            step_name="video",
                            filename="video_subtitled.mp4"
                        )
                        if subtitled_url:
                            self.state["subtitled_video_url"] = subtitled_url
                    
                    if srt_path and os.path.exists(srt_path):
                        srt_url = upload_file(
                            local_path=srt_path,
                            job_id=self.supabase_job_id,
                            step_name="video",
                            filename="video.srt"
                        )
                        if srt_url:
                            self.state["srt_url"] = srt_url
                    
                    # Also upload state for recovery
                    upload_state(self.supabase_job_id, self.state)
                    await self.send_message(f"☁️ Subtitled video uploaded to cloud storage")
                except Exception as e:
                    print(f"Failed to upload subtitled video to Supabase: {e}")
            
            # Try to send video preview (skip if too large)
            if subtitled_path and os.path.exists(subtitled_path):
                video_size_mb = os.path.getsize(subtitled_path) / (1024 * 1024)
                if video_size_mb > 45:
                    await self.send_message(f"⚠️ Subtitled video is {video_size_mb:.1f}MB - too large for Telegram preview. You can download from Supabase.")
                else:
                    try:
                        with open(subtitled_path, 'rb') as video_file:
                            await self.bot.send_video(
                                chat_id=self.chat_id,
                                video=video_file,
                                caption="📝 Subtitled video preview"
                            )
                    except Exception as e:
                        print(f"Failed to send subtitled video preview: {e}")
                        await self.send_message(f"⚠️ Video preview failed: {str(e)[:100]}")
            
            await self.send_keyboard(
                f"✅ **Subtitled Video Generated**\n\n"
                f"Path: `{subtitled_path}`\n\n"
                f"Approve subtitles or regenerate?",
                [
                    ("✅ Approve Subtitles", "newvideo_subtitles_approve"),
                    ("🔄 Regenerate", "newvideo_subtitles_regen"),
                ]
            )
            self.state["step"] = "approving_subtitles"
            self.save_state()  # Save for resume
        except Exception as e:
            await self.send_message(f"❌ Subtitle error: {str(e)}")
            print(f"Subtitle exception: {e}")
    
    async def _regenerate_video(self):
        """Regenerate video from images and audio."""
        await self.send_message("🔄 Regenerating video...")
        await self._generate_video()
    
    async def _regenerate_subtitles(self):
        """Regenerate subtitles."""
        await self.send_message("🔄 Regenerating subtitles...")
        await self._add_subtitles()
    
    async def _generate_metadata(self):
        """Generate tags and description (separate from thumbnail)."""
        await self.send_message("📊 Generating tags and description...")
        
        # Generate timestamps from SRT
        timestamps_text = ""
        if self.state.get("srt_path"):
            timestamps_result = generate_timestamps_from_srt(self.state["srt_path"])
            if timestamps_result.get("success"):
                timestamps_text = timestamps_result.get("formatted", "")
                self.state["timestamps"] = timestamps_text
        
        # Generate full metadata (tags, description with timestamps)
        # Get reference metadata from state (set during research phase)
        original_title = self.state.get("reference_title", self.state.get("title", ""))
        original_description = self.state.get("reference_description", "")
        original_tags = self.state.get("reference_tags", [])
        
        metadata = generate_full_metadata(
            original_title=original_title,
            original_description=original_description,
            original_tags=original_tags,
            topic=self.state.get("topic", self.state.get("title", "")),
            script_text=self.state.get("script", ""),
            timestamps_text=timestamps_text
        )
        self.state["description"] = metadata.get("description")
        self.state["tags"] = metadata.get("tags", [])
        
        # Show for approval
        desc_preview = self.state["description"][:500] if self.state["description"] else "No description"
        tags_preview = ", ".join(self.state["tags"][:8]) if self.state["tags"] else "No tags"
        
        await self.send_keyboard(
            f"📊 **Metadata Generated**\n\n"
            f"**Tags:** {tags_preview}...\n\n"
            f"**Description Preview:**\n```\n{desc_preview}...\n```\n\n"
            f"Approve metadata?",
            [
                ("✅ Approve Metadata", "newvideo_metadata_approve"),
                ("🔄 Regenerate", "newvideo_metadata_regen"),
            ]
        )
        self.state["step"] = "approving_metadata"
        self.save_state()  # Save for resume
    
    async def _regenerate_metadata(self):
        """Regenerate metadata."""
        await self.send_message("🔄 Regenerating metadata...")
        await self._generate_metadata()
    
    async def _generate_thumbnail(self):
        """Generate thumbnail (separate step)."""
        await self.send_message("🖼️ Generating thumbnail...")
        
        thumbnail_path = os.path.join(self.output_dir, "thumbnail.jpg")
        try:
            result = generate_thumbnail(
                topic=self.state.get("topic", self.state.get("title", "")),
                title=self.state.get("title", ""),
                output_path=thumbnail_path,
                auto_compress=True  # Ensure compression for YouTube
            )
            if not result or not os.path.exists(thumbnail_path):
                await self.send_message("⚠️ Thumbnail generation failed. Proceeding without thumbnail...")
                self.state["thumbnail_path"] = None
            else:
                self.state["thumbnail_path"] = thumbnail_path
        except Exception as e:
            await self.send_message(f"⚠️ Thumbnail error: {str(e)[:100]}. Proceeding without thumbnail...")
            self.state["thumbnail_path"] = None
        
        # Send thumbnail preview as photo
        if self.state.get("thumbnail_path") and os.path.exists(self.state["thumbnail_path"]):
            try:
                with open(self.state["thumbnail_path"], 'rb') as thumb_file:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=thumb_file,
                        caption="🖼️ Thumbnail preview"
                    )
            except Exception as e:
                print(f"Failed to send thumbnail preview: {e}")
        
        await self.send_keyboard(
            f"🖼️ **Thumbnail Generated**\n\n"
            f"Approve thumbnail?",
            [
                ("✅ Approve Thumbnail", "newvideo_thumbnail_approve"),
                ("🔄 Regenerate", "newvideo_thumbnail_regen"),
            ]
        )
        self.state["step"] = "approving_thumbnail"
        self.save_state()  # Save for resume
    
    async def _regenerate_thumbnail(self):
        """Regenerate thumbnail."""
        await self.send_message("🔄 Regenerating thumbnail...")
        await self._generate_thumbnail()
    
    async def _prepare_upload(self):
        """Prepare files for upload and show final confirmation."""
        await self.send_message("📦 Preparing files for upload...")
        
        # Get video path - prefer subtitled, fallback to regular
        video_path = self.state.get("subtitled_video_path") or self.state.get("video_path")
        thumbnail_path = self.state.get("thumbnail_path")
        
        # Validate paths exist
        if not video_path or not os.path.exists(video_path):
            await self.send_message(f"❌ Video file not found: {video_path}")
            return
        
        # Rename files - use raw topic or extract from title
        topic_for_naming = self.state.get("topic") or self.state.get("raw_topic") or extract_topic_from_title(self.state["title"])
        new_video, new_thumb = rename_output_files(
            video_path,
            thumbnail_path,
            topic_for_naming
        )
        self.state["final_video_path"] = new_video
        self.state["final_thumbnail_path"] = new_thumb
        
        # Get display names (handle None gracefully)
        video_name = os.path.basename(new_video) if new_video else "No video"
        thumb_name = os.path.basename(new_thumb) if new_thumb else "No thumbnail"
        
        await self.send_keyboard(
            f"🚀 **Ready to Upload**\n\n"
            f"**Title:** {self.state['title']}\n"
            f"**Video:** `{video_name}`\n"
            f"**Thumbnail:** `{thumb_name}`\n\n"
            f"Upload to YouTube?",
            [
                ("🚀 Upload Now", "newvideo_upload_confirm"),
                ("💾 Save Locally", "newvideo_upload_cancel")
            ]
        )
        self.state["step"] = "confirming_upload"
    
    async def _upload_to_youtube(self):
        """Upload to YouTube."""
        await self.send_message("📤 Uploading to YouTube...")
        
        from execution.youtube_upload import upload_video_with_captions
        
        result = upload_video_with_captions(
            video_path=self.state["final_video_path"],
            title=self.state["title"],
            description=self.state["description"],
            tags=self.state["tags"],
            thumbnail_path=self.state.get("final_thumbnail_path"),
            srt_path=self.state.get("srt_path")
        )
        
        if result.get("success"):
            await self.send_message(
                f"✅ **Upload Complete!**\n\n"
                f"**Video ID:** `{result.get('video_id')}`\n"
                f"**URL:** {result.get('url')}"
            )
        else:
            await self.send_message(f"❌ Upload failed: {result.get('error')}")


# Pipeline instance storage
_pipeline_instances: Dict[int, NewVideoPipeline] = {}


def get_pipeline(chat_id: int) -> Optional[NewVideoPipeline]:
    """Get existing pipeline instance."""
    return _pipeline_instances.get(chat_id)


def create_pipeline(chat_id: int, send_message_func, send_keyboard_func, bot=None, test_mode: bool = False) -> NewVideoPipeline:
    """Create new pipeline instance."""
    pipeline = NewVideoPipeline(chat_id, send_message_func, send_keyboard_func, bot=bot, test_mode=test_mode)
    _pipeline_instances[chat_id] = pipeline
    return pipeline


def remove_pipeline(chat_id: int):
    """Remove pipeline instance."""
    if chat_id in _pipeline_instances:
        del _pipeline_instances[chat_id]


def has_saved_session(chat_id: int) -> bool:
    """Check if there's a saved session for this chat."""
    return NewVideoPipeline.has_saved_state(chat_id)


def get_saved_session_info(chat_id: int) -> Optional[Dict]:
    """Get saved session info for resume prompt."""
    return NewVideoPipeline.load_state(chat_id)
