#!/usr/bin/env python3
"""
Test script: Generate 5 images using 2-step process
1. Gemini Flash 2.5 to create visual metaphor from script chunk
2. Gemini 2.5 Flash Image to generate the actual image
"""
import os
import io
from dotenv import load_dotenv
import google.generativeai as genai
from google.genai import types
from PIL import Image

load_dotenv()

api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
client = genai.Client(api_key=api_key)

# Output directory
OUTPUT_DIR = ".tmp/generated_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 5 finance-related script chunks to test
SCRIPT_CHUNKS = [
    "The Federal Reserve just printed another trillion dollars",
    "China is stockpiling gold at an unprecedented rate",
    "The US national debt has crossed 35 trillion dollars",
    "BRICS nations are building a new payment system",
    "Inflation is silently eroding your purchasing power"
]

# Step 1: Convert chunk to visual metaphor
def get_visual_metaphor(chunk_text: str) -> str:
    """Use Gemini Flash to convert script text to a visual metaphor description."""
    
    prompt = f"""You are a visual concept artist for documentary-style YouTube videos about finance and economics.

Given this script chunk: "{chunk_text}"

Create a SINGLE visual metaphor/scene description that:
1. Is symbolic/metaphorical (not literal text or charts)
2. Uses powerful imagery (objects, scenes, people, landscapes)
3. Can be painted in an impressionist oil painting style
4. Is visually striking and cinematic
5. Relates to finance/economics themes

Examples:
- "inflation eroding savings" → "ancient gold coins slowly crumbling into dust on a marble table"
- "Federal Reserve printing money" → "a massive printing press in a grand hall, paper bills flying everywhere like confetti"
- "stock market crash" → "a golden bull statue shattering into pieces on Wall Street"

Respond with ONLY the visual description, nothing else. Keep it under 30 words."""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt]
    )
    return response.text.strip()


# Step 2: Generate image with consistent style
def generate_styled_image(visual_metaphor: str, output_path: str) -> bool:
    """Generate image using the visual metaphor with consistent impressionist style."""
    
    full_prompt = f"""Impressionist oil painting, {visual_metaphor}, warm color palette with rich gold and teal-turquoise tones, soft visible brushstrokes, classical vintage aesthetic, cinematic composition, 16:9 wide aspect ratio horizontal landscape format, no text or words or letters in the image, highly detailed, professional art quality"""
    
    print(f"   📸 Generating with prompt: {full_prompt[:100]}...")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[full_prompt],
        config=types.GenerateContentConfig(
            response_modalities=['IMAGE', 'TEXT']
        )
    )
    
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            image = Image.open(io.BytesIO(image_bytes))
            image.save(output_path)
            print(f"   ✅ Saved: {output_path} ({image.size})")
            return True
    
    return False


# Main execution
print("=" * 60)
print("🎨 GENERATING 5 TEST IMAGES")
print(f"📁 Output directory: {OUTPUT_DIR}")
print("=" * 60)

for i, chunk in enumerate(SCRIPT_CHUNKS, 1):
    print(f"\n[{i}/5] Script chunk: \"{chunk}\"")
    
    # Step 1
    print("   🧠 Step 1: Getting visual metaphor...")
    metaphor = get_visual_metaphor(chunk)
    print(f"   💡 Metaphor: {metaphor}")
    
    # Step 2
    print("   🎨 Step 2: Generating image...")
    output_file = os.path.join(OUTPUT_DIR, f"test_image_{i}.png")
    success = generate_styled_image(metaphor, output_file)
    
    if not success:
        print(f"   ❌ Failed to generate image")

print("\n" + "=" * 60)
print(f"✅ DONE! Check images in: {OUTPUT_DIR}")
print("=" * 60)
