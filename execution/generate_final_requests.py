#!/usr/bin/env python3
"""
Generate the 2 Requirement Scenarios using the LOCKED MASTER TEMPLATE.
Reference: execution/assets/master_template.jpg (The "Visual V5" result).
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai
from execution.generate_thumbnail import generate_thumbnail_image_only

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

MASTER_REF_PATH = "execution/assets/master_template.jpg"

SCENARIOS = [
    {
        "name": "US Empire / Yuan",
        "title_context": "U.S.Economic EMPIRE COLLAPSES, Panicked Washington Threatens Canada,China Yuan REPLACES USD Globally",
        "prompt": """
        TEMPLATE: LOCKED V5 WRAPPER (Strict Visual Match).
        LAYOUT: Symmetrical "Text Wrapper".
        CENTER: Donald Trump (Serious/Panicked).
        BACKGROUND: Split - US Flag/Dollar Burning (Left) vs Chinese Flag/Yuan Rising (Right).
        
        TEXT BLOCKS (Strict Style Transfer from Reference):
        - TOP: "EMPIRE COLLAPSE" (White/Red).
        - LEFT (Yellow Text on Black w/ Slanted Border): "YUAN REPLACES DOLLAR".
        - RIGHT (White/Red on Black): "USA IS DONE".
        
        BUTTON: "Watch Video Now" (Bottom Left).
        """
    },
    {
        "name": "10 Companies Job Cuts",
        "title_context": "10 U.S. Companies Quietly Cutting Millions of Jobs in 2026",
        "prompt": """
        TEMPLATE: LOCKED V5 WRAPPER (Strict Visual Match).
        LAYOUT: Symmetrical "Text Wrapper".
        CENTER: Donald Trump (Serious).
        BACKGROUND: Office buildings with "For Lease" / "Closed" signs.
        
        TEXT BLOCKS (Strict Style Transfer from Reference):
        - TOP: "MASS LAYOFFS" (White/Red).
        - LEFT (Yellow Text on Black w/ Slanted Border): "MILLIONS FIRED".
        - RIGHT (White/Red on Black): "JOBS GONE ZERO".
        
        BUTTON: "Watch Video Now" (Bottom Left).
        """
    }
]

def run_final_gen():
    print("🚀 Generating Final User Requests with LOCKED MASTER TEMPLATE...")
    
    for i, scen in enumerate(SCENARIOS):
        print(f"\nGenerating: {scen['name']}...")
        
        full_prompt = f"""
        Create a YouTube Thumbnail.
        STRICTLY FOLLOW THE VISUAL STYLE OF THE REFERENCE IMAGE.
        Replicate the 'Text Box Wrapper' look exactly.
        
        {scen['prompt']}
        """
        
        output_path = f".tmp/final_req_{i+1}.jpg"
        if generate_thumbnail_image_only(full_prompt, output_path, reference_image_path=MASTER_REF_PATH):
             print(f"   ✅ Saved: {output_path}")
        else:
             print(f"   ❌ Failed: {scen['name']}")

if __name__ == "__main__":
    run_final_gen()
