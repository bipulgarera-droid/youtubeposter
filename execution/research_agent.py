"""
Research Agent - Deep research for video scripts.

Gathers comprehensive information from multiple sources:
- Recent news (Serper)
- Historical context (web search)
- Key statistics and data
"""

import os
import json
import requests
from typing import Dict, List, Optional
from datetime import datetime
import google.generativeai as genai

# Load API keys
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def deep_research(topic: str, country: Optional[str] = None) -> Dict:
    """
    Conduct deep research on a topic for script writing.
    
    Returns structured research with:
    - Recent news
    - Historical context
    - Key statistics
    - Notable quotes/sources
    """
    print(f"Researching: {topic}")
    
    research = {
        "topic": topic,
        "country": country,
        "timestamp": datetime.now().isoformat(),
        "recent_news": [],
        "historical_context": [],
        "statistics": [],
        "key_sources": [],
        "summary": ""
    }
    
    # 1. Recent news (last week)
    research["recent_news"] = _search_recent_news(topic, country)
    
    # 2. Historical context (broader search)
    research["historical_context"] = _search_historical_context(topic, country)
    
    # 3. Statistics and data
    research["statistics"] = _search_statistics(topic, country)
    
    # 4. Generate summary using AI
    research["summary"] = _generate_research_summary(research)
    
    return research


def _search_recent_news(topic: str, country: Optional[str]) -> List[Dict]:
    """Search for recent news on the topic."""
    query = f"{topic} {country or ''} news 2024"
    return _serper_search(query, search_type="news", num=8)


def _search_historical_context(topic: str, country: Optional[str]) -> List[Dict]:
    """Search for historical context and background."""
    queries = [
        f"{country or topic} economic history",
        f"why {country or topic} crisis origin",
        f"{country or topic} problem started when"
    ]
    
    results = []
    for q in queries[:2]:
        results.extend(_serper_search(q, search_type="search", num=5))
    return results


def _search_statistics(topic: str, country: Optional[str]) -> List[Dict]:
    """Search for statistics and data."""
    query = f"{country or topic} GDP debt statistics data"
    return _serper_search(query, search_type="search", num=5)


def _serper_search(query: str, search_type: str = "search", num: int = 10) -> List[Dict]:
    """Execute Serper API search."""
    if not SERPER_API_KEY:
        return []
    
    url = f"https://google.serper.dev/{search_type}"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "gl": "us",
        "hl": "en",
        "num": num
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if search_type == "news":
            items = data.get("news", [])
        else:
            items = data.get("organic", [])
        
        return [
            {
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "date": item.get("date", "")
            }
            for item in items
        ]
    except Exception as e:
        print(f"Serper error: {e}")
        return []


def _generate_research_summary(research: Dict) -> str:
    """Generate AI summary of research findings."""
    if not GEMINI_API_KEY:
        return "Research compilation complete. No AI summary available."
    
    # Compile research text
    news_text = "\n".join([
        f"- {n['title']}: {n['snippet']}"
        for n in research["recent_news"][:5]
    ])
    
    history_text = "\n".join([
        f"- {h['title']}: {h['snippet']}"
        for h in research["historical_context"][:5]
    ])
    
    stats_text = "\n".join([
        f"- {s['title']}: {s['snippet']}"
        for s in research["statistics"][:3]
    ])
    
    prompt = f"""Summarize this research for a YouTube video script about "{research['topic']}".

RECENT NEWS:
{news_text}

HISTORICAL CONTEXT:
{history_text}

STATISTICS:
{stats_text}

Provide a 300-word summary covering:
1. The current situation (what's happening now)
2. The historical origin (how did this start, go back 20-50 years)
3. Key statistics and numbers to cite
4. The main "story" or narrative arc

Be factual. Include specific numbers and dates where available."""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI summary error: {e}")
        return "Research compiled. AI summary failed."


def format_research_for_script(research: Dict) -> str:
    """Format research into a prompt-ready string for script generation."""
    output = f"""# Research: {research['topic']}
Country: {research.get('country', 'N/A')}
Date: {research['timestamp']}

## Summary
{research['summary']}

## Recent News Headlines
"""
    for news in research["recent_news"][:5]:
        output += f"- {news['title']}\n"
    
    output += "\n## Historical Context\n"
    for ctx in research["historical_context"][:3]:
        output += f"- {ctx['title']}: {ctx['snippet'][:100]}...\n"
    
    output += "\n## Key Statistics\n"
    for stat in research["statistics"][:3]:
        output += f"- {stat['snippet'][:150]}...\n"
    
    return output


if __name__ == "__main__":
    # Test
    print("Testing research agent...")
    research = deep_research("Germany energy crisis", "Germany")
    print(f"\nSummary:\n{research['summary'][:500]}...")
