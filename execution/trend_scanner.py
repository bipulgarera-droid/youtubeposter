"""
Trend Scanner - Scan news for video topic opportunities.

Uses Serper API to find trending geopolitical/economic stories.
"""

import os
import json
import requests
from typing import List, Dict, Optional
from datetime import datetime

# Load API key
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")


def scan_trending_topics(category: str = "economics") -> List[Dict]:
    """
    Scan news for trending video opportunities.
    
    Categories:
    - economics: Country economic crises, currency issues
    - geopolitics: Wars, sanctions, trade conflicts
    - energy: Oil, gas, renewable energy news
    - general: Mixed trending stories
    
    Returns list of topic suggestions with headlines.
    """
    # Define search queries per category
    queries = {
        "economics": [
            "country economic crisis 2024",
            "economy collapsing news",
            "currency crisis country",
            "debt crisis europe asia",
        ],
        "geopolitics": [
            "country sanctions news",
            "border conflict world news",
            "trade war countries 2024",
            "geopolitical tension rising",
        ],
        "energy": [
            "energy crisis country 2024",
            "oil price impact economy",
            "renewable energy failure success",
            "gas shortage europe asia",
        ],
        "general": [
            "country crisis news today",
            "economic collapse warning",
            "political instability country",
        ]
    }
    
    selected_queries = queries.get(category, queries["general"])
    all_results = []
    
    for query in selected_queries[:2]:  # Limit API calls
        results = _search_news(query)
        all_results.extend(results)
    
    # Deduplicate and rank
    topics = _extract_topics(all_results)
    return topics[:5]  # Return top 5


def _search_news(query: str) -> List[Dict]:
    """Search news using Serper API."""
    if not SERPER_API_KEY:
        print("Warning: SERPER_API_KEY not set")
        return []
    
    url = "https://google.serper.dev/news"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "gl": "us",
        "hl": "en",
        "num": 10,
        "tbs": "qdr:w"  # Last week
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("news", [])
    except Exception as e:
        print(f"Serper search error: {e}")
        return []


def _extract_topics(news_items: List[Dict]) -> List[Dict]:
    """Extract video topics from news items."""
    topics = []
    seen_countries = set()
    
    # Keywords that indicate good video topics
    trigger_words = [
        "crisis", "collapse", "failing", "bankrupt", "debt", 
        "sanctions", "war", "conflict", "shortage", "inflation",
        "protest", "unrest", "recession", "default", "dying"
    ]
    
    for item in news_items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        
        # Check for trigger words
        combined = f"{title} {snippet}".lower()
        has_trigger = any(word in combined for word in trigger_words)
        
        if has_trigger:
            # Extract country if mentioned
            country = _extract_country(combined)
            
            # Avoid duplicates per country
            if country and country in seen_countries:
                continue
            if country:
                seen_countries.add(country)
            
            topics.append({
                "headline": title,
                "snippet": snippet[:200],
                "source_url": link,
                "country": country,
                "suggested_topic": _generate_topic_suggestion(title, country),
                "category": _categorize_news(combined)
            })
    
    return topics


def _extract_country(text: str) -> Optional[str]:
    """Extract country name from text."""
    countries = [
        "germany", "france", "italy", "spain", "uk", "britain", 
        "usa", "america", "united states", "china", "russia",
        "japan", "india", "brazil", "mexico", "canada", "australia",
        "turkey", "argentina", "venezuela", "ukraine", "poland",
        "netherlands", "belgium", "greece", "portugal", "sweden",
        "norway", "denmark", "finland", "austria", "switzerland",
        "south korea", "north korea", "taiwan", "indonesia", "vietnam",
        "thailand", "philippines", "malaysia", "singapore", "pakistan",
        "iran", "iraq", "saudi arabia", "israel", "egypt", "nigeria",
        "south africa", "kenya", "ethiopia", "colombia", "chile", "peru"
    ]
    
    text_lower = text.lower()
    for country in countries:
        if country in text_lower:
            return country.title()
    return None


def _categorize_news(text: str) -> str:
    """Categorize news item."""
    text_lower = text.lower()
    
    if any(w in text_lower for w in ["oil", "gas", "energy", "power", "electricity"]):
        return "energy"
    if any(w in text_lower for w in ["war", "military", "sanction", "conflict"]):
        return "geopolitics"
    if any(w in text_lower for w in ["debt", "inflation", "currency", "economy", "gdp"]):
        return "economics"
    return "general"


def _generate_topic_suggestion(headline: str, country: Optional[str]) -> str:
    """Generate a video topic suggestion from headline."""
    if country:
        return f"Why {country}'s Economy is in Trouble"
    
    # Fallback: clean headline
    return headline[:60]


def get_evergreen_topics() -> List[Dict]:
    """
    Return evergreen topic suggestions (not news-dependent).
    """
    return [
        {
            "suggested_topic": "Why X Country Can't Grow",
            "category": "economics",
            "description": "Deep dive into structural economic problems"
        },
        {
            "suggested_topic": "The Hidden Crisis of Y",
            "category": "economics",
            "description": "Expose an underreported economic issue"
        },
        {
            "suggested_topic": "How Z Became Rich/Poor",
            "category": "economics", 
            "description": "Origin story of economic success/failure"
        },
        {
            "suggested_topic": "Why Invading X is Impossible",
            "category": "geopolitics",
            "description": "Geographic/strategic analysis"
        },
        {
            "suggested_topic": "The Death of Y Currency/System",
            "category": "economics",
            "description": "End of an era analysis"
        }
    ]


if __name__ == "__main__":
    # Test
    print("Scanning trending topics...")
    topics = scan_trending_topics("economics")
    for t in topics:
        print(f"\n- {t['suggested_topic']}")
        print(f"  Headline: {t['headline']}")
        print(f"  Country: {t.get('country', 'N/A')}")
