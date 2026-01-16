#!/usr/bin/env python3
"""
Test script for Gemini 2.5 Flash Image generation.
"""
import os
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from google.genai import types
from PIL import Image

# Initialize client (uses GOOGLE_API_KEY or GEMINI_API_KEY from env)
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")

client = genai.Client(api_key=api_key)

prompt = "A futuristic neon-lit cityscape at night with flying cars, cyberpunk style, 4K quality"

print(f"🎨 Generating image with prompt: {prompt}")
print("📡 Using model: gemini-2.5-flash-image")

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=['IMAGE', 'TEXT']
        )
    )
    
    # Check for image in response
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(f"📝 Text response: {part.text}")
        elif part.inline_data is not None:
            # Save the image - inline_data.data is raw bytes
            import io
            image_bytes = part.inline_data.data
            image = Image.open(io.BytesIO(image_bytes))
            output_path = ".tmp/test_generated_image.png"
            os.makedirs(".tmp", exist_ok=True)
            image.save(output_path)
            print(f"✅ Image saved to: {output_path}")
            print(f"📐 Image size: {image.size}")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
