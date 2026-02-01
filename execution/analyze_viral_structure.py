#!/usr/bin/env python3
"""
Analyze Viral Video Structure.

Analyzes a transcript to extract the "Beat Map" — the pacing structure
that made the video go viral. This is used to guide our script generation
WITHOUT copying content.

Output: A beat map identifying:
- Hook technique (0-30s)
- Tension build (30s-2min)
- Mechanism explanation
- Evidence/stats distribution
- Resolution/empowerment
"""

import os
import json
from typing import Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def analyze_viral_structure(transcript: str, title: str = "", word_count: int = None) -> Dict:
    """
    Analyze viral video transcript to extract pacing structure.
    
    Args:
        transcript: Full transcript text
        title: Video title
        word_count: Approximate word count (for timing estimation)
    
    Returns:
        Dict with beat map:
        - hook: Technique used in first 30 seconds
        - tension_build: How stakes are escalated (30s-2min)
        - mechanism: Where/how the "secret" is revealed
        - evidence_density: Where stats are concentrated
        - resolution: How agency is returned to viewer
        - anti_patterns: Things they did poorly (fat to cut)
    """
    if not GEMINI_API_KEY:
        return {"success": False, "error": "GEMINI_API_KEY not set"}
    
    # Estimate words per section (150 words ≈ 1 minute)
    wc = word_count or len(transcript.split())
    
    prompt = f"""Analyze this viral video transcript to extract its STRUCTURAL PACING.

TITLE: {title}
ESTIMATED LENGTH: ~{wc} words (~{wc // 150} minutes)

TRANSCRIPT:
{transcript[:10000]}

---

Analyze the STRUCTURE, not the content. We want to learn:
1. What TECHNIQUE made the hook effective?
2. How do they BUILD TENSION in the first 2 minutes?
3. Where is the MECHANISM (the "how it works") explained?
4. How are STATS distributed throughout?
5. How do they END — do they empower the viewer?
6. What is FLUFF that we should cut?

---

Output as valid JSON:

{{
  "hook": {{
    "technique": "One of: 'imagine_scenario', 'shocking_stat', 'controversial_claim', 'you_been_lied_to', 'time_anchor', 'personal_stake'",
    "example_phrase": "The actual opening line or paraphrased version",
    "elements": ["list", "of", "elements", "used"],
    "why_it_works": "Brief explanation of why this hook is effective"
  }},
  "tension_build": {{
    "technique": "How do they escalate stakes in first 2 min?",
    "escalation_steps": ["Step 1", "Step 2", "Step 3"],
    "open_loops": ["Questions or promises that keep viewer watching"]
  }},
  "mechanism": {{
    "location": "Early (0-5min) / Middle (5-15min) / Late (15min+)",
    "technique": "How is the 'secret' revealed? Analogy? Step-by-step? Named concept?",
    "named_concept": "Any memorable name they give the mechanism, or null"
  }},
  "evidence_distribution": {{
    "pattern": "Frontloaded / Evenly distributed / Backloaded",
    "stat_density": "High / Medium / Low",
    "uses_comparisons": true/false,
    "uses_personal_examples": true/false
  }},
  "resolution": {{
    "technique": "How do they end? Empowerment / Fear / Call-to-action / Open question",
    "viewer_agency": "Does the viewer feel they can DO something?",
    "memorable_line": "Closing line or null"
  }},
  "anti_patterns": {{
    "fluff_sections": ["Any sections that felt like filler"],
    "repeated_points": ["Points made multiple times unnecessarily"],
    "we_should_cut": ["Specific things to avoid in our version"]
  }},
  "recommended_beat_order": [
    "hook",
    "stakes",
    "context (brief)",
    "mechanism",
    "evidence",
    "counter_argument",
    "resolution"
  ]
}}"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean JSON markers
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        result = json.loads(response_text)
        result["success"] = True
        result["source_word_count"] = wc
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return {
            "success": False,
            "error": f"JSON parse error: {e}",
            "raw_response": response_text[:500] if 'response_text' in dir() else ""
        }
    except Exception as e:
        print(f"Structure analysis error: {e}")
        return {"success": False, "error": str(e)}


def format_beat_map_for_telegram(beat_map: Dict) -> str:
    """Format beat map for Telegram display."""
    if not beat_map.get("success"):
        return f"❌ Analysis failed: {beat_map.get('error', 'Unknown error')}"
    
    output = "🎬 **Viral Video Structure Analysis**\n\n"
    
    # Hook
    hook = beat_map.get("hook", {})
    output += f"**🎣 Hook Technique:** {hook.get('technique', 'Unknown')}\n"
    if hook.get("example_phrase"):
        output += f"  _\"{hook['example_phrase'][:100]}...\"_\n"
    output += f"  Why it works: {hook.get('why_it_works', 'N/A')}\n\n"
    
    # Tension
    tension = beat_map.get("tension_build", {})
    output += f"**📈 Tension Build:** {tension.get('technique', 'Unknown')}\n"
    if tension.get("open_loops"):
        output += f"  Open loops: {', '.join(tension['open_loops'][:2])}\n\n"
    
    # Mechanism
    mech = beat_map.get("mechanism", {})
    output += f"**⚙️ Mechanism:** {mech.get('location', 'Unknown')} - {mech.get('technique', 'N/A')}\n"
    if mech.get("named_concept"):
        output += f"  Named: \"{mech['named_concept']}\"\n\n"
    else:
        output += "\n"
    
    # Resolution
    res = beat_map.get("resolution", {})
    output += f"**🏁 Resolution:** {res.get('technique', 'Unknown')}\n"
    output += f"  Viewer agency: {res.get('viewer_agency', 'N/A')}\n\n"
    
    # Anti-patterns
    anti = beat_map.get("anti_patterns", {})
    if anti.get("we_should_cut"):
        output += f"**✂️ We'll Cut:** {', '.join(anti['we_should_cut'][:3])}\n\n"
    
    # Recommended order
    order = beat_map.get("recommended_beat_order", [])
    if order:
        output += f"**📋 Recommended Structure:** {' → '.join(order)}\n"
    
    return output


def get_beat_guidance_for_script(beat_map: Dict) -> str:
    """
    Generate guidance text to inject into script generation prompt.
    
    This tells the script generator HOW to structure the content
    based on the viral video's pacing.
    """
    if not beat_map.get("success"):
        return ""
    
    hook = beat_map.get("hook", {})
    tension = beat_map.get("tension_build", {})
    mech = beat_map.get("mechanism", {})
    res = beat_map.get("resolution", {})
    anti = beat_map.get("anti_patterns", {})
    
    guidance = f"""
=== VIRAL VIDEO PACING GUIDE (USE THIS STRUCTURE) ===

HOOK (First 30 seconds):
- Technique: {hook.get('technique', 'shocking_stat')}
- Must include: {', '.join(hook.get('elements', ['time anchor', 'personal stake']))}
- Example style: "{hook.get('example_phrase', 'Start with Imagine or shocking stat')[:100]}"

TENSION BUILD (30s - 2min):
- Technique: {tension.get('technique', 'escalating stakes')}
- Open loops to create: {', '.join(tension.get('open_loops', ['Promise revelation'])[:2])}

MECHANISM REVEAL:
- Location: {mech.get('location', 'Middle')}
- Technique: {mech.get('technique', 'Step-by-step with analogy')}
- Consider naming it: give the concept a memorable name

EVIDENCE DISTRIBUTION:
- Pattern: {beat_map.get('evidence_distribution', {}).get('pattern', 'Evenly distributed')}
- Use comparisons: {beat_map.get('evidence_distribution', {}).get('uses_comparisons', True)}

RESOLUTION:
- Technique: {res.get('technique', 'Empowerment')}
- Viewer must feel: {res.get('viewer_agency', 'They can take action')}

ANTI-PATTERNS (AVOID THESE):
- {chr(10).join(['- ' + x for x in anti.get('we_should_cut', ['Unnecessary repetition'])])}

===
"""
    return guidance


if __name__ == "__main__":
    # Test with sample transcript
    test_transcript = """
    Imagine waking up tomorrow to find out that the dollar in your pocket 
    is worth 30% less than it was yesterday. China just announced they've 
    dumped $688 billion in US treasuries, the largest single sale in history.
    Janet Yellen called an emergency press conference. The Federal Reserve 
    is in crisis mode. This isn't a drill. On January 3rd, 2026, Beijing 
    made a decision that could reshape the global financial order.
    
    Now you might be thinking: so what? China sells some bonds, big deal.
    But here's what the mainstream media isn't telling you. When China 
    sells treasuries, they're essentially voting with their wallet against 
    the US dollar. And they took a loss to do it. A $40 billion loss.
    
    Think about that. The second largest economy in the world just paid 
    $40 billion to get OUT of American debt. Why would they do that?
    
    To understand this, we need to go back to 2014...
    """
    
    result = analyze_viral_structure(test_transcript, "China Dumps $688B in US Debt")
    print(json.dumps(result, indent=2))
