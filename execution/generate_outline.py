"""
Outline Generator - Generate script outlines from research.

Creates a 7-chapter outline following script_style.md structure.
"""

import os
import google.generativeai as genai
from typing import Dict, Optional

# Load API key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def generate_outline(
    title: str,
    research: Dict,
    country: Optional[str] = None
) -> Dict:
    """
    Generate a 7-chapter outline from research.
    
    Args:
        title: The video title
        research: Research dict with raw_facts, recent_news, etc.
        country: Optional country focus
    
    Returns:
        Dict with outline structure
    """
    if not GEMINI_API_KEY:
        return {"success": False, "error": "GEMINI_API_KEY not set"}
    
    # Get raw facts from research
    raw_facts = research.get("raw_facts", "")
    
    # Compile news headlines for additional context
    news_context = "\n".join([
        f"- {n.get('title', '')}"
        for n in research.get("recent_news", [])[:8]
    ])
    
    prompt = f"""Generate a YouTube video script OUTLINE for this topic.

TITLE: {title}
COUNTRY FOCUS: {country or 'General'}

RESEARCH FACTS:
{raw_facts}

RECENT NEWS CONTEXT:
{news_context}

---

OUTLINE STRUCTURE (follow EXACTLY):

## HOOK
- Vivid scene-setting in second person ("Imagine for a second that you are...")
- One shocking stat or number
- Promise of revelation

## CONTEXT
- Historical origin (go back 30-50 years)
- The "original sin" of the problem
- How we got to today

## CHAPTER 1: [Title], [Subtitle]
- Main point
- Key data/stat to cite
- Analogy to make it relatable

## CHAPTER 2: [Title], [Subtitle]
- Main point
- Key data/stat to cite
- Analogy to make it relatable

## CHAPTER 3: [Title], [Subtitle]
- Main point
- Key data/stat to cite
- Analogy to make it relatable

## CHAPTER 4: [Title], [Subtitle]
- Main point
- Key data/stat to cite
- Analogy to make it relatable

## CHAPTER 5: [Title], [Subtitle]
- Main point
- Key data/stat to cite
- Analogy to make it relatable

## CHAPTER 6: [Title], [Subtitle]
- Main point
- Key data/stat to cite
- Analogy to make it relatable

## CHAPTER 7: [Title], [Subtitle]
- Main point
- Key data/stat to cite
- Analogy to make it relatable

## FINAL THOUGHTS
- Summary of the 7 problems
- Is there any hope?
- Return agency to viewer

## OUTRO
- Question for comments
- Like button CTA

---

RULES:
1. Chapter titles should be punchy and memorable (e.g., "The Russian Needle", "The Debt Trap")
2. Subtitles explain the chapter (e.g., "Addicted to Cheap Gas", "Living on Borrowed Time")
3. Each chapter must cite at least ONE specific number/stat from the research
4. Build narrative tension - each chapter should be worse than the last until Final Thoughts
5. Use vivid analogies (gaming metaphors, everyday comparisons)

Generate the outline now:"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        outline_text = response.text
        
        return {
            "success": True,
            "outline": outline_text,
            "title": title,
            "country": country
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_outline_for_telegram(outline_result: Dict) -> str:
    """Format outline for Telegram display."""
    if not outline_result.get("success"):
        return f"❌ Outline generation failed: {outline_result.get('error', 'Unknown error')}"
    
    outline = outline_result.get("outline", "")
    title = outline_result.get("title", "")
    
    # Truncate if too long for Telegram (4096 char limit)
    if len(outline) > 3500:
        outline = outline[:3500] + "\n\n... [truncated for display]"
    
    return f"""📋 **Script Outline**

**Title:** {title}

{outline}

---
Review this outline. If approved, the full 4,500-word script will be generated based on this structure."""


def format_outline_for_script(outline_result: Dict) -> str:
    """Format outline as context for script generation."""
    if not outline_result.get("success"):
        return ""
    
    return f"""APPROVED OUTLINE:
{outline_result.get('outline', '')}

Follow this outline structure EXACTLY when writing the script.
Each chapter must match the outline's chapter titles and cover the points listed."""


if __name__ == "__main__":
    # Test
    print("Outline generator ready.")
    print("Usage: generate_outline(title, research_dict, country)")
