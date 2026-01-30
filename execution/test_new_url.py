#!/usr/bin/env python3
"""
Test script for viral thumbnail cloning with new URL.
"""
import os
import requests
import time
from pathlib import Path
from execution.generate_thumbnail import generate_thumbnail
from execution.youtube_video_info import get_video_details

VIDEO_ID = "kpCNB4hwAC0"

def test_cloning():
    print(f"🎬 Testing thumbnail cloning for video: {VIDEO_ID}")
    
    # 1. Get video details
    print("   Fetching video info...")
    try:
        info = get_video_details(VIDEO_ID)
    except Exception as e:
        print(f"❌ Failed format: {e}, using fallback info extraction if possible")
        return

    if not info.get("success"):
        print(f"❌ Failed to get video info: {info.get('error')}")
        return
    
    title = info.get("title")
    thumb_url = info.get("thumbnails", {}).get("high", {}).get("url")
    print(f"   Title: {title}")
    print(f"   Thumb URL: {thumb_url}")
    
    if not thumb_url:
        print("❌ No thumbnail URL found")
        return

    # 2. Download thumbnail
    print("⬇️ Downloading original thumbnail...")
    thumb_path = ".tmp/test_original_thumb_new.jpg"
    Path(".tmp").mkdir(exist_ok=True)
    
    response = requests.get(thumb_url)
    with open(thumb_path, "wb") as f:
        f.write(response.content)
    print(f"   Saved to {thumb_path}")
    
    # 3. Generate clone
    print("🎨 Generating clone thumbnail (this may take 10-20s)...")
    output_path = ".tmp/test_clone_thumb_new.jpg"
    
    start_time = time.time()
    result = generate_thumbnail(
        topic=title,
        title=title,
        output_path=output_path,
        style_reference=thumb_path,
        auto_compress=True
    )
    duration = time.time() - start_time
    
    if result and os.path.exists(result):
        print(f"✅ SUCCESS! Clone generated in {duration:.1f}s")
        print(f"   Output: {result}")
        print(f"   Size: {os.path.getsize(result) / 1024:.1f} KB")
    else:
        print("❌ Generation failed")

if __name__ == "__main__":
    test_cloning()
