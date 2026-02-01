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
    country: Optional[str] = None,
    beat_map: Optional[Dict] = None
) -> Dict:
    """
    Generate a 7-chapter outline from research.
    
    Args:
        title: The video title
        research: Research dict with raw_facts, recent_news, etc.
        country: Optional country focus
        beat_map: Optional Beat Map from analyze_viral_structure for pacing guidance
    
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
    
    # Build pacing guidance from Beat Map if available
    pacing_guidance = ""
    if beat_map and beat_map.get("success"):
        hook = beat_map.get("hook", {})
        tension = beat_map.get("tension_build", {})
        mech = beat_map.get("mechanism", {})
        res = beat_map.get("resolution", {})
        
        pacing_guidance = f"""
=== PACING GUIDE (from viral video analysis) ===
HOOK: Use this technique: {hook.get('technique', 'shocking_stat')}
  - Elements: {', '.join(hook.get('elements', ['time anchor', 'personal stake']))}
  - Why it works: {hook.get('why_it_works', 'Creates immediate engagement')}

TENSION BUILD: {tension.get('technique', 'escalate stakes')}
  - Open loops: {', '.join(tension.get('open_loops', ['Promise revelation'])[:2])}

MECHANISM: Reveal in {mech.get('location', 'Middle')} using {mech.get('technique', 'analogy')}

RESOLUTION: End with {res.get('technique', 'empowerment')} - viewer agency: {res.get('viewer_agency', 'They can take action')}
===
"""
    
    prompt = f"""Generate a YouTube video script OUTLINE for this topic.

TITLE: {title}
COUNTRY FOCUS: {country or 'General'}

RESEARCH FACTS:
{raw_facts}

RECENT NEWS CONTEXT:
{news_context}

{pacing_guidance}

---

OUTLINE STRUCTURE (follow EXACTLY):

## HOOK (First 30 seconds - CRITICAL for retention)
- Use the pacing guide's hook technique if provided
- Vivid scene-setting in second person ("Imagine for a second...")
- One shocking stat or number from research
- Open loop: Promise what they'll learn

## STAKES (30s - 2min - Build tension)
- Connect to viewer's money, life, future
- Escalate the problem
- Create urgency

## MECHANISM
- The "how does this work" section
- Give it a memorable name if possible
- Use analogy to explain complex concepts

## CHAPTER 1: [Title], [Subtitle]
- Main point + Key data/stat
- Analogy to make it relatable

## CHAPTER 2: [Title], [Subtitle]
- Main point + Key data/stat
- Analogy to make it relatable

## CHAPTER 3: [Title], [Subtitle]
- Main point + Key data/stat
- Analogy to make it relatable

## CHAPTER 4: [Title], [Subtitle]
- Main point + Key data/stat
- Analogy to make it relatable

## CHAPTER 5: [Title], [Subtitle]
- Main point + Key data/stat
- Analogy to make it relatable

## COUNTER-ARGUMENTS (Balance section)
- Present the opposing view
- Address it with data
- Acknowledge nuance

## FINAL THOUGHTS
- Summary of key points
- Is there hope?
- Return agency to viewer - what can THEY do?

## OUTRO
- Question for comments
- Natural CTA

---

RULES:
1. Chapter titles should be punchy and memorable (e.g., "The Russian Needle", "The Debt Trap")
2. Subtitles explain the chapter (e.g., "Addicted to Cheap Gas", "Living on Borrowed Time")
3. Each chapter must cite at least ONE specific number/stat from the research
4. Build narrative tension - each chapter escalates until Counter-Arguments/Final Thoughts provide relief
5. Use vivid analogies (gaming metaphors, everyday comparisons)
6. NO STANDALONE HISTORY SECTION - weave historical context into chapters only when it supports a claim
7. End with EMPOWERMENT - viewer should feel rewarded, not just scared

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
