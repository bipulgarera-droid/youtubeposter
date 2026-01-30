#!/usr/bin/env python3
"""
AI Thumbnail Generation.
Creates thumbnails based on topic using AI image generation.
Supports style reference for consistent branding.
Includes compression for YouTube (<2MB) and title-based naming.
"""
import os
import re
import json
import base64
import requests
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Base directory
BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / '.tmp'
ASSETS_DIR = BASE_DIR / 'assets'


def sanitize_filename(title: str, max_length: int = 100) -> str:
    """Convert title to safe filename."""
    # Remove special characters, keep alphanumeric, spaces, hyphens
    safe = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with underscores
    safe = safe.strip().replace(' ', '_')
    # Truncate
    return safe[:max_length]


def compress_thumbnail(image_path: str, max_size_mb: float = 2.0) -> str:
    """
    Compress image to under max_size_mb for YouTube upload.
    Converts to JPEG if needed for better compression.
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    
    # Check current size
    current_size = os.path.getsize(image_path)
    if current_size <= max_size_bytes:
        print(f"✅ Thumbnail already under {max_size_mb}MB ({current_size / 1024 / 1024:.2f}MB)")
        return image_path
    
    print(f"⚠️ Thumbnail is {current_size / 1024 / 1024:.2f}MB, compressing...")
    
    # Open image
    img = Image.open(image_path)
    
    # Convert to RGB if necessary (for JPEG)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Change extension to jpg for output
    output_path = str(Path(image_path).with_suffix('.jpg'))
    
    quality = 95
    while quality >= 50:
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        new_size = os.path.getsize(output_path)
        
        if new_size <= max_size_bytes:
            print(f"✅ Compressed to {new_size / 1024 / 1024:.2f}MB (quality={quality})")
            return output_path
        
        quality -= 5
    
    print(f"⚠️ Could only compress to {new_size / 1024 / 1024:.2f}MB")
    return output_path


def generate_thumbnail_prompt(topic: str, style_notes: str = "") -> str:
    """
    Generate an optimized prompt for thumbnail creation following the style guide.
    Extracts the 2-4 word emotional punch from the title and includes it in the image.
    """
    # Extract thumbnail text (2-4 word emotional punch) from topic/title
    thumbnail_text = extract_thumbnail_text(topic)
    
    base_prompt = f"""Create a YouTube thumbnail image in ILLUSTRATED/CARTOON style (NOT photorealistic).

TOPIC: {topic}

TEXT TO RENDER: "{thumbnail_text}"
- Position: RIGHT SIDE of the image, stacked vertically (each word on its own line)
- Font style: BOLD sans-serif (like Impact or similar YouTube thumbnail font)
- Text color: SOLID WHITE fill (completely opaque, no transparency, no holes)
- Outline: THICK BLACK stroke around each letter for readability
- Size: LARGE and prominent, taking up the right third of the image
- Rendering: CLEAN and CRISP - no artifacts, no fuzzy edges, no missing parts

COMPOSITION:
1. LEFT SIDE: A character showing emotion - worried businessman in suit with hands on head looking shocked, OR man with back turned looking at destruction. Semi-realistic cartoon style. Orange/red jacket or suit for contrast.

2. CENTER: Dramatic visual elements relevant to {topic}. Include fire, smoke, collapsing buildings, burning money, oil barrels, etc. for urgency. Dark moody stormy atmosphere.

3. RIGHT SIDE: The text "{thumbnail_text}" prominently displayed with perfect clean white letters and black outline.

STYLE:
- Semi-realistic cartoon/illustration (like The Economist magazine covers)
- Dark moody background (dark blue, stormy gray, deep purple)
- Fire and orange/red accents for urgency
- High contrast, punchy saturated colors
- 16:9 aspect ratio (1280x720)
- Dramatic apocalyptic mood

{style_notes}"""
    
    return base_prompt


def extract_thumbnail_text(topic: str) -> str:
    """
    Extract 2-4 word emotional punch from title based on style guide patterns.
    
    Correlations from reference channel:
    - "DEATH of X" → "IT'S OVER" (Petrodollar example)
    - "X is Collapsing" → "[X] IS DYING" (Europe example)
    - "IMPOSSIBLE" → "ZERO CHANCE"
    - "Mistake" / "FAILED" → "IT FAILED"
    - "POORER" → "[X] IS BROKE"
    - Parenthetical "(The Verdict)" → "THE REAL REASON"
    """
    topic_lower = topic.lower()
    
    # Pattern: "DEATH of X" → "IT'S OVER" (like Petrodollar)
    if "death" in topic_lower:
        return "IT'S OVER"
    
    # Pattern: "Collapsing" → "[X] IS DYING"
    if "collapsing" in topic_lower:
        import re
        match = re.search(r"(\w+)'?s?\s+(?:economy\s+)?(?:is\s+)?collapsing", topic_lower)
        if match:
            subject = match.group(1).upper()
            return f"{subject} IS DYING"
        return "IT'S DYING"
    
    # Pattern: "IMPOSSIBLE"
    if "impossible" in topic_lower:
        return "ZERO CHANCE"
    
    # Pattern: "FAILED" or "Mistake"
    if "failed" in topic_lower or "mistake" in topic_lower:
        return "IT FAILED"
    
    # Pattern: "POORER" or "BROKE"
    if "poorer" in topic_lower or "broke" in topic_lower:
        # Extract country
        import re
        match = re.search(r"why (\w+)", topic_lower)
        if match:
            country = match.group(1).upper()
            return f"{country} IS BROKE"
        return "IT'S BROKE"
    
    # Pattern: "Can't Grow" or "DYING"
    if "can't grow" in topic_lower or "dying" in topic_lower:
        import re
        match = re.search(r"why (\w+)", topic_lower)
        if match:
            country = match.group(1).upper()
            return f"WHY {country} IS DYING"
        return "IT'S DYING"
    
    # Pattern: "UNREFORMABLE" or "UNFIXABLE"
    if "unreformable" in topic_lower or "unfixable" in topic_lower:
        import re
        match = re.search(r"(\w+) (?:economy|is)", topic_lower)
        if match:
            country = match.group(1).upper()
            return f"{country} IS UNFIXABLE"
        return "IT'S UNFIXABLE"
    
    # Pattern: Parenthetical hint - often the thumbnail text
    import re
    paren_match = re.search(r"\(([^)]+)\)", topic)
    if paren_match:
        paren_content = paren_match.group(1)
        # Check if it's a good candidate
        if len(paren_content.split()) <= 5:
            # Shorten if needed
            words = paren_content.upper().split()
            if len(words) <= 4:
                return paren_content.upper()
    
    # Default fallback
    return "IT'S OVER"


def analyze_thumbnail_recipe(image_path: str, title_context: str = "") -> str:
    """
    Analyze reference image to extract the 'Virality Template' (Recipe).
    Returns a strict instruction set for the image generator.
    """
    try:
        import requests
        api_key = GEMINI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")
            
        prompt = f"""You are a YouTube Thumbnail Reverse-Engineer.
        
        CONTEXT TITLE: "{title_context}" (The video this thumb belongs to)
        
        TASK: Extract the DESIGN RECIPE used here so we can replicate it for a new topic.
        
        ANALYZE 3 LAYERS:
        
        1. **TEXT STRATEGY (Crucial):**
           - What is the exact text? Count the words.
           - How does it relate to the Title? (e.g. "Title says 'Market Crash', Thumb says 'IT'S OVER'").
           - Font Colors & Backgrounds (e.g. "Big Yellow text, Red background strip").
           - POSITION: Where is it? (Center, Top-Left, etc).
        
        2. **LAYOUT TEMPLATE:**
           - Character: Who is it? (Left or Right?) Expression?
           - Background: What elements are shown? (Split screen? Chaos?)
        
        3. **THE RECIPE (Output this part clearly):**
           - Write a prompt instruction: "Template: Split screen. Left side: [Crisis Element]. Right side: [Host]. Text: [2-3 words] in [Color] style."
        
        Keep it concise. Focus on the RECIPE."""
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_data}}
                ]
            }]
        }
        
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Recipe analysis failed: {response.text}")
            return None
    except Exception as e:
        print(f"⚠️ Recipe analysis error: {e}")
        return None


def refine_prompt_with_grounding(prompt: str, topic: str, recipe: str = "") -> str:
    """
    Use Gemini to:
    1. Apply the DESIGN RECIPE from the reference (Text Strategy + Layout).
    2. Swap Leaders (Biden -> Trump 2026).
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash') 
        
        refine_prompt = f"""You are an expert YouTube Thumbnail Designer. Current Year: 2026.
        
        OBJECTIVE: Create a prompt for a NEW thumbnail about "{topic}" that follows the MASTER TEMPLATE style.
        
        THE MASTER TEMPLATE RULES (STRICT):
        1. **CHARACTER:** ALWAYS Donald Trump (2026 version). 
           - Position: CENTER, close-up portrait. 
           - Expression: Tweaked to match the topic (e.g. Concerned, Angry, Warning, Serious).
        2. **LAYOUT:**
           - TOP: Big Headline Text.
           - LEFT CENTER: A text box with 2-3 words.
           - RIGHT CENTER: A text box with 2-3 words.
           - BACKGROUND: Graphics related to the topic (e.g. Stock charts, Fire, Debt Clock) behind Trump.
        
        THE DESIGN RECIPE (FROM REFERENCE):
        {recipe}
        
        -------------------------------------------
        
        INSTRUCTIONS FOR NEW PROMPT:
        
        1. **TEXT STRATEGY:**
           - Extract the "emotional punch" from the NEW TOPIC: "{topic}".
           - Generate 3 distinct text blocks matching the layout (Top, Left, Right).
           - Text must be short, punchy, and spelled CORRECTLY.
        
        2. **VISUAL CONTENT:**
           - Subject: Donald Trump (Center).
           - Background: RELEVANT to "{topic}". If topic is "Crash", show red arrows/fire.
        
        3. **OUTPUT PROMPT:**
           - Write a highly detailed image generation prompt.
           - Format: "A YouTube thumbnail... [Visuals of Trump]... [Background details]... TEXT TO RENDER: Top: '[Text]', Left: '[Text]', Right: '[Text]'"
           - Include: "High quality, 8k, detailed, realistic skin texture."
        """
        
        # We try to use search tool config if possible
        try:
           response = model.generate_content(refine_prompt) 
        except:
           response = model.generate_content(refine_prompt)
           
        if response.text:
            return response.text.strip()
        return prompt
        
    except Exception as e:
        print(f"⚠️ Prompt refinement failed: {e}")
        return prompt

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
    """
    if not output_path:
        output_dir = TMP_DIR / 'thumbnails'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / 'thumbnail.png')
    
    # 1. Create Base Prompt
    base_prompt = generate_thumbnail_prompt(topic, "")
    final_prompt = base_prompt
    
    # 2. Analyze Reference if provided (The "Cloning" Step)
    if style_reference and Path(style_reference).exists():
        print(f"👁️ Analyzing thumbnail RECIPE: {Path(style_reference).name}...")
        # Analyze recipe
        recipe = analyze_thumbnail_recipe(style_reference, topic)
        if not recipe:
            recipe = "Use a standard high-contract YouTube style."
        
        print("✅ Recipe extracted. merging with topic...")
        
        # Formulate the "Draft" prompt
        draft_prompt = f"""Create a YouTube thumbnail based on this DESIGN RECIPE:
        
{recipe}

IMPORTANT ADAPTATION:
- Visual Subject: Depict concepts related to "{topic}"
- FOLLOW THE RECIPE'S INSTRUCTIONS FOR TEXT AND LAYOUT EXACTLY.
"""

        # 3. Refine with Grounding & Recipe
        print("🌍 Refinement: Applying Recipe & 2026 Context...")
        final_prompt = refine_prompt_with_grounding(draft_prompt, topic, recipe)
        
        # Append instruction to ensure content replacement
        final_prompt += " \n\nIMPORTANT: The main character is DONALD TRUMP. Use the reference image ONLY FOR STYLE/LAYOUT/COLORS. Do NOT copy the specific text from the reference image, use the NEW text defined in the prompt."
        
    else:
        print("⚠️ No style reference provided, using basic prompt.")
    
    # 4. Generate Image (PASSING THE REFERENCE IMAGE FOR VISUAL GROUNDING)
    print(f"🎨 Calling Image Generator... (Ref: {Path(style_reference).name if style_reference else 'None'})")
    success = generate_thumbnail_image_only(
        prompt=final_prompt,
        output_path=output_path,
        reference_image_path=style_reference  # <--- CRITICAL: Pass the image for Visual Style Transfer
    )
    
    if success:
        return output_path
    return None
    
def generate_thumbnail_image_only(prompt: str, output_path: str, reference_image_path: str = None) -> bool:
    """
    Directly call the Imagen 3 / Gemini Image Generation API with a prompt.
    Supports optional Reference Image for style/composition grounding.
    Returns True if successful.
    """
    try:
        import requests
        
        # Use Nano Banana Pro (gemini-3-pro-image-preview) for GENERATION
        api_key = GEMINI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent?key={api_key}"
        
        parts = [{"text": prompt}]
        
        # Add Reference Image if provided
        if reference_image_path and Path(reference_image_path).exists():
            print(f"   👁️ Attaching Reference Image: {Path(reference_image_path).name}")
            with open(reference_image_path, "rb") as img_file:
                b64_data = base64.b64encode(img_file.read()).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg", # Assuming JPEG/PNG, API is flexible
                        "data": b64_data
                    }
                })
        
        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }
        
        print("🎨 Sending generation request...")
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            
            for candidate in result.get('candidates', []):
                for part in candidate.get('content', {}).get('parts', []):
                    if 'inlineData' in part:
                        image_data = base64.b64decode(part['inlineData']['data'])
                        
                        # Ensure output directory exists
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(output_path, 'wb') as f:
                            f.write(image_data)
                        print(f"✅ Thumbnail saved: {output_path}")
                        return True
            
            print("⚠️ No image in response")
            return False
        else:
            print(f"❌ API error: {response.status_code} - {response.text[:200]}")
            return False
        
    except Exception as e:
        print(f"❌ Thumbnail generation failed: {e}")
        return False


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
    title: str = None,
    output_path: str = None,
    style_reference: str = None,
    use_flux: bool = False,
    auto_compress: bool = True
) -> Optional[str]:
    """
    Main function to generate a thumbnail.
    
    Args:
        topic: Video topic for prompt generation
        title: Video title (used for filename if output_path not specified)
        output_path: Where to save (overrides title-based naming)
        style_reference: Optional style reference image
        use_flux: Whether to use Flux (Replicate) instead of Gemini
        auto_compress: Whether to auto-compress to <2MB for YouTube
        
    Returns:
        Path to thumbnail or None
    """
    # Generate output path from title if not specified
    if not output_path and title:
        output_dir = TMP_DIR / 'thumbnails'
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = sanitize_filename(title)
        output_path = str(output_dir / f"{safe_filename}_thumbnail.png")
    
    # Generate thumbnail
    if use_flux:
        result = generate_thumbnail_with_flux(topic, output_path)
    else:
        result = generate_thumbnail_with_gemini(topic, output_path, style_reference)
    
    # Auto-compress for YouTube if requested
    if result and auto_compress:
        result = compress_thumbnail(result, max_size_mb=2.0)
    
    return result


if __name__ == "__main__":
    # Test
    result = generate_thumbnail(
        topic="Silver Market Crash: Banks Caught Manipulating Prices",
        title="THE SILVER CRASH: Banks Caught Red-Handed",
        output_path="test_thumbnail.png"
    )
    print(f"Generated: {result}")

