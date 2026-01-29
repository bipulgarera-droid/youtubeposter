#!/usr/bin/env python3
"""
Viral Video Cloning Pipeline with Step-by-Step Approvals
Creates an improved version of a viral video to appear in suggested videos.

Flow (with approvals):
1. Fetch video info → Show original details
2. Transcribe → Show transcript preview → Wait for approval
3. Research → Show research → Wait for approval
4. Generate script → Show script + file → Wait for approval
5. Select style (Ghibli/Oil Painting)
6. Generate images → Show samples → Wait for approval
7. Generate audio + video → Show preview → Wait for approval
8. Generate metadata → Show title/desc/tags → Wait for approval
9. Generate thumbnail → Show preview → Wait for approval
10. Upload → Confirm → Upload
"""

import os
import asyncio
from typing import Dict, Optional, Callable, List
from datetime import datetime
from pathlib import Path
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

# Available styles (same as new_video_pipeline)
STYLES = {
    "ghibli_cartoon": {
        "name": "Ghibli Cartoon (Primary)",
        "description": "Studio Ghibli-inspired animated style. Clean lines, expressive characters, detailed backgrounds. Used in 75% of videos."
    },
    "impressionist_oil": {
        "name": "Impressionist Oil Painting",
        "description": "Classic French impressionist style. Oil painting aesthetic with visible brushstrokes. Muted color palette. Used for European/historical topics."
    }
}
DEFAULT_STYLE = "ghibli_cartoon"


class ViralVideoPipeline:
    """Pipeline to clone and improve a viral video with step-by-step approvals."""
    
    def __init__(self, video_id: str, chat_id: int, send_message_func, send_keyboard_func, bot=None):
        """
        Initialize pipeline with Telegram integration for approvals.
        
        Args:
            video_id: YouTube video ID to clone
            chat_id: Telegram chat ID
            send_message_func: Async function to send messages
            send_keyboard_func: Async function to send keyboard options
            bot: Telegram bot instance for sending files/photos
        """
        self.video_id = video_id
        self.chat_id = chat_id
        self.send_message = send_message_func
        self.send_keyboard = send_keyboard_func
        self.bot = bot
        
        # Output directory
        self.output_dir = f".tmp/viral_pipeline/{video_id}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Pipeline state
        self.state = {
            "step": "init",
            "video_id": video_id,
            "original": {},
            "transcript": "",
            "research": {},
            "research_formatted": "",
            "script": "",
            "style": DEFAULT_STYLE,
            "title": "",
            "description": "",
            "tags": [],
            "thumbnail_analysis": {},
            "images": [],
            "audio_result": {},
            "video_path": "",
            "subtitled_video_path": "",
            "thumbnail_path": "",
            "output_dir": self.output_dir
        }
    
    def checkpoint_path(self) -> str:
        """Get checkpoint file path for this video."""
        checkpoint_dir = Path(".tmp/viral_pipeline")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return str(checkpoint_dir / f"{self.video_id}_checkpoint.json")
    
    def save_checkpoint(self, step: str):
        """Save current state to checkpoint file."""
        import json
        self.state["last_completed_step"] = step
        try:
            with open(self.checkpoint_path(), 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(self) -> bool:
        """Load state from checkpoint file if exists."""
        import json
        try:
            with open(self.checkpoint_path(), 'r') as f:
                self.state = json.load(f)
                return True
        except:
            return False
    
    def clear_checkpoint(self):
        """Remove checkpoint file after successful completion."""
        try:
            Path(self.checkpoint_path()).unlink(missing_ok=True)
        except:
            pass
    
    async def start(self):
        """Start the viral cloning pipeline - fetch video info."""
        await self.send_message("🚀 *Starting Viral Video Clone Pipeline*")
        await self.send_message(f"📺 Video ID: `{self.video_id}`")
        
        await self._fetch_video_info()
    
    async def handle_callback(self, callback_data: str, user_input: str = None) -> bool:
        """
        Handle user callback or input.
        
        Returns True if pipeline should continue, False if complete.
        """
        step = self.state["step"]
        
        # Transcript approval
        if callback_data == "viral_transcript_approve":
            await self._start_research()
            return True
        
        elif callback_data == "viral_transcript_regen":
            await self._transcribe()
            return True
        
        elif callback_data == "viral_cancel":
            await self.send_message("❌ Pipeline cancelled.")
            return False
        
        # Research approval
        elif callback_data == "viral_research_approve":
            await self._generate_script()
            return True
        
        elif callback_data == "viral_research_regen":
            await self._start_research()
            return True
        
        # Script approval
        elif callback_data == "viral_script_approve":
            await self._select_style()
            return True
        
        elif callback_data == "viral_script_regen":
            await self._generate_script()
            return True
        
        # Style selection
        elif callback_data.startswith("viral_style_"):
            style_id = callback_data.replace("viral_style_", "")
            await self._apply_style(style_id)
            return True
        
        # Images approval
        elif callback_data == "viral_images_approve":
            await self._generate_video()
            return True
        
        elif callback_data == "viral_images_regen":
            await self._generate_images()
            return True
        
        # Video approval
        elif callback_data == "viral_video_approve":
            await self._generate_metadata()
            return True
        
        elif callback_data == "viral_video_regen":
            await self._generate_video()
            return True
        
        # Metadata approval
        elif callback_data == "viral_metadata_approve":
            await self._generate_thumbnail()
            return True
        
        elif callback_data == "viral_metadata_regen":
            await self._generate_metadata()
            return True
        
        # Thumbnail approval
        elif callback_data == "viral_thumbnail_approve":
            await self._prepare_upload()
            return True
        
        elif callback_data == "viral_thumbnail_regen":
            await self._generate_thumbnail()
            return True
        
        # Upload confirmation
        elif callback_data == "viral_upload_confirm":
            await self._upload_to_youtube()
            return False  # Pipeline complete
        
        elif callback_data == "viral_upload_cancel":
            await self.send_message("📁 Upload cancelled. Files saved locally.")
            return False
        
        return True
    
    async def _fetch_video_info(self):
        """Fetch original video's details and show preview."""
        await self.send_message("📊 Fetching original video details...")
        
        info = get_video_details(self.video_id)
        if not info.get("success"):
            await self.send_message(f"❌ Could not fetch video info: {info.get('error')}")
            return
        
        self.state["original"] = {
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "tags": info.get("tags", []),
            "thumbnail_url": info.get("thumbnails", {}).get("high", {}).get("url", ""),
            "channel": info.get("channelTitle", ""),
            "views": info.get("viewCount", 0)
        }
        
        # Show original video info
        views = int(self.state["original"]["views"]) if self.state["original"]["views"] else 0
        await self.send_message(
            f"📹 *Original Video:*\n\n"
            f"*Title:* {self.state['original']['title']}\n"
            f"*Channel:* {self.state['original']['channel']}\n"
            f"*Views:* {views:,}\n"
            f"*Tags:* {', '.join(self.state['original']['tags'][:5])}..."
        )
        
        self.save_checkpoint("fetch_video_info")
        
        # Start transcription automatically
        await self._transcribe()
    
    async def _transcribe(self):
        """Transcribe the video and show preview for approval."""
        await self.send_message("📝 Transcribing video...")
        
        result = transcribe_video(f"https://youtube.com/watch?v={self.video_id}")
        if not result.get("success"):
            await self.send_message(f"❌ Transcription failed: {result.get('message')}")
            return
        
        self.state["transcript"] = result.get("transcript", "")
        word_count = len(self.state["transcript"].split())
        
        self.save_checkpoint("transcribe")
        
        # Show transcript preview
        preview = self.state["transcript"][:800].replace("*", "").replace("_", "") + "..."
        await self.send_message(
            f"📜 *Transcript Preview*\n\n"
            f"{preview}\n\n"
            f"---\n"
            f"📊 Word count: {word_count}"
        )
        
        self.state["step"] = "approving_transcript"
        
        # Ask for approval
        await self.send_keyboard(
            "Proceed to research?",
            [
                [("✅ Approve Research", "viral_transcript_approve")],
                [("🔄 Regenerate", "viral_transcript_regen")],
                [("❌ Cancel", "viral_cancel")]
            ]
        )
    
    async def _start_research(self):
        """Research deeper using transcript and show results."""
        await self.send_message("🔍 Researching to make it 30% better...")
        
        topic = self.state["original"]["title"]
        
        research = deep_research(
            topic=topic,
            country=None,
            source_article={
                "title": self.state["original"]["title"],
                "snippet": self.state["transcript"][:2000]
            }
        )
        
        self.state["research"] = research
        self.state["research_formatted"] = format_research_for_script(research)
        
        self.save_checkpoint("research")
        
        # Show research summary
        key_figures = research.get("key_figures", [])[:3]
        stats = research.get("statistics", [])[:3]
        news_count = len(research.get("recent_news", []))
        
        research_preview = (
            f"🔬 *Research Complete*\n\n"
            f"*Key Figures:*\n" + "\n".join([f"- {f}" for f in key_figures]) + "\n\n"
            f"*Statistics:*\n" + "\n".join([f"- {s}" for s in stats]) + "\n\n"
            f"📰 Found {news_count} related news articles\n\n"
            "... truncated for display"
        )
        
        await self.send_message(research_preview)
        
        self.state["step"] = "approving_research"
        
        # Ask for approval
        await self.send_keyboard(
            "Proceed to script generation?",
            [
                [("✅ Approve Research", "viral_research_approve")],
                [("🔄 Regenerate", "viral_research_regen")],
                [("❌ Cancel", "viral_cancel")]
            ]
        )
    
    async def _generate_script(self):
        """Generate improved script and show for approval."""
        await self.send_message("✍️ Writing improved script (30% better)...")
        
        articles = []
        for news in self.state["research"].get("recent_news", []):
            articles.append({
                "title": news.get("title", ""),
                "content": news.get("content", news.get("snippet", "")),
                "source": news.get("source", "")
            })
        
        result = generate_script(
            topic=self.state["original"]["title"],
            articles=articles,
            transcript=self.state["transcript"],
            word_count=4500,
            channel_focus="Empire Finance",
            script_mode="improve"
        )
        
        if not result.get("success"):
            await self.send_message(f"❌ Script generation failed: {result.get('message')}")
            return
        
        self.state["script"] = result.get("script", {}).get("raw_text", "")
        word_count = len(self.state["script"].split())
        
        self.save_checkpoint("generate_script")
        
        # Send script as file for download
        if self.bot:
            try:
                script_path = Path(self.output_dir) / "script.txt"
                with open(script_path, 'w') as f:
                    f.write(self.state["script"])
                
                with open(script_path, 'rb') as f:
                    await self.bot.send_document(self.chat_id, f, filename="script.txt", caption="📄 Full script attached for easy copying")
            except Exception as e:
                await self.send_message(f"(Could not send file: {e})")
        
        await self.send_message(
            f"📝 *Script Generated*\n\n"
            f"Word Count: {word_count}\n"
            f"Title: {self.state['original']['title']}\n\n"
            f"📄 Full script sent as file above.\n\n"
            "Approve script?"
        )
        
        self.state["step"] = "approving_script"
        
        await self.send_keyboard(
            "Approve script?",
            [
                [("✅ Approve Script", "viral_script_approve")],
                [("🔄 Regenerate", "viral_script_regen")],
                [("❌ Cancel", "viral_cancel")]
            ]
        )
    
    async def _select_style(self):
        """Show style options for user to select."""
        style_text = "🎨 *Select Video Style:*\n\n"
        
        for style_id, style_info in STYLES.items():
            style_text += f"- *{style_info['name']}*\n{style_info['description']}\n\n"
        
        await self.send_message(style_text)
        
        self.state["step"] = "selecting_style"
        
        await self.send_keyboard(
            "Choose a style:",
            [
                [("🎨 Ghibli Cartoon (Primary)", "viral_style_ghibli_cartoon")],
                [("🎨 Impressionist Oil Painting", "viral_style_impressionist_oil")]
            ]
        )
    
    async def _apply_style(self, style_id: str):
        """Apply selected style and generate images."""
        if style_id in STYLES:
            self.state["style"] = style_id
            await self.send_message(f"🎨 Style selected: {style_id}")
        else:
            self.state["style"] = DEFAULT_STYLE
            await self.send_message(f"🎨 Using default style: {DEFAULT_STYLE}")
        
        self.save_checkpoint("select_style")
        
        # Generate images
        await self._generate_images()
    
    async def _generate_images(self):
        """Generate AI images and show samples for approval."""
        await self.send_message("🖼️ Generating images...")
        
        images_dir = Path(self.output_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        result = generate_images_for_script(
            self.state["script"],
            output_dir=str(images_dir),
            style=self.state["style"]
        )
        
        if not result.get("success"):
            await self.send_message(f"⚠️ Image generation had issues: {result.get('message', 'Unknown')}")
        
        # Get generated images
        image_files = sorted(images_dir.glob("*.png"))
        self.state["images"] = [str(f) for f in image_files]
        
        self.save_checkpoint("generate_images")
        
        # Send sample images (first 3)
        if self.bot and image_files:
            for i, img_path in enumerate(image_files[:3]):
                try:
                    with open(img_path, 'rb') as f:
                        await self.bot.send_photo(self.chat_id, f, caption=f"Image {i+1}/{len(image_files)}")
                except Exception as e:
                    await self.send_message(f"(Could not send image {i+1}: {e})")
        
        await self.send_message(
            f"🖼️ *Image Generation Complete*\n\n"
            f"✅ Generated: {len(image_files)} images\n"
            f"📷 Previewed: {min(3, len(image_files))} samples above\n\n"
            "Approve images?"
        )
        
        self.state["step"] = "approving_images"
        
        await self.send_keyboard(
            "Approve images?",
            [
                [("✅ Approve Images", "viral_images_approve")],
                [("🔄 Regenerate", "viral_images_regen")]
            ]
        )
    
    async def _generate_video(self):
        """Generate audio and video, show preview."""
        await self.send_message("🎬 Generating video...\n\n⏳ This involves generating audio for each chunk and assembling the video. This may take several minutes for longer scripts.")
        
        # Generate audio
        await self.send_message("🎙️ Generating voiceover...")
        audio_result = generate_all_audio(self.state["script"], self.output_dir)
        self.state["audio_result"] = audio_result
        
        # Build video
        await self.send_message("🎬 Stitching video...")
        
        audio_files = audio_result.get("audio_files", [])
        images_dir = Path(self.output_dir) / "images"
        image_files = sorted(images_dir.glob("*.png")) if images_dir.exists() else []
        
        chunks = []
        script_chunks = split_script_to_chunks(self.state["script"])
        
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
            self.state["video_path"] = result.get("output_path", "")
            duration = result.get("duration", 0)
            
            self.save_checkpoint("generate_video")
            
            await self.send_message(
                f"🎥 *Video Generated*\n\n"
                f"Duration: {duration/60:.1f} minutes\n"
                f"Chunks: {len(chunks)}\n\n"
                "Approve video?"
            )
            
            self.state["step"] = "approving_video"
            
            await self.send_keyboard(
                "Approve video?",
                [
                    [("✅ Approve Video", "viral_video_approve")],
                    [("🔄 Regenerate", "viral_video_regen")]
                ]
            )
        else:
            await self.send_message(f"❌ Video generation failed: {result.get('error')}")
    
    async def _generate_metadata(self):
        """Generate similar title, description, tags for approval."""
        await self.send_message("📋 Creating similar title/description/tags...")
        
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        original_title = self.state["original"]["title"]
        original_desc = self.state["original"]["description"]
        original_tags = self.state["original"]["tags"]
        
        # Generate similar title
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
        self.state["title"] = title_response.text.strip().strip('"')
        
        # Generate similar description
        desc_prompt = f"""Rewrite this YouTube description to be similar but unique.
Keep the first 2 sentences almost identical (change 1-2 words).
Add Empire Finance branding at the end.

Original first 500 chars:
{original_desc[:500]}

Return the new description (max 500 chars), nothing else."""

        desc_response = model.generate_content(desc_prompt)
        self.state["description"] = desc_response.text.strip()
        
        # Merge tags
        vague_tags = {"video", "youtube", "2024", "2025", "2026", "new", "latest", "trending"}
        good_original_tags = [t for t in original_tags if t.lower() not in vague_tags][:15]
        our_tags = ["empire finance", "economy explained", "financial news", "economic analysis"]
        self.state["tags"] = list(set(good_original_tags + our_tags))[:20]
        
        self.save_checkpoint("generate_metadata")
        
        # Show metadata for approval
        tags_preview = ", ".join(self.state["tags"][:10])
        await self.send_message(
            f"📊 *Metadata Generated*\n\n"
            f"*Title:*\n{self.state['title']}\n\n"
            f"*Tags ({len(self.state['tags'])}):* {tags_preview}...\n\n"
            f"*Description Preview:*\n`{self.state['description'][:200]}...`\n\n"
            "Approve metadata?"
        )
        
        self.state["step"] = "approving_metadata"
        
        await self.send_keyboard(
            "Approve metadata?",
            [
                [("✅ Approve Metadata", "viral_metadata_approve")],
                [("🔄 Regenerate", "viral_metadata_regen")]
            ]
        )
    
    async def _generate_thumbnail(self):
        """Generate thumbnail and show for approval."""
        await self.send_message("🖼️ Generating thumbnail...")
        
        # Analyze original thumbnail
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        prompt = f"""Create a thumbnail text overlay for this video.
Title: {self.state["title"]}
Original thumbnail style: worried face, dramatic text overlay

Return ONLY the main text (2-3 words, all caps) that should appear on the thumbnail.
Examples: "IT'S OVER", "THE TRUTH", "ECONOMY DESTROYED"."""

        try:
            response = model.generate_content(prompt)
            main_text = response.text.strip().replace('"', '')
        except:
            main_text = "IT'S HAPPENING"
        
        self.state["thumbnail_analysis"] = {"main_text": main_text}
        
        # Generate actual thumbnail
        try:
            from execution.generate_thumbnail import generate_thumbnail
            
            thumb_result = generate_thumbnail(
                title=self.state["title"],
                style=self.state["style"],
                text_overlay=main_text,
                output_dir=self.output_dir
            )
            
            if thumb_result.get("success"):
                self.state["thumbnail_path"] = thumb_result.get("path", "")
        except Exception as e:
            await self.send_message(f"⚠️ Thumbnail generation issue: {e}")
        
        self.save_checkpoint("generate_thumbnail")
        
        # Send thumbnail preview
        if self.bot and self.state.get("thumbnail_path") and os.path.exists(self.state["thumbnail_path"]):
            try:
                with open(self.state["thumbnail_path"], 'rb') as f:
                    await self.bot.send_photo(self.chat_id, f, caption="🖼️ Thumbnail Generated\n\nApprove thumbnail?")
            except:
                await self.send_message("🖼️ Thumbnail generated (could not preview)")
        else:
            await self.send_message("🖼️ Thumbnail generated\n\nApprove thumbnail?")
        
        self.state["step"] = "approving_thumbnail"
        
        await self.send_keyboard(
            "Approve thumbnail?",
            [
                [("✅ Approve Thumbnail", "viral_thumbnail_approve")],
                [("🔄 Regenerate", "viral_thumbnail_regen")]
            ]
        )
    
    async def _prepare_upload(self):
        """Show final confirmation before upload."""
        video_name = Path(self.state.get("video_path", "")).name or "video.mp4"
        thumb_name = Path(self.state.get("thumbnail_path", "")).name or "thumbnail.jpg"
        
        await self.send_message(
            f"🚀 *Ready to Upload*\n\n"
            f"Title: {self.state['title']}\n"
            f"Video: `{video_name}`\n"
            f"Thumbnail: `{thumb_name}`\n\n"
            "Upload to YouTube?"
        )
        
        self.state["step"] = "confirming_upload"
        
        await self.send_keyboard(
            "Upload to YouTube?",
            [
                [("🚀 Upload Now", "viral_upload_confirm")],
                [("💾 Save Locally", "viral_upload_cancel")]
            ]
        )
    
    async def _upload_to_youtube(self):
        """Upload video to YouTube."""
        await self.send_message("📤 Uploading to YouTube...")
        
        result = upload_video(
            video_path=self.state["video_path"],
            title=self.state["title"],
            description=self.state["description"],
            tags=self.state["tags"],
            thumbnail_path=self.state.get("thumbnail_path"),
            category_id="22"
        )
        
        if result.get("success"):
            video_url = result.get("url", f"https://youtube.com/watch?v={result.get('video_id', '')}")
            
            await self.send_message(
                f"✅ *Upload Complete!*\n\n"
                f"Video ID: `{result.get('video_id', 'N/A')}`\n"
                f"URL: {video_url}\n\n"
                "Your improved clone is live!"
            )
            
            self.clear_checkpoint()
        else:
            await self.send_message(f"❌ Upload failed: {result.get('error')}\n\nFiles saved locally.")
        
        self.state["step"] = "complete"


# Registry for active pipelines (by chat_id)
_active_pipelines: Dict[int, ViralVideoPipeline] = {}


def get_viral_pipeline(chat_id: int) -> Optional[ViralVideoPipeline]:
    """Get active pipeline for chat."""
    return _active_pipelines.get(chat_id)


def create_viral_pipeline(video_id: str, chat_id: int, send_message_func, send_keyboard_func, bot=None) -> ViralVideoPipeline:
    """Create and register a new pipeline."""
    pipeline = ViralVideoPipeline(video_id, chat_id, send_message_func, send_keyboard_func, bot)
    _active_pipelines[chat_id] = pipeline
    return pipeline


def remove_viral_pipeline(chat_id: int):
    """Remove pipeline from registry."""
    _active_pipelines.pop(chat_id, None)


# Legacy function for backwards compatibility
async def run_viral_pipeline(video_id: str, send_message: Callable = None) -> Dict:
    """
    Legacy convenience function - runs without approvals.
    For approval flow, use create_viral_pipeline() instead.
    """
    # Simple run-through for backwards compatibility
    print(f"⚠️ run_viral_pipeline() is deprecated. Use create_viral_pipeline() for approval flow.")
    
    # Create a minimal pipeline that auto-approves
    class AutoPipeline:
        def __init__(self):
            self.video_id = video_id
            self.send_message = send_message or print
            self.state = {}
        
        async def log(self, msg):
            if asyncio.iscoroutinefunction(self.send_message):
                await self.send_message(msg)
            else:
                self.send_message(msg)
    
    # This is a simplified version - real usage should use the full pipeline
    pipeline = AutoPipeline()
    await pipeline.log("⚠️ Running in legacy mode without approvals. Use /clone command for full experience.")
    
    return {"success": False, "error": "Legacy mode not fully supported. Use /clone command."}


if __name__ == "__main__":
    print("Usage: Import and use create_viral_pipeline() for approval flow")
    print("Or use legacy run_viral_pipeline() for auto mode (deprecated)")
