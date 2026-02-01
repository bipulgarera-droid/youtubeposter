#!/usr/bin/env python3
"""
Generate FINAL Template Candidate V2.
Corrections:
- Top Text: CLEARS head (Higher/Behind).
- Left Text: YELLOW COLOR on Black/Dark Background.
- Right Text: WHITE/RED COLOR on Black Background.
- Level/Adjacent/Equal Size.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

FINAL_RECIPE_V2 = """
STRICT VISUAL RECIPE (V2 Corrections):

1. GLOBAL COMPOSITION:
   - CENTER: Donald Trump (Serious), clearly separated from the top edge.
   - BACKGROUND: Dark Finance/Crisis theme.

2. TOP TEXT (Fix: No Head Overlap):
   - Text: "$36 TRILLION DEBT"
   - Style: Big White Font with Red Outline.
   - POSITION: Floated at the VERY TOP EDGE. Must NOT overlap Trump's hair. If needed, Trump is slightly lower in frame.

3. SIDE TEXTS ( The "Wrapper" Effect):
   - Concept: Two equal-sized text blocks flanking Trump's head, appearing as a continuous band behind/beside him.
   - ALIGNMENT: Perfectly Level horizontally. Same Font Size.
   
   - LEFT BLOCK:
     - Text: "YOUR 401k ZERO"
     - Color: BRIGHT YELLOW Text.
     - Background: Solid Black Rectangular Box (or very dark strip).
   
   - RIGHT BLOCK:
     - Text: "AMERICA IS BROKE"
     - Color: WHITE and RED Text (e.g. "AMERICA" White, "BROKE" Red).
     - Background: Solid Black Rectangular Box.

4. BUTTON:
   - Bottom Left: "Watch Video Now" button.
   - SIZE: TINY. Micro-scale (5-8% of screen width). Subtle.

5. LAYER ORDER:
   - Top Text is BACKGROUND layer relative to Trump (should look like it's behind him if they touch, or just high above).
"""

def generate_final_v2():
    print("🎨 Generating Final Template Candidate V2...")
    
    full_prompt = f"""
    Create a YouTube Thumbnail.
    {FINAL_RECIPE_V2}
    """
    
    from execution.generate_thumbnail import generate_thumbnail_image_only
    output_path = ".tmp/final_template_candidate_v2.jpg"
    
    if generate_thumbnail_image_only(full_prompt, output_path):
        print(f"   ✅ Saved: {output_path}")
    else:
        print("   ❌ Failed")

if __name__ == "__main__":
    generate_final_v2()
