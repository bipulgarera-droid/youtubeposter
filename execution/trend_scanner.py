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
        print("❌ SERPER_API_KEY not set")
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
        data = response.json()
        
        # Check for credit error
        if data.get("message") == "Not enough credits" or data.get("statusCode") == 400:
            print(f"❌ Serper API: No credits remaining")
            return []
        
        response.raise_for_status()
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


def scan_by_country(country: str) -> List[Dict]:
    """
    Scan news for topics specific to a country.
    
    Args:
        country: Country name (e.g., "Venezuela", "France", "UK")
    
    Returns:
        List of 10 topic opportunities for that country
    """
    all_results = []
    
    # Country-specific queries - more varied for better results
    queries = [
        f"{country} economy crisis OR collapse 2025",
        f"{country} economy latest news today",
        f"{country} financial crisis OR debt OR deficit",
        f"{country} government economic policy reform",
        f"{country} currency crisis OR inflation OR recession",
        f"{country} trade sanctions tariff",
    ]
    
    for query in queries:
        results = _search_news(query)
        all_results.extend(results)
    
    # Process results with country override
    topics = []
    seen_headlines = set()
    
    for item in all_results:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        
        # Skip duplicates
        title_key = title.lower()[:50]
        if title_key in seen_headlines:
            continue
        seen_headlines.add(title_key)
        
        combined = f"{title} {snippet}".lower()
        viral_score = _calculate_viral_score(combined)
        
        # Force the country for these results
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
    
    # Sort by viral score and limit to 10
    topics.sort(key=lambda x: x["viral_score"], reverse=True)
    return topics[:10]


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
    Generate title matching EXACT patterns from reference videos.
    
    MASTER PATTERNS (56 reference titles analyzed):
    
    1. "The REAL TRUTH About X's Economy (The Y)" - Lebanon, Argentina, Mexico
    2. "How X Got RICH (The Y)" / "How X Became INSANELY Rich (With No Z)"
    3. "Why X Can't Grow (The Curse of Y)" - Italy
    4. "The Slow DEATH of X (And What Comes Next)" - Petrodollar, Globalization
    5. "X's $N Billion/Trillion PROBLEM/Mistake (The Y Trap)"
    6. "How X SWALLOWED Y's Economy (The Z Trap)"
    7. "The X Economy That Nailed Y (The Verdict)"
    8. "Why X is UNREFORMABLE/Is Broken (The Y Trap)"
    9. "Nothing About X Is Normal (Here's Why)"
    10. "The END of X (The Y)"
    11. "Why X is LOSING/WINNING Y (While Z)"
    12. "The X Economic DISASTER/MIRACLE (Why Y)"
    13. "Why X is POORER Than You Think (The Economic Truth)"
    14. "Is X Rigged to Collapse? (The N Fatal Flaws)"
    15. "How to Bankrupt a Country in N Steps (The X Story)"
    16. "Why X Can't Quit Y (The Z Curse)"
    """
    import random
    import re
    text_lower = text.lower()
    
    # Extract dollar/trillion amounts
    money_match = re.search(r'\$?([\d.,]+)\s*(billion|trillion|million)', text_lower)
    money_str = None
    if money_match:
        num = money_match.group(1).replace(',', '')
        money_str = f"${num} {money_match.group(2).title()}"
    
    # =================================================
    # PATTERN 1: The REAL TRUTH About X's Economy (The Y)
    # =================================================
    if any(w in text_lower for w in ["truth", "reality", "real", "actually", "really"]):
        if country:
            hooks = [
                "The Greatest Ponzi Scheme",
                "The World's Greatest Financial Laboratory",
                "Boom or Bust?",
                "The Hidden Truth"
            ]
            return f"The REAL TRUTH About {country}'s Economy ({random.choice(hooks)})"
    
    # =================================================
    # PATTERN 2: How X Got RICH / Became INSANELY Rich
    # Use ONLY for genuinely positive success stories
    # Check for negative context first to avoid false positives
    # =================================================
    negative_words = ["crisis", "collapse", "failing", "decline", "headwind", "recession", "threat", "disaster", "dying", "death", "broken"]
    has_negative = any(w in text_lower for w in negative_words)
    
    if not has_negative and any(w in text_lower for w in ["rich", "wealthy", "prosperity", "boom", "miracle", "success"]):
        if country:
            hooks = [
                "And Why They Don't Spend It",
                "With No Resources",
                "It Wasn't Just Oil",
                "The Masterclass in Resource Control",
                "The Real Reason"
            ]
            return f"How {country} Actually Got RICH ({random.choice(hooks)})"
    
    # =================================================
    # PATTERN 3: Why X Can't Grow (The Curse of Y)
    # =================================================
    if any(w in text_lower for w in ["stagnant", "can't grow", "declining", "shrinking", "demographic"]):
        if country:
            curses = [
                "The Curse of The Lira",
                "The Demographic Trap",
                "The Structural Crisis",
                "The Union Trap"
            ]
            return f"Why {country} Can't Grow ({random.choice(curses)})"
    
    # =================================================
    # PATTERN 4: The Slow DEATH of X (And What Comes Next)
    # =================================================
    if any(w in text_lower for w in ["death", "dying", "collapse", "end of", "dead"]):
        subjects = {
            "petrodollar": "The Petrodollar",
            "dollar": "The Dollar",
            "globalization": "Globalization",
            "home ownership": "Home Ownership",
            "growth": "Economic Growth"
        }
        for key, val in subjects.items():
            if key in text_lower:
                return f"The Slow DEATH of {val} (And What Comes Next)"
        if country:
            return f"The Slow DEATH of {country}'s Economy (And What Comes Next)"
    
    # =================================================
    # PATTERN 5: X's $N Billion Mistake/PROBLEM (The Y Trap)
    # =================================================
    if money_str and country:
        hooks = [
            "The Green Energy Trap",
            "The End of an Era",
            "The Trade Trap",
            "The Policy Trap"
        ]
        return f"{country}'s {money_str} Mistake ({random.choice(hooks)})"
    
    # =================================================
    # PATTERN 6: How X SWALLOWED Y's Economy (The Z Trap)
    # =================================================
    if any(w in text_lower for w in ["housing", "real estate", "property", "bubble"]):
        if country:
            return f"How Housing SWALLOWED {country}'s Economy (The Real Estate Trap)"
    
    # =================================================
    # PATTERN 7: The X Economy That Nailed Y (The Verdict)
    # =================================================
    leader = _extract_leader(text)
    if any(w in text_lower for w in ["arrested", "ousted", "verdict", "coup", "overthrow"]):
        if country and leader:
            return f"The {country} Economy That Nailed {leader} (The Verdict)"
        elif country:
            return f"The {country} Economy That DESTROYED Its Leaders (The Verdict)"
    
    # =================================================
    # PATTERN 8: Why X is UNREFORMABLE/Is Broken (The Y)
    # =================================================
    if any(w in text_lower for w in ["broken", "unreformable", "unfixable", "can't be fixed"]):
        if country:
            hooks = [
                "The Union Trap",
                "The End of Empire",
                "The Structural Crisis"
            ]
            return f"Why {country}'s Economy Is Broken ({random.choice(hooks)})"
    
    # =================================================
    # PATTERN 9: Nothing About X Is Normal (Here's Why)
    # =================================================
    if any(w in text_lower for w in ["vanguard", "blackrock", "fed", "central bank"]):
        subjects = ["Vanguard", "BlackRock", "The Fed", "Central Banks"]
        for s in subjects:
            if s.lower() in text_lower:
                return f"Nothing About {s} Is Normal (Here's Why)"
    
    # =================================================
    # PATTERN 10: The END of X (The Y)
    # =================================================
    if any(w in text_lower for w in ["end of", "ending", "finished"]):
        hooks = [
            "The Population Collapse",
            "The New Rules Analysis",
            "And What Comes Next"
        ]
        if country:
            return f"The END of {country}'s Economic Growth ({random.choice(hooks)})"
    
    # =================================================
    # PATTERN 11: Why X is WINNING While Y is LOSING
    # =================================================
    if any(w in text_lower for w in ["winning", "losing", "versus", "vs", "beating"]):
        if country:
            return f"Why {country} Is Winning While Others Fail (The Hidden Advantage)"
    
    # =================================================
    # PATTERN 12: The X Economic DISASTER/MIRACLE (Why Y)
    # =================================================
    if any(w in text_lower for w in ["disaster", "catastrophe", "failure"]):
        if country:
            return f"The {country} Economic DISASTER Explained (Why It Never Ends)"
    if any(w in text_lower for w in ["miracle", "success", "boom"]):
        if country:
            return f"The {country} Economic MIRACLE (How They Beat The West)"
    
    # =================================================
    # PATTERN 13: Why X is POORER Than You Think
    # =================================================
    if any(w in text_lower for w in ["poor", "poverty", "poorer", "broke"]):
        if country:
            return f"Why {country} is POORER Than You Think (The Economic Truth)"
    
    # =================================================
    # PATTERN 14: Is X Rigged to Collapse?
    # =================================================
    if any(w in text_lower for w in ["rigged", "manipulated", "rigging"]):
        if country:
            return f"Is {country}'s Economy Rigged to Collapse? (The 5 Fatal Flaws)"
    
    # =================================================
    # PATTERN 15: Debt/Budget specific
    # =================================================
    if any(w in text_lower for w in ["debt", "budget", "deficit", "trillion"]):
        if country:
            hooks = [
                "The Hidden Numbers",
                "The 5 Fatal Flaws",
                "And What Comes Next"
            ]
            return f"Why {country}'s Debt Crisis is UNFIXABLE ({random.choice(hooks)})"
    
    # =================================================
    # PATTERN 16: Crisis/Collapse
    # =================================================
    if any(w in text_lower for w in ["crisis", "collapse", "collapsing"]):
        if country:
            return f"Why {country}'s Economy is COLLAPSING (The 5 Fatal Wounds)"
    
    # =================================================
    # PATTERN 17: Engineer/Industry obsolete
    # =================================================
    if any(w in text_lower for w in ["obsolete", "engineers", "industry"]):
        if country:
            return f"Why {country}'s Engineers Are Obsolete (The Hidden Crisis)"
    
    # =================================================
    # PATTERN 18: Invasion (ONLY for major powers!)
    # =================================================
    if any(w in text_lower for w in ["invasion", "invade", "invading"]):
        if country and country in ["USA", "United States", "Russia", "China"]:
            return f"Why Invading {country} is IMPOSSIBLE (It's Not the Army)"
    
    # =================================================
    # DEFAULT: The REAL TRUTH About X's Economy
    # =================================================
    if country:
        hooks = [
            "The Hidden Crisis",
            "The Economic Truth",
            "Here's Why",
            "The 5 Fatal Flaws"
        ]
        return f"The REAL TRUTH About {country}'s Economy ({random.choice(hooks)})"
    
    # Fallback
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
