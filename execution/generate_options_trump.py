#!/usr/bin/env python3
"""
Generate 3 Design Options for ONE Title ("US Debt Hits $36 Trillion").
STRICT REQUIREMENT: TRUMP SOLO + WATCH VIDEO BUTTON.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# Common "Base" features for all options
BASE_RECIPE = """
MANDATORY ELEMENTS:
1. CHARACTER: DONALD TRUMP ONLY. (No other people). Center/Right placement. High quality, serious/shocked expression.
2. BOTTOM-LEFT BUTTON: A Red/White Button graphic that says "Watch Video Now".
3. VIBE: High Contrast, 8k, Detailed, Dramatic YouTube Thumbnail.
"""

# The 3 Variations
OPTIONS = [
    {
        "name": "Option A (Direct Clone)",
        "prompt_add": """
        LAYOUT: Split Screen. Left: US Flag + Falling Money. Right: Red Stock Crash Chart.
        TEXT 1 (Top Left, Big White/Red): "$36 TRILLION DEBT"
        TEXT 2 (Mid Left, Yellow Caution Tape): "YOUR 401k ZERO"
        TEXT 3 (Right, Striped Badge): "AMERICA IS BROKE"
        """
    },
    {
        "name": "Option B (Fire Variant)",
        "prompt_add": """
        LAYOUT: Burning Background. Trump in foreground looking panicked.
        TEXT 1 (Top Center, Big Red): "TOTAL COLLAPSE"
        TEXT 2 (Side, Yellow Tape): "DOLLAR ZERO"
        TEXT 3 (Bottom Right): "IT'S ALL GONE"
        """
    },
    {
        "name": "Option C (Bank Run Variant)",
        "prompt_add": """
        LAYOUT: Background shows an EMPTY BANK VAULT and "CLOSED" signs. Trump shouting.
        TEXT 1 (Top Left, Big White): "GAME OVER"
        TEXT 2 (Mid Right, Yellow Tape): "NO MONEY LEFT"
        """
    }
]

def generate_option(index, option):
    print(f"\n🎨 Generating {option['name']}...")
    
    full_prompt = f"""
    Create a YouTube Thumbnail.
    {BASE_RECIPE}
    
    SPECIFIC OPTION DETAILS:
    {option['prompt_add']}
    
    Ensure the "Watch Video Now" button is visible in the bottom left corner.
    """
    
    from execution.generate_thumbnail import generate_thumbnail_image_only
    output_path = f".tmp/trump_option_{index+1}.jpg"
    
    if generate_thumbnail_image_only(full_prompt, output_path):
        print(f"   ✅ Saved: {output_path}")
    else:
        print("   ❌ Failed")

if __name__ == "__main__":
    for i, opt in enumerate(OPTIONS):
        generate_option(i, opt)
