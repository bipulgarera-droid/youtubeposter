#!/usr/bin/env python3
"""
AI Image Generation for Video Chunks
Uses Gemini Flash for visual metaphor + Gemini 2.5 Flash Image for generation.
Ensures consistent 16:9 YouTube dimensions via post-processing.
"""
import os
import io
import re
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.genai import types
from PIL import Image

load_dotenv()

# Constants
YOUTUBE_WIDTH = 1920
YOUTUBE_HEIGHT = 1080
YOUTUBE_ASPECT = YOUTUBE_WIDTH / YOUTUBE_HEIGHT  # 16:9 = 1.777...

api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("No API key found. Set GEMINI_API_KEY in .env")

client = genai.Client(api_key=api_key)


def crop_to_youtube(image: Image.Image) -> Image.Image:
    """
    Crop/resize image to exact 16:9 YouTube dimensions (1920x1080).
    Centers the crop to keep the most important part.
    """
    original_width, original_height = image.size
    original_aspect = original_width / original_height
    
    if abs(original_aspect - YOUTUBE_ASPECT) < 0.01:
        # Already close to 16:9, just resize
        return image.resize((YOUTUBE_WIDTH, YOUTUBE_HEIGHT), Image.Resampling.LANCZOS)
    
    if original_aspect > YOUTUBE_ASPECT:
        # Image is wider than 16:9, crop sides
        new_width = int(original_height * YOUTUBE_ASPECT)
        left = (original_width - new_width) // 2
        cropped = image.crop((left, 0, left + new_width, original_height))
    else:
        # Image is taller than 16:9, crop top/bottom
        new_height = int(original_width / YOUTUBE_ASPECT)
        top = (original_height - new_height) // 2
        cropped = image.crop((0, top, original_width, top + new_height))
    
    # Resize to exact dimensions
    return cropped.resize((YOUTUBE_WIDTH, YOUTUBE_HEIGHT), Image.Resampling.LANCZOS)


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


def generate_chunk_image(chunk_text: str, output_path: str, chunk_index: int = 0) -> dict:
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
    
    # Build the full image prompt with style constraints
    full_prompt = f"""Impressionist oil painting style, {metaphor}, 
warm color palette with rich gold and teal-turquoise tones, 
soft visible brushstrokes, classical vintage aesthetic, 
cinematic wide composition suitable for YouTube video background,
horizontal landscape format 16:9 aspect ratio,
SINGLE UNIFIED SCENE ONLY - no split panels, no multiple images, no collage, no side-by-side compositions,
no borders, no frames, no black bars, no letterboxing,
no text or words or letters or numbers in the image,
highly detailed, professional art quality, dramatic lighting,
fill the entire canvas with one cohesive image"""

    print(f"   🎨 Generating image...")
    
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


def generate_all_images(script: str, output_dir: str) -> dict:
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
        result = generate_chunk_image(chunk, output_path, i)
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
