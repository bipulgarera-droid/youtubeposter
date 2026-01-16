#!/usr/bin/env python3
"""
AI Image Generation for Video Chunks
Uses Gemini Flash for visual metaphor + Gemini 2.5 Flash Image for generation.
Ensures consistent 16:9 YouTube dimensions via post-processing.
"""
import os
import io
import re
import base64
from pathlib import Path
from dotenv import load_dotenv

# Try new SDK first, fallback to old SDK
try:
    from google import genai
    from google.genai import types
    NEW_SDK = True
except ImportError:
    import google.generativeai as genai
    types = None
    NEW_SDK = False

from PIL import Image

# Import style selector
try:
    from execution.style_selector import apply_style_to_prompt, auto_select_mood, auto_select_scene_type, DEFAULT_STYLE
except ImportError:
    # Fallback if running standalone
    print("⚠️ Style selector not found, using defaults")
    apply_style_to_prompt = lambda p, s, m, t: f"{s} style: {p}"
    auto_select_mood = lambda t: "bright_sunny"
    auto_select_scene_type = lambda t: "street_wide"
    DEFAULT_STYLE = "ghibli_cartoon"

load_dotenv()

# Constants
YOUTUBE_WIDTH = 1920
YOUTUBE_HEIGHT = 1080
YOUTUBE_ASPECT = YOUTUBE_WIDTH / YOUTUBE_HEIGHT  # 16:9 = 1.777...

api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("⚠️ No GEMINI_API_KEY found. Image generation will fail.")

if NEW_SDK and api_key:
    client = genai.Client(api_key=api_key)
else:
    if api_key:
        genai.configure(api_key=api_key)
    client = None


def crop_to_youtube(image: Image.Image) -> Image.Image:
    """
    Crop/resize image to exact 16:9 YouTube dimensions (1920x1080).
    Uses COVER-FIT logic: scales up to fill entire frame, then crops excess.
    This prevents any black/white bars.
    """
    original_width, original_height = image.size
    
    # Convert to RGB if needed (removes alpha channel that can cause issues)
    if image.mode in ('RGBA', 'P', 'LA'):
        # Create white background for transparency
        background = Image.new('RGB', image.size, (0, 0, 0))  # Black background
        if image.mode == 'RGBA':
            background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
        else:
            background.paste(image)
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    
    original_aspect = original_width / original_height
    
    # COVER-FIT: Scale to fill, then crop to exact size
    # Add 1% safety margin to ensure we cover edges completely (prevents single-pixel white lines)
    SAFETY_MARGIN = 1.01
    
    if original_aspect > YOUTUBE_ASPECT:
        # Image is wider: scale by height to fill, then crop width
        scale_factor = (YOUTUBE_HEIGHT / original_height) * SAFETY_MARGIN
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Crop excess width from center
        left = (new_width - YOUTUBE_WIDTH) // 2
        top = (new_height - YOUTUBE_HEIGHT) // 2
        cropped = resized.crop((left, top, left + YOUTUBE_WIDTH, top + YOUTUBE_HEIGHT))
    else:
        # Image is taller: scale by width to fill, then crop height
        scale_factor = (YOUTUBE_WIDTH / original_width) * SAFETY_MARGIN
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Crop excess height from center
        left = (new_width - YOUTUBE_WIDTH) // 2
        top = (new_height - YOUTUBE_HEIGHT) // 2
        cropped = resized.crop((left, top, left + YOUTUBE_WIDTH, top + YOUTUBE_HEIGHT))
    
    # Validate final dimensions
    if cropped.size != (YOUTUBE_WIDTH, YOUTUBE_HEIGHT):
        print(f"   ⚠️ Size mismatch, forcing resize: {cropped.size} -> {YOUTUBE_WIDTH}x{YOUTUBE_HEIGHT}")
        cropped = cropped.resize((YOUTUBE_WIDTH, YOUTUBE_HEIGHT), Image.Resampling.LANCZOS)
    
    return cropped



def get_visual_metaphor(chunk_text: str) -> str:
    """
    Use Gemini Flash to convert script text to a visual description.
    Emphasizes LITERAL, DIRECT imagery over abstract metaphors.
    """
    prompt = f"""You are a visual director for documentary-style YouTube videos about finance, economics, and geopolitics.

Given this script chunk: "{chunk_text}"

Create a SINGLE visual scene description that:
1. Is DIRECTLY related to the topic (not abstract metaphors)
2. Shows LITERAL objects related to the content (buildings, money, gold, maps, documents, etc.)
3. Can be rendered as an impressionist oil painting
4. Is visually striking and documentary-style

BE LITERAL, NOT ABSTRACT. Examples:
- "Federal Reserve printing money" → "a massive industrial printing press in a grand marble hall, US dollar bills being printed, stacks of fresh currency"
- "China stockpiling gold" → "endless rows of gold bars in a massive vault, Chinese flag in background, warm golden lighting"
- "US national debt" → "the US Capitol building with a massive digital counter showing trillions, surrounded by stacks of government bonds"
- "BRICS new payment system" → "a world map highlighting Brazil, Russia, India, China, South Africa, with golden trade routes connecting them"
- "Inflation eroding savings" → "a wallet with money visibly shrinking, grocery prices rising on a store shelf behind"

DO NOT use boats, abstract water imagery, or overly poetic metaphors.
Respond with ONLY the visual description, nothing else. Keep it under 40 words."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt]
        )
        return response.text.strip()
    except Exception as e:
        print(f"   ⚠️ Metaphor generation failed: {e}")
        # Fallback: use the chunk text directly  
        return f"a cinematic documentary scene depicting: {chunk_text}"


def generate_chunk_image(chunk_text: str, output_path: str, chunk_index: int = 0, style_id: str = DEFAULT_STYLE) -> dict:
    """
    Generate an AI image for a script chunk.
    
    Args:
        chunk_text: The script text for this chunk
        output_path: Where to save the image
        chunk_index: Index for logging
    
    Returns:
        dict with success status, path, and metadata
    """
    print(f"   🧠 Getting visual metaphor for chunk {chunk_index}...")
    metaphor = get_visual_metaphor(chunk_text)
    print(f"   💡 Metaphor: {metaphor[:80]}...")
    
    # Auto-select mood and scene type
    mood = auto_select_mood(chunk_text)
    scene_type = auto_select_scene_type(chunk_text)
    
    # Build prompt using style selector
    full_prompt = apply_style_to_prompt(
        base_prompt=metaphor,
        style_id=style_id,
        mood_id=mood,
        scene_type=scene_type
    )
    
    # Add negative prompt protection
    full_prompt += ", SINGLE UNIFIED SCENE ONLY - no split panels, no collage, no text, no words, no white bars, no white padding"

    print(f"   🎨 Generating image ({style_id}/{mood})...")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[full_prompt],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE', 'TEXT']
            )
        )
        
        # Extract image from response
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data
                image = Image.open(io.BytesIO(image_bytes))
                
                # CRITICAL: Force 16:9 YouTube dimensions
                youtube_image = crop_to_youtube(image)
                
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Save as high-quality PNG
                youtube_image.save(output_path, "PNG", optimize=True)
                
                print(f"   ✅ Saved: {output_path} ({youtube_image.size})")
                
                return {
                    'success': True,
                    'path': output_path,
                    'size': youtube_image.size,
                    'metaphor': metaphor,
                    'chunk_text': chunk_text
                }
        
        return {'success': False, 'error': 'No image in response'}
        
    except Exception as e:
        print(f"   ❌ Error generating image: {e}")
        return {'success': False, 'error': str(e)}


def split_script_to_chunks(script: str, max_words: int = 25, max_sentences: int = 3) -> list:
    """
    Split script into chunks for image generation.
    Each chunk is max 25 words OR 3 sentences, whichever comes first.
    
    Rationale:
    - TTS speaks ~150 words/minute = 2.5 words/second
    - 25 words = ~10 seconds of audio per chunk
    - For a 25-min video (1500 sec) = ~150 chunks at 10 sec each
    - For a 12-min video (720 sec) = ~72 chunks at 10 sec each
    """
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    current_sentence_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        words_in_sentence = len(sentence.split())
        
        # Check if adding this sentence would exceed limits
        if (current_word_count + words_in_sentence > max_words or 
            current_sentence_count >= max_sentences) and current_chunk:
            # Save current chunk and start new one
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_word_count = words_in_sentence
            current_sentence_count = 1
        else:
            current_chunk.append(sentence)
            current_word_count += words_in_sentence
            current_sentence_count += 1
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def generate_all_images(script: str, output_dir: str, style: str = DEFAULT_STYLE) -> dict:
    """
    Generate images for all chunks in a script.
    
    Args:
        script: Full script text
        output_dir: Directory to save images
    
    Returns:
        dict with results for each chunk
    """
    chunks = split_script_to_chunks(script)
    
    print(f"📝 Split script into {len(chunks)} chunks")
    print(f"📁 Output directory: {output_dir}")
    
    results = []
    
    for i, chunk in enumerate(chunks):
        print(f"\n[{i+1}/{len(chunks)}] \"{chunk[:50]}...\"")
        
        output_path = os.path.join(output_dir, f"chunk_{i:03d}.png")
        result = generate_chunk_image(chunk, output_path, i, style_id=style)
        result['index'] = i
        result['chunk_text'] = chunk
        results.append(result)
    
    successful = sum(1 for r in results if r.get('success'))
    
    return {
        'success': successful == len(chunks),
        'total_chunks': len(chunks),
        'successful': successful,
        'failed': len(chunks) - successful,
        'chunks': results,
        'output_dir': output_dir
    }

# Alias for pipeline compatibility
generate_images_for_script = generate_all_images


# CLI for testing
if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--script', '-s', help='Script text to generate images for')
    parser.add_argument('--chunk', '-c', help='Single chunk to generate image for')
    parser.add_argument('--output', '-o', default='.tmp/ai_images', help='Output directory')
    args = parser.parse_args()
    
    if args.chunk:
        result = generate_chunk_image(args.chunk, f"{args.output}/test.png", 0)
        print(json.dumps(result, indent=2))
    elif args.script:
        result = generate_all_images(args.script, args.output)
        print(json.dumps(result, indent=2, default=str))
    else:
        # Demo with sample text
        demo_script = """
        The Federal Reserve just printed another trillion dollars.
        China is stockpiling gold at an unprecedented rate.
        The US national debt has crossed 35 trillion dollars.
        """
        result = generate_all_images(demo_script, args.output)
        print(json.dumps(result, indent=2, default=str))
