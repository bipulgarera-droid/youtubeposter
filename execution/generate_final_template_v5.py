#!/usr/bin/env python3
"""
Generate FINAL Template Candidate V5.
KEY CHANGE: Passes the Reference Image directly to the model as visual grounding.
Goal: Replicate the 'Slanted Yellow Lines/Wrapper' EXACTLY.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# Use the image the user specifically pointed to for "box, spacing, font"
REFERENCE_IMAGE_PATH = "/Users/bipul/.gemini/antigravity/brain/a7ffae11-e96b-4bce-95a3-d0be5ead3e63/uploaded_media_1769789409612.png"

FINAL_RECIPE_V5 = """
STRICT VISUAL STYLE TRANSFER PROMPT:

Look at the REFERENCE IMAGE provided. I need you to replicate the DESIGN STYLE of the TEXT BOXES exactly.

1. LEFT TEXT BLOCK ("401k"):
   - **STYLE MATCHING:** Copy the exact look of the "YOUR 401k ZERO" box in the reference.
   - Observe the **Yellow Slanted Lines** on the top and bottom borders.
   - Observe the **Black Background**.
   - Observe the **Bright Yellow Font**.
   - REPLICATE THIS EXACT "CAUTION WRAPPER" STYLE.

2. COMPOSITION:
   - Center: Donald Trump (Serious).
   - Left: The "401k" Wrapper Box (Yellow/Black).
   - Right: "AMERICA IS BROKE" Box (White/Red on Black).
   - Bottom Left: "Watch Video Now" button.

3. TEXT CONTENT:
   - Top: "$36 TRILLION DEBT"
   - Left: "YOUR 401k ZERO"
   - Right: "AMERICA IS BROKE"

4. INSTRUCTION:
   - "Use the provided image as a strict Style Reference for the text containers."
"""

def generate_final_v5():
    print("🎨 Generating Final Template Candidate V5 (Visual Reference)...")
    
    # We call the helper which now supports reference_image_path
    from execution.generate_thumbnail import generate_thumbnail_image_only
    output_path = ".tmp/final_template_candidate_v5.jpg"
    
    if generate_thumbnail_image_only(FINAL_RECIPE_V5, output_path, reference_image_path=REFERENCE_IMAGE_PATH):
        print(f"   ✅ Saved: {output_path}")
    else:
        print("   ❌ Failed")

if __name__ == "__main__":
    generate_final_v5()
