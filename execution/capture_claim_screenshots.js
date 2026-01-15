/**
 * Claim-Based Screenshot Capture with Validation
 * 
 * Features:
 * - Page validation (detect CAPTCHAs, popups, paywalls)
 * - Fallback to alternate URLs
 * - Human-like behavior (stealth mode)
 * - Popup/cookie dismissal
 * - Scroll down for better content visibility
 * - Domain blacklisting
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

// Helper: timeout wrapper for any async operation
function withTimeout(promise, ms, fallback = null) {
    return Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), ms))
    ]).catch(() => fallback);
}

// BLACKLISTED DOMAINS - Skip these entirely
const BLACKLISTED_DOMAINS = [
    'twitter.com',
    'x.com',
    'facebook.com',
    'instagram.com',
    'linkedin.com',
    'wsj.com',           // Hard paywall
    'nytimes.com',       // CAPTCHA issues
    'nyt.com',           // NYT short domain
    'ft.com',            // Financial Times paywall
    'bloomberg.com',     // Paywall
    'washingtonpost.com', // Paywall
    'economist.com',     // Paywall
    'forbes.com',        // Heavy popups
    'reuters.com',       // Human verification puzzle
    'time.com',          // Subscribe popups
    'theglobeandmail.com', // Paywall
    'dw.com',            // Persistent cookie consent
    'cbsnews.com',       // Blank pages
    'news.sky.com',      // Cookie banner issues
    'sky.com',           // Cookie banner issues
    'azerbaycan24.com',  // Cloudflare human verification
    'vocal.media'        // Geo-blocked
];

// Blocked patterns to detect (case-insensitive) - EXPANDED LIST
const BLOCKED_PATTERNS = [
    // CAPTCHA patterns
    'verify you are human',
    'verifying you are human',  // Cloudflare
    'confirm you are not a robot',
    'confirm you are human',
    'please verify',
    'captcha',
    'are you a robot',
    'prove you are human',
    'security check',
    'checking your browser',
    'just a moment',
    'please wait while we verify',
    'slide to verify',
    'complete the puzzle',
    'review the security of your connection',  // Cloudflare
    // Access denied / Geo-blocking
    'access denied',
    'access blocked',
    '403 forbidden',
    '401 unauthorized',
    'not available in your country',  // Geo-blocked
    'not available in your region',
    'content is not available',
    // Paywalls
    'subscribe to continue',
    'subscription required',
    'member only',
    'sign up to read',
    'create an account',
    'enter email to continue',
    'enter your email',
    'email to keep reading',
    'register for free',
    'sign in to continue',
    'register to continue',
    'login to continue',
    'create a free account',
    'start your free trial',
    // Device verification
    'verify your device',
    'verify device',
    'one more step',
    // Other blockers
    'enable javascript',
    'javascript is required',
    'please enable cookies'
];

// Popup selectors to try dismissing (in order of priority) - EXPANDED
const POPUP_SELECTORS = [
    // Cookie consent - common button text patterns
    'button:has-text("Accept")',
    'button:has-text("Accept All")',
    'button:has-text("Accept Cookies")',
    'button:has-text("I Accept")',
    'button:has-text("Agree")',
    'button:has-text("I Agree")',
    'button:has-text("OK")',
    'button:has-text("Got it")',
    'button:has-text("Allow")',
    'button:has-text("Allow All")',
    'button:has-text("Continue")',
    // Cookie consent - attribute-based
    'button[id*="accept"]',
    'button[id*="agree"]',
    'button[id*="consent"]',
    'button[id*="cookie"]',
    'button[class*="accept"]',
    'button[class*="agree"]',
    'button[class*="consent"]',
    'a[id*="accept"]',
    'a[class*="accept"]',
    // Cookie banner container buttons
    '[class*="cookie"] button',
    '[class*="Cookie"] button',
    '[class*="consent"] button',
    '[class*="Consent"] button',
    '[class*="gdpr"] button',
    '[class*="GDPR"] button',
    '[id*="cookie"] button',
    '[id*="consent"] button',
    '#onetrust-accept-btn-handler',           // OneTrust (very common)
    '.onetrust-accept-btn-handler',
    '[id*="onetrust"] button',
    '[class*="CookieConsent"] button',
    '.cc-accept',
    '.cc-allow',
    '#CybotCookiebotDialogBodyButtonAccept', // Cookiebot
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    // Close buttons
    '[class*="popup"] button[class*="close"]',
    '[class*="modal"] button[class*="close"]',
    '[class*="overlay"] button[class*="close"]',
    '[class*="dialog"] button[class*="close"]',
    '[aria-label="Close"]',
    '[aria-label="Dismiss"]',
    '[aria-label="close"]',
    'button[class*="close"]',
    '.close-button',
    '.btn-close',
    // Specific X buttons
    'button svg[class*="close"]',
    '[class*="dismiss"]',
    // Chatbots
    '[class*="chat"] button[class*="close"]',
    '[id*="chat"] button[class*="close"]',
    '[class*="intercom"] button',
    '[class*="drift"] button',
    '[class*="chatbot"] button[class*="close"]',
    '[class*="Zendesk"] button[class*="close"]'
];

// Elements to hide via CSS (ads, banners, etc.)
const ELEMENTS_TO_HIDE = [
    '[class*="ad-"]',
    '[class*="advertisement"]',
    '[id*="google_ads"]',
    '[class*="banner"]',
    '[class*="newsletter"]',
    '[class*="popup"]',
    '[class*="modal"]',
    '[class*="overlay"]',
    '[class*="sticky-footer"]',
    '[class*="floating"]',
    'iframe[src*="ads"]',
    '[class*="promo"]'
];

function isBlacklistedDomain(url) {
    try {
        const hostname = new URL(url).hostname.toLowerCase();
        return BLACKLISTED_DOMAINS.some(domain => hostname.includes(domain));
    } catch {
        return false;
    }
}

async function hideAnnoyingElements(page) {
    try {
        await page.evaluate((selectors) => {
            selectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    el.style.display = 'none';
                });
            });
        }, ELEMENTS_TO_HIDE);
    } catch (e) {
        // Ignore errors
    }
}

async function validatePage(page) {
    try {
        const pageText = await page.evaluate(() => document.body.innerText.toLowerCase());

        for (const pattern of BLOCKED_PATTERNS) {
            if (pageText.includes(pattern.toLowerCase())) {
                return { valid: false, reason: pattern };
            }
        }

        return { valid: true, reason: null };
    } catch (e) {
        return { valid: false, reason: 'Page evaluation failed' };
    }
}

async function dismissPopups(page) {
    // Method 1: Click buttons by text content (most reliable)
    try {
        await page.evaluate(() => {
            // Prioritize 'accept all' type buttons
            const acceptTexts = [
                'accept all', 'agree all', 'allow all',     // Priority: accept all variants
                'accept cookies', 'agree to cookies',       // Cookie-specific
                'i accept', 'i agree',                      // I-prefixed
                'accept', 'agree', 'allow',                 // Basic
                'ok', 'okay', 'got it', 'understood',       // Acknowledgement
                'continue', 'proceed',                      // Continue variants
                'essential cookies only', 'essential only'  // Fallback options
            ];
            const buttons = document.querySelectorAll('button, a[role="button"], [class*="btn"], input[type="button"], span[role="button"]');

            for (const btn of buttons) {
                const text = (btn.innerText || btn.value || '').toLowerCase().trim();
                if (acceptTexts.some(t => text.includes(t))) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top < window.innerHeight) {
                        btn.click();
                        return; // Only click first match
                    }
                }
            }
        });
    } catch (e) { }

    await new Promise(r => setTimeout(r, 300));

    // Method 2: Try CSS selectors (skip :has-text which doesn't work in Puppeteer)
    const cssSelectors = POPUP_SELECTORS.filter(s => !s.includes(':has-text'));
    for (const selector of cssSelectors.slice(0, 20)) { // Limit to first 20 for speed
        try {
            const buttons = await page.$$(selector);
            for (const button of buttons.slice(0, 2)) {
                try {
                    const isVisible = await button.isIntersectingViewport();
                    if (isVisible) {
                        await button.click();
                        await new Promise(r => setTimeout(r, 200));
                    }
                } catch { }
            }
        } catch (e) { }
    }

    // Method 3: Press Escape to close modals
    try {
        await page.keyboard.press('Escape');
    } catch (e) { }
}

async function scrollForBetterContent(page) {
    // Scroll down ~200px to get past headers/nav bars
    try {
        await page.evaluate(() => {
            window.scrollBy(0, 80);  // Very slight scroll
        });
        await new Promise(r => setTimeout(r, 500));
    } catch (e) { }
}

async function humanLikeDelay() {
    // Wait 2-3 seconds as requested to ensure full page load
    const delay = Math.random() * 1000 + 2000;
    await new Promise(r => setTimeout(r, delay));
}

async function captureWithValidation(browser, urlData, outputDir) {
    // Filter out blacklisted URLs first
    const validUrls = (urlData.urls || []).filter(url => !isBlacklistedDomain(url));

    if (validUrls.length === 0) {
        console.log(`  [Chunk ${urlData.chunk_index}] All URLs blacklisted, skipping`);
        return {
            success: false,
            chunk_index: urlData.chunk_index,
            url: urlData.urls?.[0] || null,
            error: 'All URLs are from blacklisted domains'
        };
    }

    for (let attempt = 0; attempt < Math.min(validUrls.length, 3); attempt++) {
        const url = validUrls[attempt];
        const startTime = Date.now();
        console.log(`  [Chunk ${urlData.chunk_index}] Attempt ${attempt + 1}/${Math.min(validUrls.length, 3)}`);
        console.log(`      URL: ${url.substring(0, 70)}...`);

        let page;
        try {
            page = await browser.newPage();
            console.log(`      [${Date.now() - startTime}ms] Page created`);
        } catch (e) {
            console.log(`      ❌ Failed to create page: ${e.message}`);
            continue;
        }

        try {
            // Wrap entire page interaction in 45-second timeout
            const result = await withTimeout((async () => {
                await page.setViewport({ width: 1920, height: 1080 });
                await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36');
                console.log(`      [${Date.now() - startTime}ms] Viewport set, navigating...`);

                // Navigate with shorter timeout
                await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
                console.log(`      [${Date.now() - startTime}ms] Navigation complete`);

                // Wait for page to load (2-3 seconds)
                await new Promise(r => setTimeout(r, 2500));
                console.log(`      [${Date.now() - startTime}ms] Page load wait done`);

                // Step 1: Dismiss popups/cookie banners
                await dismissPopups(page);
                await new Promise(r => setTimeout(r, 500));
                console.log(`      [${Date.now() - startTime}ms] Popups dismissed`);

                // Step 2: Hide annoying elements
                await hideAnnoyingElements(page);
                console.log(`      [${Date.now() - startTime}ms] Elements hidden`);

                // Step 3: Scroll down for better content
                await scrollForBetterContent(page);
                console.log(`      [${Date.now() - startTime}ms] Scrolled`);

                // Step 4: One more popup check after scroll
                await dismissPopups(page);
                await new Promise(r => setTimeout(r, 300));

                // Step 5: Validate page
                const validation = await validatePage(page);
                console.log(`      [${Date.now() - startTime}ms] Validation: ${validation.valid ? 'OK' : 'BLOCKED - ' + validation.reason}`);

                if (!validation.valid) {
                    return { blocked: true, reason: validation.reason };
                }

                // Use video name + chunk number for organized filenames
                const chunkNum = String(urlData.chunk_index).padStart(2, '0');
                const filename = `${global.videoName || 'video'}_chunk_${chunkNum}.png`;
                const filepath = path.join(outputDir, filename);

                await page.screenshot({ path: filepath, fullPage: false });
                console.log(`      [${Date.now() - startTime}ms] Screenshot saved!`);

                return { success: true, filename, filepath };
            })(), 45000, { timeout: true }); // 45 second timeout

            await page.close();

            if (result && result.timeout) {
                console.log(`      ❌ [${Date.now() - startTime}ms] TIMEOUT after 45s - trying next URL`);
                continue;
            }

            if (result && result.blocked) {
                console.log(`      ❌ [${Date.now() - startTime}ms] Blocked: ${result.reason}`);
                continue;
            }

            if (result && result.success) {
                console.log(`      ✅ [${Date.now() - startTime}ms] Success: ${result.filename}`);
                return {
                    success: true,
                    chunk_index: urlData.chunk_index,
                    url: url,
                    filename: result.filename,
                    filepath: result.filepath,
                    attempt: attempt + 1
                };
            }

        } catch (e) {
            const elapsed = Date.now() - startTime;
            console.log(`      ❌ [${elapsed}ms] Error: ${e.message ? e.message.substring(0, 80) : 'Unknown error'}`);
            try { await page.close(); } catch { } // Safe close
            continue;
        }
    }

    console.log(`  [Chunk ${urlData.chunk_index}] ❌ All ${Math.min(validUrls.length, 3)} attempts failed`);

    return {
        success: false,
        chunk_index: urlData.chunk_index,
        url: urlData.urls?.[0] || null,
        error: 'All URLs failed validation',
        attempts: Math.min(validUrls.length, 3)
    };
}

async function main() {
    const args = process.argv.slice(2);
    const dataFileIndex = args.indexOf('--data');

    if (dataFileIndex === -1 || !args[dataFileIndex + 1]) {
        console.error('Usage: node capture_claim_screenshots.js --data <json_file>');
        process.exit(1);
    }

    const dataFile = args[dataFileIndex + 1];
    const rawData = JSON.parse(fs.readFileSync(dataFile, 'utf8'));

    // Support both old format (array) and new format ({video_name, chunks})
    let data, videoName;
    if (Array.isArray(rawData)) {
        data = rawData;
        videoName = 'video';
    } else {
        data = rawData.chunks || [];
        videoName = rawData.video_name || 'video';
    }

    // Store videoName globally for filename generation
    global.videoName = videoName;

    const outputDir = path.join(__dirname, '..', '.tmp', 'screenshots');
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    console.log('\n' + '='.repeat(60));
    console.log('CLAIM-BASED SCREENSHOT CAPTURE (v2)');
    console.log(`Video: ${videoName}`);
    console.log(`Processing ${data.length} chunks`);
    console.log('='.repeat(60) + '\n');

    const browser = await puppeteer.launch({
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled'
        ]
    });

    const results = [];
    const totalChunks = data.length;

    for (let i = 0; i < data.length; i++) {
        const item = data[i];
        console.log(`\n${'─'.repeat(50)}`);
        console.log(`📸 CHUNK ${item.chunk_index} (${i + 1}/${totalChunks})`);
        console.log(`${'─'.repeat(50)}`);

        if (!item.urls || item.urls.length === 0) {
            console.log(`  ⚠️ No URLs provided - skipping`);
            results.push({
                success: false,
                chunk_index: item.chunk_index,
                error: 'No URLs provided'
            });
            continue;
        }

        console.log(`  Claim: ${(item.claim || '').substring(0, 50)}...`);
        console.log(`  URLs available: ${item.urls.length}`);

        // Wrap entire chunk processing in 2-minute timeout
        try {
            const result = await withTimeout(
                captureWithValidation(browser, item, outputDir),
                120000,  // 2 minute timeout per chunk
                { timeout: true, chunk_index: item.chunk_index, error: 'Chunk processing timeout' }
            );

            if (result.timeout) {
                console.log(`  ❌ CHUNK TIMEOUT after 2 minutes`);
            }

            results.push(result);
        } catch (e) {
            console.log(`  ❌ CHUNK ERROR: ${e.message}`);
            results.push({
                success: false,
                chunk_index: item.chunk_index,
                error: `Chunk error: ${e.message}`
            });
        }

        // Small delay between chunks
        await new Promise(r => setTimeout(r, 500));

        // Progress update every 10 chunks
        if ((i + 1) % 10 === 0) {
            const successSoFar = results.filter(r => r.success).length;
            console.log(`\n📊 Progress: ${i + 1}/${totalChunks} chunks processed, ${successSoFar} successful so far`);
        }
    }

    await browser.close();

    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;

    console.log('\n' + '='.repeat(60));
    console.log(`COMPLETE: ${successful} succeeded, ${failed} failed`);
    console.log('='.repeat(60));

    console.log('\n__JSON_START__');
    console.log(JSON.stringify(results, null, 2));
    console.log('__JSON_END__');
}

main().catch(console.error);
