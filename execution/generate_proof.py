#!/usr/bin/env python3
"""
Generate proof for user: "IT'S OVER: China Just Sold All US Debt"
Using the new Recipe Extraction method.
"""
import os
import requests
import time
from pathlib import Path
from execution.generate_thumbnail import generate_thumbnail

VIDEO_ID = "xi8BV6bWsWg"
TARGET_TITLE = "IT'S OVER: China Just Sold All US Debt What They Aren't Telling You"

def generate_proof():
    print(f"🎬 Generating Proof for title: '{TARGET_TITLE}'")
    
    # 1. Ensure Reference Exists
    thumb_path = f".tmp/test_orig_{VIDEO_ID}.jpg"
    if not os.path.exists(thumb_path):
        print(f"❌ Reference file {thumb_path} missing. Downloading...")
        # Fallback download
        info_url = f"https://www.youtube.com/watch?v={VIDEO_ID}"
        # Simplified: just use maxres default URL if possible
        dl_url = f"https://i.ytimg.com/vi/{VIDEO_ID}/maxresdefault.jpg"
        r = requests.get(dl_url)
        if r.status_code != 200:
             dl_url = f"https://i.ytimg.com/vi/{VIDEO_ID}/hqdefault.jpg"
             r = requests.get(dl_url)
        with open(thumb_path, "wb") as f:
            f.write(r.content)
            
    print(f"   Using Reference: {thumb_path}")
    
    # 2. Generate Clone
    output_path = ".tmp/proof_thumb.jpg"
    print("🎨 Generating with Recipe Engine...")
    
    start = time.time()
    res = generate_thumbnail(
        topic=TARGET_TITLE,
        title=TARGET_TITLE,
        output_path=output_path,
        style_reference=thumb_path, # Passed as source for Recipe
        auto_compress=True
    )
    
    if res and os.path.exists(res):
        print(f"✅ Proof Generated in {time.time()-start:.1f}s")
        print(f"   Start: {thumb_path}")
        print(f"   End: {res}")
    else:
        print("❌ Generation failed")

if __name__ == "__main__":
    generate_proof()
