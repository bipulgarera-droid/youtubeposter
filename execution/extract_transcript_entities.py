#!/usr/bin/env python3
"""
Extract Entities and Claims from Viral Video Transcript.

Mines the transcript for:
- Named entities (people, countries, events, policies, dollar amounts)
- Key claims (what the video asserts)
- Counter-queries (devil's advocate questions for balanced research)
"""

import os
import json
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def extract_entities_and_claims(transcript: str, title: str = "") -> Dict:
    """
    Extract entities, claims, and generate counter-queries from a transcript.
    
    Args:
        transcript: Full transcript text
        title: Video title (for context)
    
    Returns:
        Dict with:
        - entities: List of named entities (people, places, events, amounts)
        - claims: List of key assertions made in the video
        - counter_queries: Devil's advocate queries for balanced research
        - search_queries: Specific queries for Serper based on entities
    """
    if not GEMINI_API_KEY:
        return {"success": False, "error": "GEMINI_API_KEY not set"}
    
    # Truncate transcript if too long (keep first 8000 chars)
    transcript_chunk = transcript[:8000] if len(transcript) > 8000 else transcript
    
    prompt = f"""Analyze this viral video transcript and extract structured information.

TITLE: {title}

TRANSCRIPT:
{transcript_chunk}

---

Extract the following:

## 1. NAMED ENTITIES (5-10 most important)
Extract specific, searchable entities:
- People (names of leaders, economists, experts mentioned)
- Countries/Regions (affected areas)
- Organizations (central banks, governments, institutions)
- Policies/Events (specific bills, treaties, crises)
- Dollar Amounts (specific figures like $688 billion, 47%)
- Dates (specific dates or time periods mentioned)

## 2. KEY CLAIMS (3-5 main assertions)
What is the video CLAIMING? These are the core arguments.
Format: "[Subject] [Verb] [Object]" — specific, falsifiable statements.
Example: "China sold $688 billion in US treasuries at a record loss"

## 3. COUNTER-QUERIES (2-4 devil's advocate questions)
Questions that challenge the video's claims for balanced research.
Example: "Did China actually lose money on the treasury sales?"
Example: "What are economists saying about the treasury sell-off?"

## 4. SEARCH QUERIES (5-8 specific Serper queries)
Generate specific search queries using the extracted entities.
NOT generic like "China economy" but specific like "China $688 billion treasury sale 2026"
Include queries for:
- The main topic + recent news
- Counter-facts / opposing views
- Statistics and data

---

Output as valid JSON:
{{
  "entities": [
    {{"type": "person", "name": "...", "context": "..."}},
    {{"type": "country", "name": "...", "context": "..."}},
    {{"type": "amount", "value": "...", "context": "..."}},
    ...
  ],
  "claims": [
    "Claim 1",
    "Claim 2",
    ...
  ],
  "counter_queries": [
    "Question 1",
    "Question 2",
    ...
  ],
  "search_queries": [
    "Specific query 1",
    "Specific query 2",
    ...
  ]
}}"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean JSON markers if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        result = json.loads(response_text)
        result["success"] = True
        
        # Validate we have the required fields
        if "entities" not in result:
            result["entities"] = []
        if "claims" not in result:
            result["claims"] = []
        if "counter_queries" not in result:
            result["counter_queries"] = []
        if "search_queries" not in result:
            result["search_queries"] = []
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        # Try to extract what we can
        return {
            "success": False,
            "error": f"JSON parse error: {e}",
            "raw_response": response_text[:500] if 'response_text' in dir() else ""
        }
    except Exception as e:
        print(f"Entity extraction error: {e}")
        return {"success": False, "error": str(e)}


def format_entities_for_display(extraction: Dict) -> str:
    """Format extracted entities for Telegram display."""
    if not extraction.get("success"):
        return f"❌ Extraction failed: {extraction.get('error', 'Unknown error')}"
    
    output = "📊 **Extracted from Transcript**\n\n"
    
    # Entities
    entities = extraction.get("entities", [])
    if entities:
        output += "**🏷️ Key Entities:**\n"
        for e in entities[:8]:
            if isinstance(e, dict):
                output += f"• {e.get('type', 'entity').title()}: {e.get('name', e.get('value', 'N/A'))}\n"
            else:
                output += f"• {e}\n"
        output += "\n"
    
    # Claims
    claims = extraction.get("claims", [])
    if claims:
        output += "**📌 Key Claims:**\n"
        for c in claims[:5]:
            output += f"• {c}\n"
        output += "\n"
    
    # Counter queries
    counter = extraction.get("counter_queries", [])
    if counter:
        output += "**🔍 Counter-Research Queries:**\n"
        for q in counter[:4]:
            output += f"• {q}\n"
        output += "\n"
    
    # Search queries
    queries = extraction.get("search_queries", [])
    if queries:
        output += f"**🔎 Generated {len(queries)} specific search queries**\n"
    
    return output


if __name__ == "__main__":
    # Test with sample transcript
    test_transcript = """
    Imagine waking up tomorrow to find out that the dollar in your pocket 
    is worth 30% less than it was yesterday. China just announced they've 
    dumped $688 billion in US treasuries, the largest single sale in history.
    Janet Yellen called an emergency press conference. The Federal Reserve 
    is in crisis mode. This isn't a drill. On January 3rd, 2026, Beijing 
    made a decision that could reshape the global financial order...
    """
    
    result = extract_entities_and_claims(test_transcript, "China Dumps $688B in US Debt")
    print(json.dumps(result, indent=2))
