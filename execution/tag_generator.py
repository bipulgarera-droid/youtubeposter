"""
Tag Generator - Auto-generate YouTube tags based on video metadata.

Uses patterns from metadata_style.md directive.
"""

import os
import re
from typing import List, Optional
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def generate_tags(
    title: str,
    topic: str,
    country: Optional[str] = None,
    script_summary: Optional[str] = None
) -> List[str]:
    """
    Generate YouTube tags for a video.
    
    Returns list of 25-35 tags.
    """
    if GEMINI_API_KEY:
        return _generate_tags_with_ai(title, topic, country, script_summary)
    else:
        return _generate_tags_fallback(title, topic, country)


def _generate_tags_with_ai(
    title: str,
    topic: str,
    country: Optional[str],
    script_summary: Optional[str]
) -> List[str]:
    """Generate tags using AI."""
    prompt = f"""Generate 30 YouTube tags for this video:

TITLE: {title}
TOPIC: {topic}
COUNTRY: {country or 'N/A'}
SUMMARY: {script_summary[:500] if script_summary else 'N/A'}

Follow these patterns:

1. Primary Topic (3-5 tags): Main subject and specific aspects
2. Related Concepts (5-8 tags): Economic/geopolitical/financial terms
3. Searchable Phrases (5-8 tags): "why X is", "X vs Y", "X explained"
4. Trending/Discovery (3-5 tags): Year-based, categories
5. Long-tail Keywords (5-10 tags): Very specific terms, person names

Return ONLY the tags, comma-separated, lowercase, no hashtags.
Example: france,french economy,why france is poor,economic collapse,geopolitics"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        
        # Parse tags
        tags_text = response.text.strip()
        tags = [t.strip().lower() for t in tags_text.split(',')]
        
        # Clean tags
        tags = [re.sub(r'[^\w\s-]', '', t) for t in tags]
        tags = [t for t in tags if t and len(t) > 2]
        
        return tags[:35]
    except Exception as e:
        print(f"AI tag generation error: {e}")
        return _generate_tags_fallback(title, topic, country)


def _generate_tags_fallback(
    title: str,
    topic: str,
    country: Optional[str]
) -> List[str]:
    """Generate tags without AI (fallback)."""
    tags = []
    
    # Base categories always included
    base_tags = [
        "economics", "geopolitics", "finance", "business", 
        "history", "documentary", "global economy"
    ]
    
    # Add country if present
    if country:
        country_lower = country.lower()
        tags.extend([
            country_lower,
            f"{country_lower} economy",
            f"{country_lower} crisis",
            f"why {country_lower}",
            f"{country_lower} explained"
        ])
    
    # Extract words from title
    title_words = re.findall(r'\b[A-Za-z]{4,}\b', title.lower())
    stopwords = {'this', 'that', 'with', 'from', 'what', 'when', 'where', 'which', 'think', 'than'}
    title_words = [w for w in title_words if w not in stopwords]
    
    # Add title-based tags
    if title_words:
        tags.extend(title_words[:5])
        
        # Phrase combinations
        if len(title_words) >= 2:
            tags.append(' '.join(title_words[:2]))
    
    # Add topic
    if topic:
        topic_lower = topic.lower()
        tags.append(topic_lower)
        tags.append(f"{topic_lower} explained")
    
    # Add base tags
    tags.extend(base_tags)
    
    # Deduplicate
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return unique_tags[:30]


def generate_description(
    title: str,
    topic: str,
    script: str,
    timestamps: Optional[str] = None,
    country: Optional[str] = None
) -> str:
    """
    Generate YouTube description for a video.
    
    Returns formatted description with hook, bullets, and hashtags.
    """
    if GEMINI_API_KEY:
        return _generate_description_with_ai(title, topic, script, timestamps, country)
    else:
        return _generate_description_fallback(title, topic, timestamps)


def _generate_description_with_ai(
    title: str,
    topic: str,
    script: str,
    timestamps: Optional[str],
    country: Optional[str]
) -> str:
    """Generate description using AI."""
    script_excerpt = script[:2000] if script else ""
    
    prompt = f"""Generate a YouTube description for this video:

TITLE: {title}
TOPIC: {topic}
COUNTRY: {country or 'N/A'}

SCRIPT EXCERPT:
{script_excerpt}

Create a description with:
1. Hook (1-2 sentences - question or bold statement)
2. Context paragraph (2-3 sentences about what we cover)
3. "In this video, we cover:" section with 5 emoji bullet points
4. Leave "[TIMESTAMPS]" placeholder for chapters
5. 8 hashtags at the end
6. Disclaimer for financial content

Format the bullet points like:
📉 [Topic]: [Brief description]
🏭 [Topic]: [Brief description]

Keep it under 800 words."""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        
        description = response.text.strip()
        
        # Insert timestamps if provided
        if timestamps:
            description = description.replace("[TIMESTAMPS]", f"CHAPTERS:\n{timestamps}")
        else:
            description = description.replace("[TIMESTAMPS]", "")
        
        return description
    except Exception as e:
        print(f"AI description generation error: {e}")
        return _generate_description_fallback(title, topic, timestamps)


def _generate_description_fallback(
    title: str,
    topic: str,
    timestamps: Optional[str]
) -> str:
    """Generate description without AI (fallback)."""
    description = f"""In this video, we take a deep dive into {topic}.

We break down the key factors, analyze the data, and uncover the truth behind the headlines.

In this video, we cover:
📉 The current situation and what's happening now
📊 The key statistics and data you need to know
🏭 The historical context and how we got here
💡 What this means for the future
⚠️ The risks and opportunities ahead

"""
    
    if timestamps:
        description += f"CHAPTERS:\n{timestamps}\n\n"
    
    description += "#Economics #Geopolitics #Finance #Business #Documentary #GlobalEconomy\n\n"
    description += "Disclaimer: This video is for educational and entertainment purposes only."
    
    return description


def generate_hashtags(topic: str, country: Optional[str] = None) -> List[str]:
    """Generate hashtags for end of description."""
    hashtags = ["#Economics", "#Geopolitics", "#Finance"]
    
    if country:
        hashtags.append(f"#{country.replace(' ', '')}")
    
    # Add topic-based hashtags
    topic_words = topic.split()[:2]
    for word in topic_words:
        clean = re.sub(r'[^\w]', '', word)
        if clean and len(clean) > 3:
            hashtags.append(f"#{clean.title()}")
    
    # Add common ones
    hashtags.extend(["#Business", "#History", "#Documentary"])
    
    return hashtags[:10]


if __name__ == "__main__":
    # Test
    print("Testing tag generator...")
    
    tags = generate_tags(
        title="Why France is POORER Than You Think (The Economic Truth)",
        topic="French Economy",
        country="France"
    )
    print(f"\nGenerated {len(tags)} tags:")
    print(", ".join(tags[:10]) + "...")
    
    hashtags = generate_hashtags("French Economy", "France")
    print(f"\nHashtags: {' '.join(hashtags)}")
