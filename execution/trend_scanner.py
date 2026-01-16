"""
Trend Scanner v2 - Scan news for HIGH-POTENTIAL video topic opportunities.

Includes:
- Priority country searches (UK, US, France, Italy, Venezuela, Germany)
- Political and economic event searches
- Dramatic title generation matching reference video style
- 10 results instead of 5
"""

import os
import json
import requests
from typing import List, Dict, Optional
from datetime import datetime

# Load API key
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")

# Priority countries to always check
PRIORITY_COUNTRIES = [
    "united states", "usa", "america",
    "united kingdom", "uk", "britain",
    "france", "french",
    "italy", "italian",
    "germany", "german",
    "venezuela",
    "china", "chinese",
    "russia", "russian"
]

# Dramatic trigger words that indicate viral potential
TRIGGER_WORDS = [
    "crisis", "collapse", "collapsing", "failing", "failed", "bankrupt",
    "debt", "trillion", "billion", "sanctions", "war", "conflict",
    "shortage", "inflation", "hyperinflation", "protest", "unrest",
    "recession", "default", "dying", "death", "dead", "end of",
    "arrested", "coup", "regime", "overthrow", "invasion", "invaded",
    "tariff", "trade war", "embargo", "frozen", "seized", "crash",
    "bubble", "popping", "exodus", "fleeing", "escape", "brain drain"
]


def scan_trending_topics(category: str = "economics") -> List[Dict]:
    """
    Scan news for HIGH-POTENTIAL video opportunities.
    
    Returns 10 deduplicated topics with viral potential.
    """
    all_results = []
    
    # 1. Priority country-specific searches
    priority_queries = [
        # Major economies in crisis
        "France economy crisis OR collapse OR failing",
        "Italy economy crisis OR debt OR failing",
        "Germany economy recession OR crisis",
        "UK Britain economy crisis OR collapse",
        "United States economy recession OR crisis",
        "Venezuela Maduro economy OR crisis OR collapse",
        # Political drama
        "country leader arrested OR coup OR overthrow",
        "government collapse OR crisis",
        # Trade/sanctions
        "tariff trade war impact economy",
        "sanctions country economy impact",
    ]
    
    # 2. Category-specific searches
    category_queries = {
        "economics": [
            "economy collapsing country 2025",
            "debt crisis trillion country",
            "currency crisis country",
            "hyperinflation country",
        ],
        "geopolitics": [
            "country invasion threat",
            "sanctions impact country economy",
            "trade war escalation",
            "border conflict",
        ],
        "energy": [
            "energy crisis country",
            "oil price impact economy",
            "gas shortage impact",
        ]
    }
    
    selected_category = category_queries.get(category, category_queries["economics"])
    
    # Run priority searches first
    for query in priority_queries[:6]:  # Top 6 priority searches
        results = _search_news(query)
        all_results.extend(results)
    
    # Then category searches
    for query in selected_category[:2]:
        results = _search_news(query)
        all_results.extend(results)
    
    # Extract and rank topics
    topics = _extract_topics(all_results)
    
    # Return top 10
    return topics[:10]


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
    """Extract video topics with viral potential scoring."""
    topics = []
    seen_countries = set()
    seen_headlines = set()
    
    for item in news_items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        
        # Skip duplicate headlines
        title_key = title.lower()[:50]
        if title_key in seen_headlines:
            continue
        seen_headlines.add(title_key)
        
        combined = f"{title} {snippet}".lower()
        
        # Calculate viral score
        viral_score = _calculate_viral_score(combined)
        
        if viral_score > 0:
            country = _extract_country(combined)
            
            # Only one topic per country (highest scored)
            if country and country in seen_countries:
                continue
            if country:
                seen_countries.add(country)
            
            # Generate dramatic title
            suggested_title = _generate_dramatic_title(title, country, combined)
            
            topics.append({
                "headline": title,
                "snippet": snippet[:200],
                "source_url": link,
                "country": country,
                "suggested_topic": suggested_title,
                "category": _categorize_news(combined),
                "viral_score": viral_score
            })
    
    # Sort by viral score
    topics.sort(key=lambda x: x["viral_score"], reverse=True)
    return topics


def _calculate_viral_score(text: str) -> int:
    """Calculate how viral this topic could be."""
    score = 0
    text_lower = text.lower()
    
    # Trigger words (+2 each)
    for word in TRIGGER_WORDS:
        if word in text_lower:
            score += 2
    
    # Priority country bonus (+5)
    for country in PRIORITY_COUNTRIES:
        if country in text_lower:
            score += 5
            break
    
    # Numbers are engaging (+1)
    if any(char.isdigit() for char in text):
        score += 1
    
    # Dramatic words (+3)
    drama_words = ["impossible", "shocking", "secret", "hidden", "truth", "real", "actually"]
    for word in drama_words:
        if word in text_lower:
            score += 3
    
    return score


def _generate_dramatic_title(headline: str, country: Optional[str], text: str) -> str:
    """
    Generate a dramatic title matching reference video style.
    
    Reference formulas from title_style.md:
    1. Why [X] is [NEGATIVE STATE] (The [Hook])
    2. How [X] [DRAMATIC VERB] (And/The [Consequence])
    3. The [DRAMATIC NOUN] of [Subject]
    4. [X]'s $[N] Billion Mistake (The [Hook])
    """
    import random
    text_lower = text.lower()
    
    # Extract dollar amounts if present
    import re
    money_match = re.search(r'\$?([\d.]+)\s*(billion|trillion|million)', text_lower)
    money_amount = None
    if money_match:
        money_amount = f"${money_match.group(1)} {money_match.group(2).title()}"
    
    # FORMULA 1: Why [Country] is POORER Than You Think
    # Use for: economic decline, poverty, falling standards
    if any(w in text_lower for w in ["poverty", "poor", "poorer", "declining", "falling", "shrinking"]):
        if country:
            hooks = ["The Economic Truth", "The Hidden Crisis", "No One Talks About This"]
            return f"Why {country} is POORER Than You Think ({random.choice(hooks)})"
    
    # FORMULA 2: Why [Country] Can't Grow (The Curse of X)
    # Use for: structural problems, stagnation
    if any(w in text_lower for w in ["stagnant", "growth", "gdp", "can't grow", "no growth"]):
        if country:
            curses = ["The Demographic Trap", "The Debt Spiral", "The Structural Crisis"]
            return f"Why {country} Can't Grow ({random.choice(curses)})"
    
    # FORMULA 3: The Slow DEATH of [X] (And What Comes Next)
    # Use for: collapse, dying industries, end of era
    if any(w in text_lower for w in ["dying", "death", "end of", "collapse", "collapsing", "obsolete"]):
        if country:
            return f"The Slow DEATH of {country}'s Economy (And What Comes Next)"
        else:
            # Extract subject from headline
            return f"The Slow DEATH of {_extract_subject(headline)} (And What Comes Next)"
    
    # FORMULA 4: [Country]'s $X Billion Mistake (The [Trap])
    # Use for: policy failures with numbers
    if money_amount and country:
        traps = ["The Green Energy Trap", "The Trade Trap", "The Debt Trap", "The Policy Trap"]
        return f"{country}'s {money_amount} Mistake ({random.choice(traps)})"
    
    # FORMULA 5: Why Invading [Country] is IMPOSSIBLE
    # Use for: military, invasion, defense
    if any(w in text_lower for w in ["invasion", "invade", "military", "defense", "army"]):
        if country:
            return f"Why Invading {country} is IMPOSSIBLE (It's Not the Army)"
    
    # FORMULA 6: The [Country] Economy That [VERB] [Leader]
    # Use for: political consequences of economy
    if any(w in text_lower for w in ["arrested", "coup", "overthrow", "resign", "ousted", "verdict"]):
        if country:
            leaders = _extract_leader(text)
            if leaders:
                return f"The {country} Economy That Nailed {leaders} (The Verdict)"
            return f"The {country} Economy That DESTROYED Its Leaders (The Verdict)"
    
    # FORMULA 7: Why [Country]'s [X] is Worse Than You Think
    # Use for: trade wars, sanctions, tariffs
    if any(w in text_lower for w in ["tariff", "sanction", "trade war", "embargo"]):
        if country:
            return f"Why {country}'s Trade War is Worse Than You Think (The Hidden Cost)"
        return "The Trade War That Will DEVASTATE Everyone (It's Already Happening)"
    
    # FORMULA 8: How [Subject] SWALLOWED [Country]'s Economy
    # Use for: housing, debt, single industry dominance
    if any(w in text_lower for w in ["housing", "real estate", "property", "bubble"]):
        if country:
            return f"How Housing SWALLOWED {country}'s Economy (The Real Estate Trap)"
    
    # FORMULA 9: Why Europe's/[Region]'s Economy is Collapsing (The N Fatal Wounds)
    # Use for: multiple crises
    if any(w in text_lower for w in ["crisis", "crises", "multiple", "wounds"]):
        if country:
            return f"Why {country}'s Economy is COLLAPSING (The 5 Fatal Wounds)"
    
    # FORMULA 10: Budget/Debt specific
    if any(w in text_lower for w in ["budget", "debt", "deficit", "trillion", "billion"]):
        if country:
            return f"Why {country}'s Debt Crisis is UNFIXABLE (The Hidden Numbers)"
    
    # DEFAULT: Why [Country] is in SERIOUS Trouble (The [Category] Crisis)
    if country:
        category = _categorize_news(text_lower)
        crisis_types = {
            "economics": "The Economic Crisis",
            "energy": "The Energy Crisis", 
            "geopolitics": "The Geopolitical Crisis",
            "political": "The Political Crisis",
            "general": "The Hidden Crisis"
        }
        hook = crisis_types.get(category, "The Hidden Crisis")
        return f"Why {country} is in SERIOUS Trouble ({hook})"
    
    # Fallback for no country detected
    return headline[:60]


def _extract_subject(headline: str) -> str:
    """Extract main subject from headline for 'The DEATH of X' format."""
    # Common subjects to extract
    subjects = ["petrodollar", "dollar", "euro", "growth", "trade", "industry"]
    headline_lower = headline.lower()
    for s in subjects:
        if s in headline_lower:
            return f"The {s.title()}"
    return headline.split()[0:3] if len(headline.split()) > 3 else headline


def _extract_leader(text: str) -> Optional[str]:
    """Extract leader names from text."""
    leaders = {
        "maduro": "Maduro",
        "putin": "Putin",
        "macron": "Macron",
        "scholz": "Scholz",
        "trump": "Trump",
        "biden": "Biden",
        "xi": "Xi",
        "modi": "Modi",
        "sunak": "Sunak",
        "meloni": "Meloni"
    }
    text_lower = text.lower()
    for key, name in leaders.items():
        if key in text_lower:
            return name
    return None


def _extract_country(text: str) -> Optional[str]:
    """Extract country name from text."""
    country_map = {
        "germany": "Germany", "german": "Germany",
        "france": "France", "french": "France", 
        "italy": "Italy", "italian": "Italy",
        "spain": "Spain", "spanish": "Spain",
        "uk": "UK", "britain": "UK", "british": "UK", "united kingdom": "UK",
        "usa": "USA", "america": "USA", "united states": "USA", "american": "USA",
        "china": "China", "chinese": "China",
        "russia": "Russia", "russian": "Russia",
        "japan": "Japan", "japanese": "Japan",
        "india": "India", "indian": "India",
        "brazil": "Brazil", "brazilian": "Brazil",
        "mexico": "Mexico", "mexican": "Mexico",
        "canada": "Canada", "canadian": "Canada",
        "australia": "Australia", "australian": "Australia",
        "turkey": "Turkey", "turkish": "Turkey",
        "argentina": "Argentina",
        "venezuela": "Venezuela", "venezuelan": "Venezuela",
        "ukraine": "Ukraine", "ukrainian": "Ukraine",
        "poland": "Poland", "polish": "Poland",
        "greece": "Greece", "greek": "Greece",
        "portugal": "Portugal",
        "sweden": "Sweden",
        "norway": "Norway",
        "denmark": "Denmark",
        "finland": "Finland",
        "austria": "Austria",
        "switzerland": "Switzerland",
        "south korea": "South Korea", "korean": "South Korea",
        "taiwan": "Taiwan",
        "indonesia": "Indonesia",
        "vietnam": "Vietnam",
        "thailand": "Thailand",
        "philippines": "Philippines",
        "pakistan": "Pakistan",
        "iran": "Iran", "iranian": "Iran",
        "iraq": "Iraq",
        "saudi arabia": "Saudi Arabia",
        "israel": "Israel", "israeli": "Israel",
        "egypt": "Egypt", "egyptian": "Egypt",
        "nigeria": "Nigeria",
        "south africa": "South Africa",
        "kenya": "Kenya",
        "ethiopia": "Ethiopia",
        "sudan": "Sudan",
        "lebanon": "Lebanon",
        "greenland": "Greenland",
    }
    
    text_lower = text.lower()
    for key, value in country_map.items():
        if key in text_lower:
            return value
    return None


def _categorize_news(text: str) -> str:
    """Categorize news item."""
    text_lower = text.lower()
    
    if any(w in text_lower for w in ["oil", "gas", "energy", "power", "electricity"]):
        return "energy"
    if any(w in text_lower for w in ["war", "military", "sanction", "conflict", "invasion"]):
        return "geopolitics"
    if any(w in text_lower for w in ["debt", "inflation", "currency", "economy", "gdp", "recession"]):
        return "economics"
    if any(w in text_lower for w in ["arrested", "coup", "election", "protest"]):
        return "political"
    return "general"


def get_evergreen_topics() -> List[Dict]:
    """
    Return evergreen topic suggestions matching reference video style.
    """
    return [
        {
            "suggested_topic": "Why [Country] Can't Grow (The Curse of X)",
            "category": "economics",
            "description": "Deep dive into structural economic failure"
        },
        {
            "suggested_topic": "Why [Country] is POORER Than You Think",
            "category": "economics",
            "description": "Expose hidden economic decline"
        },
        {
            "suggested_topic": "The Slow DEATH of [System/Currency]",
            "category": "economics", 
            "description": "End of an era analysis"
        },
        {
            "suggested_topic": "Why Invading [Country] is IMPOSSIBLE",
            "category": "geopolitics",
            "description": "Geographic/strategic analysis"
        },
        {
            "suggested_topic": "Why [Country] Wants to BUY [Territory]",
            "category": "geopolitics",
            "description": "Geopolitical resource grab analysis"
        },
        {
            "suggested_topic": "How [Country] REALLY Became Rich",
            "category": "economics",
            "description": "Hidden origin story of economic success"
        },
        {
            "suggested_topic": "Why [Country]'s Economy is Collapsing (The 6 Fatal Wounds)",
            "category": "economics",
            "description": "Numbered list deep-dive format"
        },
        {
            "suggested_topic": "The [Country] Economy That DESTROYED [Leader]",
            "category": "political",
            "description": "How economics toppled a regime"
        }
    ]


if __name__ == "__main__":
    # Test
    print("Scanning trending topics (v2)...")
    print("=" * 60)
    topics = scan_trending_topics("economics")
    
    for i, t in enumerate(topics, 1):
        print(f"\n{i}. {t['suggested_topic']}")
        print(f"   └ {t['headline'][:60]}...")
        print(f"   Country: {t.get('country', 'N/A')} | Score: {t.get('viral_score', 0)}")
    
    print(f"\n{'=' * 60}")
    print(f"Found {len(topics)} topics")
