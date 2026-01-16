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

# Import existing generators (with try/except for missing modules)
try:
    from execution.generate_script import generate_script
except ImportError:
    generate_script = None

try:
    from execution.generate_ai_images import generate_images_for_script
except ImportError:
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


class NewVideoPipeline:
    """
    Orchestrates the research-first video generation pipeline.
    Each step waits for user approval via Telegram.
    """
    
    def __init__(self, chat_id: int, send_message_func, send_keyboard_func):
        """
        Initialize pipeline.
        
        Args:
            chat_id: Telegram chat ID
            send_message_func: Async function to send messages
            send_keyboard_func: Async function to send keyboard options
        """
        self.chat_id = chat_id
        self.send_message = send_message_func
        self.send_keyboard = send_keyboard_func
        
        # Pipeline state
        self.state = {
            "step": "init",
            "topic": None,
            "title": None,
            "research": None,
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
            "output_dir": None
        }
        
        # Create output directory
        self.output_dir = f".tmp/pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        self.state["output_dir"] = self.output_dir
    
    async def start(self):
        """Start the pipeline - ask to scan trends."""
        self.state["step"] = "ask_opportunity"
        
        await self.send_keyboard(
            "🎬 **New Video Pipeline**\n\nShould I scan for trending opportunities?",
            [
                ("Yes - Scan News", "newvideo_scan_yes"),
                ("No - I have a topic", "newvideo_scan_no"),
                ("Evergreen Topic", "newvideo_evergreen")
            ]
        )
    
    async def handle_callback(self, callback_data: str, user_input: str = None) -> bool:
        """
        Handle user callback or input.
        
        Returns True if pipeline should continue.
        """
        step = self.state["step"]
        
        # Step 1: Scan for opportunities
        if callback_data == "newvideo_scan_yes":
            await self._scan_trends()
            return True
        
        elif callback_data == "newvideo_scan_no":
            self.state["step"] = "waiting_topic_input"
            await self.send_message("📝 Enter your topic:")
            return True
        
        elif callback_data == "newvideo_evergreen":
            await self._show_evergreen_topics()
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
        
        # Step 4: Research approval
        elif callback_data == "newvideo_research_approve":
            await self._generate_script()
            return True
        
        # Step 5: Script approval
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
        
        # Step 9: Subtitles done - generate metadata
        elif callback_data == "newvideo_subtitles_approve":
            await self._generate_metadata()
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
        
        # Handle text input
        if step == "waiting_topic_input" and user_input:
            self.state["topic"] = user_input
            await self._generate_title()
            return True
        
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
        
        # Format summary for user
        summary = research.get("summary", "Research complete.")
        
        await self.send_keyboard(
            f"📚 **Research Summary:**\n\n{summary[:1500]}...\n\nProceed to script generation?",
            [
                ("✅ Approve Research", "newvideo_research_approve"),
                ("❌ Cancel", "newvideo_cancel")
            ]
        )
        self.state["step"] = "approving_research"
    
    async def _generate_script(self):
        """Generate the video script."""
        await self.send_message("📝 Generating 4,500-word script (7 chapters)...")
        self.state["step"] = "generating_script"
        
        research_text = format_research_for_script(self.state["research"])
        
        # Generate script using style guide
        script_path = os.path.join(self.output_dir, "script.txt")
        script = generate_script(
            topic=self.state["topic"],
            title=self.state["title"],
            research=research_text,
            output_path=script_path,
            target_words=4500
        )
        
        self.state["script"] = script
        self.state["script_path"] = script_path
        
        # Show preview
        preview = script[:2000] if len(script) > 2000 else script
        word_count = len(script.split())
        
        await self.send_keyboard(
            f"📜 **Script Generated**\n\n"
            f"**Word Count:** {word_count}\n"
            f"**Title:** {self.state['title']}\n\n"
            f"**Preview:**\n```\n{preview}...\n```\n\n"
            f"Approve script?",
            [
                ("✅ Approve Script", "newvideo_script_approve"),
                ("🔄 Regenerate", "newvideo_script_regen")
            ]
        )
        self.state["step"] = "approving_script"
    
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
        
        msg = "🎨 **Select Video Style:**\n\n"
        for s in styles:
            msg += f"**{s['name']}**\n{s['description']}\n\n"
        
        await self.send_keyboard(msg, options)
    
    async def _apply_style(self, style_id: str):
        """Apply selected style and generate images."""
        self.state["style"] = style_id
        await self.send_message(f"🎨 Style selected: {style_id}\n\n⏳ Generating images...")
        
        # Generate images
        images = generate_images_for_script(
            script=self.state["script"],
            output_dir=self.output_dir,
            style=style_id
        )
        self.state["images"] = images
        
        await self.send_keyboard(
            f"🖼️ **{len(images)} Images Generated**\n\nApprove images?",
            [
                ("✅ Approve Images", "newvideo_images_approve"),
                ("🔄 Regenerate", "newvideo_images_regen")
            ]
        )
        self.state["step"] = "approving_images"
    
    async def _regenerate_images(self):
        """Regenerate images."""
        await self.send_message("🔄 Regenerating images...")
        await self._apply_style(self.state["style"])
    
    async def _generate_video(self):
        """Generate video from images and audio."""
        await self.send_message("🎬 Generating video...")
        self.state["step"] = "generating_video"
        
        # Generate audio
        audio_path = os.path.join(self.output_dir, "audio.mp3")
        generate_audio_from_script(self.state["script"], audio_path)
        self.state["audio_path"] = audio_path
        
        # Build video
        video_path = os.path.join(self.output_dir, "video.mp4")
        build_video_from_chunks(
            images=self.state["images"],
            audio=audio_path,
            output=video_path
        )
        self.state["video_path"] = video_path
        
        await self.send_keyboard(
            f"🎬 **Video Generated**\n\nPath: `{video_path}`\n\nApprove video?",
            [
                ("✅ Approve Video", "newvideo_video_approve"),
                ("🔄 Regenerate", "newvideo_video_regen")
            ]
        )
        self.state["step"] = "approving_video"
    
    async def _add_subtitles(self):
        """Add subtitles to video."""
        await self.send_message("📝 Adding subtitles...")
        
        result = generate_subtitled_video(
            video_path=self.state["video_path"],
            audio_path=self.state["audio_path"]
        )
        
        self.state["subtitled_video_path"] = result.get("subtitled_video")
        self.state["srt_path"] = result.get("srt_path")
        
        await self.send_keyboard(
            "✅ **Subtitles Added**\n\nProceed to thumbnail and metadata?",
            [
                ("✅ Continue", "newvideo_subtitles_approve"),
            ]
        )
        self.state["step"] = "subtitles_done"
    
    async def _generate_metadata(self):
        """Generate tags, description, and thumbnail."""
        await self.send_message("📊 Generating metadata and thumbnail...")
        
        # Generate timestamps
        if self.state["srt_path"]:
            timestamps = generate_timestamps_from_srt(self.state["srt_path"])
            self.state["timestamps"] = timestamps
        
        # Generate full metadata
        metadata = generate_full_metadata(
            script=self.state["script"],
            title=self.state["title"],
            timestamps=self.state.get("timestamps")
        )
        self.state["description"] = metadata.get("description")
        self.state["tags"] = metadata.get("tags", [])
        
        # Generate thumbnail
        thumbnail_path = os.path.join(self.output_dir, "thumbnail.jpg")
        generate_thumbnail(
            title=self.state["title"],
            topic=self.state["topic"],
            style=self.state["style"],
            output_path=thumbnail_path
        )
        self.state["thumbnail_path"] = thumbnail_path
        
        await self.send_keyboard(
            f"🖼️ **Thumbnail Generated**\n\n"
            f"**Tags:** {', '.join(self.state['tags'][:5])}...\n\n"
            f"Approve thumbnail?",
            [
                ("✅ Approve", "newvideo_thumbnail_approve"),
                ("🔄 Regenerate", "newvideo_thumbnail_regen")
            ]
        )
        self.state["step"] = "approving_thumbnail"
    
    async def _regenerate_thumbnail(self):
        """Regenerate thumbnail."""
        await self.send_message("🔄 Regenerating thumbnail...")
        await self._generate_metadata()
    
    async def _prepare_upload(self):
        """Prepare files for upload and show final confirmation."""
        await self.send_message("📦 Preparing files for upload...")
        
        # Rename files
        topic_slug = extract_topic_from_title(self.state["title"])
        new_video, new_thumb = rename_output_files(
            self.state["subtitled_video_path"] or self.state["video_path"],
            self.state["thumbnail_path"],
            topic_slug
        )
        self.state["final_video_path"] = new_video
        self.state["final_thumbnail_path"] = new_thumb
        
        await self.send_keyboard(
            f"🚀 **Ready to Upload**\n\n"
            f"**Title:** {self.state['title']}\n"
            f"**Video:** `{os.path.basename(new_video)}`\n"
            f"**Thumbnail:** `{os.path.basename(new_thumb)}`\n\n"
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
        
        from youtube_upload import upload_video_with_captions
        
        result = upload_video_with_captions(
            video_path=self.state["final_video_path"],
            title=self.state["title"],
            description=self.state["description"],
            tags=self.state["tags"],
            thumbnail_path=self.state["final_thumbnail_path"],
            captions_path=self.state.get("srt_path")
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


def create_pipeline(chat_id: int, send_message_func, send_keyboard_func) -> NewVideoPipeline:
    """Create new pipeline instance."""
    pipeline = NewVideoPipeline(chat_id, send_message_func, send_keyboard_func)
    _pipeline_instances[chat_id] = pipeline
    return pipeline


def remove_pipeline(chat_id: int):
    """Remove pipeline instance."""
    if chat_id in _pipeline_instances:
        del _pipeline_instances[chat_id]
