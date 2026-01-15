#!/usr/bin/env python3
"""
Thumbnail Generator Module
Extracts, downloads, and analyzes YouTube thumbnails for recreation.
"""

import os
import requests
import json
from pathlib import Path
from typing import Optional, Dict, List

# Paths
TMP_DIR = Path(__file__).parent.parent / '.tmp'
THUMBNAILS_DIR = TMP_DIR / 'thumbnails'


def ensure_directories():
    """Ensure thumbnail directory exists."""
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    import re
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'  # Direct video ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_thumbnail_url(video_id: str, quality: str = 'maxresdefault') -> str:
    """
    Get YouTube thumbnail URL for a video.
    
    Quality options:
    - maxresdefault (1280x720) - Best quality, may not exist
    - sddefault (640x480)
    - hqdefault (480x360)
    - mqdefault (320x180)
    - default (120x90)
    """
    return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"


def download_thumbnail(video_id: str, output_dir: Optional[Path] = None) -> Optional[str]:
    """
    Download thumbnail for a YouTube video.
    Tries maxresdefault first, falls back to hqdefault.
    Returns path to downloaded file or None if failed.
    """
    ensure_directories()
    output_dir = output_dir or THUMBNAILS_DIR
    
    # Try different quality levels
    for quality in ['maxresdefault', 'sddefault', 'hqdefault']:
        url = get_thumbnail_url(video_id, quality)
        try:
            response = requests.get(url, timeout=10)
            # Check if we got a valid image (not the default placeholder)
            if response.status_code == 200 and len(response.content) > 1000:
                filepath = output_dir / f"{video_id}_{quality}.jpg"
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Downloaded thumbnail: {quality}")
                return str(filepath)
        except Exception as e:
            print(f"⚠️ Failed to download {quality}: {e}")
            continue
    
    return None


def dissect_thumbnail(image_path: str, api_key: str) -> Dict:
    """
    Dissect thumbnail into 5 structured components for editing.
    Returns structured JSON with: person, expression, text, colors, graphics
    """
    import base64
    
    # Read and encode image
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Gemini Vision API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    prompt = """Analyze this YouTube thumbnail and extract these 5 components as JSON:

1. **person**: Describe the person in the image
   - "description": Full description (appearance, clothing, gender, age estimate, position in frame)
   - "position": Where in frame ("left", "center", "right", "left-center", etc.)

2. **expression**: The person's facial expression and pose
   - "description": Detailed description of expression/emotion
   - "emotion": Single word emotion (shocked, angry, happy, serious, etc.)
   - "pose": Body language description

3. **text**: All visible text in the thumbnail
   - Array of text elements, each with:
     - "content": The actual text
     - "color": Hex color code
     - "position": Where on image (top, bottom, center, etc.)
     - "style": Font style description (bold, outlined, 3D, etc.)

4. **colors**: Color palette used
   - "primary": Main background/dominant color (hex)
   - "secondary": Second most prominent color (hex)
   - "accent": Accent/highlight color (hex)

5. **graphics**: Background elements and objects
   - "description": Overall description of background
   - "elements": Array of specific objects/graphics visible

Return ONLY valid JSON, no markdown formatting:
{
  "person": {"description": "...", "position": "..."},
  "expression": {"description": "...", "emotion": "...", "pose": "..."},
  "text": [{"content": "...", "color": "...", "position": "...", "style": "..."}],
  "colors": {"primary": "#...", "secondary": "#...", "accent": "#..."},
  "graphics": {"description": "...", "elements": ["...", "..."]}
}"""

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1  # Low temperature for consistent structured output
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            text = result['candidates'][0]['content']['parts'][0]['text']
            # Parse JSON from response
            try:
                # Clean up response - remove markdown if present
                json_str = text.strip()
                if json_str.startswith('```'):
                    json_str = json_str.split('```')[1]
                    if json_str.startswith('json'):
                        json_str = json_str[4:]
                    json_str = json_str.strip()
                
                dissection = json.loads(json_str)
                return {'success': True, 'dissection': dissection, 'raw': text}
            except json.JSONDecodeError as e:
                return {'success': False, 'error': f'Failed to parse JSON: {e}', 'raw': text}
        else:
            return {'success': False, 'error': f'API error: {response.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def generate_thumbnail_prompt(
    analysis: Dict,
    topic: str,
    style_notes: str = ""
) -> str:
    """
    Generate an AI image prompt for thumbnail recreation.
    Uses analysis from existing thumbnail to match style.
    """
    prompt_parts = ["YouTube thumbnail, 1280x720 aspect ratio"]
    
    if isinstance(analysis, dict):
        # Add color scheme
        if 'color_scheme' in analysis:
            colors = analysis['color_scheme']
            if isinstance(colors, str):
                prompt_parts.append(f"color scheme: {colors}")
            elif isinstance(colors, dict):
                prompt_parts.append(f"colors: {', '.join(str(v) for v in colors.values())}")
        
        # Add style
        if 'style' in analysis:
            prompt_parts.append(f"style: {analysis['style']}")
        
        # Add composition
        if 'composition' in analysis:
            prompt_parts.append(f"composition: {analysis['composition']}")
    
    # Add topic
    prompt_parts.append(f"topic: {topic}")
    
    # Add custom notes
    if style_notes:
        prompt_parts.append(style_notes)
    
    # Add quality requirements
    prompt_parts.extend([
        "professional YouTube thumbnail",
        "high contrast",
        "eye-catching",
        "bold text if any",
        "no watermarks",
        "clean composition"
    ])
    
    return ", ".join(prompt_parts)


if __name__ == '__main__':
    # Test extraction
    test_id = extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print(f"Extracted ID: {test_id}")
