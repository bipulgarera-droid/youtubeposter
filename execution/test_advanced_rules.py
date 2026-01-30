#!/usr/bin/env python3
"""
Test script for advanced thumbnail rules (Dual Leaders vs Single Leader).
"""
import os
import requests
import time
from pathlib import Path
from execution.generate_thumbnail import generate_thumbnail
from execution.youtube_video_info import get_video_details

VIDEO_IDS = ["xi8BV6bWsWg", "PpSgNwNHno8"]

def test_video(video_id):
    print(f"\n🎬 Testing rules for video: {video_id}")
    
    # 1. Get video details
    try:
        info = get_video_details(video_id)
        if not info.get("success"):
            print(f"❌ Failed info: {info.get('error')}")
            return
            
        title = info.get("title")
        thumb_url = info.get("thumbnails", {}).get("high", {}).get("url")
        print(f"   Title: {title}")
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return

    # 2. Download thumbnail
    thumb_path = f".tmp/test_orig_{video_id}.jpg"
    Path(".tmp").mkdir(exist_ok=True)
    
    if thumb_url:
        with open(thumb_path, "wb") as f:
            f.write(requests.get(thumb_url).content)
        print(f"   Ref saved: {thumb_path}")
    
    # 3. Generate clone
    output_path = f".tmp/test_clone_{video_id}.jpg"
    print(f"🎨 Generating...")
    
    start = time.time()
    res = generate_thumbnail(
        topic=title,
        title=title,
        output_path=output_path,
        style_reference=thumb_path,
        auto_compress=True
    )
    
    if res and os.path.exists(res):
        print(f"✅ Generated in {time.time()-start:.1f}s: {res}")
    else:
        print("❌ Generation failed")

if __name__ == "__main__":
    for vid in VIDEO_IDS:
        test_video(vid)
