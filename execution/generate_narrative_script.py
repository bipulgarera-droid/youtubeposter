#!/usr/bin/env python3
"""
Narrative Engine Script Generation.

Generates engaging, retention-optimized scripts using beat-based structure
instead of outline-first approach.
"""
import os
import re
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Default narrative structure
DEFAULT_BEATS = [
    {
        "id": "intro",
        "name": "Credibility Intro",
        "word_target": 100,
        "purpose": "Establish narrator authority, explain AI voice, promise unique insider access",
        "required_elements": ["years of experience (12+ years)", "reason for AI voice (privacy/speed)", "unique data access others don't have", "anti-mainstream positioning"],
        "ends_with": "transition to the urgent news hook"
    },
    {
        "id": "hook",
        "name": "Hook",
        "word_target": 150,
        "purpose": "Grab attention with urgency, time anchor, and a hint at hidden truth",
        "required_elements": ["time anchor", "personal stake", "mainstream contradiction"],
        "ends_with": "open loop that promises revelation"
    },
    {
        "id": "stakes",
        "name": "Stakes",
        "word_target": 200,
        "purpose": "Make it personal - connect to viewer's money, life, future",
        "required_elements": ["viewer impact", "urgency", "specific numbers"],
        "ends_with": "question that leads to context"
    },
    {
        "id": "context",
        "name": "Context",
        "word_target": 300,
        "purpose": "Historical background - how we got here",
        "required_elements": ["timeline", "key players", "system explanation"],
        "ends_with": "transition to the hidden mechanism"
    },
    {
        "id": "mechanism",
        "name": "Mechanism",
        "word_target": 400,
        "purpose": "Explain how the system actually works (the 'secret')",
        "required_elements": ["give the mechanism a memorable name", "analogy for complex concept", "step-by-step breakdown"],
        "ends_with": "setup for the math/proof"
    },
    {
        "id": "math",
        "name": "Math",
        "word_target": 350,
        "purpose": "Concrete calculations that prove the thesis",
        "required_elements": ["specific calculations", "comparisons", "shock value numbers"],
        "ends_with": "transition to scenarios"
    },
    {
        "id": "scenarios",
        "name": "Scenarios",
        "word_target": 300,
        "purpose": "What happens next - conservative vs stress test",
        "required_elements": ["scenario A (conservative)", "scenario B (extreme)", "probability"],
        "ends_with": "acknowledgment of skeptic view"
    },
    {
        "id": "objections",
        "name": "Objections",
        "word_target": 300,
        "purpose": "Preempt criticism, build credibility",
        "required_elements": ["strongest objection stated fairly", "data-driven rebuttal"],
        "ends_with": "transition to personal stance"
    },
    {
        "id": "personal",
        "name": "Personal",
        "word_target": 250,
        "purpose": "What I'm doing with my money (with disclaimer)",
        "required_elements": ["specific triggers", "position sizing", "disclaimer"],
        "ends_with": "setup for rally"
    },
    {
        "id": "rally",
        "name": "Rally",
        "word_target": 150,
        "purpose": "Emotional conclusion, drive action",
        "required_elements": ["core message recap", "urgency", "subscribe/next video hook"],
        "ends_with": "memorable closing line"
    }
]

# Style guide for all beats
STYLE_GUIDE = """
STYLE RULES:
- Conversational, like talking to a smart friend who's not an expert
- Use "you" often - make it personal
- Include specific numbers, dates, sources (PREFER RECENT NEWS DATA over older transcript data)
- No filler - every sentence moves the story forward
- End each section with a hook that makes the next irresistible
- Use short sentences. Punchy. Direct.
- Include rhetorical questions to maintain engagement
- Numbers in words for small (one, two, three), digits for large (1.3 trillion)

ARCHIVIST TECHNIQUES (use sparingly, 1-2 per beat max):
- Give mechanisms memorable names: "I call this the Premium Gap" or "the 40% Lock"
- Create "write this down" moments for key numbers
- Use vivid metaphors: "vacuum cleaner for gold", "gilded cage", "financial shot across the bow"
- Contrast framing: "While the media says X, the spreadsheet says Y"
- Calculated reveal: walk through math step by step with the viewer

DATA PRIORITY:
- If news articles have more recent data than transcript, USE THE NEWS DATA
- Transcript provides structure/style inspiration; news provides FRESH FACTS
- Always cite the freshest numbers available

ANTI-REPETITION (CRITICAL):
- NEVER repeat the same named concept twice in the script
- If a named term like "Paper Sledgehammer" was used once, DO NOT use it again
- Vary your sentence structures - don't start consecutive sentences the same way
- If you explained a mechanism in an earlier beat, reference it briefly, don't re-explain
- Each beat should feel like PROGRESS, not circling back

FORBIDDEN:
- NEVER use asterisks (*) for any purpose - no bold, no emphasis, no bullets, no markdown
- NEVER use underscores (_) for emphasis
- NEVER use hashtags (#) for headers
- Use plain text only - this is a spoken script for text-to-speech
- Any asterisks in output will break the video pipeline
"""


def get_model():
    """Get Gemini 2.5 Pro model for script generation."""
    model = genai.GenerativeModel(
        'gemini-2.5-pro',
        generation_config={
            'temperature': 0.7,
            'top_p': 0.95,
        }
    )
    return model


def generate_beat(
    beat: Dict,
    research_data: str,
    previous_beats: List[Dict],
    topic: str
) -> Dict:
    """
    Generate a single narrative beat.
    
    Args:
        beat: Beat definition with id, name, word_target, purpose, etc.
        research_data: All research material (transcripts, articles)
        previous_beats: List of already-generated beats (for context)
        topic: Main topic/angle of the script
    
    Returns:
        Dict with beat content and metadata
    """
    # Build context from previous beats
    previous_context = ""
    named_concepts = []
    
    if previous_beats:
        previous_context = "PREVIOUSLY COVERED (DO NOT REPEAT ANY OF THIS - find fresh angles):\n"
        for pb in previous_beats:
            summary = pb.get('summary', pb.get('text', '')[:300])
            previous_context += f"- {pb['name']}: {summary}\n"
            
            # Extract any named concepts (phrases in quotes or capitalized multi-word terms)
            text = pb.get('text', '')
            # Find quoted phrases like "The Paper Sledgehammer"
            quoted = re.findall(r'"([^"]+)"', text)
            named_concepts.extend(quoted)
            # Find capitalized concepts like "The Great Disconnect"
            caps = re.findall(r'The [A-Z][a-z]+ [A-Z][a-z]+', text)
            named_concepts.extend(caps)
        
        if named_concepts:
            # Remove duplicates
            named_concepts = list(set(named_concepts))
            previous_context += f"\nNAMED CONCEPTS ALREADY USED (DO NOT REPEAT THESE NAMES - if you need to reference the concept, use different words):\n"
            previous_context += ", ".join(named_concepts[:20])  # Limit to 20
            previous_context += "\n"
    
    prompt = f"""You are writing a finance/economics YouTube script in the style of high-retention documentary narration.

TOPIC: {topic}

CURRENT BEAT: {beat['name']}
PURPOSE: {beat['purpose']}
WORD TARGET: {beat['word_target']} words (stay within ±15%)
MUST INCLUDE: {', '.join(beat['required_elements'])}
MUST END WITH: {beat['ends_with']}

{previous_context}

RESEARCH DATA:
{research_data[:8000]}

{STYLE_GUIDE}

CRITICAL RULES:
1. Write EXACTLY for this beat's purpose - don't cover other beats
2. Stay close to the word target ({beat['word_target']} words)
3. End with a hook that makes the viewer desperate to hear the next section
4. Do NOT include section headers or titles - just flowing prose
5. Write for SPOKEN delivery - avoid complex sentence structures
6. NEVER self-reference the video structure - no "in this section", "in this video", "let's talk about", "we'll cover"
7. NEVER mention beats, sections, or video structure - flow naturally like storytelling
8. Start directly with content - no preambles like "Let's begin" or "First, let's discuss"

DATA INTEGRITY (EXTREMELY IMPORTANT):
- ONLY use specific numbers, prices, percentages, and dates that appear VERBATIM in the RESEARCH DATA above
- If the transcript says silver is $87, use $87 - DO NOT invent a different price
- If the news says a drop of $4.61, use $4.61 - DO NOT make up a different number
- NEVER hallucinate or fabricate statistics, prices, dates, or figures
- If you need a number and it's not in the research, describe the concept without a specific figure
- Wrong numbers destroy credibility - when in doubt, omit the number

Write the {beat['name']} beat now. Just the prose, no metadata. Start directly with engaging content."""

    model = get_model()
    
    # Generate with grounding enabled (built into model tools)
    response = model.generate_content(prompt)
    text = response.text.strip()
    
    # Clean up any markdown, headers, or asterisks
    text = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE)  # Remove headers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Remove **bold** but keep text
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Remove *italic* but keep text
    text = text.replace('*', '')  # Remove any remaining asterisks
    text = text.replace('_', ' ')  # Remove underscores used for emphasis
    text = re.sub(r'^\s*[-•]\s+', '', text, flags=re.MULTILINE)  # Remove bullet points
    text = re.sub(r'\n{3,}', '\n\n', text)  # Collapse multiple newlines
    text = text.strip()
    
    word_count = len(text.split())
    
    return {
        "id": beat['id'],
        "name": beat['name'],
        "text": text,
        "word_count": word_count,
        "word_target": beat['word_target'],
        "summary": text[:200] + "..." if len(text) > 200 else text
    }


def split_into_chunks(text: str, max_words: int = 20) -> List[Dict]:
    """
    Split text into chunks for AI image generation.
    Each chunk is roughly max_words words.
    Tries to break at sentence boundaries when possible.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_words = 0
    
    for sentence in sentences:
        sentence_words = len(sentence.split())
        
        # If adding this sentence exceeds limit and we have content
        if current_words + sentence_words > max_words and current_chunk:
            chunks.append({
                "text": ' '.join(current_chunk),
                "word_count": current_words
            })
            current_chunk = []
            current_words = 0
        
        # If single sentence is too long, split it
        if sentence_words > max_words:
            words = sentence.split()
            for i in range(0, len(words), max_words):
                chunk_words = words[i:i+max_words]
                chunks.append({
                    "text": ' '.join(chunk_words),
                    "word_count": len(chunk_words)
                })
        else:
            current_chunk.append(sentence)
            current_words += sentence_words
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append({
            "text": ' '.join(current_chunk),
            "word_count": current_words
        })
    
    # Add index to each chunk
    for i, chunk in enumerate(chunks):
        chunk['index'] = i
    
    return chunks


def generate_narrative_script(
    research_data: str,
    topic: str,
    target_minutes: int = 15,
    beats: Optional[List[Dict]] = None
) -> Dict:
    """
    Generate a full narrative script using beat-based structure.
    
    Args:
        research_data: Combined transcripts and articles
        topic: Main topic/angle
        target_minutes: Target video duration in minutes
        beats: Optional custom beat structure (uses DEFAULT_BEATS if not provided)
    
    Returns:
        Dict with full script, beats, and chunks
    """
    if beats is None:
        beats = DEFAULT_BEATS.copy()
    
    # Scale beats for longer videos
    target_words = target_minutes * 150  # ~150 words per minute
    current_total = sum(b['word_target'] for b in beats)
    
    if target_words > current_total * 1.3:
        # For longer videos, duplicate some beats
        beats = scale_beats_for_duration(beats, target_words)
    
    print(f"📝 Generating narrative script for: {topic}")
    print(f"🎯 Target: {target_minutes} minutes (~{target_words} words)")
    print(f"📊 Beat structure: {len(beats)} beats")
    
    generated_beats = []
    
    for i, beat in enumerate(beats):
        print(f"\n[{i+1}/{len(beats)}] Generating: {beat['name']} (~{beat['word_target']} words)")
        
        try:
            result = generate_beat(beat, research_data, generated_beats, topic)
            
            # Split beat into image chunks
            result['chunks'] = split_into_chunks(result['text'], max_words=12)
            result['chunk_count'] = len(result['chunks'])
            
            generated_beats.append(result)
            print(f"    ✅ Generated {result['word_count']} words, {result['chunk_count']} chunks")
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            generated_beats.append({
                "id": beat['id'],
                "name": beat['name'],
                "text": f"[Error generating {beat['name']}: {str(e)}]",
                "word_count": 0,
                "word_target": beat['word_target'],
                "chunks": [],
                "chunk_count": 0,
                "error": str(e)
            })
    
    # Combine all text
    full_script = "\n\n".join([b['text'] for b in generated_beats if b.get('text')])
    
    # Final cleanup - absolutely ensure no asterisks or markdown
    full_script = full_script.replace('*', '')
    full_script = re.sub(r'_([^_]+)_', r'\1', full_script)  # Remove _underscores_
    full_script = re.sub(r'\n{3,}', '\n\n', full_script)
    
    total_words = sum(b.get('word_count', 0) for b in generated_beats)
    
    # Combine all chunks
    all_chunks = []
    chunk_index = 0
    for beat in generated_beats:
        for chunk in beat.get('chunks', []):
            chunk['beat_id'] = beat['id']
            chunk['beat_name'] = beat['name']
            chunk['global_index'] = chunk_index
            all_chunks.append(chunk)
            chunk_index += 1
    
    return {
        "success": True,
        "topic": topic,
        "target_minutes": target_minutes,
        "beats": generated_beats,
        "full_script": full_script,
        "total_words": total_words,
        "estimated_minutes": round(total_words / 150, 1),
        "all_chunks": all_chunks,
        "total_chunks": len(all_chunks)
    }


def scale_beats_for_duration(beats: List[Dict], target_words: int) -> List[Dict]:
    """
    Scale beat structure for longer videos by adding more beats.
    Each beat stays under 400 words.
    """
    current_total = sum(b['word_target'] for b in beats)
    
    if target_words <= current_total:
        return beats
    
    # Calculate how many extra beats we need
    extra_words_needed = target_words - current_total
    
    # Beats that can be duplicated for depth
    expandable = ['context', 'mechanism', 'math', 'scenarios', 'objections']
    
    scaled_beats = []
    part_counter = {}
    
    for beat in beats:
        beat_copy = beat.copy()
        
        if beat['id'] in expandable and extra_words_needed > 0:
            # Add "Part 1" suffix
            part_counter[beat['id']] = 1
            beat_copy['name'] = f"{beat['name']} Part 1"
            scaled_beats.append(beat_copy)
            
            # Add Part 2 if needed
            if extra_words_needed > beat['word_target']:
                part_counter[beat['id']] = 2
                beat_part2 = beat.copy()
                beat_part2['id'] = f"{beat['id']}_2"
                beat_part2['name'] = f"{beat['name']} Part 2"
                beat_part2['purpose'] = f"Continue {beat['purpose'].lower()} with additional depth"
                scaled_beats.append(beat_part2)
                extra_words_needed -= beat['word_target']
        else:
            scaled_beats.append(beat_copy)
    
    return scaled_beats


# CLI for testing
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate narrative script')
    parser.add_argument('--topic', '-t', required=True, help='Script topic/angle')
    parser.add_argument('--research', '-r', help='Path to research file')
    parser.add_argument('--minutes', '-m', type=int, default=15, help='Target duration')
    parser.add_argument('--output', '-o', help='Output JSON file')
    args = parser.parse_args()
    
    # Load research data
    research = ""
    if args.research and os.path.exists(args.research):
        with open(args.research, 'r') as f:
            research = f.read()
    else:
        research = f"Topic: {args.topic}\n[No additional research provided]"
    
    # Generate script
    result = generate_narrative_script(
        research_data=research,
        topic=args.topic,
        target_minutes=args.minutes
    )
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n✅ Saved to {args.output}")
    else:
        print("\n" + "="*60)
        print(f"GENERATED SCRIPT: {result['total_words']} words, {result['estimated_minutes']} min")
        print("="*60)
        print(result['full_script'][:2000] + "..." if len(result['full_script']) > 2000 else result['full_script'])
