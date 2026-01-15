const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const path = require('path');

const QUEUE_FILE = path.join(__dirname, '../.tmp/whatsapp_queue.json');
const RESULTS_FILE = path.join(__dirname, '../.tmp/whatsapp_results.json');

// Helper to read queue
function readQueue() {
    if (!fs.existsSync(QUEUE_FILE)) return [];
    try {
        const data = fs.readFileSync(QUEUE_FILE, 'utf8');
        return JSON.parse(data);
    } catch (e) {
        console.error("Error reading queue:", e);
        return [];
    }
}

// Helper to write results
function writeResults(results) {
    fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
}

// Helper for random delay
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const randomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1) + min);

// Create client with local auth (saves session)
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '../tokens/whatsapp-web-js')
    }),
    puppeteer: {
        headless: false, // Show browser
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// QR Code event
client.on('qr', (qr) => {
    console.log('QR Code received. Scan with WhatsApp:');
    qrcode.generate(qr, { small: true });
});

// Ready event
client.on('ready', async () => {
    console.log('✓ Client is ready! Reading queue...');

    const queue = readQueue();
    const results = [];

    if (queue.length === 0) {
        console.log('No pending messages in queue.');
        await client.destroy();
        process.exit(0);
    }

    console.log(`Found ${queue.length} messages to send.`);

    for (const item of queue) {
        const { phone, message, name } = item;

        // Clean phone number
        let cleanPhone = phone.replace(/\D/g, '');
        if (cleanPhone.length === 10) cleanPhone = '91' + cleanPhone;
        const chatId = `${cleanPhone}@c.us`;

        console.log(`Sending to ${name} (${cleanPhone})...`);

        try {
            await client.sendMessage(chatId, message);
            console.log(`✔ Sent to ${name}`);
            results.push({ phone, status: 'Sent', error: null, message_sent: message });
        } catch (error) {
            const errorMsg = error.message || error.text || JSON.stringify(error);
            console.error(`✖ Failed to send to ${name}:`, errorMsg);
            results.push({ phone, status: 'Failed', error: errorMsg, message_sent: message });
        }

        // Random delay between 10 and 20 seconds
        const waitTime = randomDelay(10000, 20000);
        console.log(`Waiting ${(waitTime / 1000).toFixed(1)}s...`);
        await delay(waitTime);
    }

    console.log('All messages processed. Writing results...');
    writeResults(results);

    console.log('Done. Closing...');
    await client.destroy();
    process.exit(0);
});

// Authentication failure
client.on('auth_failure', (msg) => {
    console.error('Authentication failed:', msg);
    process.exit(1);
});

// Disconnected
client.on('disconnected', (reason) => {
    console.log('Client disconnected:', reason);
});

// Initialize
console.log('Launching WhatsApp Web (whatsapp-web.js)...');
client.initialize();
