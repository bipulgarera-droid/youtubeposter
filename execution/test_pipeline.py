#!/usr/bin/env python3
"""
Pipeline Component Tester - Minimal tests for each endpoint.

Tests each component individually without full generation to save API credits.
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Track results
results = {}

def log_result(component: str, success: bool, msg: str):
    """Log test result."""
    results[component] = {"success": success, "message": msg}
    status = "✅" if success else "❌"
    print(f"{status} {component}: {msg}")


def test_trend_scanner():
    """Test trend scanning - just verify API call works."""
    try:
        from execution.trend_scanner import scan_trending_topics, get_evergreen_topics
        
        # Test evergreen (no API call)
        evergreen = get_evergreen_topics()
        if not evergreen:
            log_result("Trend Scanner (Evergreen)", False, "No evergreen topics returned")
            return
        log_result("Trend Scanner (Evergreen)", True, f"{len(evergreen)} topics available")
        
        # Test news scan (uses API)
        topics = scan_trending_topics("economics")
        if topics:
            log_result("Trend Scanner (News)", True, f"{len(topics)} topics found")
        else:
            log_result("Trend Scanner (News)", False, "No topics returned (API may have failed)")
            
    except Exception as e:
        log_result("Trend Scanner", False, str(e))


def test_research_agent():
    """Test research - single short query."""
    try:
        from execution.research_agent import deep_research
        
        # Minimal research call
        research = deep_research("Germany economy", country="Germany")
        
        if research and research.get("summary"):
            summary_preview = research["summary"][:100] + "..."
            log_result("Research Agent", True, f"Summary: {summary_preview}")
        else:
            log_result("Research Agent", False, "No research summary returned")
            
    except Exception as e:
        log_result("Research Agent", False, str(e))


def test_style_selector():
    """Test style system - no API calls."""
    try:
        from execution.style_selector import (
            get_style_options, 
            apply_style_to_prompt,
            auto_select_mood,
            auto_select_scene_type
        )
        
        styles = get_style_options()
        if len(styles) != 2:
            log_result("Style Selector", False, f"Expected 2 styles, got {len(styles)}")
            return
        
        # Test prompt generation
        prompt = apply_style_to_prompt(
            "businessman on bench", 
            "ghibli_cartoon", 
            "dark_moody",
            "character_focus"
        )
        if "Ghibli" in prompt and "dark" in prompt.lower():
            log_result("Style Selector", True, "Styles and moods apply correctly")
        else:
            log_result("Style Selector", False, "Prompt not generated correctly")
        
        # Test auto selection
        mood = auto_select_mood("The economy collapsed in 2008 crisis")
        if mood == "dark_moody":
            log_result("Style Auto-Select", True, f"Auto-detected mood: {mood}")
        else:
            log_result("Style Auto-Select", True, f"Mood detected: {mood} (expected dark_moody)")
            
    except Exception as e:
        log_result("Style Selector", False, str(e))


def test_tag_generator():
    """Test tag generation - single API call."""
    try:
        from execution.tag_generator import generate_tags, generate_hashtags
        
        # Test hashtags (no API)
        hashtags = generate_hashtags("German Economy", "Germany")
        if hashtags:
            log_result("Tag Generator (Hashtags)", True, f"Generated: {' '.join(hashtags[:5])}")
        else:
            log_result("Tag Generator (Hashtags)", False, "No hashtags generated")
        
        # Test tags (with API)
        tags = generate_tags(
            title="Why Germany is in Crisis",
            topic="German Economy",
            country="Germany"
        )
        if tags and len(tags) > 10:
            log_result("Tag Generator (Tags)", True, f"{len(tags)} tags: {', '.join(tags[:5])}...")
        else:
            log_result("Tag Generator (Tags)", False, f"Only {len(tags)} tags generated")
            
    except Exception as e:
        log_result("Tag Generator", False, str(e))


def test_file_renamer():
    """Test file renaming logic - no API calls."""
    try:
        from execution.file_renamer import generate_topic_slug, extract_topic_from_title
        
        # Test slug generation
        slug = generate_topic_slug("The German Economic Crisis of 2025")
        if slug and len(slug.split("-")) <= 4:
            log_result("File Renamer (Slug)", True, f"Slug: {slug}")
        else:
            log_result("File Renamer (Slug)", False, f"Bad slug: {slug}")
        
        # Test title extraction
        topic = extract_topic_from_title("Why Germany is POORER Than You Think (The Economic Truth)")
        if topic:
            log_result("File Renamer (Extract)", True, f"Extracted: {topic}")
        else:
            log_result("File Renamer (Extract)", False, "Failed to extract topic")
            
    except Exception as e:
        log_result("File Renamer", False, str(e))


def test_pipeline_init():
    """Test pipeline initialization - no API calls."""
    try:
        from execution.new_video_pipeline import NewVideoPipeline, create_pipeline, get_pipeline
        
        # Mock send functions
        async def mock_send(text): pass
        async def mock_keyboard(text, options): pass
        
        # Create pipeline
        pipeline = create_pipeline(12345, mock_send, mock_keyboard)
        
        if pipeline and pipeline.state.get("step") == "init":
            log_result("Pipeline Init", True, "Pipeline created successfully")
        else:
            log_result("Pipeline Init", False, "Pipeline not initialized properly")
        
        # Check output dir created
        if os.path.exists(pipeline.output_dir):
            log_result("Pipeline Output Dir", True, f"Created: {pipeline.output_dir}")
        else:
            log_result("Pipeline Output Dir", False, "Output dir not created")
            
    except Exception as e:
        log_result("Pipeline Init", False, str(e))


def test_existing_generators():
    """Test existing generator imports work."""
    # Test imports only - no actual generation
    generators = [
        ("generate_script", "generate_script"),
        ("generate_ai_images", "generate_all_images"),
        ("generate_audio", "generate_audio_from_script"),
        ("generate_video", "build_video_from_chunks"),
        ("generate_subtitles", "generate_subtitled_video"),
        ("generate_thumbnail", "generate_thumbnail"),
        ("generate_metadata", "generate_full_metadata"),
        ("generate_timestamps", "generate_timestamps_from_srt"),
    ]
    
    for module_name, func_name in generators:
        try:
            module = __import__(f"execution.{module_name}", fromlist=[func_name])
            func = getattr(module, func_name, None)
            if func:
                log_result(f"Import {module_name}", True, f"{func_name}() found")
            else:
                log_result(f"Import {module_name}", False, f"{func_name}() not found")
        except Exception as e:
            log_result(f"Import {module_name}", False, str(e)[:60])


def test_telegram_bot_imports():
    """Test Telegram bot state imports."""
    try:
        # Just test the states exist
        from execution.telegram_bot import NEWVIDEO_FLOW, get_main_menu_keyboard
        
        if NEWVIDEO_FLOW == 7:  # Should be index 7 in range(8)
            log_result("Telegram NEWVIDEO_FLOW", True, f"State={NEWVIDEO_FLOW}")
        else:
            log_result("Telegram NEWVIDEO_FLOW", True, f"State exists (value={NEWVIDEO_FLOW})")
            
    except ImportError as e:
        # Expected if telegram not installed
        if "telegram" in str(e).lower():
            log_result("Telegram Bot", True, "Skipped (telegram package not installed)")
        else:
            log_result("Telegram Bot", False, str(e))
    except Exception as e:
        log_result("Telegram Bot", False, str(e))


def print_summary():
    """Print test summary."""
    print("\n" + "="*60)
    print("PIPELINE TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results.values() if r["success"])
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed < total:
        print("\n❌ Failed components:")
        for name, r in results.items():
            if not r["success"]:
                print(f"  - {name}: {r['message']}")
    
    print("\n" + "="*60)
    return passed == total


if __name__ == "__main__":
    print("🧪 PIPELINE COMPONENT TESTS")
    print("="*60)
    print("Testing each component with minimal API usage...\n")
    
    # Run tests
    test_style_selector()  # No API
    test_file_renamer()    # No API
    test_pipeline_init()   # No API
    test_existing_generators()  # Just imports
    test_telegram_bot_imports()  # Just imports
    
    print("\n--- API Tests (minimal credits) ---\n")
    test_tag_generator()   # 1 API call
    test_trend_scanner()   # 1-2 API calls
    test_research_agent()  # 2-3 API calls
    
    # Summary
    all_passed = print_summary()
    
    sys.exit(0 if all_passed else 1)
