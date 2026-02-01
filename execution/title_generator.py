#!/usr/bin/env python3
"""
Title Generator Module
Generates high-CTR YouTube titles based on inspiration and content.
"""

import os
import requests
import json
from typing import List, Dict, Optional


def generate_title_options(
    topic: str,
    outline: str,
    inspiration_title: str,
    channel_type: str,
    api_key: str,
    num_options: int = 5,
    key_figure: str = None
) -> Dict:
    """
    Generate CTR-optimized title options using Gemini.
    
    Args:
        topic: Main topic of the video
        outline: Script outline or summary
        inspiration_title: Title to use as style inspiration
        channel_type: Type of channel (e.g., "Geopolitics", "Tech Review")
        api_key: Gemini API key
        num_options: Number of title options to generate
        key_figure: Optional key money figure to include (e.g., "$917B")
    
    Returns:
        Dict with success status and list of title options
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    # Calculate reference title length for matching
    ref_char_count = len(inspiration_title) if inspiration_title else 50
    
    # Check if content summary has specific instructions
    has_custom_instructions = outline and len(outline.strip()) > 20
    
    # Key figure instruction
    key_figure_instruction = ""
    if key_figure:
        key_figure_instruction = f"""
**KEY FIGURE REQUIREMENT:**
You MUST organically include this figure in AT LEAST 3 of your {num_options} titles: "{key_figure}"
- DO NOT just tack it on at the end
- Work it INTO the title naturally, as if it's the news hook
- Examples of BAD integration: "Title Here ({key_figure})" or "Title Here - {key_figure}"
- Examples of GOOD integration: "The {key_figure} Crisis Nobody Saw Coming" or "How {key_figure} Just Vanished Overnight"
- The figure should feel like THE REASON someone would click
"""
    
    prompt = f"""You are a YouTube title expert. Generate {num_options} title options for a video.

**REFERENCE TITLE (The "Vibe" & Length Guide):**
"{inspiration_title}"
Target Length: ~{ref_char_count} chars

**MY CHANNEL ANGLE:** {channel_type}

**CONTENT CONTEXT:**
{outline[:500] if outline else 'Not provided'}
{key_figure_instruction}

**INSTRUCTIONS:**
1. **SAME PUNCH, NEW ANGLE**: Rewrite the reference title to fit my channel angle, but keep the exact same "punchiness" and rhythm.
2. **REARRANGE, DON'T JUST INSERT**: Do NOT just insert words like "Financial" or "Economic". Change the sentence structure while keeping the meaning.
3. **STRICT LENGTH**: Must be within ±5 characters of the reference title.
4. **RETAIN THE ESSENCE**: If the original uses a question, use a question. If it uses a list, use a list. Keep the *psychological hook*.

{"**USER CUSTOM INSTRUCTIONS:**" + chr(10) + outline[:300] if has_custom_instructions else ""}

**BAD EXAMPLES (Do NOT do this):**
- Ref: "Why China Failed" -> Bad: "Why China *Economically* Failed" (Lazy insertion)
- Ref: "The End of Apple" -> Bad: "The *Financial* End of Apple" (Lazy insertion)

**GOOD EXAMPLES (Do this):**
- Ref: "Why China Failed" -> Good: "The Real Reason China's Economy Collapsed" (Same vibe, new structure)
- Ref: "The End of Apple" -> Good: "Is Apple's Business Model Finally Dead?" (Same vibe, new structure)

**OUTPUT FORMAT:**
Return exactly {num_options} titles as a JSON array:
["Title 1", "Title 2", "Title 3", "Title 4", "Title 5"]

Only output the JSON array, nothing else."""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.8,
            "topP": 0.95,
            "maxOutputTokens": 500
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            text = result['candidates'][0]['content']['parts'][0]['text']
            
            # Parse JSON from response
            try:
                # Clean up response
                text = text.strip()
                if text.startswith('```json'):
                    text = text[7:]
                if text.startswith('```'):
                    text = text[3:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
                
                titles = json.loads(text)
                if isinstance(titles, list):
                    return {
                        'success': True,
                        'titles': titles[:num_options],
                        'inspiration': inspiration_title
                    }
            except json.JSONDecodeError:
                # Fallback: try to extract titles from text
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                titles = []
                for line in lines:
                    # Remove numbering like "1.", "2.", etc.
                    clean = line.lstrip('0123456789.-) ').strip('"\'')
                    if clean and len(clean) > 10:
                        titles.append(clean)
                if titles:
                    return {
                        'success': True,
                        'titles': titles[:num_options],
                        'inspiration': inspiration_title
                    }
                return {'success': False, 'error': 'Failed to parse titles', 'raw': text}
        else:
            return {'success': False, 'error': f'API error: {response.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def analyze_title_pattern(title: str, api_key: str) -> Dict:
    """
    Analyze what makes a title effective.
    Returns patterns and elements that make it click-worthy.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    prompt = f"""Analyze this YouTube title and explain what makes it effective:

Title: "{title}"

Identify:
1. Power words used
2. Emotional triggers
3. Pattern/structure (question, statement, number, etc.)
4. What creates curiosity
5. Target emotion (fear, curiosity, excitement, etc.)

Format as JSON with keys: power_words, emotional_triggers, pattern, curiosity_element, target_emotion"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            text = result['candidates'][0]['content']['parts'][0]['text']
            try:
                if '```json' in text:
                    json_str = text.split('```json')[1].split('```')[0].strip()
                elif '```' in text:
                    json_str = text.split('```')[1].split('```')[0].strip()
                else:
                    json_str = text
                return {'success': True, 'analysis': json.loads(json_str)}
            except:
                return {'success': True, 'analysis': None, 'raw': text}
        else:
            return {'success': False, 'error': response.text}
    except Exception as e:
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    # Test
    print("Title Generator Module loaded")
