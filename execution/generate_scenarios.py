#!/usr/bin/env python3
"""
Generate 3 specific "US Debt" scenarios using the strict Finance Template.
"""
import os
import requests
import time
from execution.generate_thumbnail import refine_prompt_with_grounding
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# The "Golden Recipe" extracted from user reference
STRICT_RECIPE = """
Template: FINANCE CRISIS SPLIT
1. LAYOUT: Split Screen.
   - Background Left: US Flag overlaying piles of burning money.
   - Background Right: Stock market chart crashing (Red lines going down).
   - Foreground Center: Donald Trump (Hyper-realistic) looking sweaty/shocked/serious.
   
2. TEXT ELEMENTS (Crucial - Match this style):
   - TOP BANNER (Floating): Big Bold White Text with Red Outline.
   - MIDDLE/SIDE BADGE: Yellow Caution Tape Background with Black Text.
   - Text Content must relate to the specific Topic below.

3. VIBE: High contrast, HD, Dramatic, 8k resolution.
"""

SCENARIOS = [
    {
        "title": "US National Debt Hits $40 Trillion - Economic Collapse Imminent",
        "topic": "US Debt $40 Trillion Crisis"
    },
    {
        "title": "Social Security Fund Emptied by 2026 - Seniors Left With Nothing",
        "topic": "Social Security Bankruptcy"
    },
    {
        "title": "China Dumps All US Treasuries - Dollar becomes Worthless",
        "topic": "China Sells US Debt"
    }
]

def generate_scenario_thumb(index, scenario):
    print(f"\n🎬 Generating Scenario {index+1}: {scenario['title']}")
    
    # 1. Generate Prompt using Refinement Engine
    print("   Refining prompt with Strict Recipe...")
    final_prompt = refine_prompt_with_grounding(
        prompt="Create a finance thumbnail", 
        topic=scenario['topic'], 
        recipe=STRICT_RECIPE
    )
    
    # 2. Generate Image
    print("   🎨 Rendering Image...")
    # We'll use the existing generation function to handle the API call correctly
    from execution.generate_thumbnail import generate_thumbnail_image_only
    
    output_path = f".tmp/scenario_{index+1}.jpg"
    success = generate_thumbnail_image_only(final_prompt, output_path)
    
    if success:
        print(f"   ✅ Saved: {output_path}")
    else:
        print("   ❌ Generation failed")

if __name__ == "__main__":
    for i, scenario in enumerate(SCENARIOS):
        generate_scenario_thumb(i, scenario)
