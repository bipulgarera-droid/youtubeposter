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


def deep_research(topic: str, country: Optional[str] = None, source_article: Optional[Dict] = None) -> Dict:
    """
    Conduct deep research on a topic for script writing.
    
    Args:
        topic: The topic/title to research
        country: Optional country to focus on
        source_article: Optional original news article that triggered this topic
    
    Returns structured research with:
    - Recent news (current year)
    - Historical context
    - Key statistics
    - Notable quotes/sources
    """
    print(f"Researching: {topic}")
    current_year = datetime.now().year
    
    research = {
        "topic": topic,
        "country": country,
        "timestamp": datetime.now().isoformat(),
        "source_article": source_article,
        "recent_news": [],
        "historical_context": [],
        "statistics": [],
        "expert_analysis": [],
        "key_sources": [],
        "raw_facts": ""  # Changed from summary - just facts, no narrative
    }
    
    # 1. Recent news (THIS year - multiple queries)
    research["recent_news"] = _search_recent_news(topic, country, current_year)
    
    # 2. Historical context (deeper, multiple angles)
    research["historical_context"] = _search_historical_context(topic, country)
    
    # 3. Statistics and economic data
    research["statistics"] = _search_statistics(topic, country)
    
    # 4. Expert analysis and opinion pieces
    research["expert_analysis"] = _search_expert_analysis(topic, country)
    
    # 5. Generate RAW FACTS compilation (no narrative, just facts)
    research["raw_facts"] = _compile_raw_facts(research)
    
    return research


def _search_recent_news(topic: str, country: Optional[str], year: int) -> List[Dict]:
    """Search for recent news - CURRENT YEAR."""
    search_term = country or topic
    
    # Multiple queries for comprehensive coverage
    queries = [
        f"{search_term} economy {year} latest",
        f"{search_term} crisis news {year}",
        f"{search_term} economic policy {year}",
        f"{search_term} financial news today",
    ]
    
    all_results = []
    for query in queries:
        results = _serper_search(query, search_type="news", num=5)
        all_results.extend(results)
    
    # Deduplicate by title
    seen = set()
    unique = []
    for r in all_results:
        key = r.get("title", "")[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    return unique[:12]  # Return up to 12 unique articles


def _search_historical_context(topic: str, country: Optional[str]) -> List[Dict]:
    """Search for historical context and background - MULTIPLE ANGLES."""
    search_term = country or topic
    
    queries = [
        f"{search_term} economic history timeline",
        f"{search_term} economy how it started",
        f"{search_term} economic crisis origin cause",
        f"{search_term} economy 1990s 2000s background",
        f"why {search_term} economy collapsed history",
    ]
    
    all_results = []
    for q in queries:
        results = _serper_search(q, search_type="search", num=4)
        all_results.extend(results)
    
    return all_results[:10]


def _search_statistics(topic: str, country: Optional[str]) -> List[Dict]:
    """Search for statistics and economic data."""
    search_term = country or topic
    
    queries = [
        f"{search_term} GDP debt statistics",
        f"{search_term} inflation rate data",
        f"{search_term} unemployment poverty statistics",
        f"{search_term} economic indicators World Bank IMF",
    ]
    
    all_results = []
    for q in queries:
        results = _serper_search(q, search_type="search", num=3)
        all_results.extend(results)
    
    return all_results[:8]


def _search_expert_analysis(topic: str, country: Optional[str]) -> List[Dict]:
    """Search for expert analysis and opinion pieces."""
    search_term = country or topic
    
    queries = [
        f"{search_term} economy analysis expert",
        f"{search_term} economic outlook forecast",
        f"{search_term} economist opinion",
    ]
    
    all_results = []
    for q in queries:
        results = _serper_search(q, search_type="search", num=3)
        all_results.extend(results)
    
    return all_results[:6]


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


def _compile_raw_facts(research: Dict) -> str:
    """Compile raw facts from research - NO narrative, just facts and data."""
    if not GEMINI_API_KEY:
        return "Research compilation complete. No AI processing available."
    
    # Compile all research text
    source_text = ""
    if research.get("source_article"):
        source_text = f"ORIGINAL TRIGGER ARTICLE: {research['source_article'].get('title', '')}: {research['source_article'].get('snippet', '')}\n\n"
    
    news_text = "\n".join([
        f"- [{n.get('date', 'Recent')}] {n['title']}: {n['snippet']}"
        for n in research["recent_news"][:10]
    ])
    
    history_text = "\n".join([
        f"- {h['title']}: {h['snippet']}"
        for h in research["historical_context"][:8]
    ])
    
    stats_text = "\n".join([
        f"- {s['snippet']}"
        for s in research["statistics"][:6]
    ])
    
    expert_text = "\n".join([
        f"- {e['title']}: {e['snippet']}"
        for e in research.get("expert_analysis", [])[:4]
    ])
    
    prompt = f"""Extract RAW FACTS from this research about "{research['topic']}".

{source_text}
RECENT NEWS (Current year):
{news_text}

HISTORICAL CONTEXT:
{history_text}

STATISTICS & DATA:
{stats_text}

EXPERT ANALYSIS:
{expert_text}

INSTRUCTIONS:
1. Extract ONLY verifiable facts, numbers, dates, and quotes
2. DO NOT create a narrative or story structure
3. DO NOT include opinions or interpretations
4. Group facts into categories: CURRENT EVENTS, HISTORY, STATISTICS, KEY FIGURES
5. Each fact should be one line
6. Include specific numbers, percentages, dates wherever available
7. If something is uncertain, note it as "reportedly" or "allegedly"

Format as:
## CURRENT EVENTS (What's happening NOW)
- Fact 1
- Fact 2...

## HISTORY (How we got here)
- Fact 1...

## STATISTICS (Numbers and data)
- Fact 1...

## KEY FIGURES (People, organizations)
- Fact 1..."""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI facts compilation error: {e}")
        return "Research compiled. AI processing failed."


def format_research_for_script(research: Dict) -> str:
    """Format research into a prompt-ready string for script generation."""
    output = f"""# Research: {research['topic']}
Country: {research.get('country', 'N/A')}
Date: {research['timestamp']}

## Raw Facts
{research.get('raw_facts', research.get('summary', 'No summary available'))}

## Recent News Headlines ({len(research['recent_news'])} articles)
"""
    for news in research["recent_news"][:8]:
        date = news.get('date', '')
        output += f"- [{date}] {news['title']}\n"
    
    output += f"\n## Historical Context ({len(research['historical_context'])} sources)\n"
    for ctx in research["historical_context"][:5]:
        output += f"- {ctx['title']}\n"
    
    output += f"\n## Statistics ({len(research['statistics'])} sources)\n"
    for stat in research["statistics"][:4]:
        output += f"- {stat['snippet'][:150]}...\n"
    
    output += f"\n## Expert Analysis ({len(research.get('expert_analysis', []))} sources)\n"
    for exp in research.get("expert_analysis", [])[:3]:
        output += f"- {exp['title']}\n"
    
    return output


if __name__ == "__main__":
    # Test
    print("Testing research agent...")
    research = deep_research("Germany energy crisis", "Germany")
    print(f"\nRaw Facts:\n{research['raw_facts'][:500]}...")
