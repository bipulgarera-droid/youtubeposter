#!/usr/bin/env python3
"""
Article Content Fetcher using Jina Reader
Fetches and extracts readable content from article URLs using Jina's AI reader.
"""

import os
import requests
from typing import Optional, List, Dict
import time

# Jina Reader base URL
JINA_READER_URL = "https://r.jina.ai"


def fetch_article_with_jina(url: str, timeout: int = 45) -> Optional[str]:
    """
    PRIMARY METHOD: Fetch article content using Jina Reader.
    Jina Reader handles JS, paywalls, and extracts clean markdown.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/plain',
    }
    
    try:
        jina_url = f"{JINA_READER_URL}/{url}"
        response = requests.get(jina_url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            content = response.text
            
            # Jina returns markdown - clean it up for our use
            # Remove markdown images and links formatting but keep text
            import re
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)  # Remove images
            content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)  # Keep link text
            
            # Limit content length (10000 chars ≈ 1500 words per article)
            if len(content) > 10000:
                content = content[:10000] + '...'
            
            return content if len(content) > 100 else None
        else:
            print(f"  ⚠️ Jina returned {response.status_code} for {url[:50]}")
            return None
            
    except requests.Timeout:
        print(f"  ❌ Jina timeout for {url[:50]}...")
        return None
    except Exception as e:
        print(f"  ❌ Jina error for {url[:50]}...: {str(e)[:50]}")
        return None


def fetch_article_with_requests(url: str, timeout: int = 10) -> Optional[str]:
    """FALLBACK: Fetch using requests + BeautifulSoup when Jina fails."""
    from bs4 import BeautifulSoup
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        
        paragraphs = soup.find_all('p')
        content = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
        
        if len(content) > 5000:
            content = content[:5000] + '...'
        
        return content if len(content) > 100 else None
        
    except Exception as e:
        print(f"  ❌ Requests fallback error for {url[:50]}...: {str(e)[:50]}")
        return None


def fetch_article_content(url: str) -> Optional[str]:
    """Fetch article content, trying Jina Reader first, then requests fallback."""
    # PRIMARY: Jina Reader (handles JS, paywalls, etc.)
    content = fetch_article_with_jina(url)
    if content:
        return content
    
    # FALLBACK: Simple requests
    return fetch_article_with_requests(url)


def fetch_multiple_articles(articles: List[Dict], max_articles: int = 25) -> List[Dict]:
    """
    Fetch content for multiple articles using Jina Reader.
    All fetched articles are passed forward - not truncated.
    """
    print(f"\n📖 Fetching content from {min(len(articles), max_articles)} articles with Jina Reader...")
    
    articles_to_fetch = articles[:max_articles]
    enriched_articles = []
    
    for i, article in enumerate(articles_to_fetch):
        url = article.get('url', '')
        if not url:
            continue
            
        print(f"  [{i+1}/{len(articles_to_fetch)}] {article.get('title', 'Unknown')[:50]}...")
        
        content = fetch_article_content(url)
        if content:
            article['content'] = content
            print(f"      ✅ Got {len(content)} chars")
        else:
            article['content'] = article.get('snippet', '')
            print(f"      ⚠️ Using snippet")
        
        enriched_articles.append(article)
        
        # Rate limit - Jina can handle ~60/min, but be safe
        if i < len(articles_to_fetch) - 1:
            time.sleep(0.5)
    
    # Add remaining articles with just snippets (if any beyond max)
    for article in articles[max_articles:]:
        article['content'] = article.get('snippet', '')
        enriched_articles.append(article)
    
    successful = len([a for a in enriched_articles if len(a.get('content', '')) > 200])
    print(f"\n✅ Successfully fetched content from {successful} articles (all passed forward)")
    
    return enriched_articles


if __name__ == '__main__':
    test_url = "https://www.bbc.com/news"
    print(f"Testing with: {test_url}")
    content = fetch_article_content(test_url)
    if content:
        print(f"Got {len(content)} characters")
        print(content[:500])
    else:
        print("Failed to fetch content")
