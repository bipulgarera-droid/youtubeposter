#!/usr/bin/env python3
"""
AI Thumbnail Generation.
Creates thumbnails based on topic using AI image generation.
Supports style reference for consistent branding.
"""
import os
import json
import base64
import requests
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Base directory
BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / '.tmp'
ASSETS_DIR = BASE_DIR / 'assets'


def generate_thumbnail_prompt(topic: str, style_notes: str = "") -> str:
    """
    Generate an optimized prompt for thumbnail creation.
    """
    base_prompt = f"""Create a YouTube thumbnail image for a video about: {topic}

Style requirements:
- Dramatic, attention-grabbing visuals
- High contrast colors (dark backgrounds work well)
- Bold, impactful imagery
- Financial/economic theme if relevant
- Professional look, not cheap or clickbaity
- 16:9 aspect ratio optimized
- Leave space for text overlay on the right third

{style_notes}

Do NOT include any text in the image - just visuals."""
    
    return base_prompt


def generate_thumbnail_with_gemini(
    topic: str,
    output_path: str = None,
    style_reference: str = None
) -> Optional[str]:
    """
    Generate thumbnail using Gemini's image generation.
    
    Args:
        topic: Video topic for the thumbnail
        output_path: Where to save the image
        style_reference: Optional path to reference image for style
        
    Returns:
        Path to generated thumbnail or None
    """
    if not output_path:
        output_dir = TMP_DIR / 'thumbnails'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / 'thumbnail.png')
    
    # Create prompt
    style_notes = ""
    if style_reference and Path(style_reference).exists():
        style_notes = "Match the visual style of the reference image provided."
    
    prompt = generate_thumbnail_prompt(topic, style_notes)
    
    try:
        # Use Gemini with Imagen for image generation
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # If we have a style reference, include it
        contents = [prompt]
        if style_reference and Path(style_reference).exists():
            # Load and encode reference image
            with open(style_reference, 'rb') as f:
                image_data = f.read()
            contents = [
                "Generate a thumbnail in this style:",
                {"mime_type": "image/png", "data": base64.b64encode(image_data).decode()},
                prompt
            ]
        
        response = model.generate_content(
            contents,
            generation_config={
                "response_mime_type": "image/png"
            }
        )
        
        # Save the generated image
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data'):
                            image_data = base64.b64decode(part.inline_data.data)
                            with open(output_path, 'wb') as f:
                                f.write(image_data)
                            print(f"✅ Thumbnail saved: {output_path}")
                            return output_path
        
        print("⚠️ No image in response")
        return None
        
    except Exception as e:
        print(f"❌ Thumbnail generation failed: {e}")
        return None


def generate_thumbnail_with_flux(
    topic: str,
    output_path: str = None
) -> Optional[str]:
    """
    Alternative: Use Replicate's Flux model for thumbnails.
    Requires REPLICATE_API_TOKEN environment variable.
    """
    REPLICATE_TOKEN = os.getenv('REPLICATE_API_TOKEN')
    if not REPLICATE_TOKEN:
        print("⚠️ REPLICATE_API_TOKEN not set, falling back to Gemini")
        return generate_thumbnail_with_gemini(topic, output_path)
    
    if not output_path:
        output_dir = TMP_DIR / 'thumbnails'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / 'thumbnail.png')
    
    prompt = generate_thumbnail_prompt(topic)
    
    try:
        # Call Replicate API
        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={"Authorization": f"Token {REPLICATE_TOKEN}"},
            json={
                "version": "black-forest-labs/flux-schnell",
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": "16:9",
                    "output_format": "png"
                }
            }
        )
        
        if response.status_code == 201:
            prediction = response.json()
            # Poll for result
            import time
            for _ in range(60):  # Max 60 seconds
                status_response = requests.get(
                    prediction['urls']['get'],
                    headers={"Authorization": f"Token {REPLICATE_TOKEN}"}
                )
                result = status_response.json()
                if result['status'] == 'succeeded':
                    image_url = result['output'][0]
                    # Download image
                    img_response = requests.get(image_url)
                    with open(output_path, 'wb') as f:
                        f.write(img_response.content)
                    print(f"✅ Thumbnail saved: {output_path}")
                    return output_path
                elif result['status'] == 'failed':
                    print(f"❌ Generation failed: {result.get('error')}")
                    return None
                time.sleep(1)
        
        return None
        
    except Exception as e:
        print(f"❌ Flux thumbnail generation failed: {e}")
        return None


def generate_thumbnail(
    topic: str,
    output_path: str = None,
    style_reference: str = None,
    use_flux: bool = False
) -> Optional[str]:
    """
    Main function to generate a thumbnail.
    
    Args:
        topic: Video topic
        output_path: Where to save
        style_reference: Optional style reference image
        use_flux: Whether to use Flux (Replicate) instead of Gemini
        
    Returns:
        Path to thumbnail or None
    """
    if use_flux:
        return generate_thumbnail_with_flux(topic, output_path)
    else:
        return generate_thumbnail_with_gemini(topic, output_path, style_reference)


if __name__ == "__main__":
    # Test
    result = generate_thumbnail(
        topic="Silver Market Crash: Banks Caught Manipulating Prices",
        output_path="test_thumbnail.png"
    )
    print(f"Generated: {result}")
