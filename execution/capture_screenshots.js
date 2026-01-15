#!/usr/bin/env node
/**
 * Screenshot Capture Script
 * Uses Puppeteer to capture website screenshots with optional text highlighting.
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Configuration
const TMP_DIR = path.join(__dirname, '..', '.tmp', 'screenshots');

// Ensure output directory exists
if (!fs.existsSync(TMP_DIR)) {
    fs.mkdirSync(TMP_DIR, { recursive: true });
}

/**
 * Generate a short hash for filenames
 */
function generateHash(str) {
    return crypto.createHash('md5').update(str).digest('hex').substring(0, 8);
}

/**
 * Extract domain from URL for filename
 */
function extractDomain(url) {
    try {
        const hostname = new URL(url).hostname;
        return hostname.replace('www.', '').replace(/\./g, '_');
    } catch {
        return 'unknown';
    }
}

/**
 * Dismiss common popups (cookie consent, newsletter, etc.)
 */
async function dismissPopups(page) {
    const dismissSelectors = [
        // Cookie consent
        '[class*="cookie"] button[class*="accept"]',
        '[class*="cookie"] button[class*="agree"]',
        '[id*="cookie"] button',
        'button[class*="consent"]',
        // Generic close buttons
        '[class*="popup"] [class*="close"]',
        '[class*="modal"] [class*="close"]',
        '[aria-label="Close"]',
        '[class*="overlay"] button',
    ];
    
    for (const selector of dismissSelectors) {
        try {
            const element = await page.$(selector);
            if (element) {
                await element.click();
                await page.waitForTimeout(500);
            }
        } catch {
            // Ignore errors
        }
    }
}

/**
 * Find and highlight text on the page
 */
async function highlightText(page, searchText) {
    if (!searchText) return false;
    
    const result = await page.evaluate((text) => {
        // Find text in the page
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        let node;
        while (node = walker.nextNode()) {
            if (node.textContent.toLowerCase().includes(text.toLowerCase())) {
                const parent = node.parentElement;
                if (parent) {
                    // Add highlight overlay
                    const originalBackground = parent.style.backgroundColor;
                    const originalOutline = parent.style.outline;
                    
                    parent.style.backgroundColor = 'rgba(255, 255, 0, 0.4)';
                    parent.style.outline = '3px solid #FFD700';
                    parent.style.borderRadius = '4px';
                    
                    // Scroll element into view
                    parent.scrollIntoView({ behavior: 'instant', block: 'center' });
                    
                    return {
                        found: true,
                        rect: parent.getBoundingClientRect()
                    };
                }
            }
        }
        return { found: false };
    }, searchText);
    
    return result.found;
}

/**
 * Capture screenshot of a single URL
 */
async function captureScreenshot(browser, url, highlightText_) {
    const page = await browser.newPage();
    
    try {
        // Set viewport
        await page.setViewport({ width: 1280, height: 800 });
        
        // Navigate to page
        console.log(`Navigating to: ${url}`);
        await page.goto(url, { 
            waitUntil: 'networkidle2',
            timeout: 30000 
        });
        
        // Wait a bit for dynamic content
        await page.waitForTimeout(2000);
        
        // Try to dismiss popups
        await dismissPopups(page);
        
        // Highlight text if provided
        let highlighted = false;
        if (highlightText_) {
            highlighted = await highlightText(page, highlightText_);
            console.log(`  Highlight "${highlightText_.substring(0, 50)}...": ${highlighted ? 'Found' : 'Not found'}`);
        }
        
        // Generate filename
        const domain = extractDomain(url);
        const hash = generateHash(url);
        const filename = `${domain}_${hash}.png`;
        const filepath = path.join(TMP_DIR, filename);
        
        // Take screenshot
        await page.screenshot({
            path: filepath,
            fullPage: false  // Just viewport for cleaner screenshots
        });
        
        console.log(`  Screenshot saved: ${filename}`);
        
        return {
            url,
            filename,
            filepath,
            highlighted,
            success: true
        };
        
    } catch (error) {
        console.error(`  Error capturing ${url}: ${error.message}`);
        return {
            url,
            filename: null,
            filepath: null,
            highlighted: false,
            success: false,
            error: error.message
        };
    } finally {
        await page.close();
    }
}

/**
 * Main function to capture screenshots for multiple URLs
 */
async function captureScreenshots(urlsWithHighlights) {
    console.log(`\nStarting screenshot capture for ${urlsWithHighlights.length} URLs...\n`);
    
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const results = [];
    
    try {
        for (const item of urlsWithHighlights) {
            const url = item.url || item;
            const highlight = item.highlight_text || item.highlightText || null;
            
            const result = await captureScreenshot(browser, url, highlight);
            results.push(result);
            
            // Small delay between requests
            await new Promise(r => setTimeout(r, 1000));
        }
        
        // Save manifest
        const manifestPath = path.join(TMP_DIR, 'screenshots_manifest.json');
        fs.writeFileSync(manifestPath, JSON.stringify(results, null, 2));
        console.log(`\nManifest saved: ${manifestPath}`);
        
        return {
            success: true,
            screenshots: results,
            manifest_path: manifestPath,
            message: `Captured ${results.filter(r => r.success).length}/${results.length} screenshots`
        };
        
    } finally {
        await browser.close();
    }
}

// CLI interface
if (require.main === module) {
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        console.log('Usage: node capture_screenshots.js --urls <urls.json>');
        console.log('       node capture_screenshots.js --url <single-url> [--highlight "text to highlight"]');
        process.exit(1);
    }
    
    // Parse arguments
    let urlsWithHighlights = [];
    
    if (args.includes('--urls')) {
        const urlsFile = args[args.indexOf('--urls') + 1];
        const data = JSON.parse(fs.readFileSync(urlsFile, 'utf-8'));
        urlsWithHighlights = Array.isArray(data) ? data : data.urls || [];
    } else if (args.includes('--url')) {
        const url = args[args.indexOf('--url') + 1];
        const highlight = args.includes('--highlight') ? args[args.indexOf('--highlight') + 1] : null;
        urlsWithHighlights = [{ url, highlight_text: highlight }];
    }
    
    captureScreenshots(urlsWithHighlights)
        .then(result => {
            console.log('\n' + JSON.stringify(result, null, 2));
        })
        .catch(error => {
            console.error('Fatal error:', error);
            process.exit(1);
        });
}

module.exports = { captureScreenshots, captureScreenshot };
