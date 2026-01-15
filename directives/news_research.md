# News Article Research

**Goal:** Search the web for relevant news articles on a topic and build a repository of 20 URLs.

**Inputs:**
- `topic`: Main topic to search for (e.g., "Venezuela PM abduction finance impact")
- `transcript`: Optional transcript from reference video to extract additional search terms
- `num_articles`: Number of articles to find (default: 20)

**Outputs:**
- JSON array of articles with: `url`, `title`, `snippet`, `source`, `date`

**Tools/Scripts:**
- `execution/search_news.py`

**API Options:**
- Serper API (preferred) - requires `SERPER_API_KEY` in `.env`
- Google Custom Search API - requires `GOOGLE_CSE_ID` and `GOOGLE_CSE_KEY` in `.env`

**Edge Cases:**
- API rate limits: Implement backoff and retry
- Duplicate URLs: Deduplicate by domain
- Paywall sites: Include but mark as potentially paywalled
- No results: Try broader search terms

**Steps:**
1. Build search queries from topic (3-5 variations)
2. If transcript provided, extract key entities/terms
3. Execute searches via Serper API
4. Collect and deduplicate results
5. Prioritize news sources over blogs/forums
6. Return top N articles as JSON
