#!/usr/bin/env python3
"""
Script Generation with Chunked Approach (MoFu Pattern)
Generates YouTube scripts using the same REST API approach as seo-system-main:
1. Analyze transcript for style/angle
2. Generate outline
3. Write each section chunked (350-600 words each)
4. Concatenate
"""

import os
import json
import requests
import time
from typing import Optional, List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Variable word distribution (percentages) - 8 SECTION TEMPLATE
# Note: HOOK, CHANNEL_PROMO, and CONCLUSION have FIXED lengths, not percentage-based
# Variable sections: CONTEXT(14%) + DD1(23%) + DD2(23%) + DD3(23%) + ANALYSIS(17%) = 100%
SCRIPT_SECTIONS = [
    {"title": "HOOK", "pct": 0.00, "fixed_words": 100, "instructions": "FIXED: MAX 100 WORDS. Start with a SHOCKING STATEMENT or provocative fact. NO casual greetings like 'Alright listen up', 'Hey guys', 'What's up'. Jump straight into the most compelling point. Example: 'Silver is a ticking time bomb. And most investors have no idea.' Make it urgent and newsworthy."},
    {"title": "CONTEXT", "pct": 0.14, "instructions": "Background: What's happening? Why does it matter RIGHT NOW? Set the stage quickly. Write conversationally."},
    {"title": "CHANNEL_PROMO", "pct": 0.00, "fixed_words": 25, "instructions": "FIXED: EXACTLY THIS TEXT: 'Welcome to Empire Finance. We cover economics, finance, and the latest news. Subscribe for daily, well-researched videos that go deeper than the headlines.' DO NOT MODIFY."},
    {"title": "DEEP DIVE 1", "pct": 0.23, "instructions": "First major point. Use specific facts, numbers, and data. Write naturally like explaining to a friend."},
    {"title": "DEEP DIVE 2", "pct": 0.23, "instructions": "Second major point. Connect dots. Show implications. Keep it conversational."},
    {"title": "DEEP DIVE 3", "pct": 0.23, "instructions": "Third point OR twist. 'The thing most people miss'. The 'aha' moment."},
    {"title": "ANALYSIS", "pct": 0.17, "instructions": "Empire Finance's take. What does this mean for YOUR wallet/life? Make it personal and actionable."},
    {"title": "CONCLUSION", "pct": 0.00, "fixed_words": 150, "instructions": "FIXED: MAX 150 WORDS. Deliver on the Hook's promise. Summarize the key takeaway. Strong CTA to subscribe/comment. Keep it punchy."},
]


def call_gemini_rest(prompt: str, model: str = "gemini-2.5-flash", temperature: float = 0.7, use_grounding: bool = False) -> Optional[str]:
    """
    Call Gemini API directly via REST (same pattern as seo-system-main).
    This approach reliably generates long-form content.
    """
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not found")
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 16384  # Much higher than SDK default
        }
    }
    
    if use_grounding:
        payload["tools"] = [{"google_search": {}}]
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 429:
            print(f"      Rate limit hit, waiting 30s...")
            time.sleep(30)
            response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            print(f"      API Error {response.status_code}: {response.text[:200]}")
            return None
        
        result = response.json()
        
        try:
            text = result['candidates'][0]['content']['parts'][0]['text']
            return text
        except (KeyError, IndexError):
            print(f"      Unexpected response structure")
            return None
            
    except Exception as e:
        print(f"      REST API error: {e}")
        return None


def prepare_articles_text(articles: list) -> str:
    """Format articles with full content for AI. Include ALL sources for citation diversity."""
    formatted = []
    # Use ALL articles (up to 30 max to fit in context)
    for i, article in enumerate(articles[:30], 1):
        content = article.get('content', article.get('snippet', ''))
        # 8000 chars ~ 1200-1500 words (captures most full articles)
        if len(content) > 8000:
            content = content[:8000] + '... (truncated)'
        
        formatted.append(f"""
=== SOURCE [{i}] ===
TITLE: {article.get('title', 'N/A')}
URL: {article.get('url', 'N/A')}
DATE: {article.get('date', 'Unknown')}
KEY FACTS:
{content}
""")
    
    # Add source count summary
    summary = f"\n\n📊 TOTAL SOURCES AVAILABLE: {len(articles[:30])} — Prioritize the TOP 15 sources. Sources 16-30 are optional/supporting.\n"
    return summary + "\n".join(formatted)


def analyze_transcript(transcript_text: str) -> str:
    """Analyze the transcript for engagement patterns."""
    print("Step 1: Analyzing transcript for engagement patterns...")
    
    prompt = f"""ANALYZE THIS YOUTUBE TRANSCRIPT STYLE.
    
    TRANSCRIPT:
    {transcript_text[:50000]}
    
    OUTPUT REQUIREMENTS (300 words max):
    1. What is the "Angle" or "Hook" style?
    2. How does the speaker transition between topics?
    3. What is the tone (e.g., urgent, calm, sarcastic)?
    4. How are facts presented?
    
    Provide a "Style Guide" based on this analysis."""

    return call_gemini_rest(prompt) or "Use engaging YouTube style."


def extract_engagement_tactics(transcript_text: str) -> str:
    """
    Extract specific engagement tactics from a high-performing video transcript.
    Returns 5-7 actionable tips that can be applied to new content.
    """
    print("Step 1b: Extracting engagement tactics from high-performer...")
    
    prompt = f"""ANALYZE THIS HIGH-PERFORMING YOUTUBE VIDEO TRANSCRIPT.

Your job: Identify the SPECIFIC TECHNIQUES that likely drove high engagement.

TRANSCRIPT (from a video with high views/multiplier):
{transcript_text[:15000]}

OUTPUT: List exactly 5-7 SPECIFIC, ACTIONABLE engagement tactics.

FORMAT (use this exact format):
- TIP: [Specific technique observed]

EXAMPLES of what to look for:
- Hook structure in first 30 seconds
- Pattern interrupts ("But wait...", "Here's the twist...")
- Cliffhangers before transitions
- Rhetorical questions before reveals
- Use of specific numbers/dates for credibility
- Emotional escalation patterns
- Call-to-action placement

DO NOT include generic advice like "be engaging" or "use good pacing".
ONLY include SPECIFIC techniques you observed in THIS transcript.

OUTPUT ONLY THE 5-7 TIPS, nothing else."""

    result = call_gemini_rest(prompt, temperature=0.3)
    return result or ""


def generate_outline(articles: list, sections: list, word_count: int, script_mode: str = "original", transcript: str = None, topic: str = None) -> dict:
    """
    Generate a detailed outline BEFORE writing sections.
    This assigns specific articles and key facts to each section to prevent repetition.
    """
    print(f"\nStep 2: Generating outline (Mode: {script_mode})...")
    
    # Create a summary of available articles
    articles_summary = ""
    for i, article in enumerate(articles[:30], 1):
        title = article.get('title', 'Unknown')[:80]
        snippet = article.get('content', article.get('snippet', ''))[:200]
        date = article.get('date', 'Unknown')
        articles_summary += f"[{i}] {title} ({date})\n    Key info: {snippet}...\n\n"
    
    # Create sections list
    sections_list = "\n".join([f"{i+1}. {s['title']} (~{int(word_count * s['pct'])} words): {s['instructions'][:150]}" 
                               for i, s in enumerate(sections)])
    
    mode_instruction = ""
    if script_mode == "transcript_refined" and transcript:
        mode_instruction = f"""
MODE: TRANSCRIPT-REFINED
You must roughly follow the flow of the ORIGINAL TRANSCRIPT provided below, but IMPROVE it.
1. Map the original transcript's topics to the sections below.
2. For each section, select NEW sources (search results) that update/verify the transcript's points.
3. If the transcript is outdated (>3 days), assign NEWER sources to correct it.

ORIGINAL TRANSCRIPT (Summary):
{transcript[:5000]}...
"""
    elif script_mode == "news_based":
        mode_instruction = f"""
MODE: NEWS-BASED
TOPIC: {topic if topic else 'Breaking News Update'}
Prioritize sources from the PAST 7 DAYS.
The script should revolve around the LATEST developments matching the TOPIC.
"""
    else: # Original mode
        mode_instruction = f"""
MODE: ORIGINAL SCRIPT
TOPIC: {topic if topic else 'General Finance Update'}
Structure the entire script around this TOPIC using the provided sources.
"""

    prompt = f"""You are planning a well-researched YouTube video script. Your job is to create an OUTLINE that assigns specific sources to each section.
    
TOPIC: {topic if topic else 'General Update'}

AVAILABLE SOURCES (Top 30 ranked by relevance):
{articles_summary}

SCRIPT SECTIONS:
{sections_list}

{mode_instruction}

TASK: Create an outline that:
1. Assigns 3-4 DIFFERENT source numbers to each section.
2. PRIORITIZE sources 1-15 (highest relevance). Use these for the core arguments.
3. Use sources 16-30 ONLY if they add unique value or covering a gap.
4. DO NOT repeat facts across sections.
5. Ensure at least 15 UNIQUE sources are used in total across the outline.
6. Lists 1-2 KEY FACTS from each assigned source that will be mentioned in that section.

OUTPUT FORMAT (JSON):
{{
  "sections": [
    {{
      "section": "HOOK",
      "assigned_sources": [3, 7, 12],
      "key_facts": [
        {{"source": 3, "fact": "Venezuela has 300B barrels of oil"}},
        {{"source": 7, "fact": "Trump announced new tariffs"}},
        {{"source": 12, "fact": "Gold prices hit record high"}}
      ]
    }},
    ...
  ],
  "source_usage": {{
    "1": ["CONTEXT"],
    "2": ["DEEP DIVE 1"],
    ...
  }}
}}

Return ONLY valid JSON."""

    result = call_gemini_rest(prompt, temperature=0.3)
    
    if result:
        try:
            # Parse JSON from response
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                outline = json.loads(json_match.group())
                print(f"      ✅ Outline generated: {len(outline.get('sections', []))} sections planned")
                return outline
        except Exception as e:
            print(f"      ⚠️ Outline parsing failed: {e}")
    
    # Fallback: simple round-robin assignment
    print("      ⚠️ Using fallback outline (round-robin)")
    fallback = {"sections": []}
    articles_per_section = max(3, len(articles) // len(sections))
    for i, section in enumerate(sections):
        start_idx = (i * articles_per_section) % len(articles)
        assigned = [(start_idx + j) % len(articles) + 1 for j in range(articles_per_section)]
        fallback["sections"].append({
            "section": section["title"],
            "assigned_sources": assigned,
            "key_facts": []
        })
    return fallback


def generate_section(
    section: Dict,
    section_num: int,
    total_sections: int,
    target_words: int,
    articles_text: str,
    analysis: str,
    previous_content: str,
    outline_info: dict = None,
    used_facts: list = None,
    engagement_tips: str = "",
    channel_focus: str = "",
    script_mode: str = "original",
    transcript: str = None
) -> str:
    """Generate a single section using the MoFu chunking pattern with outline guidance."""
    
    # Strict tolerance: +/- 50 words only
    min_words = max(target_words - 50, 20)
    max_words = target_words + 50
    
    # Build outline guidance
    outline_guidance = ""
    if outline_info:
        assigned = outline_info.get('assigned_sources', [])
        key_facts = outline_info.get('key_facts', [])
        outline_guidance = f"""
=== YOUR ASSIGNED SOURCES FOR THIS SECTION ===
Use ONLY these source numbers: {assigned}
Key facts to include:
"""
        for kf in key_facts:
            outline_guidance += f"- Source [{kf.get('source')}]: {kf.get('fact')}\n"
    
    # Build anti-repetition list with STRONG instructions
    anti_repeat = ""
    if used_facts:
        anti_repeat = """
=== FACTS ALREADY COVERED (CRITICAL - DO NOT REPEAT) ===
🚨 THE FOLLOWING FACTS/STATISTICS HAVE BEEN USED IN PREVIOUS SECTIONS.
🚨 IF YOU MENTION ANY OF THESE AGAIN, YOUR OUTPUT WILL BE REJECTED.
🚨 Find DIFFERENT angles, statistics, and examples instead.

"""
        for fact in used_facts[-30:]:  # Last 30 facts
            anti_repeat += f"❌ BANNED: {fact}\n"
        anti_repeat += """
🚨 Instead of repeating these facts, you MUST:
- Find NEW statistics from the source material
- Cover a DIFFERENT aspect of the topic
- Go DEEPER on something only touched on briefly before
- Introduce a NEW angle the viewer hasn't heard yet
"""
    
    # Build engagement tips section
    engagement_section = ""
    if engagement_tips:
        engagement_section = f"""
=== ENGAGEMENT TACTICS FROM HIGH-PERFORMING VIDEO ===
Apply these techniques where natural. Do NOT override the Critical Rules below.
{engagement_tips}
"""
    
    # Build channel focus section
    channel_focus_section = ""
    if channel_focus:
        channel_focus_section = f"""
=== CHANNEL FOCUS (MANDATORY ANGLE) ===
This channel focuses on: {channel_focus}
YOU MUST include analysis relevant to this perspective in every section.
Even if the source material doesn't emphasize it, find the {channel_focus} angle.
"""

    # Build mode-specific prompt
    mode_prompt = ""
    if script_mode == "transcript_refined" and transcript:
        mode_prompt = f"""
=== MODE: TRANSCRIPT REFINEMENT (CRITICAL) ===
You are creating a "30% BETTER" version of an original viral video.
1. BASE CONTENT: Use the original transcript segment (below) as a base for flow/argument.
2. IMPROVEMENT: Inject NEW FACTS from your assigned sources (especially those <3 days old).
3. GOAL: Keep the original's engaging style/structure, but make the content fresher and more accurate.
4. If the original transcript mentions outdated stats, replace them with new ones from assigned sources.

ORIGINAL TRANSCRIPT CONTEXT:
{transcript[:3000]}...
"""
    elif script_mode == "news_based":
        mode_prompt = f"""
=== MODE: NEWS-BASED (CRITICAL) ===
Focus HEAVILY on the LATEST NEWS (Sources dated within last 3 days).
Create urgency. "This just happened." "New development."
"""

    print(f"  [{section_num}/{total_sections}] {section['title']} — Target: {target_words} words")
    
    prompt = f"""You are writing Section {section_num} of {total_sections} for a YouTube video script.

SECTION: {section['title']}
GOAL: {section['instructions']}

=== STYLE GUIDE ===
{analysis[:2000]}
{engagement_section}
{channel_focus_section}
{mode_prompt}
{outline_guidance}
{anti_repeat}

=== PREVIOUS SCRIPT CONTENT (READ THIS - DO NOT REPEAT) ===
Below is what has ALREADY been written. You MUST read this to avoid repetition.
Any fact, statistic, or point made below should NOT appear in your section.

{previous_content[-5000:] if previous_content else "(Start of script)"}

=== SOURCE MATERIAL ===
{articles_text}

=== CRITICAL RULES ===

1. **TRANSITIONS (MANDATORY for sections 2-8)**: 
   - Start this section with a TRANSITION PHRASE that connects to the previous content.
   - Examples: "But here's where it gets interesting...", "Now, wait till you hear this...", "And that's not all...", "Here's another thing to consider..."

2. **COHERENCE**: This is ONE continuous story. Build on what came before. Reference previous points briefly if relevant.

3. **NO REPETITION (CRITICAL)**:
   - 🚨 Do NOT mention ANY fact, statistic, or concept from the PREVIOUS SCRIPT CONTENT or BANNED FACTS list.
   - If you've seen "70% is byproduct" mentioned earlier, DO NOT SAY IT AGAIN.
   - If you've seen "5 years of deficit", DO NOT SAY IT AGAIN.
   - Find FRESH information. Go DEEPER on new angles. This is the most important rule.

4. **NO QUOTATION MARKS**: Never use quotation marks ("") anywhere in the script. Paraphrase everything.

5. **NO NEWS OUTLET NAMES**: NEVER mention outlet names. Just state facts directly.

6. **NO CITATIONS OR URLS**: This is a SPEAKABLE script. Do NOT include any URLs, source numbers like [5], or citations.

7. **LENGTH**: {min_words}-{max_words} words.

=== WRITING STYLE (CRITICAL) ===

**OVERALL APPROACH:**
- Write like you're talking to a friend. Imagine you're explaining this over coffee.
- If a sentence sounds weird when spoken out loud, rewrite it.

**SENTENCE STRUCTURE (ENFORCED - NOT OPTIONAL):**
- 🚨 MAXIMUM 20 words per sentence. COUNT EVERY SENTENCE.
- 🚨 If ANY sentence exceeds 20 words, SPLIT IT into two sentences.
- 🚨 Common mistakes to avoid:
  - "Silver, which is essential for solar panels, is also used in..." → TOO LONG, SPLIT IT
  - "This means that investors who understand this, and act now, could see..." → TOO LONG, SPLIT IT
- ✅ One idea = one sentence. Period.
- ✅ Mix lengths: short (5-10 words), medium (12-18 words). Max 20.
- ✅ End paragraphs with punchy closers: "Think about that." / "Let that sink in."

**VOICE & TONE:**
- Use contractions: "It's", "wasn't", "they're" — sounds natural
- Use ACTIVE voice: "The U.S. seized the tanker" NOT "The tanker was seized by the U.S."
- Use active verbs: seized, grabbed, declared, locked in, took over
- Add callback phrases: "Remember those 300 billion barrels?"

**THINGS TO AVOID (NEVER DO THESE):**
- ❌ Nested clauses: "The U.S., which had already seized three tankers, according to reports, then moved to..."
- ❌ Adverb stacking: "systematically, dramatically, relentlessly"
- ❌ Abstract nouns: "the inherent instability of such interventions"
- ❌ Starting too many sentences with "And" or "But"
- ❌ Full titles: Say "Mike Waltz, the UN ambassador" NOT "U.S. Representative to the UN, Ambassador Mike Waltz"
- ❌ Jargon/academic language: say "control" not "hegemony", "take over" not "assert dominance"
- ❌ Passive voice
- ❌ More than 2-3 rhetorical questions per section

**THINGS TO EMPHASIZE:**
- ✅ Short declarative statements after claims: "This wasn't liberation. It was a takeover."
- ✅ Colloquial interjections (sparingly): "Look," "Here's the thing," "Now,"
- ✅ Callback phrases that reference earlier points
- ✅ Plain, direct language a 12-year-old could understand
- ✅ EMPIRICAL DATA: Always cite specific numbers, percentages, dollar amounts, dates
- ✅ EDUCATIONAL TONE: Explain WHY things matter, what they mean for the viewer
- ✅ FACTUAL GROUNDING: Every major claim should be followed by supporting evidence
- ✅ EXCLUSIVITY: "You won't hear this on the mainstream news", "Here's the deeper truth"
- ✅ ANALYSIS: Don't just state facts - explain implications and connect the dots

=== WORD COUNT ENFORCEMENT (ABSOLUTE REQUIREMENT) ===
🚨 THIS IS NOT OPTIONAL. YOUR OUTPUT MUST BE EXACTLY {target_words} WORDS (±50 tolerance).
🚨 MINIMUM: {min_words} words. MAXIMUM: {max_words} words.
🚨 If you write MORE than {max_words} words, you have FAILED.
🚨 If you write FEWER than {min_words} words, you have FAILED.
🚨 COUNT YOUR WORDS before submitting. This is mandatory.

=== OUTPUT FORMAT (CRITICAL) ===
❌ DO NOT include "[Word Count: X]" in your output
❌ DO NOT include any reasoning, thinking, or planning text
❌ DO NOT include "Let me expand this" or similar meta-commentary
❌ DO NOT include "Revised Draft" or version labels
❌ DO NOT include markdown headers like "**Revised Draft:**"
✅ ONLY output the FINAL speakable script content
✅ Just the words the host will read out loud. Nothing else.

Write the {section['title']} section now. ONLY the script text. {target_words} words."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            content = call_gemini_rest(prompt, temperature=0.7)
            
            if not content:
                raise Exception("Empty response from AI")
            
            content = content.strip()
            word_count = len(content.split())
            print(f"      Generated: {word_count} words (Target: {target_words})")
            return content
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                wait_time = (attempt + 1) * 15
                print(f"      Rate limit hit. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"      ERROR: {e}")
                return ""
    
    print(f"      Failed after {max_retries} retries")
    return ""


def generate_script(topic: str, articles: list, transcript: Optional[str] = None, word_count: int = 4000, channel_focus: str = "", script_mode: str = "original") -> dict:
    """Generate a YouTube script using chunked MoFu pattern."""
    
    if not GEMINI_API_KEY:
        return {'success': False, 'script': None, 'message': 'GEMINI_API_KEY not found'}
    
    print(f"\n{'='*60}")
    print(f"CHUNKED SCRIPT GENERATION (MoFu Pattern)")
    print(f"Mode: {script_mode}")
    print(f"Target Total: {word_count} words")
    print(f"{'='*60}\n")
    
    try:
        # Step 1: Analyze transcript (if available, used for style AND refinement in transcript mode)
        transcript_text = transcript if transcript else ""
        engagement_tips = ""
        if transcript_text:
            print("Analyzing transcript style...")
            analysis = analyze_transcript(transcript_text)
            engagement_tips = extract_engagement_tactics(transcript_text)
        else:
            analysis = "Use engaging YouTube style: hook in 5 seconds, build tension, end with question."
        
        # Step 2: Prepare articles
        articles_text = prepare_articles_text(articles)
        
        # Step 3: Generate outline (assigns sources to sections)
        # Step 3: Generate outline (assigns sources to sections)
        outline = generate_outline(articles, SCRIPT_SECTIONS, word_count, script_mode=script_mode, transcript=transcript_text, topic=topic)
        outline_sections = outline.get('sections', [])
        
        # Step 4: Calculate word distribution
        # Note: Some sections have fixed word counts, not percentage-based
        print(f"\nWord Distribution:")
        section_targets = []
        remaining_words = word_count
        
        # First pass: allocate fixed-word sections
        for section in SCRIPT_SECTIONS:
            if 'fixed_words' in section:
                remaining_words -= section['fixed_words']
        
        # Second pass: calculate targets
        for section in SCRIPT_SECTIONS:
            if 'fixed_words' in section:
                target = section['fixed_words']
                print(f"  {section['title']}: ~{target} words (FIXED)")
            else:
                # Recalculate percentage based on remaining words
                total_pct = sum(s['pct'] for s in SCRIPT_SECTIONS if 'fixed_words' not in s)
                adjusted_pct = section['pct'] / total_pct if total_pct > 0 else section['pct']
                target = int(remaining_words * adjusted_pct)
                print(f"  {section['title']}: ~{target} words ({int(section['pct']*100)}%)")
            section_targets.append(target)
        
        # Step 5: Generate each section with outline guidance
        print(f"\nGenerating sections...")
        
        all_sections = []
        previous_content = ""
        used_facts = []  # Track facts already mentioned
        
        for i, section in enumerate(SCRIPT_SECTIONS):
            # Get outline info for this section
            outline_info = outline_sections[i] if i < len(outline_sections) else None
            
            # Extract key facts from outline to track
            if outline_info:
                for kf in outline_info.get('key_facts', []):
                    if kf.get('fact'):
                        used_facts.append(kf.get('fact'))
            
            section_content = generate_section(
                section=section,
                section_num=i + 1,
                total_sections=len(SCRIPT_SECTIONS),
                target_words=section_targets[i],
                articles_text=articles_text,
                analysis=analysis,
                previous_content=previous_content,
                outline_info=outline_info,
                engagement_tips=engagement_tips,
                used_facts=used_facts,
                channel_focus=channel_focus,
                script_mode=script_mode,
                transcript=transcript_text
            )
            
            all_sections.append(section_content)
            previous_content += "\n\n" + section_content
            
            # Rate limit pause
            time.sleep(2)
        
        # Step 5: Combine with section markers for chunking
        # Add markers so chunker can keep sections like CHANNEL_PROMO as independent chunks
        marked_sections = []
        for i, section_content in enumerate(all_sections):
            section_title = SCRIPT_SECTIONS[i]['title']
            marked_sections.append(f"[SECTION: {section_title}]\n{section_content}")
        
        full_script = "\n\n".join(marked_sections)
        
        # Create clean version without markers for display
        clean_script = "\n\n".join(all_sections)
        actual_words = len(clean_script.split())
        
        print(f"\n{'='*60}")
        print(f"COMPLETE: {actual_words} words (target: {word_count})")
        print(f"{'='*60}\n")
        
        return {
            'success': True,
            'script': {
                'title': f'Script: {topic}',
                'total_words': actual_words,
                'target_words': word_count,
                'raw_text': full_script,  # With markers for chunking
                'clean_text': clean_script,  # Without markers for display
                'analysis': analysis
            },
            'message': f"Script generated: {actual_words} words"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'script': None, 'message': f'Script generation failed: {str(e)}'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--articles', '-a', required=True)
    parser.add_argument('--transcript', '-r')
    parser.add_argument('--words', '-w', type=int, default=4000)
    parser.add_argument('--output', '-o')
    args = parser.parse_args()
    
    with open(args.articles, 'r') as f:
        articles = json.load(f)
    
    transcript = None
    if args.transcript:
        with open(args.transcript, 'r') as f:
            transcript = f.read()
    
    result = generate_script(
        topic='',
        articles=articles if isinstance(articles, list) else articles.get('articles', []),
        transcript=transcript,
        word_count=args.words
    )
    
    if args.output and result['success']:
        with open(args.output, 'w') as f:
            f.write(result['script']['raw_text'])
    else:
        print(json.dumps(result, indent=2))
