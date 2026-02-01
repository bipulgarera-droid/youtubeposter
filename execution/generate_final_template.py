#!/usr/bin/env python3
"""
Generate FINAL Template Candidate.
Constraint: TRUMP CENTER. SYMMETRICAL TEXT FLANKS. CENTERED TOP TEXT.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# Title: US Debt Hits $36 Trillion
# Text Selection: 
#   Top: "$36 TRILLION DEBT"
#   Left: "YOUR 401k ZERO"
#   Right: "AMERICA IS BROKE"

FINAL_RECIPE = """
STRICT VISUAL RECIPE:

1. COMPOSITION: Symmetrical "Triptych" Layout.
   - CENTER IMAGE: Donald Trump (Serious/Shocked), taking up the middle third.
   - BACKGROUND: Dark, dramatically lit (Red/Black gradient or blurred Stock Chart).

2. TEXT LAYOUT (Crucial Alignment):
   - TOP CENTER: Text "$36 TRILLION DEBT" is DIRECTLY centered at the very top. Big, White Font with Red Outline.
   - LEFT SIDE: Text "YOUR 401k ZERO". Style: Bright Yellow Text on a Dark Background Strip. Position: Mid-height, to the LEFT of Trump's head.
   - RIGHT SIDE: Text "AMERICA IS BROKE". Style: White & Red Text on a Black Background Strip. Position: Mid-height, to the RIGHT of Trump's head.
   - ALIGNMENT RULE: The Left Text and Right Text must be horizontally LEVEL (same height) and equal in visual size. They act as "brackets" around Trump.

3. BUTTON:
   - Bottom Left Corner: A VERY SMALL red button graphic that says "Watch Video Now". Scale: 10% of width.

4. VIBE: Professional YouTube Finance Channel. High Contrast. HD.
"""

def generate_final():
    print("🎨 Generating Final Template Candidate...")
    
    full_prompt = f"""
    Create a YouTube Thumbnail.
    {FINAL_RECIPE}
    """
    
    from execution.generate_thumbnail import generate_thumbnail_image_only
    output_path = ".tmp/final_template_candidate.jpg"
    
    if generate_thumbnail_image_only(full_prompt, output_path):
        print(f"   ✅ Saved: {output_path}")
    else:
        print("   ❌ Failed")

if __name__ == "__main__":
    generate_final()
