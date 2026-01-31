#!/usr/bin/env python3
"""
Viral Video Cloning Pipeline with Step-by-Step Approvals
Creates an improved version of a viral video to appear in suggested videos.

Uses the SAME generation modules as new_video_pipeline:
- generate_narrative_script() - no headers, TTS-ready
- generate_outline() - 7-chapter outline with stats
- storage_helper - Supabase upload for persistence

Flow (with approvals):
1. Fetch video info → Show original details
2. Transcribe → Show transcript preview → Approve
3. Research → Show research facts → Approve  
4. Outline → Show 7-chapter outline → Approve
5. Generate script → Show script + file → Approve
6. Select style (Ghibli/Oil Painting)
7. Generate images → Upload to Supabase → Show previews → Approve
8. Generate video → Show preview → Approve
9. Generate metadata → Show title/desc/tags → Approve
10. Generate thumbnail → Show preview → Approve
11. Upload → Confirm → Upload
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

# NEW: Use correct generation modules (same as new_video_pipeline)
from execution.generate_outline import generate_outline, format_outline_for_telegram, format_outline_for_script
from execution.generate_narrative_script import generate_narrative_script

from execution.generate_audio import generate_all_audio
from execution.generate_ai_images import generate_images_for_script, split_script_to_chunks
from execution.generate_video import build_video_from_chunks
from execution.youtube_upload import upload_video, upload_video_with_captions

# NEW: Import Locked Template Generator
from execution.generate_thumbnail import generate_thumbnail_with_gemini

# Subtitle generation
try:
    from execution.generate_subtitles import generate_subtitled_video
except ImportError:
    generate_subtitled_video = None

# Timestamp generation for description
try:
    from execution.generate_timestamps import generate_timestamps_from_srt
except ImportError:
    generate_timestamps_from_srt = None

# Supabase storage for persistence across restarts
try:
    from execution.storage_helper import (
        upload_file, upload_text, upload_state, download_file,
        get_latest_job_with_assets, download_state, get_job_assets
    )
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    upload_file = None
    upload_state = None
    download_file = None

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Available styles (same as new_video_pipeline)
STYLES = {
    "ghibli_cartoon": {
        "name": "Ghibli Cartoon (Primary)",
        "description": "Studio Ghibli-inspired animated style. Clean lines, expressive characters, detailed backgrounds."
    },
    "impressionist_oil": {
        "name": "Impressionist Oil Painting",
        "description": "Classic French impressionist style. Oil painting aesthetic with visible brushstrokes."
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
        
        # Supabase job ID for cloud storage
        self.supabase_job_id = f"viral_{video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
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
            "outline": "",
            "script": "",
            "style": DEFAULT_STYLE,
            "title": "",
            "description": "",
            "tags": [],
            "thumbnail_analysis": {},
            "images": {},
            "image_urls": [],  # Supabase URLs for resume
            "audio_result": {},
            "video_path": "",
            "subtitled_video_path": "",
            "thumbnail_path": "",
            "paraphrased_title": "",  # User-approved paraphrased title
            "title_keywords": [],     # 3 key words for file naming
            "output_dir": self.output_dir,
            "supabase_job_id": self.supabase_job_id,
            "chat_id": chat_id  # Persist chat_id for recovery
        }
    
    def checkpoint_path(self) -> str:
        """Get checkpoint file path for this video."""
        checkpoint_dir = Path(".tmp/viral_pipeline")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return str(checkpoint_dir / f"{self.video_id}_checkpoint.json")
    
    def save_checkpoint(self, step: str):
        """Save state to both local file and Supabase."""
        import json
        self.state["last_completed_step"] = step
        
        # Local checkpoint
        try:
            with open(self.checkpoint_path(), 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save local checkpoint: {e}")
        
        # Supabase checkpoint (for cross-restart persistence)
        if STORAGE_AVAILABLE and upload_state:
            try:
                upload_state(self.supabase_job_id, self.state)
                print(f"✅ State uploaded to Supabase: {self.supabase_job_id}")
            except Exception as e:
                print(f"Failed to upload state to Supabase: {e}")
    
    def load_checkpoint(self) -> bool:
        """Load state from checkpoint file if exists."""
        import json
        try:
            with open(self.checkpoint_path(), 'r') as f:
                self.state = json.load(f)
                self.supabase_job_id = self.state.get("supabase_job_id", self.supabase_job_id)
                return True
        except:
            return False
    
    def clear_checkpoint(self):
        """Remove checkpoint file after successful completion."""
        try:
            Path(self.checkpoint_path()).unlink(missing_ok=True)
        except:
            pass
    
    async def _generate_locked_thumbnail_early(self):
        """Generate a thumbnail using the Locked Master Template (V5) immediately."""
        if self.bot:
            await self.send_message("⚡ Generating Thumbnail... (Using 'Trump Center' Template)")
        
        try:
            # Use the title as the topic
            topic = self.state["title"]
            master_template_path = os.path.abspath("execution/assets/master_template.jpg")
            
            if not os.path.exists(master_template_path):
                 await self.send_message(f"❌ Master template not found at {master_template_path}")
                 return

            # Run in thread executor to avoid blocking asyncio loop
            loop = asyncio.get_event_loop()
            output_path = await loop.run_in_executor(
                None, 
                lambda: generate_thumbnail_with_gemini(
                    topic=topic,
                    style_reference=master_template_path
                )
            )
            
            if output_path and os.path.exists(output_path):
                # CRITICAL: Save thumbnail path to state for upload
                self.state["thumbnail_path"] = output_path
                self.save_checkpoint("thumbnail_v5")
                
                # Send the image
                if self.bot:
                    with open(output_path, 'rb') as img:
                        await self.bot.send_photo(
                            self.chat_id, 
                            img, 
                            caption=f"⚡ **Locked V5 Thumbnail**\nTopic: {topic}\n\n_Strict adherence to Master Template_"
                        )
                        # After thumbnail, proceed to title generation
                        await self._generate_paraphrased_title()
                else:
                     await self.send_message("✅ Thumbnail generated (check server logs for path).")
            else:
                 await self.send_message("❌ Generation failed (no output path returned).")
                 
        except Exception as e:
            await self.send_message(f"❌ Thumbnail generation error: {e}")
            import traceback
            traceback.print_exc()

    async def _generate_paraphrased_title(self):
        """Generate a paraphrased title (90% similar) and extract 3 key words for file naming."""
        import google.generativeai as genai
        
        original_title = self.state["original"]["title"]
        await self.send_message(f"✏️ Generating paraphrased title from:\n`{original_title}`")
        
        try:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            prompt = f"""You are a YouTube title expert. Generate 5 paraphrased versions of this title.

ORIGINAL TITLE: "{original_title}"

PARAPHRASING RULES:
1. Keep 90% of the meaning — change only 1-2 words or rearrange slightly
2. Use the format: Main Statement (Bracketed Detail) — where the bracket completes the thought organically
3. The bracketed part should be a RESTRUCTURED piece of the original, not something new
4. Keep all numbers, emotional hooks, and core topic intact
5. Each option should feel natural, not forced

EXAMPLES:
- Original: "China Just Dumped $688 Billion in U.S. Debt at a Record Loss"
  Paraphrased: "China Just Sold Off $688 Billion in U.S. Bonds (And Took a Massive Hit)"
  
- Original: "The Dollar Is Collapsing Faster Than Expected"
  Paraphrased: "The Dollar's Collapse Is Accelerating (Faster Than Anyone Predicted)"

- Original: "How Warren Buffett Made $150 Billion While Everyone Lost Money"
  Paraphrased: "Warren Buffett Just Made $150 Billion (While Everyone Else Lost)"

ALSO: Extract the 3 MOST IMPORTANT words from the first option for file naming (alphanumeric only).

Return ONLY valid JSON:
{{"options": ["Title 1", "Title 2", "Title 3", "Title 4", "Title 5"], "keywords": ["word1", "word2", "word3"]}}"""

            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean JSON markers if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            import json
            result = json.loads(response_text)
            
            options = result.get("options", [original_title])
            keywords = result.get("keywords", ["video", "upload", "new"])
            
            # Clean keywords for file naming
            clean_keywords = []
            for kw in keywords[:3]:
                clean_kw = ''.join(c for c in kw if c.isalnum())
                if clean_kw:
                    clean_keywords.append(clean_kw)
            
            # Store options and keywords
            self.state["title_options"] = options
            self.state["title_keywords"] = clean_keywords
            self.state["paraphrased_title"] = options[0] if options else original_title
            
            self.save_checkpoint("paraphrase_title")
            
            # Display all options
            options_text = "\n".join([f"**{i+1}.** {opt}" for i, opt in enumerate(options)])
            await self.send_message(
                f"📝 *Title Options (90% Similar):*\n\n{options_text}\n\n"
                f"🔑 *Keywords for file naming:* {', '.join(clean_keywords)}"
            )
            
            # Create selection buttons
            await self.send_keyboard(
                "Select a title:",
                [
                    [("1️⃣", "viral_title_select_0"), ("2️⃣", "viral_title_select_1"), ("3️⃣", "viral_title_select_2")],
                    [("4️⃣", "viral_title_select_3"), ("5️⃣", "viral_title_select_4")],
                    [("🔄 Regenerate Options", "viral_title_regen")],
                    [("❌ Cancel", "viral_cancel")]
                ]
            )
            
        except Exception as e:
            await self.send_message(f"⚠️ Title generation error: {e}. Using original title.")
            self.state["paraphrased_title"] = original_title
            self.state["title_keywords"] = original_title.split()[:3]
            await self.send_keyboard(
                "Use original title?",
                [
                    [("✅ Approve Title", "viral_title_approve")],
                    [("🔄 Regenerate", "viral_title_regen")]
                ]
            )

    async def start(self):
        """Start the viral cloning pipeline - fetch video info."""
        await self.send_message("🚀 *Starting Viral Video Clone Pipeline*\n\n_Uses same quality generation as main pipeline_")
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
        
        # Locked Thumbnail Generation (Early access) -> now triggers title generation after
        elif callback_data == "viral_create_thumbnail_locked":
            await self._generate_locked_thumbnail_early()
            return True
        
        # Title selection (after thumbnail) - select from 5 options
        elif callback_data.startswith("viral_title_select_"):
            try:
                idx = int(callback_data.replace("viral_title_select_", ""))
                options = self.state.get("title_options", [])
                if 0 <= idx < len(options):
                    self.state["paraphrased_title"] = options[idx]
                    self.state["title"] = options[idx]
                    await self.send_message(f"✅ Selected: `{options[idx]}`")
                    
                    # Show exact tags from viral video (no filtering)
                    original_tags = self.state.get("original", {}).get("tags", [])
                    self.state["tags"] = original_tags  # Use exact tags
                    tags_preview = ", ".join(original_tags[:15]) if original_tags else "None"
                    await self.send_message(
                        f"🏷️ *Tags from Viral Video ({len(original_tags)} total):*\n"
                        f"`{tags_preview}{'...' if len(original_tags) > 15 else ''}`\n\n"
                        "_These exact tags will be used for your video._"
                    )
                    
                    await self._start_research()
                else:
                    await self.send_message("⚠️ Invalid selection")
            except:
                await self.send_message("⚠️ Selection error")
            return True
        
        elif callback_data == "viral_title_approve":
            self.state["title"] = self.state.get("paraphrased_title", self.state["original"]["title"])
            await self._start_research()
            return True
        
        elif callback_data == "viral_title_regen":
            await self._generate_paraphrased_title()
            return True
        
        # Research approval
        elif callback_data == "viral_research_approve":
            await self._generate_outline()  # NEW: Go to outline first
            return True
        
        elif callback_data == "viral_research_regen":
            await self._start_research()
            return True
        
        # Outline approval (NEW)
        elif callback_data == "viral_outline_approve":
            await self._generate_script()
            return True
        
        elif callback_data == "viral_outline_regen":
            await self._generate_outline()
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
        
        # Video approval -> now goes to subtitles first
        elif callback_data == "viral_video_approve":
            await self._add_subtitles()
            return True
        
        elif callback_data == "viral_video_regen":
            await self._generate_video()
            return True
        
        # Subtitles approval (NEW)
        elif callback_data == "viral_subtitles_approve":
            await self._generate_metadata()
            return True
        
        elif callback_data == "viral_subtitles_regen":
            await self._add_subtitles()
            return True
        
        # Metadata approval - skip to upload prep (V5 thumbnail already generated early)
        elif callback_data == "viral_metadata_approve":
            # Check if V5 thumbnail already exists (generated after transcript)
            if self.state.get("thumbnail_path") and os.path.exists(self.state["thumbnail_path"]):
                await self.send_message("✅ Using V5 Thumbnail (Trump Center) generated earlier")
                await self._prepare_upload()
            else:
                # Fallback: generate if somehow missing (shouldn't happen)
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
        
        # Use original title as our base title
        self.state["title"] = self.state["original"]["title"]
        
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
            error_msg = result.get('message', 'Unknown error')
            print(f"⚠️ Transcription failed: {error_msg}. Falling back to Description.")
            
            # FALLBACK: Use Description/Title as "Transcript"
            fallback_text = self.state['original'].get('description', '')
            if not fallback_text or len(fallback_text) < 50:
                 fallback_text = f"Title: {self.state['original']['title']}. " + fallback_text
            
            self.state["transcript"] = fallback_text
            
            await self.send_message(
                f"⚠️ *Transcription Failed but we can proceed!*\n"
                f"Error: {error_msg}\n\n"
                f"✅ *Falling back to Video Description* for research context."
            )
        else:
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
                [("⚡ Create V5 Thumbnail", "viral_create_thumbnail_locked")],
                [("✅ Approve Research", "viral_transcript_approve")],
                [("🔄 Regenerate", "viral_transcript_regen")],
                [("❌ Cancel", "viral_cancel")]
            ]
        )
    
    async def _start_research(self):
        """Research deeper using transcript and show results."""
        await self.send_message("🔍 Researching topic in depth...")
        
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
        
        # Show research facts (same format as new_video_pipeline)
        raw_facts = research.get("raw_facts", "")
        display_facts = raw_facts[:1500] if len(raw_facts) > 1500 else raw_facts
        
        if not display_facts:
            display_facts = "Research complete. Key findings compiled."
        
        await self.send_message(
            f"📚 *Research Facts:*\n\n{display_facts}...\n\n"
            f"📰 Found {len(research.get('recent_news', []))} related articles"
        )
        
        self.state["step"] = "approving_research"
        
        await self.send_keyboard(
            "Proceed to outline generation?",
            [
                [("✅ Approve Research", "viral_research_approve")],
                [("🔄 Regenerate", "viral_research_regen")],
                [("❌ Cancel", "viral_cancel")]
            ]
        )
    
    async def _generate_outline(self):
        """Generate 7-chapter outline from research (NEW - same as new_video_pipeline)."""
        await self.send_message("📋 Generating 7-chapter outline...")
        
        result = generate_outline(
            title=self.state["title"],
            research=self.state["research"],
            country=None
        )
        
        if not result.get("success"):
            await self.send_message(f"❌ Outline generation failed: {result.get('error')}")
            return
        
        self.state["outline"] = result.get("outline", "")
        
        self.save_checkpoint("outline")
        
        # Show outline for approval (using same formatter as new_video_pipeline)
        outline_text = format_outline_for_telegram(result)
        
        await self.send_keyboard(
            outline_text,
            [
                [("✅ Approve Outline", "viral_outline_approve")],
                [("🔄 Regenerate", "viral_outline_regen")],
                [("❌ Cancel", "viral_cancel")]
            ]
        )
        
        self.state["step"] = "approving_outline"
    
    async def _generate_script(self):
        """Generate script using generate_narrative_script (NEW - no headers, TTS-ready)."""
        await self.send_message("✍️ Generating 4,500-word script (~30 min video)...\n\n_Using narrative engine (no headers, TTS-optimized)_")
        
        # Combine research + outline for context
        research_text = format_research_for_script(self.state["research"])
        outline_context = format_outline_for_script({"success": True, "outline": self.state["outline"]})
        full_context = research_text + "\n\n" + outline_context
        
        try:
            # Use generate_narrative_script (same as new_video_pipeline)
            result = generate_narrative_script(
                research_data=full_context,
                topic=self.state["title"],
                target_minutes=30  # 4500 words
            )
            
            if not result or not result.get("full_script"):
                await self.send_message("❌ Script generation failed. Try regenerating.")
                return
            
            script = result.get("full_script", "")
            word_count = result.get("total_words", len(script.split()))
            
            self.state["script"] = script
            
            # Save to file
            script_path = Path(self.output_dir) / "script.txt"
            with open(script_path, "w") as f:
                f.write(script)
            
            self.save_checkpoint("generate_script")
            
            # Send script as file for download
            if self.bot:
                try:
                    with open(script_path, 'rb') as f:
                        await self.bot.send_document(
                            self.chat_id, f, 
                            filename="script.txt", 
                            caption="📄 Full script attached (no headers, TTS-ready)"
                        )
                except Exception as e:
                    await self.send_message(f"(Could not send file: {e})")
            
            # Upload script to Supabase
            if STORAGE_AVAILABLE and upload_file:
                try:
                    upload_file(str(script_path), self.supabase_job_id, 'scripts', 'script.txt')
                except Exception as e:
                    print(f"Failed to upload script to Supabase: {e}")
            
            await self.send_message(
                f"📝 *Script Generated*\n\n"
                f"Word Count: {word_count}\n"
                f"Estimated Duration: {word_count // 150} minutes\n\n"
                f"📄 Full script sent as file above.\n\n"
                "_No section headers - ready for TTS_"
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
        except Exception as e:
            await self.send_message(f"❌ Script generation error: {str(e)}")
    
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
            await self.send_message(f"🎨 Style selected: {STYLES[style_id]['name']}")
        else:
            self.state["style"] = DEFAULT_STYLE
            await self.send_message(f"🎨 Using default style: Ghibli Cartoon")
        
        self.save_checkpoint("select_style")
        
        # Generate images
        await self._generate_images()
    
    async def _generate_images(self):
        """Generate AI images and upload to Supabase for persistence."""
        await self.send_message("🖼️ Generating images...\n\n_Images will be uploaded to cloud for resume capability_")
        
        images_dir = Path(self.output_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        result = generate_images_for_script(
            script=self.state["script"],
            output_dir=str(images_dir),
            style=self.state["style"]
        )
        
        self.state["images"] = result
        
        # Get counts
        total_chunks = result.get('total_chunks', 0)
        successful = result.get('successful', 0)
        failed = result.get('failed', 0)
        chunks_data = result.get('chunks', [])
        
        # Upload images to Supabase for persistence (KEY FEATURE)
        uploaded_urls = []
        if STORAGE_AVAILABLE and upload_file:
            await self.send_message("☁️ Uploading images to cloud storage...")
            for chunk_result in chunks_data:
                if chunk_result.get('success') and chunk_result.get('path'):
                    try:
                        url = upload_file(
                            local_path=chunk_result['path'],
                            job_id=self.supabase_job_id,
                            step_name='images',
                            filename=f"chunk_{chunk_result.get('index', 0):03d}.png"
                        )
                        if url:
                            uploaded_urls.append(url)
                            chunk_result['supabase_url'] = url
                    except Exception as e:
                        print(f"Failed to upload image to Supabase: {e}")
            
            self.state["image_urls"] = uploaded_urls
            print(f"✅ Uploaded {len(uploaded_urls)} images to Supabase")
        
        self.save_checkpoint("generate_images")
        
        # Send sample images to Telegram (first 3)
        sent_previews = 0
        if self.bot:
            for chunk_result in chunks_data[:3]:
                if chunk_result.get('success') and chunk_result.get('path'):
                    try:
                        with open(chunk_result['path'], 'rb') as img_file:
                            await self.bot.send_photo(
                                self.chat_id,
                                img_file,
                                caption=f"Image {chunk_result.get('index', 0)+1}/{total_chunks}"
                            )
                            sent_previews += 1
                    except Exception as e:
                        print(f"Failed to send preview: {e}")
        
        status_msg = f"🖼️ *Image Generation Complete*\n\n"
        status_msg += f"✅ Generated: {successful}/{total_chunks} images\n"
        if failed > 0:
            status_msg += f"❌ Failed: {failed}\n"
        if sent_previews > 0:
            status_msg += f"📸 Previewed: {sent_previews} samples above\n"
        if uploaded_urls:
            status_msg += f"☁️ Uploaded to cloud: {len(uploaded_urls)} images\n"
        status_msg += "\nApprove images?"
        
        await self.send_message(status_msg)
        
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
        await self.send_message("🎬 Generating video...\n\n⏳ Generating audio and stitching video. This may take several minutes.")
        
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
    
    async def _add_subtitles(self):
        """Add subtitles to video - show SRT preview and downloadable file."""
        await self.send_message("📝 Adding subtitles to video...")
        
        video_path = self.state.get("video_path")
        if not video_path:
            await self.send_message("❌ Video path not found. Cannot add subtitles.")
            return
        
        if not generate_subtitled_video:
            await self.send_message("❌ Subtitle generation module not available.")
            await self._generate_metadata()  # Skip to metadata
            return
        
        try:
            result = generate_subtitled_video(
                video_path=video_path,
                audio_path=None  # Let it extract audio from video
            )
            
            if not result.get("success"):
                await self.send_message(f"❌ Subtitle generation failed: {result.get('error')}")
                return
            
            subtitled_path = result.get("subtitled_video")
            srt_path = result.get("srt_path")
            
            if not subtitled_path or not os.path.exists(subtitled_path):
                await self.send_message("❌ Subtitled video file not created.")
                return
            
            self.state["subtitled_video_path"] = subtitled_path
            self.state["srt_path"] = srt_path
            
            # Upload SRT to Supabase for persistence
            if STORAGE_AVAILABLE and srt_path and os.path.exists(srt_path):
                try:
                    srt_url = upload_file(
                        local_path=srt_path,
                        job_id=self.supabase_job_id,
                        step_name="video",
                        filename="video.srt"
                    )
                    if srt_url:
                        self.state["srt_url"] = srt_url
                except Exception as e:
                    print(f"Failed to upload SRT: {e}")
            
            # Send SRT file as downloadable (KEY FIX)
            if self.bot and srt_path and os.path.exists(srt_path):
                try:
                    with open(srt_path, 'rb') as srt_file:
                        await self.bot.send_document(
                            self.chat_id,
                            srt_file,
                            filename="subtitles.srt",
                            caption="📄 Subtitles file - download and review"
                        )
                except Exception as e:
                    await self.send_message(f"(Could not send SRT file: {e})")
            
            # Show subtitle preview (first few lines)
            srt_preview = ""
            if srt_path and os.path.exists(srt_path):
                try:
                    with open(srt_path, 'r') as f:
                        lines = f.readlines()[:20]  # First 20 lines
                        srt_preview = "".join(lines)
                except:
                    pass
            
            if srt_preview:
                await self.send_message(f"📝 *Subtitle Preview:*\n\n```\n{srt_preview}...\n```")
            
            # Try to send video preview if small enough
            if os.path.exists(subtitled_path):
                video_size_mb = os.path.getsize(subtitled_path) / (1024 * 1024)
                if video_size_mb > 45:
                    await self.send_message(f"⚠️ Subtitled video is {video_size_mb:.1f}MB - too large for Telegram preview.")
                else:
                    try:
                        with open(subtitled_path, 'rb') as vf:
                            await self.bot.send_video(
                                self.chat_id,
                                vf,
                                caption="📝 Subtitled video preview"
                            )
                    except Exception as e:
                        await self.send_message(f"⚠️ Video preview failed: {str(e)[:50]}")
            
            self.save_checkpoint("add_subtitles")
            
            await self.send_keyboard(
                f"✅ *Subtitles Added*\n\n"
                f"📄 SRT file sent above for download\n"
                f"Video: `{Path(subtitled_path).name}`\n\n"
                f"Approve subtitles?",
                [
                    [("✅ Approve Subtitles", "viral_subtitles_approve")],
                    [("🔄 Regenerate", "viral_subtitles_regen")]
                ]
            )
            self.state["step"] = "approving_subtitles"
            
        except Exception as e:
            await self.send_message(f"❌ Subtitle error: {str(e)}")
    
    async def _generate_metadata(self):
        """Generate description for approval. Title and tags are already set."""
        await self.send_message("📋 Creating description with timestamps...")
        
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        original_desc = self.state["original"]["description"]
        
        # Title is already set from title selection step
        # Tags are already set from title selection step (exact viral tags)
        
        # Generate paraphrased description (90% similar)
        desc_prompt = f"""Paraphrase this YouTube video description while keeping 90% of its meaning.
Keep the same structure, main points, and call to action.
Change 1-2 words per sentence for uniqueness.

Original:
{original_desc[:800]}

Rules:
- Keep the same length and structure
- Keep any important keywords, numbers, and topics
- Make it engaging and hook the viewer
- Do NOT include timestamps (they will be added separately)
- Max 400 characters

Return ONLY the paraphrased description, nothing else."""

        desc_response = model.generate_content(desc_prompt)
        paraphrased_desc = desc_response.text.strip()
        
        # Generate timestamps from SRT
        timestamps_text = ""
        if generate_timestamps_from_srt and self.state.get("srt_path"):
            try:
                timestamps_result = generate_timestamps_from_srt(self.state["srt_path"])
                if timestamps_result.get("success"):
                    timestamps_text = timestamps_result.get("formatted", "")
                    self.state["timestamps"] = timestamps_text
            except Exception as e:
                print(f"Timestamp generation failed: {e}")
        
        # Combine in user's format: Title + blank line + paraphrased desc + TIMESTAMPS:
        final_description = self.state["title"]
        final_description += "\n\n"
        final_description += paraphrased_desc
        
        if timestamps_text:
            final_description += "\n\n"
            final_description += "TIMESTAMPS:\n"
            final_description += timestamps_text
        
        self.state["description"] = final_description
        
        self.save_checkpoint("generate_metadata")
        
        # Show full description for approval (it's the main thing to review now)
        await self.send_message(
            f"📊 *Description Preview:*\n\n```\n{final_description[:800]}{'...' if len(final_description) > 800 else ''}\n```"
        )
        
        self.state["step"] = "approving_metadata"
        
        await self.send_keyboard(
            "Approve description?",
            [
                [("✅ Approve Description", "viral_metadata_approve")],
                [("🔄 Regenerate", "viral_metadata_regen")]
            ]
        )
    
    async def _generate_thumbnail(self):
        """Generate thumbnail and show for approval."""
        await self.send_message("🖼️ Generating thumbnail...")
        
        # No need to manually analyze text - generate_thumbnail does it internally
        # matching the exact logic of new_video_pipeline
        
        # Download original thumbnail for style cloning (80-90% match)
        style_reference_path = None
        original_thumb_url = self.state.get("original", {}).get("thumbnail_url")
        
        if original_thumb_url:
            try:
                import requests
                response = requests.get(original_thumb_url, timeout=10)
                if response.status_code == 200:
                    style_reference_path = os.path.join(self.output_dir, "original_thumb_reference.jpg")
                    with open(style_reference_path, "wb") as f:
                        f.write(response.content)
                    await self.send_message("🖼️ Using original thumbnail as reference for cloning...")
            except Exception as e:
                print(f"Failed to download original thumbnail: {e}")

        # Generate actual thumbnail with correct parameters
        try:
            from execution.generate_thumbnail import generate_thumbnail
            
            # Create output path
            thumb_output = os.path.join(self.output_dir, "thumbnail.jpg")
            
            result_path = generate_thumbnail(
                topic=self.state["title"],  # Use title as topic
                title=self.state["title"],
                output_path=thumb_output,
                style_reference=style_reference_path, # Pass original thumb as reference
                auto_compress=True
            )
            
            if result_path and os.path.exists(result_path):
                self.state["thumbnail_path"] = result_path
                await self.send_message(f"✅ Thumbnail created: `{Path(result_path).name}`")
            else:
                await self.send_message("⚠️ Thumbnail generation returned no path")
        except Exception as e:
            await self.send_message(f"⚠️ Thumbnail generation issue: {e}")
            import traceback
            traceback.print_exc()
        
        self.save_checkpoint("generate_thumbnail")
        
        # Send thumbnail preview (KEY FIX - show actual image)
        if self.bot and self.state.get("thumbnail_path") and os.path.exists(self.state["thumbnail_path"]):
            try:
                with open(self.state["thumbnail_path"], 'rb') as f:
                    await self.bot.send_photo(self.chat_id, f, caption="🖼️ Thumbnail Generated")
            except Exception as e:
                await self.send_message(f"⚠️ Could not send thumbnail preview: {e}")
        else:
            await self.send_message("⚠️ No thumbnail file to preview")
        
        await self.send_message("🖼️ Thumbnail generated\n\nApprove thumbnail?")
        
        self.state["step"] = "approving_thumbnail"
        
        await self.send_keyboard(
            "Approve thumbnail?",
            [
                [("✅ Approve Thumbnail", "viral_thumbnail_approve")],
                [("🔄 Regenerate", "viral_thumbnail_regen")]
            ]
        )
    
    def _extract_seo_keywords(self, title: str) -> str:
        """Extract 2-4 key words from title for SEO filename."""
        import re
        # Remove emojis, special chars, keep alphanumeric and spaces
        clean = re.sub(r'[^\w\s-]', '', title)
        # Split into words, filter short/common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'will', 'be', 'to', 'for', 'of', 'in', 'on', 'with', 'and', 'or', 'how', 'why', 'what'}
        words = [w for w in clean.split() if w.lower() not in stop_words and len(w) > 2]
        # Take first 2-4 important words
        key_words = words[:4] if len(words) >= 4 else words[:max(2, len(words))]
        # Join with hyphens for filename
        return '-'.join(key_words) if key_words else 'video'
    
    async def _prepare_upload(self):
        """Show final confirmation before upload. Renames files for SEO using 3 keywords."""
        # Use title_keywords from paraphrase step (3 key words)
        keywords = self.state.get("title_keywords", [])
        if keywords and len(keywords) >= 2:
            seo_filename = '-'.join(keywords[:3])
        else:
            # Fallback to extracting from title
            seo_filename = self._extract_seo_keywords(self.state["title"])
        
        # Rename subtitled video for SEO
        video_path = self.state.get("subtitled_video_path") or self.state.get("video_path")
        if video_path and os.path.exists(video_path):
            video_dir = os.path.dirname(video_path)
            seo_video_path = os.path.join(video_dir, f"{seo_filename}.mp4")
            if video_path != seo_video_path:
                try:
                    import shutil
                    shutil.copy2(video_path, seo_video_path)
                    if self.state.get("subtitled_video_path"):
                        self.state["subtitled_video_path"] = seo_video_path
                    else:
                        self.state["video_path"] = seo_video_path
                except Exception as e:
                    print(f"Failed to rename video: {e}")
        
        # Rename thumbnail for SEO (same name as video, just different extension)
        thumb_path = self.state.get("thumbnail_path")
        if thumb_path and os.path.exists(thumb_path):
            thumb_dir = os.path.dirname(thumb_path)
            ext = os.path.splitext(thumb_path)[1] or '.jpg'
            seo_thumb_path = os.path.join(thumb_dir, f"{seo_filename}{ext}")
            if thumb_path != seo_thumb_path:
                try:
                    import shutil
                    shutil.copy2(thumb_path, seo_thumb_path)
                    self.state["thumbnail_path"] = seo_thumb_path
                except Exception as e:
                    print(f"Failed to rename thumbnail: {e}")
        
        # Get renamed video name
        final_video_path = self.state.get("subtitled_video_path") or self.state.get("video_path", "")
        video_name = Path(final_video_path).name or "video.mp4"
        
        await self.send_message(
            f"🚀 *Ready to Upload*\\n\\n"
            f"Title: {self.state['title']}\\n"
            f"Video: `{video_name}` (SEO optimized)\\n\\n"
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
        """Upload video to YouTube with SRT captions."""
        await self.send_message("📤 Uploading to YouTube...")
        
        # Use subtitled video if available, otherwise raw video
        video_to_upload = self.state.get("subtitled_video_path") or self.state.get("video_path")
        srt_path = self.state.get("srt_path")
        
        if not video_to_upload:
            await self.send_message("❌ No video found to upload.")
            return
        
        try:
            # Use upload_video_with_captions if SRT available
            # Note: Removed category_id arg as it caused issues on some deployments (defaults to 22 anyway)
            if srt_path and os.path.exists(srt_path):
                await self.send_message("📝 Uploading with SRT captions...")
                result = upload_video_with_captions(
                    video_path=video_to_upload,
                    title=self.state["title"],
                    description=self.state["description"],
                    tags=self.state["tags"],
                    thumbnail_path=self.state.get("thumbnail_path"),
                    srt_path=srt_path
                )
            else:
                result = upload_video(
                    video_path=video_to_upload,
                    title=self.state["title"],
                    description=self.state["description"],
                    tags=self.state["tags"],
                    thumbnail_path=self.state.get("thumbnail_path")
                )
        except TypeError as e:
            # Fallback if arguments mismatch persists
            await self.send_message(f"⚠️ Upload argument error: {e}. Trying simple upload...")
            result = upload_video(
                 video_path=video_to_upload,
                 title=self.state["title"],
                 description=self.state["description"],
                 tags=self.state["tags"]
            )
        except Exception as e:
            await self.send_message(f"❌ Upload failed with exception: {e}")
            return
        
        if result.get("success"):
            video_url = result.get("url", f"https://youtube.com/watch?v={result.get('video_id', '')}")
            
            caption_status = "✅ Captions uploaded" if result.get("captions_uploaded") else "⚠️ Captions not uploaded"
            
            await self.send_message(
                f"✅ *Upload Complete!*\n\n"
                f"Video ID: `{result.get('video_id', 'N/A')}`\n"
                f"URL: {video_url}\n"
                f"{caption_status}\n\n"
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


async def resume_viral_from_cloud(chat_id: int, send_message_func, send_keyboard_func, bot=None) -> Optional[ViralVideoPipeline]:
    """
    Resume a viral pipeline from Supabase storage.
    Downloads images from cloud and resumes from image step.
    """
    if not STORAGE_AVAILABLE:
        return None
    
    try:
        # Find latest job with images
        job_id, assets = get_latest_job_with_assets()
        
        if not job_id or not assets.get('images'):
            return None
        
        # Extract video_id from job_id (format: viral_{video_id}_{timestamp})
        parts = job_id.split('_')
        if len(parts) >= 2:
            video_id = parts[1]
        else:
            video_id = "unknown"
        
        # Create pipeline
        pipeline = ViralVideoPipeline(video_id, chat_id, send_message_func, send_keyboard_func, bot)
        pipeline.supabase_job_id = job_id
        
        # Download state
        state = download_state(job_id)
        if state:
            pipeline.state = state
        
        # Download images from Supabase
        images_dir = Path(pipeline.output_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        for i, img_path in enumerate(assets.get('images', [])):
            local_path = images_dir / f"chunk_{i:03d}.png"
            download_file(img_path, str(local_path))
        
        _active_pipelines[chat_id] = pipeline
        
        await send_message_func(
            f"☁️ *Resumed from Cloud*\n\n"
            f"Job: `{job_id}`\n"
            f"Downloaded: {len(assets.get('images', []))} images\n\n"
            "Continuing from image approval step..."
        )
        
        # Go directly to image approval
        pipeline.state["step"] = "approving_images"
        await send_keyboard_func(
            "Resume - Approve images?",
            [
                [("✅ Approve Images", "viral_images_approve")],
                [("🔄 Regenerate", "viral_images_regen")]
            ]
        )
        
        return pipeline
        
    except Exception as e:
        print(f"Failed to resume from cloud: {e}")
        return None


    print("Or use resume_viral_from_cloud() to resume from Supabase images")


def recover_viral_pipeline(chat_id: int, send_message_func, send_keyboard_func, bot=None) -> Optional[ViralVideoPipeline]:
    """
    Attempt to recover an active pipeline from local checkpoints for this chat_id.
    Useful if bot restarted and memory state was lost.
    """
    import json
    from pathlib import Path
    
    checkpoint_dir = Path(".tmp/viral_pipeline")
    if not checkpoint_dir.exists():
        return None
    
    # Scan all checkpoints
    for cp_file in checkpoint_dir.glob("*_checkpoint.json"):
        try:
            with open(cp_file, 'r') as f:
                state = json.load(f)
            
            # Check if this checkpoint belongs to the chat
            if state.get("chat_id") == chat_id:
                video_id = state.get("video_id")
                if not video_id:
                    continue
                    
                print(f"🔄 Recovering pipeline for chat {chat_id} from {cp_file}")
                
                # Reconstruct pipeline
                pipeline = ViralVideoPipeline(video_id, chat_id, send_message_func, send_keyboard_func, bot)
                pipeline.state = state
                
                # Re-register
                _active_pipelines[chat_id] = pipeline
                return pipeline
                
        except Exception as e:
            print(f"Error checking checkpoint {cp_file}: {e}")
            continue
            
    return None


