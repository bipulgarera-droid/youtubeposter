#!/usr/bin/env python3
"""
Enhanced News Article Research Script
Uses AI to analyze transcript and generate comprehensive search queries.
Searches multiple sources: news, Twitter, general web.
Filters for recency.
"""

import os
import json
import argparse
import requests
from typing import Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

SERPER_API_KEY = os.getenv('SERPER_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')


def extract_search_queries_with_ai(transcript: str, channel_focus: str = "") -> list:
    """
    Use Gemini to analyze transcript and extract key search queries.
    Returns a list of diverse, targeted search queries.
    If channel_focus is provided, adds 3 extra queries prioritizing that angle.
    """
    if not GEMINI_API_KEY:
        print("No Gemini API key, falling back to basic extraction")
        return extract_basic_queries(transcript)
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    # Add channel focus instructions if provided
    channel_focus_instruction = ""
    if channel_focus:
        channel_focus_instruction = f"""
CHANNEL FOCUS: {channel_focus}
IMPORTANT: Include 3 EXTRA queries (total 13) that specifically search for:
- {channel_focus} implications of this topic
- {channel_focus} analysis or expert opinions
- {channel_focus} data, statistics, or market impact
These focused queries should be PRIORITIZED and returned FIRST in your list.
"""
    
    prompt = f"""Analyze this video transcript and generate search queries to find supporting news articles and sources.
    
TRANSCRIPT EXCERPT:
{transcript[:4000]}
{channel_focus_instruction}
NOTE: The transcript might contain unverified names, specific dates, or narrative elements that are fictional or heavily exaggerated.
DO NOT assume names like "Dr. Chen Wei" or specific dates are real unless verifyable.

Generate TWO TYPES of queries:
1. SPECIFIC QUERIES (5 queries): Search for specific claims/names IF they seem credible.
2. BROAD VERIFICATION QUERIES (5 queries): Search for the general event/theme WITHOUT specific names/dates to verify if the event actually happened.
   - Example: Instead of "Dr. Chen Wei January 3 statement", search for "China Venezuela official statement January 2025"
   - Example: Instead of "Great Bypass initiative", search for "China new financial system for sanctions evasion"

Goal: Find REAL news articles with EMPIRICAL DATA and FACTS that confirm or debunk the transcript's narrative.

Return ONLY a JSON array of {13 if channel_focus else 10} search query strings."""
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Parse JSON from response
        if text.startswith('['):
            queries = json.loads(text)
        else:
            # Try to find JSON array in response
            import re
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                queries = json.loads(match.group())
            else:
                queries = extract_basic_queries(transcript)
        
        # Handle structured output where AI returns [{query_type: X, queries: [...]}]
        if queries and isinstance(queries[0], dict):
            flattened = []
            for item in queries:
                if isinstance(item, dict) and 'queries' in item:
                    # It's a structured object like {query_type: 'SPECIFIC', queries: [...]}
                    flattened.extend(item['queries'])
                elif isinstance(item, str):
                    flattened.append(item)
            queries = flattened
        
        # Ensure all items are strings (not dicts or other types)
        queries = [q for q in queries if isinstance(q, str)]
        
        if not queries:
            print("⚠️ AI returned no valid string queries, falling back")
            queries = extract_basic_queries(transcript)
        
        print(f"AI generated {len(queries)} search queries")
        return queries
        
    except Exception as e:
        print(f"AI query generation failed: {e}")
        return extract_basic_queries(transcript)


def extract_basic_queries(transcript: str) -> list:
    """Fallback: extract basic queries from transcript."""
    # Take key phrases from first part of transcript
    words = transcript.split()[:100]
    topic = ' '.join(words[:15])
    
    return [
        topic,
        f"{topic} latest news",
        f"{topic} analysis",
        "Venezuela China relations latest",
        "US Venezuela sanctions update"
    ]


def search_serper_news(query: str, num_results: int = 10) -> list:
    """Search for news articles using Serper."""
    if not SERPER_API_KEY:
        raise ValueError("SERPER_API_KEY not found in .env file")
    
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    payload = {
        'q': query,
        'num': num_results,
        'type': 'news',
        'tbs': 'qdr:m'  # Last month (more lenient than last 24h which was qdr:d)
    }
    
    try:
        response = requests.post("https://google.serper.dev/news", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        articles = []
        for item in data.get('news', []):
            articles.append({
                'url': item.get('link', ''),
                'title': item.get('title', ''),
                'snippet': item.get('snippet', ''),
                'source': item.get('source', ''),
                'date': item.get('date', ''),
                'type': 'news'
            })
        return articles
    except Exception as e:
        print(f"News search failed: {e}")
        return []


def search_serper_general(query: str, num_results: int = 10, time_range: str = None) -> list:
    """Search general web results."""
    if not SERPER_API_KEY:
        return []
    
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    payload = {
        'q': query,
        'num': num_results
    }
    
    if time_range:
        payload['tbs'] = time_range
    
    try:
        response = requests.post("https://google.serper.dev/search", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        articles = []
        for item in data.get('organic', []):
            articles.append({
                'url': item.get('link', ''),
                'title': item.get('title', ''),
                'snippet': item.get('snippet', ''),
                'source': extract_domain(item.get('link', '')),
                'date': '',
                'type': 'web'
            })
        return articles
    except Exception as e:
        print(f"General search failed: {e}")
        return []


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')
    except:
        return ''


def deduplicate_articles(articles: list) -> list:
    """Remove duplicate articles based on URL."""
    seen_urls = set()
    unique = []
    
    for article in articles:
        url = article['url']
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(article)
    
    return unique


# Domains to exclude from research (not credible news sources)
EXCLUDED_DOMAINS = [
    'youtube.com', 'youtu.be',           # Video platforms
    'tiktok.com',                         # Video platforms
    'facebook.com', 'fb.com',             # Social media
    'instagram.com',                      # Social media
    'twitter.com', 'x.com',               # Social media (already removed, but safety)
    'reddit.com',                         # Social media
    'pinterest.com',                      # Social media
    'linkedin.com',                       # Social media
    'quora.com',                          # Q&A site
    'medium.com',                         # Blog platform (not news)
    'wikipedia.org',                      # Encyclopedia (not news)
    'amazon.com', 'ebay.com',             # E-commerce
]


def filter_invalid_sources(articles: list) -> list:
    """Remove non-credible sources like YouTube, social media, etc."""
    valid = []
    removed_count = 0
    
    for article in articles:
        url = article.get('url', '').lower()
        is_excluded = any(domain in url for domain in EXCLUDED_DOMAINS)
        
        if is_excluded:
            removed_count += 1
        else:
            valid.append(article)
    
    if removed_count > 0:
        print(f"      🚫 Filtered out {removed_count} non-news sources (YouTube, social media, etc.)")
    
    return valid

def search_news(topic: str, num_articles: int = 30, transcript: Optional[str] = None, channel_focus: str = "", days_limit: int = 7) -> dict:
    """
    Main function to search for news articles.
    Uses AI to analyze transcript and generate targeted queries.
    Searches news and general web (Twitter disabled).
    If channel_focus is provided, generates extra queries for that angle.
    days_limit: Number of days to look back (default 7). uses qdr:d{N} or qdr:w format.
    """
    try:
        print("="*50)
        print("ENHANCED NEWS RESEARCH")
        if channel_focus:
            print(f"📊 CHANNEL FOCUS: {channel_focus}")
        print(f"🕒 TIME LIMIT: Past {days_limit} days")
        print("="*50)
        
        # Generate AI-powered search queries from transcript
        # Reverted to 4,000 chars as requested (sufficient for keywords)
        if transcript:
            queries = extract_search_queries_with_ai(transcript[:4000], channel_focus=channel_focus)
        else:
            queries = [topic, f"{topic} news", f"{topic} latest"]
            if channel_focus:
                queries.extend([f"{topic} {channel_focus}", f"{topic} {channel_focus} analysis"])
        
        all_articles = []
        
        # Determine time range string
        if days_limit <= 1:
            time_range = 'qdr:d'  # Last 24h
        elif days_limit <= 7:
            time_range = f'qdr:d{days_limit}'  # Last N days (e.g. qdr:d3)
        elif days_limit <= 30:
            time_range = 'qdr:m'  # Last month
        else:
            time_range = 'qdr:y'  # Last year
            
        # Unified Search Strategy:
        # All queries run against General Web Search with date filter.
        print(f"\n🌐 Searching sources ({time_range})...")
        
        for i, query in enumerate(queries):  
            print(f"  [{i+1}] {query}")
            results = search_serper_general(query, num_results=10, time_range=time_range)
            all_articles.extend(results)
            print(f"      → Found {len(results)} results")
        
        # Fallback if specific searches completely failed
        if len(all_articles) < 5:
            print("\n⚠️ Low results found. Running broad fallback search...")
            fallback_query = topic
            print(f"  Fallback: {fallback_query}")
            results = search_serper_general(fallback_query, num_results=20, time_range='qdr:w')
            all_articles.extend(results)
            print(f"      → Found {len(results)} results")
            
        # Deduplicate
        unique_articles = deduplicate_articles(all_articles)
        print(f"\n📊 Total unique candidates: {len(unique_articles)}")
        
        # Filter out non-news sources (YouTube, social media, etc.)
        filtered_articles = filter_invalid_sources(unique_articles)
        print(f"📊 After filtering: {len(filtered_articles)} credible sources")
        
        # Rank by relevance using AI
        print("🤖 AI Ranking (finding the most specific matches)...")
        ranked_articles = rank_articles_with_ai(filtered_articles, transcript or topic)
        
        # Limit to requested number (User requested ~25)
        # If no ranking happened (fallback), request might use raw list
        final_articles = ranked_articles[:num_articles]
        
        # Count by type
        news_count = len([a for a in final_articles if a['type'] == 'news'])
        web_count = len([a for a in final_articles if a['type'] == 'web'])
        
        return {
            'success': True,
            'articles': final_articles,
            'message': f'Found {len(final_articles)} specific sources: {news_count} news, {web_count} web'
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'articles': [],
            'message': f'Search failed: {str(e)}'
        }

def rank_articles_with_ai(articles: list, context: str) -> list:
    """
    Rank articles by relevance to the context (transcript/topic).
    Uses Gemini Flash for fast batch processing.
    """
    if not articles:
        return []
        
    if not GEMINI_API_KEY:
        print("Warning: No API key for ranking, using default sort")
        # Default sort: News > Web
        type_priority = {'news': 0, 'web': 1}
        return sorted(articles, key=lambda x: type_priority.get(x.get('type', 'web'), 2))

    try:
        # Prepare batch for AI
        # We'll send limited info to save tokens: Title + Source + Snippet
        candidates_text = ""
        for i, a in enumerate(articles):
            candidates_text += f"ID {i}: {a.get('title', 'No Title')} ({a.get('source', 'Unknown')}) - {a.get('snippet', '')[:150]}\n"

        prompt = f"""Task: Rank these search results by RELEVANCE to the provided Context.
        
CONTEXT:
{context[:2000]}

CANDIDATES:
{candidates_text}

INSTRUCTIONS:
1. Identify the most specific, high-quality sources that match the Context details (names, events, specific angles).
2. Downrank generic or tangentially related sources.
3. Return a JSON array of the Top {min(len(articles), 30)} IDs in order of relevance (most relevant first).
Example: [14, 2, 5, 0, ...]

Return ONLY the JSON array."""

        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Parse output
        import re
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            ranked_ids = json.loads(match.group())
            
            # Reconstruct list in ranked order
            ranked_list = []
            seen_ids = set()
            
            # Add ranked items first
            for aid in ranked_ids:
                if 0 <= aid < len(articles):
                    ranked_list.append(articles[aid])
                    seen_ids.add(aid)
            
            # Add remaining items (just in case AI missed some good ones or hallucinated IDs) usually we just drop them if looking for top N
            # But let's append the rest just to be safe, but sorted by type
            remaining = [a for i, a in enumerate(articles) if i not in seen_ids]
            
            type_priority = {'news': 0, 'twitter': 1, 'web': 2}
            remaining.sort(key=lambda x: type_priority.get(x.get('type', 'web'), 3))
            
            ranked_list.extend(remaining)
            
            print(f"      ✅ AI successfully ranked top {len(ranked_ids)} items")
            return ranked_list
            
        else:
            print("      ⚠️ AI ranking output parsing failed, using default sort")
            type_priority = {'news': 0, 'twitter': 1, 'web': 2}
            return sorted(articles, key=lambda x: type_priority.get(x.get('type', 'web'), 3))

    except Exception as e:
        print(f"      ⚠️ AI ranking failed: {e}")
        type_priority = {'news': 0, 'twitter': 1, 'web': 2}
        return sorted(articles, key=lambda x: type_priority.get(x.get('type', 'web'), 3))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Search for news articles on a topic')
    parser.add_argument('--topic', '-t', help='Search topic')
    parser.add_argument('--num-articles', '-n', type=int, default=20, help='Number of articles to find')
    parser.add_argument('--transcript', '-r', help='Path to transcript file')
    
    args = parser.parse_args()
    
    transcript = None
    if args.transcript:
        with open(args.transcript, 'r') as f:
            transcript = f.read()
    
    result = search_news(
        topic=args.topic or '',
        num_articles=args.num_articles,
        transcript=transcript
    )
    
    print(json.dumps(result, indent=2))
