# Script Generation

**Goal:** Generate a 2000-word YouTube video script using reference transcript and news articles, with clear source attribution.

**Inputs:**
- `transcript`: Transcript of reference video
- `articles`: JSON array of news articles (URL, title, snippet)
- `topic`: Main topic of the video
- `style`: Optional style preferences (tone, pacing, etc.)

**Outputs:**
- `script`: Full 2000-word script with source markers
- `source_map`: JSON mapping script sections to article URLs

**Output Format:**
```json
{
  "title": "Video Title",
  "sections": [
    {
      "id": 1,
      "type": "intro",
      "content": "Script text for this section...",
      "sources": [],
      "word_count": 150
    },
    {
      "id": 2,
      "type": "segment",
      "content": "Script text referencing Article 1...",
      "sources": [
        {"url": "https://example.com/article", "title": "Article Title", "highlight_text": "Specific quote or fact used"}
      ],
      "word_count": 250
    }
  ],
  "total_words": 2000
}
```

**Tools/Scripts:**
- `execution/generate_script.py`

**API Used:**
- Gemini 2.5 Pro (for quality, long-form generation)
- Requires `GEMINI_API_KEY` in `.env`

**Edge Cases:**
- Not all 20 articles may be equally relevant: Prioritize most relevant
- Articles may have conflicting information: Note discrepancies
- Word count target: Aim for 2000 ± 100 words

**Steps:**
1. Load transcript and articles
2. Analyze transcript structure (intro, segments, conclusion)
3. Match articles to relevant topics/segments
4. Generate script using Gemini 2.5 Pro with structured output
5. Ensure each segment has source attribution
6. Validate word count, adjust if needed
7. Return structured script with source map
