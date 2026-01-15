"""
Claim-Based Screenshot Generator

Splits script into chunks, extracts claims, searches for matching sources,
and captures screenshots with validation and fallback.
"""

import os
import re
import json
import time
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

# Settings
WORDS_PER_CHUNK = 37  # Target ~15 seconds at 150 wpm
MIN_CHUNK_WORDS = 25   # Minimum words per chunk
MAX_CHUNK_WORDS = 50   # Maximum words per chunk
MAX_FALLBACK_ATTEMPTS = 3


def chunk_script(script_text: str, words_per_chunk: int = WORDS_PER_CHUNK) -> List[Dict]:
    """
    Split script into chunks that END on sentence boundaries.
    Respects [SECTION: X] markers - keeps small sections like CHANNEL_PROMO as single chunks.
    Target ~37 words but allow 25-50 words to ensure full sentences.
    Returns list of {index, text, start_word, end_word}
    """
    # Remove URLs from text for chunking
    text_clean = re.sub(r'https?://\S+', '', script_text)
    
    # Split by section markers first
    section_pattern = r'\[SECTION:\s*([^\]]+)\]'
    sections = re.split(section_pattern, text_clean)
    
    # sections will be: [text_before, section_name, section_content, section_name, section_content, ...]
    # Skip the first element if it's empty or just whitespace
    
    chunks = []
    current_index = 0
    
    i = 0
    while i < len(sections):
        section_text = sections[i].strip()
        section_name = None
        
        # Check if this is a section name (they come in pairs: name, content)
        if i + 1 < len(sections) and section_text in ['HOOK', 'CONTEXT', 'CHANNEL_PROMO', 'DEEP DIVE 1', 'DEEP DIVE 2', 'DEEP DIVE 3', 'ANALYSIS', 'CONCLUSION']:
            section_name = section_text
            section_text = sections[i + 1].strip() if i + 1 < len(sections) else ""
            i += 2  # Skip both name and content
        else:
            i += 1
        
        if not section_text:
            continue
        
        # For CHANNEL_PROMO, keep as single chunk
        if section_name == 'CHANNEL_PROMO':
            chunks.append({
                'index': current_index,
                'text': section_text,
                'word_count': len(section_text.split()),
                'section': section_name
            })
            current_index += 1
            continue
        
        # For other sections, apply normal chunking
        section_chunks = chunk_section_text(section_text, words_per_chunk, current_index, section_name)
        chunks.extend(section_chunks)
        current_index += len(section_chunks)
    
    # Restore periods in abbreviations
    for chunk in chunks:
        chunk['text'] = chunk['text'].replace('§', '.')
    
    return chunks


def chunk_section_text(text: str, words_per_chunk: int, start_index: int, section_name: str = None) -> List[Dict]:
    """Chunk a section of text into sentence-boundary chunks."""
    # Protect common abbreviations from being treated as sentence endings
    abbreviations = [
        r'\bU\.S\.', r'\bU\.K\.', r'\bU\.N\.', r'\bE\.U\.',
        r'\bDr\.', r'\bMr\.', r'\bMrs\.', r'\bMs\.', r'\bProf\.',
        r'\bGen\.', r'\bCol\.', r'\bLt\.', r'\bSgt\.',
        r'\bInc\.', r'\bCorp\.', r'\bLtd\.', r'\bCo\.',
        r'\bvs\.', r'\bet al\.', r'\bi\.e\.', r'\be\.g\.',
        r'\bJan\.', r'\bFeb\.', r'\bMar\.', r'\bApr\.', r'\bJun\.',
        r'\bJul\.', r'\bAug\.', r'\bSept\.', r'\bOct\.', r'\bNov\.', r'\bDec\.'
    ]
    
    protected_text = text
    for abbr in abbreviations:
        protected_text = re.sub(abbr, lambda m: m.group().replace('.', '§'), protected_text, flags=re.IGNORECASE)
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', protected_text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    
    chunks = []
    current_chunk_words = []
    current_word_count = 0
    
    for sentence in sentences:
        sentence_words = sentence.split()
        sentence_word_count = len(sentence_words)
        
        if current_word_count + sentence_word_count > MAX_CHUNK_WORDS and current_word_count >= MIN_CHUNK_WORDS:
            chunks.append({
                'index': start_index + len(chunks),
                'text': ' '.join(current_chunk_words),
                'word_count': current_word_count,
                'section': section_name
            })
            current_chunk_words = sentence_words.copy()
            current_word_count = sentence_word_count
        else:
            current_chunk_words.extend(sentence_words)
            current_word_count += sentence_word_count
            
            if current_word_count >= words_per_chunk:
                chunks.append({
                    'index': start_index + len(chunks),
                    'text': ' '.join(current_chunk_words),
                    'word_count': current_word_count,
                    'section': section_name
                })
                current_chunk_words = []
                current_word_count = 0
    
    # Handle remaining words
    if current_chunk_words:
        if current_word_count < MIN_CHUNK_WORDS and chunks:
            last_chunk = chunks[-1]
            last_chunk['text'] += ' ' + ' '.join(current_chunk_words)
            last_chunk['word_count'] += current_word_count
        else:
            chunks.append({
                'index': start_index + len(chunks),
                'text': ' '.join(current_chunk_words),
                'word_count': current_word_count,
                'section': section_name
            })
    
    return chunks


def extract_claim(chunk_text: str) -> str:
    """
    Use AI to extract the main factual claim from a chunk.
    Returns a search-friendly query string.
    """
    if not GEMINI_API_KEY:
        # Fallback: use first 10 words
        words = chunk_text.split()[:10]
        return ' '.join(words)
    
    prompt = f"""Extract the main FACTUAL CLAIM from this script segment.
Convert it into a Google News search query (max 8 words).

SEGMENT:
{chunk_text}

RULES:
1. Focus on the specific fact, statistic, or event mentioned
2. Include names, numbers, locations if present
3. Make it search-engine friendly
4. DO NOT include any news outlet names (no CNN, NYT, BBC, etc.)
5. DO NOT include any Twitter/X handles or social media account names
6. DO NOT include any quotes (" or ')
7. DO NOT use words like "reported", "according to", "highlights"
8. Just the raw factual claim in simple keywords

BAD EXAMPLES (never do this):
- "NYT reports Trump oil deal" ❌ (has outlet name)
- "Javier Blas X tweet about oil" ❌ (has social media handle)
- "Globe and Mail Venezuela" ❌ (has outlet name)
- "TV20 Detroit coverage" ❌ (has outlet name)

GOOD EXAMPLES:
- "Trump Venezuela oil deal 50 million barrels" ✓
- "US seizes Venezuela oil tanker Caribbean" ✓
- "Greenland annexation Trump policy" ✓

OUTPUT: Just the search query keywords, nothing else."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0.3, 'maxOutputTokens': 50}
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            claim = result['candidates'][0]['content']['parts'][0]['text'].strip()
            # Clean up any quotes or extra formatting
            claim = claim.strip('"\'').strip()
            return claim
    except Exception as e:
        print(f"      ⚠️ Claim extraction failed: {e}")
    
    # Fallback: first 8 meaningful words
    words = [w for w in chunk_text.split() if len(w) > 3][:8]
    return ' '.join(words)


def search_claim(claim: str, include_twitter: bool = True) -> List[Dict]:
    """
    Search Google News (and optionally Twitter) for the claim.
    Only returns news from the last 2 days.
    Returns list of {url, title, source, type} sorted by relevance.
    """
    if not SERPER_API_KEY:
        print("      ❌ SERPER_API_KEY not found")
        return []
    
    results = []
    
    # Google News search - last 2 days only
    try:
        response = requests.post(
            'https://google.serper.dev/news',
            headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'},
            json={
                'q': claim, 
                'num': 10,
                'tbs': 'qdr:d2'  # Last 2 days
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            for item in data.get('news', [])[:5]:
                results.append({
                    'url': item.get('link'),
                    'title': item.get('title'),
                    'source': item.get('source'),
                    'type': 'news'
                })
            print(f"      📰 News search: {len(results)} results from last 2 days")
    except Exception as e:
        print(f"      ⚠️ News search failed: {e}")
    
    # Twitter search (optional)
    if include_twitter and len(results) < 3:
        try:
            response = requests.post(
                'https://google.serper.dev/search',
                headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'},
                json={'q': f'{claim} site:twitter.com OR site:x.com', 'num': 3},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                for item in data.get('organic', [])[:3]:
                    if 'twitter.com' in item.get('link', '') or 'x.com' in item.get('link', ''):
                        results.append({
                            'url': item.get('link'),
                            'title': item.get('title'),
                            'source': 'Twitter/X',
                            'type': 'twitter'
                        })
        except Exception as e:
            print(f"      ⚠️ Twitter search failed: {e}")
    
    return results


def process_chunks_for_screenshots(chunks: List[Dict], used_urls: set = None) -> List[Dict]:
    """
    Process all chunks: extract claims, search, prepare for screenshots.
    Returns list of {chunk_index, chunk_text, claim, search_results}
    
    NEW RULE: Each URL can only be used ONCE across all chunks (no reuse).
    """
    if used_urls is None:
        used_urls = set()
    
    processed = []
    
    for i, chunk in enumerate(chunks):
        print(f"\n  [{i+1}/{len(chunks)}] Processing chunk...")
        
        # Extract claim
        claim = extract_claim(chunk['text'])
        print(f"      🔍 Claim: {claim[:50]}...")
        
        # Search for claim (no Twitter - it's blacklisted anyway)
        results = search_claim(claim, include_twitter=False)
        
        # STRICT: Only use URLs that have NEVER been used before
        fresh_results = [r for r in results if r['url'] not in used_urls]
        
        if fresh_results:
            # Mark ALL fresh results as used (so they can't be reused by any other chunk)
            for r in fresh_results[:MAX_FALLBACK_ATTEMPTS]:
                used_urls.add(r['url'])
            print(f"      ✅ Found {len(fresh_results)} fresh URLs")
        else:
            print(f"      ❌ No fresh URLs found (all {len(results)} are already used)")
        
        processed.append({
            'chunk_index': chunk['index'],
            'chunk_text': chunk['text'],
            'word_count': chunk['word_count'],
            'claim': claim,
            'search_results': fresh_results[:MAX_FALLBACK_ATTEMPTS]  # Only fresh URLs, no reuse
        })
        
        # Small delay to avoid rate limits
        time.sleep(0.3)
    
    return processed


def generate_claim_screenshots_data(script_text: str) -> Dict:
    """
    Main function: process script and prepare screenshot data.
    """
    print("\n" + "="*60)
    print("CLAIM-BASED SCREENSHOT GENERATOR")
    print("="*60)
    
    # Step 1: Chunk the script
    chunks = chunk_script(script_text)
    
    # Step 2: Process chunks (extract claims, search)
    print("\n🔎 Extracting claims and searching...")
    processed = process_chunks_for_screenshots(chunks)
    
    # Step 3: Prepare output
    screenshots_needed = []
    for item in processed:
        if item['search_results']:
            screenshots_needed.append({
                'chunk_index': item['chunk_index'],
                'chunk_text': item['chunk_text'],
                'claim': item['claim'],
                'urls': [r['url'] for r in item['search_results']],
                'titles': [r['title'] for r in item['search_results']]
            })
        else:
            screenshots_needed.append({
                'chunk_index': item['chunk_index'],
                'chunk_text': item['chunk_text'],
                'claim': item['claim'],
                'urls': [],
                'titles': [],
                'error': 'No search results found'
            })
    
    print(f"\n📊 Summary:")
    print(f"   Total chunks: {len(chunks)}")
    print(f"   With URLs: {len([s for s in screenshots_needed if s['urls']])}")
    print(f"   Without URLs: {len([s for s in screenshots_needed if not s['urls']])}")
    
    return {
        'success': True,
        'total_chunks': len(chunks),
        'screenshots_data': screenshots_needed
    }


if __name__ == '__main__':
    # Test with sample text
    sample = """Venezuela holds over 300 billion barrels of proven oil reserves, making it the world's largest. 
    President Trump announced new tariffs on Venezuelan oil imports. The intervention could unlock 
    undermanaged resources worth trillions of dollars. Critics argue this is about control, not democracy."""
    
    result = generate_claim_screenshots_data(sample)
    print(json.dumps(result, indent=2))
