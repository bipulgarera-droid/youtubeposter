const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');

// Enable stealth plugin
puppeteer.use(StealthPlugin());

// Command line arguments
const args = process.argv.slice(2);
const urlsIndex = args.indexOf('--urls');
if (urlsIndex === -1 || !args[urlsIndex + 1]) {
    console.error('Usage: node capture_screenshots_stealth.js --urls <path_to_urls_json>');
    process.exit(1);
}

const urlsFile = args[urlsIndex + 1];
const outputDir = path.join(__dirname, '../.tmp/screenshots');

// Ensure output directory exists
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

// Helper: Wait function
const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Helper: Random number generator
const random = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

// Helper: Sanitized filename
const sanitizeFilename = (url) => {
    return url.replace(/[^a-z0-9]/gi, '_').toLowerCase().substring(0, 100);
};

// Human-like scroll function
async function humanScroll(page) {
    await page.evaluate(async () => {
        await new Promise((resolve) => {
            let totalHeight = 0;
            const distance = 100;
            const timer = setInterval(() => {
                const scrollHeight = document.body.scrollHeight;

                // Random scroll down
                window.scrollBy(0, distance);
                totalHeight += distance;

                // Stop scrolling when reached bottom or scrolled enough
                if (totalHeight >= scrollHeight - window.innerHeight || totalHeight > 5000) { // Cap at 5000px to save time
                    clearInterval(timer);
                    resolve();
                }
            }, 100); // 100ms delay between scrolls
        });
    });
}

// Main capture function
async function captureScreenshots() {
    let urlsToCapture = [];
    try {
        const fileContent = fs.readFileSync(urlsFile, 'utf8');
        urlsToCapture = JSON.parse(fileContent);
    } catch (error) {
        console.error('Error reading URLs file:', error);
        process.exit(1);
    }

    console.log(`Starting stealth capture for ${urlsToCapture.length} URLs...`);

    const browser = await puppeteer.launch({
        headless: "new", // "new" is the new headless mode, safer than true
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--window-size=1920,1080',
            '--disable-web-security',
        ]
    });

    const results = [];

    for (const item of urlsToCapture) {
        const url = item.url;
        console.log(`Processing: ${url}`);

        const page = await browser.newPage();

        // Set viewport
        await page.setViewport({ width: 1920, height: 1080 });

        // Set random user agent just in case (stealth plugin does this primarily)
        // await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

        try {
            // Navigate with longer timeout and 'networkidle2' to wait for loads
            await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

            // Wait a random bit like a human
            await wait(random(1000, 3000));

            // Simulate mouse movement
            await page.mouse.move(random(100, 1000), random(100, 800));
            await wait(random(500, 1000));

            // Human-like scroll to trigger lazy loading images
            console.log('  Scrolling...');
            await humanScroll(page);

            // Wait for any final animations/loading
            await wait(random(1000, 2000));

            // Screenshot filename
            const filename = `${sanitizeFilename(url)}_${Date.now().toString().slice(-6)}.png`;
            const filepath = path.join(outputDir, filename);
            const relativePath = `.tmp/screenshots/${filename}`;

            // Capture viewport (1080p) - Better for video editing than fullPage
            await page.screenshot({ path: filepath, fullPage: false });

            console.log(`  ✅ Captured: ${filename}`);

            results.push({
                url: url,
                success: true,
                screenshot_path: relativePath
            });

        } catch (error) {
            console.error(`  ❌ Failed to capture ${url}:`, error.message);
            results.push({
                url: url,
                success: false,
                error: error.message
            });
        } finally {
            await page.close();
        }

        // Random pause between processed URLs
        await wait(random(2000, 5000));
    }

    await browser.close();

    // Output results as JSON specifically formatted for python to pick up
    console.log('__JSON_START__');
    console.log(JSON.stringify(results));
    console.log('__JSON_END__');
}

captureScreenshots();
