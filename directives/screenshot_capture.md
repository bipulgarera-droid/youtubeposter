# Screenshot Capture with Highlighting

**Goal:** Visit news article URLs, take screenshots, and add colored highlight overlays on relevant text.

**Inputs:**
- `urls`: List of article URLs to capture
- `highlights`: Dict mapping URL to text to highlight (from script source_map)
- `output_dir`: Directory to save screenshots (default: `.tmp/screenshots/`)

**Outputs:**
- Screenshots saved as PNG files: `{domain}_{hash}.png`
- JSON manifest: `screenshots_manifest.json` mapping URLs to file paths

**Tools/Scripts:**
- `execution/capture_screenshots.js` (Puppeteer/Node.js)

**Edge Cases:**
- Paywall/login walls: Take screenshot of visible content
- Cookie consent popups: Attempt to dismiss
- Slow-loading pages: Wait for network idle
- Highlight text not found: Take full screenshot without highlight
- Dynamic content: Wait for DOM stable

**Steps:**
1. Launch Puppeteer browser (headless)
2. For each URL:
   a. Navigate to page
   b. Wait for content to load
   c. If highlight text provided, search for it in DOM
   d. If found, add colored overlay box around the element
   e. Take screenshot (full page or viewport)
   f. Save to output directory
3. Generate manifest JSON
4. Close browser
