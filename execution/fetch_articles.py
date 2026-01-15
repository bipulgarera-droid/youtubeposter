#!/usr/bin/env python3
"""
Article Content Fetcher using Camoufox
Fetches and extracts readable content from article URLs using stealth browser.
"""

import os
from typing import Optional, List, Dict
import concurrent.futures
import time

# Try to import camoufox, fall back to requests if not available
try:
    from camoufox.sync_api import Camoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    print("Warning: Camoufox not available, falling back to requests")


def fetch_article_with_camoufox(url: str, timeout: int = 15000) -> Optional[str]:
    """
    Fetch and extract main content from an article URL using Camoufox.
    Returns cleaned text content or None if failed.
    """
    try:
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            page.goto(url, timeout=timeout)
            
            # Wait for content to load
            page.wait_for_load_state('domcontentloaded')
            time.sleep(1)  # Small delay for JS to render
            
            # Try to find main article content
            selectors = [
                'article',
                '[role="main"]',
                '.article-content',
                '.post-content', 
                '.entry-content',
                '.story-body',
                '.article-body',
                '#article-body',
                '.content-body',
                'main',
            ]
            
            content = ""
            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        content = element.inner_text()
                        if len(content) > 200:
                            break
                except:
                    continue
            
            # Fallback to body
            if len(content) < 200:
                content = page.query_selector('body').inner_text()
            
            # Clean up
            page.close()
            
            # Limit content length (8000 chars ≈ 1200 words per article)
            if len(content) > 8000:
                content = content[:8000] + '...'
            
            return content if len(content) > 100 else None
            
    except Exception as e:
        print(f"  ❌ Camoufox error for {url[:50]}...: {str(e)[:50]}")
        return None


def fetch_article_with_requests(url: str, timeout: int = 10) -> Optional[str]:
    """Fallback: Fetch using requests + BeautifulSoup."""
    import requests
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
        
        if len(content) > 3000:
            content = content[:3000] + '...'
        
        return content if len(content) > 100 else None
        
    except Exception as e:
        print(f"  ❌ Requests error for {url[:50]}...: {str(e)[:50]}")
        return None


def fetch_article_content(url: str) -> Optional[str]:
    """Fetch article content, trying camoufox first, then requests fallback."""
    if CAMOUFOX_AVAILABLE:
        content = fetch_article_with_camoufox(url)
        if content:
            return content
    
    # Fallback to requests
    return fetch_article_with_requests(url)


def fetch_multiple_articles(articles: List[Dict], max_articles: int = 15) -> List[Dict]:
    """
    Fetch content for multiple articles.
    Uses Camoufox for better extraction.
    """
    print(f"\n📖 Fetching content from {min(len(articles), max_articles)} articles with Camoufox...")
    
    articles_to_fetch = articles[:max_articles]
    enriched_articles = []
    
    # Process sequentially for camoufox (browser context)
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
    
    # Add remaining articles with just snippets
    for article in articles[max_articles:]:
        article['content'] = article.get('snippet', '')
        enriched_articles.append(article)
    
    successful = len([a for a in enriched_articles if len(a.get('content', '')) > 200])
    print(f"\n✅ Successfully fetched content from {successful} articles")
    
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
