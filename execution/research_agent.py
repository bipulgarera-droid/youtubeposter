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
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Import article content fetcher (uses Camoufox or requests fallback)
try:
    from execution.fetch_articles import fetch_multiple_articles
    FETCH_AVAILABLE = True
except ImportError:
    FETCH_AVAILABLE = False
    print("Warning: fetch_articles not available, will use snippets only")

# Load API keys
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def deep_research(
    topic: str, 
    country: Optional[str] = None, 
    source_article: Optional[Dict] = None,
    extracted_entities: Optional[Dict] = None
) -> Dict:
    """
    Conduct deep research on a topic for script writing.
    
    Args:
        topic: The topic/title to research
        country: Optional country to focus on
        source_article: Optional original news article that triggered this topic
        extracted_entities: Optional dict from extract_transcript_entities.py with:
            - search_queries: Specific queries to run
            - counter_queries: Devil's advocate queries for balanced research
    
    Returns structured research with:
    - Recent news (current year)
    - Historical context
    - Key statistics
    - Notable quotes/sources
    - Counter-facts (opposing views)
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
        "counter_facts": [],  # NEW: Opposing views for balanced reporting
        "key_sources": [],
        "raw_facts": ""  # Changed from summary - just facts, no narrative
    }
    
    # If we have extracted entities, use their specific queries
    entity_queries = []
    counter_queries = []
    if extracted_entities and extracted_entities.get("success"):
        entity_queries = extracted_entities.get("search_queries", [])
        counter_queries = extracted_entities.get("counter_queries", [])
        print(f"📊 Using {len(entity_queries)} entity-derived queries")
        print(f"🔍 Using {len(counter_queries)} counter-fact queries")
    
    # 1. Recent news (THIS year - multiple queries)
    research["recent_news"] = _search_recent_news(topic, country, current_year, entity_queries)
    
    # 2. Historical context (brief, to support claims - not standalone)
    research["historical_context"] = _search_historical_context(topic, country)
    
    # 3. Statistics and economic data
    research["statistics"] = _search_statistics(topic, country)
    
    # 4. Expert analysis and opinion pieces
    research["expert_analysis"] = _search_expert_analysis(topic, country)
    
    # 5. Counter-facts (opposing views for balanced reporting)
    if counter_queries:
        research["counter_facts"] = _search_counter_facts(counter_queries)
    
    # 6. SCRAPE ARTICLE CONTENT (new step - fetch full article text)
    if FETCH_AVAILABLE:
        print("📖 Scraping full article content...")
        # Combine all articles that have URLs
        all_articles_with_urls = []
        for article in research["recent_news"]:
            if article.get("url"):
                all_articles_with_urls.append(article)
        for article in research["historical_context"]:
            if article.get("url"):
                all_articles_with_urls.append(article)
        for article in research["expert_analysis"]:
            if article.get("url"):
                all_articles_with_urls.append(article)
        # Include counter-facts for balanced scraping
        for article in research.get("counter_facts", []):
            if article.get("url"):
                all_articles_with_urls.append(article)
        
        # Scrape ALL articles (using Jina Reader for quality)
        if all_articles_with_urls:
            enriched = fetch_multiple_articles(all_articles_with_urls, max_articles=25)
            # Update original articles with content
            url_to_content = {a.get('url'): a.get('content', '') for a in enriched}
            for article in research["recent_news"]:
                if article.get("url") in url_to_content:
                    article["content"] = url_to_content[article["url"]]
            for article in research["historical_context"]:
                if article.get("url") in url_to_content:
                    article["content"] = url_to_content[article["url"]]
            for article in research["expert_analysis"]:
                if article.get("url") in url_to_content:
                    article["content"] = url_to_content[article["url"]]
            for article in research.get("counter_facts", []):
                if article.get("url") in url_to_content:
                    article["content"] = url_to_content[article["url"]]
    
    # 6. Generate RAW FACTS compilation (no narrative, just facts)
    research["raw_facts"] = _compile_raw_facts(research)
    
    return research


def _search_recent_news(topic: str, country: Optional[str], year: int, entity_queries: List[str] = None) -> List[Dict]:
    """Search for recent news - CURRENT YEAR. Prioritizes entity-derived queries."""
    search_term = country or topic
    
    # Use entity-derived queries first if available
    queries = []
    if entity_queries:
        queries.extend(entity_queries[:5])  # Use up to 5 entity queries
    
    # Fallback/supplemental generic queries
    queries.extend([
        f"{search_term} economy {year} latest",
        f"{search_term} crisis news {year}",
        f"{search_term} financial news today",
    ])
    
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


def _search_counter_facts(counter_queries: List[str]) -> List[Dict]:
    """
    Search for opposing viewpoints and counter-arguments.
    
    Uses devil's advocate queries generated from entity extraction
    to find balanced reporting and alternative perspectives.
    """
    all_results = []
    
    for query in counter_queries[:4]:  # Limit to 4 counter queries
        # Search for opposing views
        results = _serper_search(query, search_type="search", num=3)
        for r in results:
            r["is_counter_fact"] = True  # Mark as counter-fact for later processing
        all_results.extend(results)
    
    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = r.get("title", "")[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    return unique[:8]  # Return up to 8 counter-fact sources


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
    
    # NEW: Include counter-facts for balanced reporting
    counter_text = "\n".join([
        f"- {c['title']}: {c['snippet']}"
        for c in research.get("counter_facts", [])[:4]
    ])
    
    prompt = f"""Extract RAW FACTS from this research about "{research['topic']}".

{source_text}
RECENT NEWS (Current year):
{news_text}

HISTORICAL CONTEXT (Use sparingly - only to support claims):
{history_text}

STATISTICS & DATA:
{stats_text}

EXPERT ANALYSIS:
{expert_text}

COUNTER-ARGUMENTS & OPPOSING VIEWS:
{counter_text}

INSTRUCTIONS:
1. Extract ONLY verifiable facts, numbers, dates, and quotes
2. DO NOT create a narrative or story structure
3. DO NOT include opinions or interpretations
4. Group facts into categories: CURRENT EVENTS, STATISTICS, KEY FIGURES, COUNTER-ARGUMENTS
5. Each fact should be one line
6. Include specific numbers, percentages, dates wherever available
7. If something is uncertain, note it as "reportedly" or "allegedly"
8. IMPORTANT: Include counter-arguments that challenge the main narrative for balance

Format as:
## CURRENT EVENTS (What's happening NOW)
- Fact 1
- Fact 2...

## STATISTICS (Numbers and data)
- Fact 1...

## KEY FIGURES (People, organizations)
- Fact 1...

## COUNTER-ARGUMENTS (Opposing views, nuance)
- Fact 1...

## BRIEF HISTORY (Only if directly supports a claim)
- Fact 1..."""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI facts compilation error: {e}")
        return "Research compiled. AI processing failed."


def format_research_for_script(research: Dict) -> str:
    """Format research into a prompt-ready string for script generation.
    
    Now includes FULL ARTICLE CONTENT (scraped via Camoufox) for better source material.
    """
    output = f"""# Research: {research['topic']}
Country: {research.get('country', 'N/A')}
Date: {research['timestamp']}

## Raw Facts (AI-compiled summary)
{research.get('raw_facts', research.get('summary', 'No summary available'))}

## Recent News Articles ({len(research['recent_news'])} sources)
"""
    # Pass ALL fetched articles with more content
    for i, news in enumerate(research["recent_news"][:15]):  # Increased from 8
        date = news.get('date', '')
        title = news.get('title', 'No title')
        content = news.get('content', news.get('snippet', ''))
        
        # Include full content if available - increased limit
        if content and len(content) > 100:
            content_preview = content[:3500] + '...' if len(content) > 3500 else content  # Increased from 2000
            output += f"\n### [{i+1}] {title}\nDate: {date}\n{content_preview}\n"
        else:
            output += f"- [{date}] {title}\n"
    
    output += f"\n## Historical Context ({len(research['historical_context'])} sources)\n"
    for i, ctx in enumerate(research["historical_context"][:5]):
        title = ctx.get('title', 'No title')
        content = ctx.get('content', ctx.get('snippet', ''))
        
        if content and len(content) > 100:
            content_preview = content[:1500] + '...' if len(content) > 1500 else content
            output += f"\n### Historical: {title}\n{content_preview}\n"
        else:
            output += f"- {title}\n"
    
    output += f"\n## Statistics ({len(research['statistics'])} sources)\n"
    for stat in research["statistics"][:4]:
        snippet = stat.get('snippet', '')[:300]
        output += f"- {snippet}\n"
    
    output += f"\n## Expert Analysis ({len(research.get('expert_analysis', []))} sources)\n"
    for exp in research.get("expert_analysis", [])[:3]:
        title = exp.get('title', 'No title')
        content = exp.get('content', exp.get('snippet', ''))
        
        if content and len(content) > 100:
            content_preview = content[:1500] + '...' if len(content) > 1500 else content
            output += f"\n### Expert: {title}\n{content_preview}\n"
        else:
            output += f"- {title}\n"
    
    # Include counter-facts for balanced reporting
    counter_facts = research.get('counter_facts', [])
    if counter_facts:
        output += f"\n## Counter-Arguments & Opposing Views ({len(counter_facts)} sources)\n"
        for cf in counter_facts[:4]:
            title = cf.get('title', 'No title')
            content = cf.get('content', cf.get('snippet', ''))
            
            if content and len(content) > 100:
                content_preview = content[:1500] + '...' if len(content) > 1500 else content
                output += f"\n### Counter: {title}\n{content_preview}\n"
            else:
                output += f"- {title}\n"
    
    return output


if __name__ == "__main__":
    # Test
    print("Testing research agent...")
    research = deep_research("Germany energy crisis", "Germany")
    print(f"\nRaw Facts:\n{research['raw_facts'][:500]}...")
