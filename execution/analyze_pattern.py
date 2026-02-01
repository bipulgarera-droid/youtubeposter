import google.generativeai as genai
import os
import base64
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)

def analyze_pattern(image_path, title):
    print(f"🕵️ Analyzing Pattern for: '{title}'")
    
    with open(image_path, "rb") as f:
        image_data = f.read()
        
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    prompt = f"""
    You are a YouTube Viral Analyst. analyze the Relationship between the VIDEO TITLE and the THUMBNAIL.
    
    VIDEO TITLE: "{title}"
    
    Analyze the Thumbnail Image provided and determine the "Virality Template".
    
    1. **TEXT STRATEGY:** 
       - Read the text on the thumbnail. 
       - How does it relate to the Title? (Is it a summary? A reaction? A specific number?)
       - Count the words. note the colors.
    
    2. **COMPOSITION TEMPLATE:**
       - Where are the characters? (Left/Right/Center)
       - Who are they? (Is it the person mentioned in title?)
       - What is the background?
    
    3. **GENERATE RECIPE:**
       - Create a generic instruction for ANY future video to follow this exact pattern.
       - Format: "If Title is [X], Thumbnail Text must be [Y style summary]. Layout must be [Z]."
    """
    
    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": image_data}])
    print("\n--- PATTERN ANALYSIS ---")
    print(response.text)
    return response.text

if __name__ == "__main__":
    # Test with the downloaded reference images
    # We need to find the path of the images downloaded in previous step
    # Assuming .tmp/test_orig_xi8BV6bWsWg.jpg exists from previous run
    
    img = ".tmp/test_orig_xi8BV6bWsWg.jpg"
    title = "IT'S OVER: China Just Sold All US Debt What They Aren't Telling You"
    
    if os.path.exists(img):
        analyze_pattern(img, title)
    else:
        print(f"File {img} not found. Please run previous test first.")
