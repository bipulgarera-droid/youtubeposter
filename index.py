import os
import sys
import time
import traceback
import json
import requests
import threading
from flask import Flask, request, jsonify, send_from_directory, session, redirect
from flask_cors import CORS

# Add parent directory to path to import gemini_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import google.generativeai as genai  # REMOVED: Legacy SDK
# from google import genai as genai_new  # REMOVED: New SDK
# from google.genai import types # REMOVED: New SDK types
import gemini_client # Import our custom client wrapper
import markdown
from webflow_client import webflow_client
from nano_banana_client import nano_banana_client
import re
from supabase import create_client, Client
from dotenv import load_dotenv
import io
import mimetypes

# Load environment variables from .env
load_dotenv()
# Remove static_folder config entirely to avoid any startup path issues
# We are serving files manually in home() and dashboard()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Explicitly set template and static folders with absolute paths as requested
template_dir = os.path.join(BASE_DIR, 'public')
static_dir = os.path.join(BASE_DIR, 'public')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

@app.route('/ping')
def ping():
    return "pong", 200

@app.route('/favicon.ico')
def favicon():
    return "", 204
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 # Disable cache for development
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-prod')
CORS(app, supports_credentials=True)

# File-based logging for debugging
def log_debug(message):
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_path = os.path.join(BASE_DIR, "debug.log")
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Logging failed: {e}", file=sys.stderr)

# Initialize log
# Initialize log
log_debug("Server started/reloaded")

# --- AGGRESSIVE LOGGING START ---
print(f"DEBUG: BASE_DIR is {BASE_DIR}", file=sys.stderr, flush=True)
print(f"DEBUG: template_dir is {template_dir}", file=sys.stderr, flush=True)

try:
    if os.path.exists(template_dir):
        print(f"DEBUG: Listing {template_dir}: {os.listdir(template_dir)}", file=sys.stderr, flush=True)
    else:
        print(f"DEBUG: template_dir does not exist!", file=sys.stderr, flush=True)
except Exception as e:
    print(f"DEBUG: Failed to list template_dir: {e}", file=sys.stderr, flush=True)

@app.before_request
def log_request_info():
    print(f"DEBUG: Request started: {request.method} {request.url}", file=sys.stderr, flush=True)
    # print(f"DEBUG: Headers: {request.headers}", file=sys.stderr, flush=True) # Uncomment if needed

@app.after_request
def log_response_info(response):
    print(f"DEBUG: Request finished: {response.status}", file=sys.stderr, flush=True)
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"CRITICAL: Unhandled Exception: {str(e)}", file=sys.stderr, flush=True)
    traceback.print_exc()
    return jsonify({"error": "Internal Server Error", "details": str(e)}), 500
# --- AGGRESSIVE LOGGING END ---

@app.route('/api/get-debug-log', methods=['GET'])
def get_debug_log():
    try:
        log_path = os.path.join(BASE_DIR, "debug.log")
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                # Read last 50 lines
                lines = f.readlines()
                return jsonify({"logs": lines[-50:]}), 200
        return jsonify({"logs": ["Log file not found."]}), 200
    except Exception as e:
        return jsonify({"logs": [f"Error reading log: {str(e)}"]}), 200

import logging
try:
    log_path = os.path.join(BASE_DIR, 'backend.log')
    logging.basicConfig(filename=log_path, level=logging.INFO, 
                        format='%(asctime)s %(levelname)s: %(message)s')
    logger = logging.getLogger()
except Exception as e:
    print(f"Warning: Failed to setup file logging: {e}", file=sys.stderr)
    # Fallback to console logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()

# Configure Gemini
# GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# if not GEMINI_API_KEY:
#     # In production, this should ideally log an error or fail gracefully if the key is critical
#     pass 
# genai.configure(api_key=GEMINI_API_KEY) # REMOVED: Legacy SDK Config

# Configure Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Add delay to allow connection pool to spin up (prevents startup crashes)
time.sleep(1)

if SUPABASE_URL:
    print(f"DEBUG: Supabase Configuration - URL: {SUPABASE_URL}", file=sys.stderr, flush=True)
else:
    print("DEBUG: Supabase URL NOT FOUND", file=sys.stderr, flush=True)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

@app.route('/')
def home():
    try:
        print("DEBUG: Entering home route", file=sys.stderr, flush=True)
        
        # Explicitly check for template existence
        template_path = os.path.join(template_dir, 'agency.html')
        if not os.path.exists(template_path):
            error_msg = f"CRITICAL: Template not found at {template_path}"
            print(error_msg, file=sys.stderr, flush=True)
            return jsonify({"error": "Template not found", "path": template_path}), 500
            
        print(f"DEBUG: Serving template from {template_path}", file=sys.stderr, flush=True)
        return send_from_directory(template_dir, 'agency.html')
        
    except Exception as e:
        print(f"CRITICAL ERROR in home route: {str(e)}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

# Explicit route for /agency.html (needed for OAuth redirects)
@app.route('/agency.html')
def agency_html():
    """Serve agency.html directly - needed for OAuth callback redirects"""
    try:
        return send_from_directory(template_dir, 'agency.html')
    except Exception as e:
        print(f"Error serving agency.html: {str(e)}", file=sys.stderr, flush=True)
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

@app.route('/health')
def health_check():
    print("DEBUG: Health check hit", file=sys.stderr, flush=True)
    return "OK", 200

@app.route('/debug-files')
def debug_files():
    try:
        files = os.listdir(app.static_folder)
        return jsonify({"static_folder": app.static_folder, "files": files})
    except Exception as e:
        return jsonify({"error": str(e), "static_folder": app.static_folder})

@app.route('/generated-images/<path:filename>')
def serve_generated_image(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'public', 'generated_images'), filename)


@app.route('/dashboard')
def dashboard():
    try:
        file_path = os.path.join(BASE_DIR, 'public', 'dashboard.html')
        if not os.path.exists(file_path):
            return f"Error: dashboard.html not found at {file_path}", 404
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        response = app.make_response(content)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    except Exception as e:
        return f"Server Error: {str(e)}", 500



@app.route('/api/test-ai', methods=['POST'])
def test_ai():
    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"error": "GEMINI_API_KEY not found"}), 500

    try:
        data = request.get_json()
        topic = data.get('topic', 'SaaS Marketing') if data else 'SaaS Marketing'

        # Using the requested model which is confirmed to be available for this key
        # model = genai.GenerativeModel('gemini-2.5-flash')
        # response = model.generate_content(f"Write a short 1-sentence SEO strategy for '{topic}'.")
        
        generated_text = gemini_client.generate_content(
            prompt=f"Write a short 1-sentence SEO strategy for '{topic}'.",
            model_name="gemini-2.5-flash"
        )
        
        if not generated_text:
             return jsonify({"error": "Gemini generation failed"}), 500
             
        return jsonify({"strategy": generated_text.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- SHARED HELPER: Robust Scraper ---
def fetch_html_robust(url):
    """
    Fetches HTML using a 2-Layer Strategy:
    1. Requests Session with Chrome Headers (Stealth)
    2. Curl Fallback (if 403/429)
    Returns: (content_bytes, status_code, final_url)
    """
    logging.info(f"DEBUG: fetch_html_robust called for {url}")
    
    # Layer 1: Requests Session (Stealth)
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/'
    }
    
    content = None
    status_code = 0
    final_url = url
    
    try:
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        status_code = response.status_code
        final_url = response.url
        content = response.content
        logging.info(f"DEBUG: Layer 1 (Requests) Status: {status_code}")
        
        if status_code in [403, 429, 503]:
            raise Exception(f"Blocked (Status {status_code})")
            
    except Exception as e:
        logging.info(f"DEBUG: Layer 1 failed: {e}. Trying Layer 2 (Curl)...")
        # Layer 2: Curl Fallback
        try:
            # Use curl to bypass some TLS fingerprinting issues
            cmd = [
                'curl', '-L', # Follow redirects
                '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--max-time', '15',
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=False) # Get bytes
            if result.returncode == 0 and result.stdout:
                content = result.stdout
                status_code = 200
                logging.info("DEBUG: Layer 2 (Curl) successful")
            else:
                logging.info(f"DEBUG: Layer 2 (Curl) failed: {result.stderr.decode('utf-8', errors='ignore')}")
        except Exception as curl_e:
            logging.info(f"DEBUG: Layer 2 (Curl) Exception: {curl_e}")
            
    return content, status_code, final_url

@app.route('/api/start-audit', methods=['POST'])
def start_audit():
    print("DEBUG: AUDIT FIX APPLIED - STARTING REQUEST")
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500

    try:
        data = request.get_json()
        page_id = data.get('page_id')
        
        if not page_id:
            return jsonify({"error": "page_id is required"}), 400
        
        # 1. Get the page
        page_res = supabase.table('pages').select('*').eq('id', page_id).execute()
        if not page_res.data:
            return jsonify({"error": "Page not found"}), 404
        
        page = page_res.data[0]
        target_url = page['url']
        
        print(f"DEBUG: Starting Tech Audit for {target_url}")
        
        # 2. Update status to PROCESSING
        supabase.table('pages').update({"audit_status": "Processing"}).eq('id', page_id).execute()
        
        # 3. Perform Tech Audit
        audit_data = {
            "status_code": None,
            "load_time_ms": 0,
            "title": None,
            "meta_description": None,
            "h1": None,
            "word_count": 0,
            "internal_links_count": 0,
            "broken_links": []
        }
        
        try:
            start_time = time.time()
            # Use Robust Scraper Helper
            content, status_code, final_url = fetch_html_robust(target_url)
            
            audit_data["load_time_ms"] = int((time.time() - start_time) * 1000)
            audit_data["status_code"] = status_code
            
            if status_code == 200 and content:
                soup = BeautifulSoup(content, 'html.parser')
                
                # Title
                audit_data["title"] = soup.title.string.strip() if soup.title else None
                
                # Meta Description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    audit_data["meta_description"] = meta_desc.get('content', '').strip()
                
                # H1
                h1 = soup.find('h1')
                audit_data["h1"] = h1.get_text().strip() if h1 else None

                # Open Graph Tags
                og_title = soup.find('meta', attrs={'property': 'og:title'})
                audit_data["og_title"] = og_title.get('content', '').strip() if og_title else None
                
                og_desc = soup.find('meta', attrs={'property': 'og:description'})
                audit_data["og_description"] = og_desc.get('content', '').strip() if og_desc else None
                
                # Word Count (rough estimate)
                text = soup.get_text(separator=' ')
                words = [w for w in text.split() if len(w) > 2]
                audit_data["word_count"] = len(words)
                
                # Internal Links
                links = soup.find_all('a', href=True)
                audit_data["internal_links_count"] = len(links)

                # Canonical
                canonical = soup.find('link', attrs={'rel': 'canonical'})
                if canonical:
                    audit_data["canonical"] = canonical.get('href', '').strip()
                
                # Click Depth (Estimated based on URL path segments)
                import urllib.parse
                path = urllib.parse.urlparse(target_url).path
                # Root / is depth 0 or 1. Let's say root is 0.
                segments = [x for x in path.split('/') if x]
                audit_data["click_depth"] = len(segments)

                # --- On-Page Analysis ---
                score = 100
                checks = []
                
                # Title Analysis
                title = audit_data.get("title")
                if not title:
                    score -= 20
                    checks.append("Missing Title")
                    audit_data["title_length"] = 0
                else:
                    t_len = len(title)
                    audit_data["title_length"] = t_len
                    if t_len < 10: 
                        score -= 10
                        checks.append("Title too short")
                    elif t_len > 60:
                        score -= 10
                        checks.append("Title too long")

                # Meta Description Analysis
                desc = audit_data.get("meta_description")
                if not desc:
                    score -= 20
                    checks.append("Missing Meta Desc")
                    audit_data["description_length"] = 0
                else:
                    d_len = len(desc)
                    audit_data["description_length"] = d_len
                    if d_len < 50:
                        score -= 5
                        checks.append("Desc too short")
                    elif d_len > 160:
                        score -= 5
                        checks.append("Desc too long")

                # H1 Analysis
                h1 = audit_data.get("h1")
                if not h1:
                    score -= 20
                    checks.append("Missing H1")
                    audit_data["missing_h1"] = True
                else:
                    audit_data["missing_h1"] = False

                # OG Checks
                if not audit_data.get("og_title"):
                    checks.append("Missing OG Title")
                if not audit_data.get("og_description"):
                    checks.append("Missing OG Desc")
                
                # Image Alt Analysis
                images = soup.find_all('img')
                missing_alt = [img for img in images if not img.get('alt')]
                audit_data["missing_alt_count"] = len(missing_alt)
                
                if missing_alt:
                    score -= 10
                    checks.append(f"{len(missing_alt)} Images missing Alt")
                
                # --- Technical Issues Checks ---
                # Check for redirects by comparing URLs
                if final_url != target_url and final_url != target_url + '/':
                    audit_data["is_redirect"] = True
                else:
                    audit_data["is_redirect"] = 300 <= status_code < 400

                status = audit_data["status_code"]
                audit_data["is_4xx_code"] = 400 <= status < 500
                audit_data["is_5xx_code"] = 500 <= status < 600
                audit_data["high_loading_time"] = audit_data["load_time_ms"] > 2000
                
                # Advanced Checks
                audit_data["redirect_chain"] = False # Simplified for robust scraper
                
                canonical = audit_data.get("canonical")
                if canonical and canonical != target_url:
                    audit_data["canonical_mismatch"] = True
                else:
                    audit_data["canonical_mismatch"] = False
                    
                audit_data["is_orphan_page"] = False # Placeholder: Requires full link graph
                
                # Final Checks
                audit_data["is_broken"] = status >= 400 or status == 0
                
                # Schema / Microdata Check
                has_json_ld = soup.find('script', type='application/ld+json') is not None
                has_microdata = soup.find(attrs={'itemscope': True}) is not None
                audit_data["has_schema"] = has_json_ld or has_microdata
                
                # Duplicate Checks (Query DB)
                try:
                    if title:
                        dup_title = supabase.table('pages').select('id', count='exact').eq('title', title).neq('id', page_id).execute()
                        audit_data["duplicate_title"] = dup_title.count > 0
                    else:
                        audit_data["duplicate_title"] = False
                        
                    if desc:
                        dup_desc = supabase.table('pages').select('id', count='exact').eq('meta_description', desc).neq('id', page_id).execute()
                        audit_data["duplicate_desc"] = dup_desc.count > 0
                    else:
                        audit_data["duplicate_desc"] = False
                except Exception as e:
                    print(f"Duplicate Check Error: {e}")
                    audit_data["duplicate_title"] = False
                    audit_data["duplicate_desc"] = False

                audit_data["onpage_score"] = max(0, score)
                audit_data["checks"] = checks

            else:
                print(f"Audit Failed: Status {status_code}")
                audit_data["error"] = f"HTTP {status_code}"
                audit_data["onpage_score"] = 0
                
        except Exception as e:
            print(f"Audit Error: {e}")
            audit_data["error"] = str(e)
            audit_data["status_code"] = 0 # Indicate failure
    
    # 4. Save Results (Merge with existing)
        current_tech_data = page.get('tech_audit_data') or {}
        current_tech_data.update(audit_data)
        
        update_payload = {
            "audit_status": "Analyzed",
            "tech_audit_data": current_tech_data,
            # Also update core fields if found
            "title": audit_data.get("title") or page.get("title"),
            "meta_description": audit_data.get("meta_description") or page.get("meta_description"),
            "h1": audit_data.get("h1") or page.get("h1")
        }
        
        print(f"DEBUG: Updating DB for page {page_id}")
        print(f"DEBUG: Payload: {json.dumps(update_payload, default=str)[:500]}...") # Print first 500 chars
        
        res = supabase.table('pages').update(update_payload).eq('id', page_id).execute()
        print(f"DEBUG: DB Update Result: {res}")
        
        return jsonify({
            "message": "Tech audit completed",
            "data": audit_data
        })

    except Exception as e:
        print(f"ERROR in start_audit: {str(e)}")
        import traceback
        traceback.print_exc()
        supabase.table('pages').update({"audit_status": "Failed"}).eq('id', page_id).execute()
        return jsonify({"error": str(e)}), 500

        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-speed', methods=['POST'])
def analyze_speed():
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        page_id = data.get('page_id')
        strategy = data.get('strategy', 'mobile') # mobile or desktop
        
        if not page_id: return jsonify({"error": "page_id required"}), 400
        
        # Fetch Page
        page_res = supabase.table('pages').select('url, tech_audit_data').eq('id', page_id).single().execute()
        if not page_res.data: return jsonify({"error": "Page not found"}), 404
        page = page_res.data
        url = page['url']
        
        print(f"Running PageSpeed ({strategy}) for {url}...")
        
        # Call Google PageSpeed Insights API
        psi_key = os.environ.get("PAGESPEED_API_KEY")
        psi_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy={strategy}"
        if psi_key:
            psi_url += f"&key={psi_key}"
            
        psi_res = requests.get(psi_url, timeout=120)
        
        if psi_res.status_code != 200:
            return jsonify({"error": f"PSI API Failed: {psi_res.text}"}), 400
            
        psi_data = psi_res.json()
        
        # Extract Metrics
        lighthouse = psi_data.get('lighthouseResult', {})
        audits = lighthouse.get('audits', {})
        categories = lighthouse.get('categories', {})
        
        score = categories.get('performance', {}).get('score', 0) * 100
        fcp = audits.get('first-contentful-paint', {}).get('displayValue')
        lcp = audits.get('largest-contentful-paint', {}).get('displayValue')
        cls = audits.get('cumulative-layout-shift', {}).get('displayValue')
        tti = audits.get('interactive', {}).get('displayValue')
        
        # Update DB
        current_data = page.get('tech_audit_data') or {}
        speed_data = current_data.get('speed', {})
        speed_data[strategy] = {
            "score": score,
            "fcp": fcp,
            "lcp": lcp,
            "cls": cls,
            "tti": tti,
            "last_run": int(time.time())
        }
        current_data['speed'] = speed_data
        
        supabase.table('pages').update({"tech_audit_data": current_data}).eq('id', page_id).execute()
        
        return jsonify({
            "message": "Speed analysis complete",
            "data": speed_data[strategy]
        })
        
    except Exception as e:
        print(f"Speed Audit Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/update-page-status', methods=['POST'])
def update_page_status():
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        page_id = data.get('page_id')
        updates = {}
        
        if 'funnel_stage' in data:
            updates['funnel_stage'] = data['funnel_stage']
            
        if 'page_type' in data:
            updates['page_type'] = data['page_type']
            
            # Auto-fetch title if classifying as Product and title is missing
            if data['page_type'] == 'Product':
                try:
                    # Get current page data
                    page_res = supabase.table('pages').select('url, tech_audit_data').eq('id', page_id).execute()
                    if page_res.data:
                        page = page_res.data[0]
                        tech_data = page.get('tech_audit_data') or {}
                        
                        if not tech_data.get('title') or tech_data.get('title') == 'Untitled Product':
                            print(f"Auto-fetching title for {page['url']}...")
                            try:
                                resp = requests.get(page['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                                if resp.status_code == 200:
                                    soup = BeautifulSoup(resp.content, 'html.parser')
                                    if soup.title and soup.title.string:
                                        raw_title = soup.title.string.strip()
                                        new_title = clean_title(raw_title)
                                        tech_data['title'] = new_title
                                        updates['tech_audit_data'] = tech_data
                                        print(f"Fetched title: {new_title}")
                            except Exception as scrape_err:
                                print(f"Scrape failed: {scrape_err}")
                except Exception as e:
                    print(f"Auto-fetch error: {e}")

        if 'approval_status' in data:
            updates['approval_status'] = data['approval_status']
            
        if not updates:
            return jsonify({"error": "No updates provided"}), 400
            
        supabase.table('pages').update(updates).eq('id', page_id).execute()
        return jsonify({"message": "Page updated successfully", "updates": updates})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import requests
from urllib.parse import urlparse

# ... (existing imports)

# Configure DataForSEO
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")

def get_ranking_keywords(target_url):
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        print("DataForSEO credentials missing.")
        return []

    try:
        # Clean URL to get domain (DataForSEO prefers domain without protocol)
        parsed = urlparse(target_url)
        domain = parsed.netloc if parsed.netloc else parsed.path
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Normalize the target URL for comparison (remove protocol, www, trailing slash)
        normalized_target = target_url.lower().replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')
        
        print(f"DEBUG: Looking for keywords for normalized URL: {normalized_target}")

        url = "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live"
        payload = [
            {
                "target": domain,
                "location_code": 2840, # US
                "language_code": "en",
                "filters": [
                    ["ranked_serp_element.serp_item.rank_absolute", ">=", 1],
                    "and",
                    ["ranked_serp_element.serp_item.rank_absolute", "<=", 10]
                ],
                "order_by": ["keyword_data.keyword_info.search_volume,desc"],
                "limit": 100  # Get more results to filter
            }
        ]
        headers = {
            'content-type': 'application/json'
        }

        response = requests.post(url, json=payload, auth=(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD), headers=headers)
        response.raise_for_status()
        data = response.json()

        page_keywords = []
        domain_keywords = []
        
        if data['tasks'] and data['tasks'][0]['result'] and data['tasks'][0]['result'][0]['items']:
            for item in data['tasks'][0]['result'][0]['items']:
                keyword = item['keyword_data']['keyword']
                volume = item['keyword_data']['keyword_info']['search_volume']
                
                # Get the ranking URL for this keyword
                ranking_url = item.get('ranked_serp_element', {}).get('serp_item', {}).get('url', '')
                # Normalize ranking URL the same way
                normalized_ranking = ranking_url.lower().replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')
                
                # Check if this keyword ranks for the specific page
                if normalized_ranking == normalized_target:
                    page_keywords.append(f"{keyword} (Vol: {volume})")
                    print(f"DEBUG: ✓ Page match: {keyword} ranks for {normalized_ranking}")
                elif normalized_ranking.startswith(domain):
                    domain_keywords.append(f"{keyword} (Vol: {volume})")
        
        # If we found page-specific keywords, return those (up to 5)
        if page_keywords:
            print(f"DEBUG: ✓ Found {len(page_keywords)} page-specific keywords for {target_url}")
            return page_keywords[:5]
        
        # Otherwise, return only 3 domain keywords as fallback
        if domain_keywords:
            print(f"DEBUG: ⚠ No page-specific keywords found. Using 3 domain-level keywords as fallback")
            return domain_keywords[:3]
        
        print(f"DEBUG: ✗ No keywords found at all for {target_url}")
        return []

    except Exception as e:
        print(f"DataForSEO Error: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.route('/api/process-job', methods=['POST'])
def generate_dynamic_outline(topic, research_context, project_loc, gemini_client):
    """Generates a structured JSON outline for the article based on research."""
    print(f"DEBUG: Generating Dynamic Outline for '{topic}'...", flush=True)
    
    prompt = f"""
    You are an expert Content Strategist. Create a detailed Outline for a "Best-in-Class" SEO article.
    TOPIC: {topic}
    TARGET AUDIENCE: {project_loc}
    RESEARCH BRIEF:
    {research_context[:15000]} 
    TASK:
    Create a logical H2 structure for a comprehensive 2500-4500 word article.
    REQUIRED SECTIONS:
    1. "Introduction" - Hook with a relatable problem, Quick Answer box (2-3 sentence TL;DR), then thesis
    2. A "Common Problems/Mistakes" section - Frame as USER problems (e.g., "Why Most X Fail"), NOT as "How This Article Is Different"
    3. A "Self-Diagnosis/Framework" section - Actionable tool for readers to identify their situation
    4. "Detailed Breakdown" - Models/Types/Categories with specific comparisons
    5. "ROI & Hidden Costs" - Financials/Risks/Realistic timelines
    6. "Conclusion & Action Steps" - Clear next steps, NOT generic summary
    7. "FAQ" (Schema-ready) - 3-5 questions people actually search
    CRITICAL RULES:
    - Frame ALL headers as USER PROBLEMS, not self-promotion
    - BAD: "Why This Article Is Different" / "How We Provide Better Advice"
    - GOOD: "Why Most Vegan Eye Creams Don't Work for Indian Skin" / "Common Mistakes When Choosing X"
    - NO meta-commentary about the article itself
    - Headers should be search-query-aligned (what users would type in Google)
    OUTPUT FORMAT (JSON ARRAY):
    [
        {{"title": "Introduction", "instructions": "Hook with relatable problem. Include **Quick Answer:** box with 2-3 sentence summary. State thesis."}},
        {{"title": "Why Most X Fail for [Audience]", "instructions": "Problem-focused section. Use research data to explain common issues."}},
        ...
    ]
    """
    
    try:
        response = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-pro",
            use_grounding=False # Logic only
        )
        
        # Clean JSON
        if not response: return []
        cleaned = response.strip()
        if cleaned.startswith('```json'): cleaned = cleaned[7:]
        if cleaned.startswith('```'): cleaned = cleaned[3:]
        if cleaned.endswith('```'): cleaned = cleaned[:-3]
        
        import json
        return json.loads(cleaned.strip())
    except Exception as e:
        print(f"Error generating outline: {e}")
        # Fallback Outline
        return [
            {"title": "Introduction", "instructions": "Introduction to the topic."},
            {"title": "Key Concepts", "instructions": "Explain the core concepts."},
            {"title": "Detailed Analysis", "instructions": "Deep dive into the details."},
            {"title": "Comparison", "instructions": "Compare options."},
            {"title": "Conclusion", "instructions": "Wrap up."}
        ]

def generate_sections_chunked(topic, outline, research_context, project_loc, gemini_client, links_str):
    """Generates the article section by section based on the outline."""
    full_content = []
    import re
    
    print(f"DEBUG: Starting Chunked Generation for '{topic}' ({len(outline)} sections)...", flush=True)
    
    # Context Window Management (Keep it relevant)
    previous_section_summary = "Start of article."
    
    # Smart Link Tracking
    links_inserted_count = 0
    target_links = 7  # Target 7 internal links across the article
    link_cap = 8  # Never exceed 8 links
    
    for i, section in enumerate(outline):
        section_title = section.get('title', f"Section {i+1}")
        instructions = section.get('instructions', '')
        
        print(f"  > Generating Section {i+1}/{len(outline)}: {section_title}...", flush=True)
        
        # Smart Linking Logic
        link_instruction = ""
        if links_str and links_str != "No internal links available":
            remaining_sections = len(outline) - (i + 1)
            needed_links = target_links - links_inserted_count
            
            if links_inserted_count >= link_cap:
                link_instruction = "9. **Internal Links**: Do NOT include any more internal links (cap reached)."
            elif needed_links > 0:
                if needed_links >= remaining_sections:  # Must insert now to hit target
                    link_instruction = f"9. **Internal Links (REQUIRED)**: You MUST include EXACTLY 1 internal link in this section from the links below. Use natural, descriptive anchor text (NOT 'click here'). Links: {links_str}"
                else:  # Encourage but don't force
                    link_instruction = f"9. **Internal Links (Encouraged)**: Try to naturally include 1 internal link from: {links_str}. Use descriptive anchor text."
            else:
                link_instruction = "9. **Internal Links**: Optional - only if highly relevant."
        else:
            link_instruction = "9. **Internal Links**: No internal links available."
        
        prompt = f"""
        You are an expert Senior Technical Writer. Write ONE section of a comprehensive SEO guide.
        TOPIC: {topic}
        CURRENT SECTION: {section_title}
        INSTRUCTIONS: {instructions}
        CONTEXT:
        - Audience Location: {project_loc}
        - Tone: Authoritative, Data-Driven, Expert
        - Previous Section Summary: {previous_section_summary}
        RESEARCH DATA (Use strictly):
        {research_context[:10000]}
        WRITING RULES:
        1. Use Markdown (H2 for the section title, H3/H4 for subsections).
        2. NO INTRO/OUTRO FLUFF. Dive straight into the content.
        3. Use Bullet points, Data tables, and Bold text for readability.
        4. If mentioning a competitor/product from research, be specific (Pros/Cons).
        5. LENGTH: 400-600 words for this section.
        6. NEVER write self-referential statements like "This article is different", "This guide provides", 
           or "Unlike other articles". Just demonstrate expertise through content.
        7. If this is the INTRODUCTION: Include a "**Quick Answer:**" box at the start with a 2-3 sentence summary.
        8. Frame problems as USER problems ("Why X fails for you") NOT self-promotion ("How we help").
        {link_instruction}
        """
        
        try:
            section_content = gemini_client.generate_content(
                prompt=prompt,
                model_name="gemini-2.5-pro",
                use_grounding=True 
            )
            
            if section_content:
                # Clean up
                if section_content.startswith('```markdown'): section_content = section_content[11:]
                if section_content.startswith('```'): section_content = section_content[3:]
                if section_content.endswith('```'): section_content = section_content[:-3]
                
                full_content.append(section_content.strip())
                
                # Count links inserted in this chunk
                links_in_chunk = len(re.findall(r'\[.*?\]\(https?://.*?\)', section_content))
                links_inserted_count += links_in_chunk
                print(f"DEBUG: Section {i+1} generated {links_in_chunk} links. Total: {links_inserted_count}/{target_links}", flush=True)
                
                # Update summary for next chunk (simple context propagation)
                previous_section_summary = f"Just covered {section_title}. Key points: {section_content[:200]}..."
            else:
                full_content.append(f"## {section_title}\n\n(Content generation failed for this section.)")
                
        except Exception as e:
            print(f"Error generating section '{section_title}': {e}")
            full_content.append(f"## {section_title}\n\n(Error generating content.)")
            
        # Rate limit pause
        import time
        time.sleep(2)
        
    return "\n\n".join(full_content)

def final_polish(full_content, topic, primary_keyword, cta_url, project_loc, gemini_client):
    """Assembles the chunks and adds a cohesive Intro, Outro, and Meta Description."""
    print(f"DEBUG: Polishing final article for '{topic}'...", flush=True)
    
    prompt = f"""
    You are an expert Editor. Assemble and Polish this article.
    
    TOPIC: {topic}
    PRIMARY KEYWORD: {primary_keyword}
    CTA URL: {cta_url}
    LOCATION: {project_loc}
    
    RAW CONTENT CHUNKS:
    {full_content[:25000]} 
    
    TASK:
    1. Write a **Killer Introduction** (H1 Title + Hook + Thesis).
       - H1 must contain "{primary_keyword}".
    2. Review the body content (passed above) and smooth out transitions if needed (but keep the bulk of it).
    3. Write a **High-Conversion Conclusion**.
       - Must end with a Call-to-Action (CTA) linking to: {cta_url}
    4. Write a **Meta Description** (155 chars, SEO optimized).
    
    OUTPUT FORMAT (Markdown):
    **Meta Description**: [Your Description Here]
    
    # [H1 Title]
    
    [Introduction]
    
    [Body Content - Inserted/Polished]
    
    [Conclusion + CTA]
    """
    
    try:
        final_text = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-pro",
            use_grounding=False # Editing task
        )
        return final_text if final_text else full_content
    except Exception as e:
        print(f"Error in final polish: {e}")
        return full_content

def generate_chunked_article(topic, research_context, outline, project_loc, project_lang, primary_keyword, kw_list, links_str, citations_str, gemini_client, cta_url=None):
    """Generates the article section-by-section to ensure length and depth."""
    print(f"DEBUG: Starting Chunked Generation for '{topic}' ({len(outline)} sections)...", flush=True)
    
    full_content = []
    previous_context = ""
    links_inserted_count = 0
    import re
    
    # Meta Description Generation (First Step)
    meta_prompt = f"""Write a compelling SEO Meta Description for an article about "{topic}".
    Primary Keyword: {primary_keyword}
    Target Audience: {project_loc}
    Length: 150-160 characters.
    """
    try:
        meta_desc = gemini_client.generate_content(meta_prompt, model_name="gemini-2.5-flash").strip()
        full_content.append(f"**Meta Description**: {meta_desc}\n\n")
    except: pass

    for i, section in enumerate(outline):
        print(f"DEBUG: Generating Section {i+1}/{len(outline)}: {section['title']}...", flush=True)
        
        # Special Instructions based on position
        special_instructions = ""
        if i == 0:
            special_instructions += "\n        - **TL;DR**: Include a '## Key Takeaways' section immediately after the introduction bullet points."
        
        if i == len(outline) - 1:
            special_instructions += """
        - **FINAL SECTION STRUCTURE (Strict Order)**:
          1. **Conclusion**: Write the conclusion text.
          2. **CTA**: Place the Mandatory CTA here (see link instructions).
          3. **FAQ**: Add a '## Frequently Asked Questions' section (6-8 Q&As).
          4. **References**: Add a '## References' section. List the citations used as a bulleted list of Markdown links.
            """

        # Smart Linking Logic
        link_instruction = ""
        if links_str and links_str != "No internal links available":
            remaining_sections = len(outline) - (i + 1)
            target_links = 7
            needed_links = target_links - links_inserted_count
            
            # Last Section: FORCE CTA
            if i == len(outline) - 1 and cta_url:
                 link_instruction = f"6. **CTA (CRITICAL)**: You MUST include a strong Call to Action linking to {cta_url} immediately after the Conclusion text (before the FAQ). Use anchor text like 'Get Started', 'View Pricing', or 'Learn More'."
            
            # Other Sections: Smart Distribution
            elif needed_links > 0:
                if needed_links >= remaining_sections: # Must insert now to hit target
                    link_instruction = f"6. **Internal Links**: You MUST include exactly 1 internal link in this section from: {links_str}. Use DYNAMIC anchor text."
                elif links_inserted_count >= 8: # Cap at 8
                    link_instruction = "6. **Internal Links**: Do NOT include any internal links in this section."
                else: # Encourage but don't force
                    link_instruction = f"6. **Internal Links**: Try to naturally include 1 internal link from: {links_str}. Use DYNAMIC anchor text."
            else:
                 link_instruction = "6. **Internal Links**: Do NOT include any internal links in this section."
        else:
            link_instruction = "6. **Internal Links**: No internal links available."

        chunk_prompt = f"""
        You are writing Section {i+1} of {len(outline)} for a deep, expert-level article.
        
        ARTICLE TOPIC: {topic}
        SECTION TITLE: {section['title']}
        SECTION GOAL: {section['instructions']}
        
        CONTEXT:
        - Location: {project_loc}
        - Language: {project_lang}
        - Primary Keyword: {primary_keyword}
        
        PREVIOUS CONTENT CONTEXT (Last 500 words):
        ... {previous_context[-2000:]} ...
        
        FULL RESEARCH BRIEF (Source of Truth):
        {research_context}
        
        INSTRUCTIONS:
        1. Write **350-500 words** for this section alone. Do NOT exceed 600 words.
        2. Be detailed and high-impact. NO FLUFF.
        3. Use Markdown formatting (tables, bolding, lists).
        4. **Strictly follow** the Research Brief for data/facts.
        5. **Blue Ocean & Gaps**: If this section covers gaps, highlight them aggressively.
        {link_instruction}
        7. **Citations**: Use citations from research: {citations_str}
        8. **Anti-Repetition**: Check 'PREVIOUS CONTENT CONTEXT'. Do NOT repeat points already made.
        {special_instructions}
        
        OUTPUT:
        Return ONLY the content for this section. Start with the H2 header: ## {section['title']}
        """
        
        try:
            chunk_text = gemini_client.generate_content(
                prompt=chunk_prompt,
                model_name="gemini-2.5-pro",
                use_grounding=True
            )
            
            if chunk_text:
                # Clean up
                cleaned_chunk = chunk_text.strip()
                if cleaned_chunk.startswith('```markdown'): cleaned_chunk = cleaned_chunk[11:]
                if cleaned_chunk.startswith('```'): cleaned_chunk = cleaned_chunk[3:]
                if cleaned_chunk.endswith('```'): cleaned_chunk = cleaned_chunk[:-3]
                
                full_content.append(cleaned_chunk)
                previous_context += "\n" + cleaned_chunk
                
                # Count links inserted
                links_in_chunk = len(re.findall(r'\[.*?\]\(.*?\)', cleaned_chunk))
                links_inserted_count += links_in_chunk
                print(f"DEBUG: Section {i+1} generated {links_in_chunk} links. Total: {links_inserted_count}", flush=True)
                
                # Small delay to be nice to API
                import time
                time.sleep(1)
            else:
                print(f"⚠ Empty response for section {section['title']}")
                
        except Exception as e:
            print(f"Error generating section {section['title']}: {e}")
            full_content.append(f"## {section['title']}\n\n(Content generation failed for this section. Please review.)")

    return "\n\n".join(full_content)

def process_job():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500

    try:
        # Step A: Fetch one pending job
        response = supabase.table('audit_results').select("*").eq('status', 'PENDING').limit(1).execute()
        
        if not response.data:
            return jsonify({"message": "No pending jobs"})
        
        job = response.data[0]
        job_id = job['id']
        target_url = job.get('url')
        if not target_url:
            target_url = 'example.com'
        
        # Step B: Lock (Update status to PROCESSING)
        supabase.table('audit_results').update({"status": "PROCESSING"}).eq('id', job_id).execute()
        
        # Step C: Work (Generate SEO audit)
        
        # 1. Get Keywords (Graceful degradation)
        keywords = get_ranking_keywords(target_url)
        keywords_str = ", ".join(keywords) if keywords else "No specific ranking keywords found."

        # 2. Generate Audit with Gemini
        # model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"Analyze SEO for {target_url}. It currently ranks for these top keywords: {keywords_str}. Based on this, suggest 3 new content topics."
        
        audit_result = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-flash"
        )
        
        if not audit_result:
            audit_result = "Audit generation failed."
        
        # Step D: Save (Update result and status to COMPLETED)
        supabase.table('audit_results').update({
            "status": "COMPLETED",
            "result": audit_result
        }).eq('id', job_id).execute()
        
        return jsonify({
            "id": job_id,
            "status": "COMPLETED",
            "result": audit_result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/write-article', methods=['POST'])
def write_article():
    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"error": "GEMINI_API_KEY not found"}), 500

    try:
        data = request.get_json()
        topic = data.get('topic')
        keywords = data.get('keywords', [])

        if not topic:
            return jsonify({"error": "Topic is required"}), 400

        # model = genai.GenerativeModel('gemini-2.5-flash')
        
        system_instruction = "You are an expert SEO content writer. Write a comprehensive, engaging 1,500-word blog post about the given topic. Use H2 and H3 headers. Format in Markdown. Include a catchy title."
        
        keywords_str = ', '.join(keywords) if keywords else 'relevant SEO keywords'
        full_prompt = f"{system_instruction}\n\nTopic: {topic}\nTarget Keywords: {keywords_str}"
        
        generated_text = gemini_client.generate_content(
            prompt=full_prompt,
            model_name="gemini-2.5-flash"
        )
        
        if not generated_text:
             return jsonify({"error": "Gemini generation failed"}), 500
             
        # Save to DB if project_id is present
        page_id = None
        project_id = data.get('project_id')
        
        if project_id and supabase:
            try:
                # Create slug
                slug = topic.lower().replace(' ', '-')
                slug = re.sub(r'[^a-z0-9-]', '', slug)
                
                # Insert page
                page_data = {
                    "project_id": project_id,
                    "url": f"topic://{slug}", # Virtual URL
                    "status": "COMPLETED",
                    "page_type": "Topic",
                    "content": generated_text.strip(),
                    "tech_audit_data": {
                        "title": topic,
                        "meta_description": "Generated by AgencyOS" 
                    },
                    "keyword_data": keywords
                }
                res = supabase.table('pages').insert(page_data).execute()
                if res.data:
                    page_id = res.data[0]['id']
            except Exception as e:
                print(f"Error saving topic page: {e}")

        return jsonify({"content": generated_text.strip(), "page_id": page_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

from bs4 import BeautifulSoup

# ... (existing imports)





import subprocess

def fetch_with_curl(url, use_chrome_ua=True):
    """Fetch URL using system curl to bypass TLS fingerprinting blocks. Returns (content, latency)."""
    try:
        # Use a delimiter to separate content from the time metric
        delimiter = "|||CURL_TIME|||"
        # Increased timeout to 30s for slow sites
        cmd = ['curl', '-L', '-s', '-w', f'{delimiter}%{{time_total}}', '--max-time', '30']
        
        if use_chrome_ua:
            cmd.extend([
                '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                '-H', 'Accept-Language: en-US,en;q=0.9',
                '-H', 'Referer: https://www.google.com/',
                '-H', 'Upgrade-Insecure-Requests: 1'
            ])
            
        cmd.append(url)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        
        # If failed with Chrome UA, retry without it (some sites like Akamai block fake UAs but allow curl)
        if use_chrome_ua and (result.returncode != 0 or not result.stdout or "Access Denied" in result.stdout):
            print(f"DEBUG: Chrome UA failed for {url}, retrying with default curl UA...")
            return fetch_with_curl(url, use_chrome_ua=False)
            
        if result.returncode == 0 and result.stdout:
            # Split content and time
            parts = result.stdout.rsplit(delimiter, 1)
            if len(parts) == 2:
                content = parts[0]
                try:
                    latency = float(parts[1])
                except:
                    latency = 0
                return content, latency
            else:
                return result.stdout, 0
        else:
            print(f"DEBUG: curl failed with code {result.returncode}: {result.stderr}")
            return None, 0
    except Exception as e:
        print(f"DEBUG: curl exception: {e}")
        return None, 0

def crawl_sitemap(domain, project_id, max_pages=200):
    """Recursively crawl sitemaps with anti-bot headers"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }
    
    base_domain = domain.rstrip('/') if domain.startswith('http') else f"https://{domain.rstrip('/')}"
    sitemap_urls = []
    
    # 1. Try robots.txt first
    robots_url = f"{base_domain}/robots.txt"
    print(f"DEBUG: Fetching robots.txt: {robots_url}")
    try:
        robots_res = requests.get(robots_url, headers=headers, timeout=10)
        if robots_res.status_code == 200:
            for line in robots_res.text.splitlines():
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    sitemap_urls.append(sitemap_url)
            print(f"DEBUG: Found {len(sitemap_urls)} sitemaps in robots.txt")
    except Exception as e:
        print(f"DEBUG: Failed to fetch robots.txt: {e}")

    # 2. Fallback to common paths
    if not sitemap_urls:
        sitemap_urls = [
            f"{base_domain}/sitemap.xml",
            f"{base_domain}/sitemap_index.xml",
            f"{base_domain}/sitemap.php"
        ]

    pages = []
    
    # 3. Process each sitemap
    for sitemap_url in sitemap_urls:
        if len(pages) >= max_pages:
            break
        pages.extend(fetch_sitemap_urls(sitemap_url, project_id, headers, max_pages - len(pages)))
    
    return pages

def clean_title(title):
    """Clean up product titles by removing common e-commerce patterns."""
    if not title: return "Untitled Product"
    
    # Remove "Buy " from start (case insensitive)
    import re
    title = re.sub(r'^buy\s+', '', title, flags=re.IGNORECASE)
    
    # Remove " Online" from end (case insensitive)
    title = re.sub(r'\s+online$', '', title, flags=re.IGNORECASE)
    
    # Remove " - [Brand]" or " | [Brand]" suffix
    # Heuristic: split by " - " or " | " and take the first part if it's long enough
    separators = [" - ", " | ", " – "]
    for sep in separators:
        if sep in title:
            parts = title.split(sep)
            if len(parts[0]) > 3: # Avoid cutting too much if title is short
                title = parts[0]
                break
                
    return title.strip()

def fetch_sitemap_urls(sitemap_url, project_id, headers, max_urls):
    """Fetch URLs from a sitemap, recursively handling sitemap indexes"""
    print(f"DEBUG: Fetching sitemap: {sitemap_url}")
    pages = []
    
    try:
        # Use fetch_with_curl for robustness against bot protection
        content, latency = fetch_with_curl(sitemap_url)
        
        # Fallback to requests if curl fails
        if not content:
            print(f"DEBUG: curl failed for {sitemap_url}, falling back to requests...")
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                resp = requests.get(sitemap_url, headers=headers, timeout=30)
                if resp.status_code == 200:
                    content = resp.text
                    latency = resp.elapsed.total_seconds()
                    print(f"DEBUG: requests fallback successful for {sitemap_url}")
            except Exception as req_err:
                print(f"DEBUG: requests fallback failed: {req_err}")
        
        if not content:
            print(f"DEBUG: Failed to fetch {sitemap_url} (curl and requests failed)")
            return pages

        # Try parsing with XML, fallback to HTML parser if needed
        try:
            soup = BeautifulSoup(content, 'xml')
        except:
            soup = BeautifulSoup(content, 'html.parser')
        
        # Check if this is a sitemap index (contains <sitemap> tags)
        sitemap_tags = soup.find_all('sitemap')
        
        if sitemap_tags:
            # Recursively fetch ALL child sitemaps (removed limit of 5)
            for i, sitemap_tag in enumerate(sitemap_tags):
                if len(pages) >= max_urls:
                    break
                    
                loc = sitemap_tag.find('loc')
                if loc:
                    child_url = loc.text.strip()
                    print(f"DEBUG: Recursively fetching child sitemap {i+1}: {child_url}")
                    
                    # Rate Limit: Sleep 2 seconds between sitemaps to avoid 429/Blocking
                    import time
                    time.sleep(2)
                    
                    child_pages = fetch_sitemap_urls(child_url, project_id, headers, max_urls - len(pages))
                    
                    if not child_pages:
                        print(f"DEBUG: Warning - Child sitemap {child_url} returned 0 pages. Possible block?")
                        
                    pages.extend(child_pages)
        else:
            # Regular sitemap with <url> tags
            url_tags = soup.find_all('url')
            print(f"DEBUG: Found {len(url_tags)} URLs in sitemap")
            
            for tag in url_tags:
                if len(pages) >= max_urls:
                    break
                    
                loc = tag.find('loc')
                if loc and loc.text.strip():
                    url = loc.text.strip()
                    
                    # Skip title scraping for speed. 
                    # User can run "Perform Audit" to get details.
                    title = "Pending Scan"

                    pages.append({
                        'project_id': project_id,
                        'url': url,
                        'status': 'DISCOVERED',
                        'tech_audit_data': {'title': title} 
                    })
    
    except Exception as e:
        print(f"DEBUG: Error fetching sitemap {sitemap_url}: {e}")
    
    return pages


# Helper function to upload to Supabase Storage
def upload_to_supabase(file_data, filename, bucket_name='photoshoots'):
    """
    Uploads file data (bytes) to Supabase Storage and returns the public URL.
    """
    import mimetypes
    try:
        # Guess mime type
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
            
        # Upload
        res = supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=file_data,
            file_options={"content-type": mime_type, "upsert": "true"}
        )
        
        # Get Public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(filename)
        return public_url
    except Exception as e:
        print(f"Supabase Upload Error: {e}")
        raise e

# Helper to load image from URL or Path
def load_image_data(source):
    """
    Loads image data from a URL (starts with http) or local path.
    Returns PIL Image object.
    """
    import PIL.Image
    import io
    import os
    if source.startswith('http'):
        print(f"Downloading image from URL: {source}")
        resp = requests.get(source)
        resp.raise_for_status()
        return PIL.Image.open(io.BytesIO(resp.content))
    else:
        # Assume local path relative to public
        # Handle cases where source might be just filename or /uploads/filename
        clean_path = source.lstrip('/')
        local_path = os.path.join(os.getcwd(), 'public', clean_path)
        print(f"Loading image from local path: {local_path}")
        if os.path.exists(local_path):
            return PIL.Image.open(local_path)
        else:
            # Try absolute path just in case
            if os.path.exists(source):
                return PIL.Image.open(source)
            raise Exception(f"Image not found at {source} or {local_path}")



@app.route('/api/get-projects', methods=['GET'])
def get_projects():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        # Fetch projects - OPTIMIZED: Select specific columns AND filter by source
        projects_res = supabase.table('projects').select('id, project_name, domain, language, location, focus, created_at').eq('source', 'saas').order('created_at', desc=True).execute()
        projects = projects_res.data if projects_res.data else []
        
        if not projects:
            return jsonify({"projects": []})
        
        # Fetch profiles for these projects
        try:
            profiles_res = supabase.table('business_profiles').select('*').execute()
            profiles_data = profiles_res.data if profiles_res.data else []
            profiles_map = {p['project_id']: p for p in profiles_data}
        except Exception as e:
            print(f"Error fetching profiles: {e}")
            profiles_map = {}
        
        # Calculate counts per project (OPTIMIZED: Batched fetch + In-memory aggregation)
        # This avoids N+1 query problem which causes slow loading
        from collections import defaultdict
        counts = defaultdict(int)
        classified_counts = defaultdict(int)
        
        pass # Page counting disabled to fix timeout

        # Merge and parse strategy plan
        final_projects = []
        for p in projects:
            try:
                profile = profiles_map.get(p['id'], {})
                
                # Parse Strategy Plan
                summary = profile.get('business_summary') or ''
                strategy_plan = ''
                if '===STRATEGY_PLAN===' in summary:
                    try:
                        parts = summary.split('===STRATEGY_PLAN===')
                        summary = parts[0].strip()
                        if len(parts) > 1:
                            strategy_plan = parts[1].strip()
                    except:
                        pass
                
                # USE PRE-COMPUTED COUNTS (from batched fetch above)
                # This avoids N+1 queries - just dictionary lookups, instant!
                page_count = counts.get(p['id'], 0)
                classified_count = classified_counts.get(p['id'], 0)
                
                # Construct the project object to return
                project_obj = {
                    "id": p['id'],
                    "project_name": p['project_name'],
                    "domain": p['domain'],
                    "language": p['language'],
                    "location": p['location'],
                    "focus": p['focus'],
                    "created_at": p['created_at'],
                    "business_summary": summary, # Cleaned summary
                    "strategy_plan": strategy_plan, # Extracted strategy
                    "ideal_customer_profile": profile.get('ideal_customer_profile'),
                    "brand_voice": profile.get('brand_voice'),
                    "primary_products": profile.get('primary_products'),
                    "competitors": profile.get('competitors'),
                    "unique_selling_points": profile.get('unique_selling_points'),
                    "page_count": page_count,
                    "classified_count": classified_count
                }
                final_projects.append(project_obj)
            except Exception as e:
                print(f"Error processing project {p.get('id')}: {e}")
                continue
            
        return jsonify({"projects": final_projects})
    except Exception as e:
        print(f"Critical error in get_projects: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-pages', methods=['GET'])
def get_pages():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        project_id = request.args.get('project_id')
        if not project_id:
            return jsonify({"error": "project_id is required"}), 400
        
        # Optimize: Select only necessary columns for the list view
        # We need tech_audit_data for the status/title, but we don't need the full body_content if it's huge.
        # However, Supabase select doesn't support "exclude".
        # Let's select explicit columns.
        response = supabase.table('pages').select('id, project_id, url, page_type, created_at, tech_audit_data, funnel_stage, source_page_id, content_description, keywords, product_action, research_data, content, seo_analysis').eq('project_id', project_id).order('id').execute()
        
        import sys
        print(f"DEBUG: get_pages for {project_id} found {len(response.data) if response.data else 0} pages.", file=sys.stderr)
        
        # DEBUG: Check data structure
        if response.data:
            print(f"DEBUG: get_pages first row keys: {response.data[0].keys()}", file=sys.stderr)
            print(f"DEBUG: get_pages first row tech_audit_data: {response.data[0].get('tech_audit_data')}", file=sys.stderr)
            
        return jsonify({"pages": response.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-page', methods=['DELETE'])
def delete_page():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    page_id = request.args.get('page_id')
    if not page_id:
        return jsonify({"error": "page_id is required"}), 400
        
    try:
        # Recursive delete function to handle children manually
        def delete_children(pid):
            # Find all children
            children = supabase.table('pages').select('id').eq('source_page_id', pid).execute()
            if children.data:
                for child in children.data:
                    delete_children(child['id'])
            
            # Delete the page itself
            supabase.table('pages').delete().eq('id', pid).execute()

        delete_children(page_id)
        
        return jsonify({"message": "Page and all children deleted successfully"})
    except Exception as e:
        print(f"Error deleting page: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-page-status', methods=['GET'])
def get_page_status():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        page_id = request.args.get('page_id')
        if not page_id:
            return jsonify({"error": "page_id is required"}), 400
            
        response = supabase.table('pages').select('id, product_action, audit_status').eq('id', page_id).single().execute()
        
        if not response.data:
            return jsonify({"error": "Page not found"}), 404
            
        # Log the status being returned (to debug premature closing)
        print(f"DEBUG: get_page_status for {page_id}: {response.data.get('product_action')}", file=sys.stderr)
        
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-project', methods=['POST'])
def create_project():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    data = request.get_json()
    print(f"DEBUG: create_project called with data: {data}")
    domain = data.get('domain')
    project_name = data.get('project_name', domain)
    language = data.get('language', 'English')
    location = data.get('location', 'US')
    focus = data.get('focus', 'Product')
    
    if not domain:
        return jsonify({"error": "Domain is required"}), 400
        
    try:
        # 1. Create Project
        print(f"Creating project for {domain}...")
        project_res = supabase.table('projects').insert({
            "domain": domain,
            "project_name": project_name,
            "language": language,
            "location": location,
            "focus": focus,
            "source": "saas" # Explicitly tag as SaaS app project
        }).execute()
        
        if not project_res.data:
            raise Exception("Failed to create project")
            
        project_id = project_res.data[0]['id']
        print(f"Project created: {project_id}")
        
        # 2. Create Business Profile
        supabase.table('business_profiles').insert({
            "project_id": project_id,
            "domain": domain
        }).execute()
        
        return jsonify({
            "message": "Project created successfully",
            "project_id": project_id
        })
        
    except Exception as e:
        print(f"ERROR in create_project: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/classify-page', methods=['POST'])
def classify_page():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
        
    try:
        data = request.get_json()
        log_debug(f"DEBUG: classify_page received data: {data}")
        page_id = data.get('page_id')
        stage = data.get('stage') or data.get('funnel_stage')
        
        if not page_id or not stage:
            log_debug(f"DEBUG: Missing params. page_id={page_id}, stage={stage}")
            return jsonify({"error": "page_id and stage are required"}), 400
            
        # Try updating page_type instead of funnel_stage
        log_debug(f"DEBUG: Updating page_type to {stage} for {page_id}")
        
        update_data = {'page_type': stage}
        
        # ALWAYS set title from slug when moving to Product OR Category
        if stage == 'Product' or stage == 'Category':
            # Fetch current page data
            page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
            if page_res.data:
                page = page_res.data
                tech_data = page.get('tech_audit_data')
                
                # Robust JSON parsing
                if isinstance(tech_data, str):
                    try:
                        import json
                        tech_data = json.loads(tech_data)
                    except:
                        tech_data = {}
                elif not tech_data:
                    tech_data = {}
                
                # ALWAYS extract title from URL slug, no matter what
                new_title = get_title_from_url(page['url'])
                print(f"DEBUG: Setting title to '{new_title}' for {page['url']}")
                
                # Update tech_data
                tech_data['title'] = new_title
                update_data['tech_audit_data'] = tech_data
                print(f"DEBUG: update_data payload: {update_data}")
        
        supabase.table('pages').update(update_data).eq('id', page_id).execute()
        
        return jsonify({"message": f"Page classified as {stage}"})

    except Exception as e:
        log_debug(f"DEBUG: classify_page error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auto-classify', methods=['POST'])
def auto_classify():
    # Log to a separate file to ensure we see it
    with open('debug_classify.log', 'a') as f:
        f.write(f"DEBUG: ENTERING auto_classify\n")
    
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        if not project_id: return jsonify({"error": "project_id required"}), 400
        
        # Fetch all pages for project, ordered by ID to ensure "list order"
        res = supabase.table('pages').select('id, url, page_type, tech_audit_data').eq('project_id', project_id).order('id').execute()
        all_pages = res.data
        
        # Prioritize Unclassified pages
        unclassified_pages = [p for p in all_pages if p.get('page_type') in [None, 'Unclassified', 'Other', '']]
        
        # LIMIT: Only take the first 50 unclassified pages
        pages = unclassified_pages[:50]
        
        with open('debug_classify.log', 'a') as f:
            f.write(f"DEBUG: Total pages: {len(all_pages)}. Unclassified: {len(unclassified_pages)}. Processing batch of: {len(pages)}\n")
        
        updated_count = 0
        
        for p in pages:
            current_type = p.get('page_type')
            
            # Log every URL
            with open('debug_classify.log', 'a') as f:
                f.write(f"DEBUG: Processing {p['url']} | Type: {current_type}\n")

            # Allow overwriting if it's Unclassified, None, empty, OR 'Other'
            # We ONLY skip if it's already 'Product' or 'Category'
            if current_type in ['Product', 'Category']:
                with open('debug_classify.log', 'a') as f:
                    f.write(f"DEBUG: SKIPPING {p['url']} (Already {current_type})\n")
                continue
                
            url = p['url'].lower()
            new_type = None
            
            # 1. Check Technical Data (Most Accurate)
            tech_data = p.get('tech_audit_data') or {}
            og_type = tech_data.get('og_type', '').lower()
            
            if 'product' in og_type:
                new_type = 'Product'
            elif 'service' in og_type:
                new_type = 'Service'
            elif 'article' in og_type or 'blog' in og_type:
                new_type = 'Category'
            
            # 2. URL Heuristics (Fallback)
            if not new_type:
                # Strict Product
                if any(x in url for x in ['/product/', '/products/', '/item/', '/p/', '/shop/']):
                    new_type = 'Product'
                
                # Strict Service
                elif any(x in url for x in ['/service/', '/services/', '/solution/', '/solutions/', '/consulting/', '/offering/']):
                    new_type = 'Service'

                # Categories / Content
                elif any(x in url for x in ['/category/', '/categories/', '/c/', '/collection/', '/collections/', '/blog/', '/blogs/', '/article/', '/news/']):
                    new_type = 'Category'
                
                # Expanded Content (Generic E-commerce/Blog terms)
                # 'culture', 'trend', 'backstage', 'editorial', 'guide' are common content markers
                elif 'culture' in url or 'trend' in url or 'artistry' in url or 'how-to' in url or 'backstage' in url or 'collections' in url or 'editorial' in url or 'guide' in url:
                    new_type = 'Category'
                
                # Common Beauty/Fashion Categories (Generic)
                # lips, face, eyes, skincare, brushes are standard industry categories
                elif any(f"/{x}" in url for x in ['lips', 'face', 'eyes', 'brushes', 'skincare', 'bestsellers', 'new', 'sets', 'gifts']):
                    new_type = 'Category'
                
                # Keywords that imply a collection/list (Generic)
                elif 'shades' in url or 'colours' in url or 'looks' in url or 'inspiration' in url:
                    new_type = 'Category'
                
                # Generic "products" list pattern
                elif 'trending-products' in url or url.endswith('-products'):
                    new_type = 'Category'
            
            if new_type:
                with open('debug_classify.log', 'a') as f:
                    f.write(f"DEBUG: MATCH! {url} -> {new_type}\n")
            else:
                with open('debug_classify.log', 'a') as f:
                    f.write(f"DEBUG: NO MATCH for {url}\n")
            
            if new_type:
                supabase.table('pages').update({'page_type': new_type}).eq('id', p['id']).execute()
                updated_count += 1
                
        return jsonify({"message": f"Auto-classified {updated_count} pages", "count": updated_count})

    except Exception as e:
        print(f"Auto-classify error: {e}")
        return jsonify({"error": str(e)}), 500

def get_title_from_url(url):
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path
        # Get last non-empty segment
        segments = [s for s in path.split('/') if s]
        if not segments: return "Home"
        slug = segments[-1]
        # Convert slug to title (e.g., "my-page-title" -> "My Page Title")
        return slug.replace('-', ' ').replace('_', ' ').title()
    except:
        return "Untitled Page"

def scrape_page_details(url):
    """Scrape detailed technical data for a single page."""
    import requests
    from bs4 import BeautifulSoup
    import time
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
    }
    
    data = {
        'status_code': 0,
        'title': '',
        'meta_description': '',
        'h1': '',
        'canonical': '',
        'word_count': 0,
        'og_title': '',
        'og_description': '',
        'has_schema': False,
        'missing_alt_count': 0,
        'missing_h1': False,
        'onpage_score': 0,
        'load_time_ms': 0,
        'checks': [],
        'error': None
    }
    
    try:
        # Rate Limit: Sleep 1 second before scraping to be polite
        time.sleep(1)
        
        start_time = time.time()
        
        # Use curl to bypass TLS fingerprinting
        content, latency = fetch_with_curl(url)
        data['load_time_ms'] = int(latency * 1000)
        
        if content:
            data['status_code'] = 200 # Assume 200 if curl returns content
            soup = BeautifulSoup(content, 'html.parser')
            
            # Title
            # Robust extraction: Find first title not in SVG/Symbol
            page_title = None
            
            # 1. Try head > title first
            head_title = soup.select_one('head > title')
            if head_title and head_title.string:
                page_title = head_title
            
            # 2. Fallback: Search all titles and filter
            if not page_title:
                all_titles = soup.find_all('title')
                for t in all_titles:
                    # Check if parent or grandparent is SVG-related
                    parents = [p.name for p in t.parents]
                    if not any(x in ['svg', 'symbol', 'defs', 'g'] for x in parents):
                        page_title = t
                        break
            
            if page_title:
                data['title'] = page_title.get_text(strip=True)
            else:
                data['title'] = get_title_from_url(url)
                
            data['title_length'] = len(data['title'])
            
            # Meta Description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                data['meta_description'] = meta_desc.get('content', '').strip()
                data['description_length'] = len(data['meta_description'])
                
            # H1
            h1 = soup.find('h1')
            if h1:
                data['h1'] = h1.get_text(strip=True)
            else:
                data['missing_h1'] = True
                data['checks'].append("Missing H1")
                
            # Canonical
            canonical = soup.find('link', attrs={'rel': 'canonical'})
            if canonical:
                data['canonical'] = canonical.get('href', '').strip()
            else:
                # Fallback regex for malformed HTML
                import re
                match = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', content)
                if match:
                    data['canonical'] = match.group(1).strip()
                
            # Word Count (rough estimate)
            text = soup.get_text(separator=' ')
            data['word_count'] = len(text.split())
            
        # Click Depth (Proxy: URL Depth)
            # Count slashes after the domain. 
            # e.g. https://domain.com/ = 0
            # https://domain.com/page = 1
            # https://domain.com/blog/post = 2
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            data['click_depth'] = 0 if not path else len(path.split('/'))
            
            # OG Tags
            # Initialize with 'Missing' to allow fallback logic to work
            data['og_title'] = 'Missing'
            data['og_description'] = 'Missing'
            data['og_image'] = None

            og_title_tag = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'og:title'})
            if og_title_tag and og_title_tag.get('content'):
                data['og_title'] = og_title_tag['content'].strip()
            
            og_desc_tag = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'og:description'})
            if og_desc_tag and og_desc_tag.get('content'):
                data['og_description'] = og_desc_tag['content'].strip()
            
            og_image_tag = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
            if og_image_tag and og_image_tag.get('content'):
                data['og_image'] = og_image_tag['content'].strip()

            # FALLBACK: JSON-LD Schema (Common in Shopify/Wordpress if OG tags are missing/JS-rendered)
            if data['og_title'] == 'Missing' or data['og_description'] == 'Missing' or not data['og_image']:
                try:
                    import json
                    schemas = soup.find_all('script', type='application/ld+json')
                    for schema in schemas:
                        if not schema.string: continue
                        try:
                            json_data = json.loads(schema.string)
                            # Handle list of schemas
                            if isinstance(json_data, list):
                                items = json_data
                            else:
                                items = [json_data]
                                
                            for item in items:
                                # Prioritize Product, then Article, then WebPage
                                item_type = item.get('@type', '')
                                if isinstance(item_type, list): item_type = item_type[0] # Handle type as list
                                
                                if item_type in ['Product', 'Article', 'BlogPosting', 'WebPage']:
                                    if data['og_title'] == 'Missing' and item.get('name'):
                                        data['og_title'] = item['name']
                                        print(f"DEBUG: Recovered OG Title from Schema ({item_type})")
                                        
                                    if data['og_description'] == 'Missing' and item.get('description'):
                                        data['og_description'] = item['description']
                                        print(f"DEBUG: Recovered OG Desc from Schema ({item_type})")
                                        
                                    if not data['og_image'] and item.get('image'):
                                        img = item['image']
                                        if isinstance(img, list): img = img[0]
                                        elif isinstance(img, dict): img = img.get('url')
                                        data['og_image'] = img
                        except:
                            continue
                except Exception as e:
                    print(f"DEBUG: Schema parsing failed: {e}")

            # Schema
            schema = soup.find('script', type='application/ld+json')
            if schema: data['has_schema'] = True
            
            # Missing Alt Tags
            images = soup.find_all('img')
            for img in images:
                if not img.get('alt'):
                    data['missing_alt_count'] += 1
            
            # Calculate OnPage Score (Simple Heuristic)
            score = 100
            if data['missing_h1']: score -= 20
            if not data['title']: score -= 20
            if not data['meta_description']: score -= 20
            if data['missing_alt_count'] > 0: score -= min(10, data['missing_alt_count'] * 2)
            if data['word_count'] < 300: score -= 10
            if not data['og_title']: score -= 5
            if not data['og_description']: score -= 5
            
            data['onpage_score'] = max(0, score)
            
            # Technical Checks
            data['is_redirect'] = False # Cannot detect redirects easily with simple curl
            data['is_4xx_code'] = 400 <= data['status_code'] < 500
            data['is_5xx_code'] = 500 <= data['status_code'] < 600
            data['is_broken'] = data['status_code'] >= 400
            data['high_loading_time'] = data['load_time_ms'] > 30000 # Relaxed to 30s for Railway
            
            # Canonical Mismatch
            if data['canonical']:
                # Normalize URLs for comparison (remove trailing slash, etc)
                norm_url = url.rstrip('/')
                norm_canon = data['canonical'].rstrip('/')
                data['canonical_mismatch'] = norm_url != norm_canon
            else:
                data['canonical_mismatch'] = False # Or True if strict? Let's say False if missing.

    except Exception as e:
        data['error'] = str(e)
        data['is_broken'] = True
        print(f"Error scraping {url}: {e}")
        
    return data

def perform_tech_audit(project_id, limit=5):
    """Audit existing pages that are missing technical data."""
    print(f"Starting technical audit for project {project_id} (Limit: {limit})...")
    
    # 1. Get pages that need auditing (prioritize those without tech data)
    # Fetch all pages (or a large batch) and filter in python
    res = supabase.table('pages').select('id, url, tech_audit_data').eq('project_id', project_id).order('id').execute()
    all_pages = res.data
    
    # Filter for pages that have NO tech_audit_data, or "Pending Scan", or failed status (403/429)
    unaudited_pages = []
    for p in all_pages:
        tech = p.get('tech_audit_data') or {}
        status = tech.get('status_code')
        
        # Retry if:
        # 1. No data
        # 2. Title is missing or "Pending Scan"
        # 3. Status is Forbidden (403) or Rate Limited (429) or 0/None
        if not tech or \
           not tech.get('title') or \
           tech.get('title') == 'Pending Scan' or \
           status in [403, 429, 406, 0, None]:
            unaudited_pages.append(p)
            
    # Take the first 'limit' pages
    pages = unaudited_pages[:limit]
    print(f"DEBUG: Found {len(unaudited_pages)} unaudited pages. Processing first {len(pages)}.")
    
    audited_count = 0
    errors = []
    
    # Helper function for parallel execution
    def audit_single_page(p):
        try:
            url = p['url']
            print(f"DEBUG: Auditing {url}...")
            
            tech_data = scrape_page_details(url)
            # print(f"DEBUG: Scraped {url}. Status: {tech_data.get('status_code')}")
            
            # Merge with existing data
            existing_data = p.get('tech_audit_data') or {}
            existing_data.update(tech_data)
            
            # Update DB
            # print(f"DEBUG: Updating DB for {url}...")
            update_payload = {
                'tech_audit_data': existing_data
            }
            
            # Also update top-level columns if found
            if tech_data.get('title') and tech_data.get('title') != 'Pending Scan':
                update_payload['title'] = tech_data['title']
                
            if tech_data.get('meta_description'):
                update_payload['meta_description'] = tech_data['meta_description']
                
            supabase.table('pages').update(update_payload).eq('id', p['id']).execute()
            
            print(f"DEBUG: Successfully audited {url}")
            return True, p
        except Exception as e:
            print(f"ERROR: Failed to audit {p.get('url')}: {e}")
            # Mark error in object for reporting
            if not p.get('tech_audit_data'): p['tech_audit_data'] = {}
            p['tech_audit_data']['error'] = str(e)
            return False, p

    # Execute sequentially (User requested efficiency/stability over speed)
    for p in pages:
        success, result_p = audit_single_page(p)
        if success:
            audited_count += 1
        else:
            errors.append(result_p)
        
    print(f"Audit complete. Updated {audited_count} pages.")
    return audited_count, errors

@app.route('/api/run-project-setup', methods=['POST'])
def run_project_setup():
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    data = request.json
    project_id = data.get('project_id')
    do_audit = data.get('do_audit', False)
    do_tech_audit = data.get('do_tech_audit', False)
    do_profile = data.get('do_profile', False)
    max_pages = data.get('max_pages', 200)
    
    if not project_id:
        return jsonify({"error": "Project ID required"}), 400
        
    try:
        # 1. Tech Audit (Standalone)
        if do_tech_audit:
            count, errors = perform_tech_audit(project_id)
            
            msg = f"Audit complete. Updated {count} pages."
            if count == 0 and len(errors) > 0:
                msg += " (Check console for details)"
                
            return jsonify({
                "message": msg,
                "count": count,
                "details": [f"Failed: {p.get('url')}" for p in errors if p.get('tech_audit_data', {}).get('error')]
            })

        if not project_id: return jsonify({"error": "project_id required"}), 400
        
        # Fetch Project Details
        proj_res = supabase.table('projects').select('*').eq('id', project_id).execute()
        if not proj_res.data: return jsonify({"error": "Project not found"}), 404
        project = proj_res.data[0]
        domain = project['domain']
        
        print(f"Starting Setup for {domain} (Audit: {do_audit}, Tech Audit: {do_tech_audit}, Profile: {do_profile}, Max Pages: {max_pages})...")
        
        profile_data = {}
        strategy_plan = ""
        profile_insert = {} # Initialize to empty dict
        
        # 0. Technical Audit (Deep Dive) - NEW
        if do_tech_audit:
             print(f"[SCRAPER] Starting technical audit for project {project_id}...")
             try:
                 count = perform_tech_audit(project_id, limit=max_pages)
                 print(f"[SCRAPER] ✅ Technical audit completed successfully. Audited {count} pages.")
                 return jsonify({"message": f"Technical audit completed for {count} pages.", "pages_audited": count})
             except Exception as audit_error:
                 error_msg = f"Technical audit failed: {str(audit_error)}"
                 print(f"[SCRAPER] ❌ ERROR: {error_msg}")
                 import traceback
                 traceback.print_exc()
                 return jsonify({"error": error_msg}), 500


        # 1. Research Business (The Brain)
        if do_profile:
            print("Starting Gemini research...")
            # try:
            #     tools = [{'google_search': {}}]
            #     model = genai.GenerativeModel('gemini-2.0-flash-exp', tools=tools)
            # except:
            #     print("Warning: Google Search tool failed. Using standard model.")
            #     model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            prompt = f"""
            You are an expert business analyst. Research the website {domain} and create a comprehensive Business Profile.
            
            Context:
            - Language: {project.get('language')}
            - Location: {project.get('location')}
            - Focus: {project.get('focus')}
            
            I need you to find:
            1. Business Summary: What do they do? (1 paragraph)
            2. Ideal Customer Profile (ICP): Who are they selling to? Be specific.
            3. Brand Voice: How do they sound?
            4. Primary Products: List their main products/services.
            5. Competitors: List 3-5 potential competitors.
            6. Unique Selling Points (USPs): What makes them different?
            
            Return JSON:
            {{
                "business_summary": "...",
                "ideal_customer_profile": "...",
                "brand_voice": "...",
                "primary_products": ["..."],
                "competitors": ["..."],
                "unique_selling_points": ["..."]
            }}
            """
            
            text = gemini_client.generate_content(
                prompt=prompt,
                model_name="gemini-2.5-flash",
                use_grounding=True
            )
            
            if not text:
                raise Exception("Gemini generation failed for Business Profile")
            
            # Parse JSON
            import json
            if text.startswith('```json'): text = text[7:]
            if text.startswith('```'): text = text[3:]
            if text.endswith('```'): text = text[:-3]
            
            profile_data = json.loads(text.strip())
            
            # 2. Generate Content Strategy Plan
            print("Generating Strategy Plan...")
            strategy_prompt = f"""
            Based on this business profile:
            {json.dumps(profile_data)}
            
            **CONTEXT**:
            - Target Audience Location: {project.get('location')}
            - Target Language: {project.get('language')}
            
            Create a high-level Content Strategy Plan following the "Bottom-Up" approach:
            1. Bottom Funnel (BoFu): What product/service pages need optimization?
            2. Middle Funnel (MoFu): What comparison/best-of topics link to BoFu?
            3. Top Funnel (ToFu): What informational topics link to MoFu?
            
            Return a short markdown summary of the strategy.
            """
            strategy_plan = gemini_client.generate_content(
                prompt=strategy_prompt,
                model_name="gemini-2.5-flash",
                use_grounding=True
            )
            if not strategy_plan: strategy_plan = ""
            
            # Save Business Profile
            # WORKAROUND: Append Strategy Plan to Business Summary for persistence
            combined_summary = profile_data.get("business_summary", "")
            if strategy_plan:
                combined_summary += "\n\n===STRATEGY_PLAN===\n\n" + strategy_plan

            profile_insert = {
                "project_id": project_id,
                "business_summary": combined_summary,
                "ideal_customer_profile": profile_data.get("ideal_customer_profile"),
                "brand_voice": profile_data.get("brand_voice"),
                "primary_products": profile_data.get("primary_products"),
                "competitors": profile_data.get("competitors"),
                "unique_selling_points": profile_data.get("unique_selling_points")
            }
            
            # Check if exists, update or insert
            existing = supabase.table('business_profiles').select('id').eq('project_id', project_id).execute()
            if existing.data:
                supabase.table('business_profiles').update(profile_insert).eq('id', existing.data[0]['id']).execute()
            else:
                supabase.table('business_profiles').insert(profile_insert).execute()

        # 3. Crawl Sitemap (The Map)
        pages_to_insert = []
        
        if do_audit:
            print(f"Starting sitemap crawl (Audit enabled, Max Pages: {max_pages})...")
            pages_to_insert = crawl_sitemap(domain, project_id, max_pages=max_pages)
            
            if pages_to_insert:
                print(f"Found {len(pages_to_insert)} pages. syncing with DB...")
                
                # 1. Get existing URLs to avoid duplicates
                existing_res = supabase.table('pages').select('url, id, tech_audit_data').eq('project_id', project_id).execute()
                existing_map = {row['url']: row for row in existing_res.data}
                
                new_pages = []
                
                for p in pages_to_insert:
                    url = p['url']
                    if url in existing_map:
                        # Update existing page if title is missing or we have a better one
                        existing_row = existing_map[url]
                        existing_data = existing_row.get('tech_audit_data') or {}
                        new_data = p.get('tech_audit_data') or {}
                        
                        # If existing has no title, or we want to refresh it
                        if not existing_data.get('title') or new_data.get('title') != 'Untitled Product':
                            # Merge data
                            updated_data = existing_data.copy()
                            updated_data.update(new_data)
                            
                            # Only update if changed
                            if updated_data != existing_data:
                                print(f"Updating title for {url}")
                                supabase.table('pages').update({'tech_audit_data': updated_data}).eq('id', existing_row['id']).execute()
                    else:
                        new_pages.append(p)
                
                # 2. Insert only new pages
                if new_pages:
                    print(f"Inserting {len(new_pages)} new pages...")
                    batch_size = 100
                    for i in range(0, len(new_pages), batch_size):
                        batch = new_pages[i:i+batch_size]
                        supabase.table('pages').insert(batch).execute()
                    
                #3. Update project page_count field (DISABLED - column doesn't exist in schema)
                # total_pages = supabase.table('pages').select('*', count='exact').eq('project_id', project_id).execute()
                # supabase.table('projects').update({
                #     'page_count': total_pages.count
                # }).eq('id', project_id).execute()
                # print(f"Updated project page_count to {total_pages.count}")
                print(f"Inserted {len(new_pages)} new pages successfully.")
        else:
            print("Audit disabled. Skipping crawl.")
                
        return jsonify({
            "message": "Project setup complete",
            "profile": profile_insert,
            "strategy_plan": strategy_plan,
            "pages_found": len(pages_to_insert),
            "audit_run": do_audit
        })

    except Exception as e:
        print(f"Error in run_project_setup: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-funnel', methods=['POST'])
def generate_funnel():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
        
    try:
        data = request.get_json()
        page_id = data.get('page_id')
        project_id = data.get('project_id')
        current_stage = data.get('current_stage', 'BoFu') # Default to BoFu if not sent
        
        if not page_id or not project_id:
            return jsonify({"error": "page_id and project_id are required"}), 400
            
        # 1. Fetch Context
        profile_res = supabase.table('business_profiles').select('*').eq('project_id', project_id).execute()
        profile = profile_res.data[0] if profile_res.data else {}
        
        page_res = supabase.table('pages').select('*').eq('id', page_id).execute()
        page = page_res.data[0] if page_res.data else {}
        
        target_stage = "MoFu" if current_stage == 'BoFu' else "ToFu"
        
        print(f"Generating {target_stage} strategy for {page.get('url')}...")
        
        # 2. Prompt Gemini
        prompt = f"""
        You are a strategic SEO expert for this business:
        Summary: {profile.get('business_summary')}
        ICP: {profile.get('ideal_customer_profile')}
        
        We are building a Content Funnel.
        Current Page ({current_stage}): {page.get('title')} ({page.get('url')})
        
        Task: Generate 5 high-impact "{target_stage}" content ideas that will drive traffic to this Current Page.
        
        Definitions:
        - If Target is MoFu (Middle of Funnel): Generate "Comparison", "Best X for Y", or "Alternative to Z" articles. These help users evaluate options.
        - If Target is ToFu (Top of Funnel): Generate "How-to", "What is", or "Guide" articles. These help users understand the problem.
        
        Output JSON format:
        [
            {{
                "topic_title": "Title of the article",
                "primary_keyword": "Main SEO keyword",
                "rationale": "Why this drives traffic to the parent page"
            }}
        ]
        """
        
        # model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        
        text = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-flash",
            use_grounding=True
        )
        
        if not text:
            raise Exception("Gemini generation failed for Content Strategy")
            
        # Clean markdown
        if text.startswith('```json'): text = text[7:]
        if text.startswith('```'): text = text[3:]
        if text.endswith('```'): text = text[:-3]
        
        # 3. Parse and Save
        ideas = json.loads(text.strip())
        
        # 4. Enrich with DataForSEO (Optional)
        try:
            keywords = [idea.get('primary_keyword') for idea in ideas if idea.get('primary_keyword')]
            keyword_data = fetch_keyword_data(keywords)
        except Exception as e:
            print(f"DataForSEO Error: {e}")
            keyword_data = {}

        briefs_to_insert = []
        for idea in ideas:
            kw = idea.get('primary_keyword')
            data = keyword_data.get(kw, {})
            
            briefs_to_insert.append({
                "project_id": project_id,
                "topic_title": idea.get('topic_title'),
                "primary_keyword": kw,
                "rationale": idea.get('rationale'),
                "parent_page_id": page_id, 
                "status": "Proposed",
                "funnel_stage": target_stage,
                "meta_data": data # Store volume/kd here
            })
            
        if briefs_to_insert:
            supabase.table('content_briefs').insert(briefs_to_insert).execute()
            
            # SYNC TO PAGES TABLE (Fix for Dashboard Visibility)
            pages_to_insert = []
            for brief in briefs_to_insert:
                pages_to_insert.append({
                    "project_id": project_id,
                    "url": f"pending-slug-{uuid.uuid4()}", # Placeholder URL
                    "page_type": "Topic",
                    "funnel_stage": target_stage,
                    "source_page_id": page_id,
                    "tech_audit_data": {"title": brief['topic_title']},
                    "content_description": brief['rationale'],
                    "keywords": brief['primary_keyword']
                })
            
            if pages_to_insert:
                print(f"Syncing {len(pages_to_insert)} topics to pages table...")
                supabase.table('pages').insert(pages_to_insert).execute()
            
        return jsonify({
            "message": f"Generated {len(briefs_to_insert)} {target_stage} ideas",
            "ideas": briefs_to_insert
        })

    except Exception as e:
        print(f"Error in generate_funnel: {e}")
        return jsonify({"error": str(e)}), 500

def fetch_keyword_data(keywords):
    if not keywords: 
        print("No keywords provided to fetch_keyword_data")
        return {}
    
    login = os.environ.get('DATAFORSEO_LOGIN')
    password = os.environ.get('DATAFORSEO_PASSWORD')
    
    print(f"DataForSEO Login: {login}, Password: {'*' * len(password) if password else 'None'}")
    
    if not login or not password:
        print("DataForSEO credentials missing")
        return {}
        
    url = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"
    
    # We can use 'keyword_ideas' or 'keywords_for_site' or just 'search_volume'
    # 'search_volume' is best for specific lists.
    url = "https://api.dataforseo.com/v3/dataforseo_labs/google/historical_search_volume/live"
    
    payload = [{
        "keywords": keywords,
        "location_code": 2840, # US
        "language_code": "en"
    }]
    
    try:
        print(f"Fetching keyword data for {len(keywords)} keywords: {keywords[:3]}...")
        response = requests.post(url, auth=(login, password), json=payload)
        res_data = response.json()
        
        print(f"DataForSEO Response Status: {response.status_code}")
        print(f"DataForSEO Response: {res_data}")
        
        result = {}
        if res_data.get('tasks') and len(res_data['tasks']) > 0:
            task_result = res_data['tasks'][0].get('result')
            if task_result:
                for item in task_result:
                    kw = item.get('keyword')
                    vol = item.get('search_volume', 0)
                    result[kw] = {"volume": vol}
                    print(f"Keyword '{kw}': Volume = {vol}")
            else:
                print("No result in task")
        else:
            print("No tasks in response")
                
        return result
        
    except Exception as e:
        print(f"DataForSEO Request Failed: {e}")
        import traceback
        traceback.print_exc()
        return {}

def validate_and_enrich_keywords(ai_keywords_str, topic_title, min_volume=100):
    """
    Validates AI-generated keywords against DataForSEO search volume data.
    Replaces low-volume keywords with high-value alternatives.
    
    Args:
        ai_keywords_str: Comma-separated keyword string from AI
        topic_title: Topic title to use for finding alternatives if needed
        min_volume: Minimum monthly search volume threshold (default: 100)
    
    Returns:
        str: Comma-separated validated keywords with volume annotations
    """
    if not ai_keywords_str:
        return ""
    
    # Parse AI keywords
    ai_keywords = [k.strip() for k in ai_keywords_str.split(',') if k.strip()]
    if not ai_keywords:
        return ""
    
    print(f"Validating {len(ai_keywords)} AI keywords: {ai_keywords[:3]}...")
    
    # Fetch search volume data
    keyword_data = fetch_keyword_data(ai_keywords)
    
    # Filter and format keywords with volume
    validated_keywords = []
    for kw in ai_keywords:
        data = keyword_data.get(kw, {})
        volume = data.get('volume', 0)
        
        if volume >= min_volume:
            validated_keywords.append(f"{kw} (Vol: {volume})")
            print(f"✓ Kept '{kw}' - Volume: {volume}")
        else:
            print(f"✗ Rejected '{kw}' - Volume: {volume} (below threshold)")
    
    # If we have fewer than 3 good keywords, try to find alternatives
    if len(validated_keywords) < 3:
        print(f"Only {len(validated_keywords)} validated keywords. Searching for alternatives...")
        
        try:
            login = os.environ.get('DATAFORSEO_LOGIN')
            password = os.environ.get('DATAFORSEO_PASSWORD')
            
            if login and password:
                url = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"
                payload = [{
                    "keywords": [topic_title],
                    "location_code": 2840,
                    "language_code": "en",
                    "include_seed_keyword": False,
                    "filters": [
                        ["keyword_data.keyword_info.search_volume", ">=", min_volume]
                    ],
                    "order_by": ["keyword_data.keyword_info.search_volume,desc"],
                    "limit": 10
                }]
                
                response = requests.post(url, auth=(login, password), json=payload)
                res_data = response.json()
                
                if res_data.get('tasks') and res_data['tasks'][0].get('result'):
                    for item in res_data['tasks'][0]['result'][0].get('items', []):
                        kw = item['keyword']
                        volume = item['keyword_data']['keyword_info']['search_volume']
                        
                        # Avoid duplicates
                        if not any(kw.lower() in vk.lower() for vk in validated_keywords):
                            validated_keywords.append(f"{kw} (Vol: {volume})")
                            print(f"+ Added alternative '{kw}' - Volume: {volume}")
                            
                            if len(validated_keywords) >= 5:
                                break
        except Exception as e:
            print(f"Error fetching keyword alternatives: {e}")
    
    # Return top 5 validated keywords
    result = ', '.join(validated_keywords[:5])
    print(f"Final validated keywords: {result}")
    return result



def analyze_serp_for_keyword(keyword, location_code=2840):
    """
    Fetches top 10 SERP results for a keyword using DataForSEO.
    Returns competitor data: titles, URLs, ranking positions.
    """
    login = os.environ.get('DATAFORSEO_LOGIN')
    password = os.environ.get('DATAFORSEO_PASSWORD')
    
    if not login or not password:
        print("DataForSEO credentials missing for SERP analysis")
        return []
    
    try:
        url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
        payload = [{
            "keyword": keyword,
            "location_code": location_code,
            "language_code": "en",
            "device": "desktop",
            "depth": 10
        }]
        
        print(f"Analyzing SERP for '{keyword}'...")
        response = requests.post(url, auth=(login, password), json=payload)
        data = response.json()
        
        competitors = []
        if data.get('tasks') and data['tasks'][0].get('result') and data['tasks'][0]['result'][0].get('items'):
            for item in data['tasks'][0]['result'][0]['items']:
                if item.get('type') == 'organic':
                    competitors.append({
                        'url': item.get('url'),
                        'title': item.get('title'),
                        'position': item.get('rank_absolute'),
                        'domain': item.get('domain')
                    })
                    print(f"  #{item.get('rank_absolute')}: {item.get('domain')} - {item.get('title')}")
        
        print(f"Found {len(competitors)} competitors for '{keyword}'")
        return competitors
        
    except Exception as e:
        print(f"SERP analysis error for '{keyword}': {e}")
        import traceback
        traceback.print_exc()
        return []

        return []


def perform_gemini_research(topic, location="US", language="English"):
    """
    Uses Gemini 2.0 Flash with Google Search Grounding to perform free research.
    Returns structured data: {
        "competitors": [{"url": "...", "title": "...", "domain": "..."}],
        "keywords": [{"keyword": "...", "intent": "...", "volume": "N/A"}],
        "research_brief": "Markdown content...",
        "citations": ["url1", "url2"]
    }
    """
    log_debug(f"Starting Gemini 2.5 Flash Grounded Research for: {topic} (Loc: {location}, Lang: {language})")
    
    try:

        # Use gemini_client for pure REST API calls (No SDK)
        
        prompt = f"""
        Research the SEO topic: "{topic}"
        
        **CONTEXT**:
        - Target Audience Location: {location}
        - Target Language: {language}
        
        Perform a deep analysis using Google Search to find:
        1. Top 3 Competitor URLs ranking for this topic in **{location}**.
        2. **At least 30 SEO Keywords** relevant to this topic (include Search Intent).
           - Focus on keywords trending in **{location}**.
           - Mix of short-tail and long-tail.
           - Include "People Also Ask" style questions relevant to this region.
           
        **PRIORITIZATION RULES**:
        1. **Primary Focus**: Prioritize keywords specifically trending in **{location}**.
        2. **Global Keywords**: You MAY include high-volume US/Global keywords if they are highly relevant, but they must be secondary to local terms.
        3. **Relevance**: Ensure all keywords are actionable for a user in {location}.
        
        Output strictly in JSON format:
        {{
            "competitors": [
                {{"url": "https://...", "title": "Page Title", "domain": "domain.com"}}
            ],
            "keywords": [
                {{"keyword": "keyword phrase", "intent": "Informational/Commercial/Transactional"}}
            ]
        }}
        """
        
        text = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-flash",
            use_grounding=True
        )
        
        if not text:
            raise Exception("Empty response from Gemini REST API")
        
        # Clean markdown code blocks if present
        if text.startswith('```json'): text = text[7:]
        if text.startswith('```'): text = text[3:]
        if text.endswith('```'): text = text[:-3]
            
        return json.loads(text.strip())
        
    except Exception as e:
        log_debug(f"Gemini Research Failed: {e}")
        return None

def generate_image_prompt(topic, summary=""):
    """Generates an image prompt using Gemini."""
    prompt = f"""
    Create a detailed image generation prompt for a blog post titled: "{topic}"
    Summary: {summary[:500]}

    The image should be:
    - Visually matching the theme and tone of the article (e.g., if it's about nature, use natural elements; if tech, use modern tech aesthetics).
    - Strictly PHOTOREALISTIC, cinematic lighting, 8k resolution, highly detailed photography style.
    - NOT 3D render, NOT illustration, NOT cartoon.
    - No text in the image.
    - Aspect Ratio: 16:9

    Output ONLY the prompt text, no explanations.
    """
    try:
        return gemini_client.generate_content(prompt=prompt, model_name="gemini-2.5-flash")
    except Exception as e:
        print(f"Error generating image prompt: {e}")
        return f"A professional, modern header image for a blog post about {topic}, high quality, 4k, no text"


def research_with_perplexity(query, location="US", language="English", stage="MoFu"):
    """
    Conducts deep research using Perplexity's Sonar Pro model.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    
    if not api_key:
        log_debug("Perplexity API key missing - skipping research")
        print("Perplexity API key missing - skipping research")
        return {"research": "Perplexity API not configured", "citations": []}
    
    log_debug(f"Perplexity API key found: {api_key[:10]}...")
    
    # Define stage description
    stage_desc = "Middle-of-Funnel (MoFu)" if stage == "MoFu" else "Top-of-Funnel (ToFu)"
    
    try:
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar-pro",  # Using deep research model
            "max_tokens": 8000,  # Force longer, comprehensive responses
            "messages": [{
                "role": "user",
                "content": f"""**Role**: You are a Senior Content Strategist and Market Researcher conducting deep-dive competitive analysis.

**CRITICAL: LENGTH & DEPTH REQUIREMENTS**:
- This research brief MUST be MINIMUM 2500 words
- Each section requires DEEP ANALYSIS, not summaries
- Include SPECIFIC data points, prices, percentages, and citations
- Competitor analysis must include 3+ competitors with detailed strengths/weaknesses
- Content outline must have complete H2/H3/H4 structure with key points for EACH section

**Objective**: Create a comprehensive Research Brief for a {stage_desc} content asset. This must be the MOST authoritative resource on this topic, outranking all competitors with superior data, utility, and insight.

**CONTEXT**:
- Target Audience Location: {location}
- Target Language: {language}

**LOCALIZATION RULES (CRITICAL)**:
1. **Currency**: You MUST use the local currency for **{location}** (e.g., ₹ INR for India). Convert any research prices (like $) to the local currency using approximate current rates.
2. **Units**: Use the measurement system standard for **{location}**.
3. **Spelling**: Use the correct spelling dialect (e.g., "Colour" for UK/India).

{query}

**CRITICAL RULES**:
- GENERATE A COMPLETE BRIEF based on the provided data and your general knowledge
- Use the provided competitor URLs and scraped text as your primary source
- If specific data is missing, use INDUSTRY BENCHMARKS or GENERAL CATEGORY KNOWLEDGE relevant to **{location}**
- Do not refuse to generate sections - provide the best available estimates
- Format as markdown with ## headers

---

## 1. Strategic Overview

**Proposed Title**: [SEO-optimized H1 using "Best X for Y 2025" or "Product A vs B vs C" format]

**Search Intent**: [Analyze based on the provided keyword list: Informational/Commercial/Transactional]

**Format Strategy**: [Why this format fits the MoFu stage]

---

## 2. Key Insights & Benchmarks (The Evidence)

**Market Data & Specifications** (Extract from content or use category knowledge):
- [Key Feature/Spec 1]: [Value/Description]
- [Key Feature/Spec 2]: [Value/Description]
- [Price Range]: [Estimated category range]
- [User Ratings]: [Typical sentiment/rating]
- [Technical Specs]: [Ingredients, dimensions, etc.]

**Expert/Industry Concepts**:
- [Key Concept 1]: [Explanation]
- [Key Concept 2]: [Explanation]

---

## 3. Competitor Landscape & Content Gaps

**Competitor Analysis** (Based on provided URLs):
- **Competitor 1**: [Name/URL]
  - Strengths: [What they cover well]
  - Weaknesses: [What they miss]
- **Competitor 2**: [Name/URL]
  - Strengths: [What they cover well]
  - Weaknesses: [What they miss]

**The "Blue Ocean" Gap**: [The ONE angle or utility missing from the above competitors. E.g., "No one compares X vs Y directly" or "Missing detailed ingredient breakdown"]

---

## 4. Comprehensive Content Outline

**Type**: [Comparison Guide / Buying Guide / Ultimate Guide]

**Title**: [Final SEO-optimized H1]

**Detailed Structure**:

### H2: Introduction
- Hook: [Problem/Stat]
- Scope: [What's covered]

### H2: [Main Section 1 - Category Overview]
- H3: [Subtopic from keyword list]
  - **Key Point**: [Detail]
- H3: [Subtopic from keyword list]
  - **Key Point**: [Detail]

### H2: [Comparison Section]
- H3: Comparison Chart
  - **Columns**: [Attribute 1], [Attribute 2], [Attribute 3]
  - **Data Source**: [Competitor content or benchmarks]
- H3: [Product A] vs [Competitors]
  - **Differentiator**: [Specific advantage]

### H2: [Buying Guide / Selection Criteria]
- H3: Who is this for?
  - **User Type 1**: [Recommendation]
  - **User Type 2**: [Recommendation]

### H2: FAQ
- [Question from keyword list]: [Answer]
- [Question from keyword list]: [Answer]

### H2: Conclusion
- Final Recommendation
- CTA

---

## 5. Unique Ranking Hypothesis

[Explain why this content will outrank competitors based on the gaps identified above. Focus on: Better data, clearer structure, or more comprehensive scope.]

**GENERATE THE COMPLETE BRIEF NOW.**
"""
            }],
            "return_citations": True,
            "search_recency_filter": "month"
        }
        
        log_debug(f"Calling Perplexity API with query: {query[:50]}...")
        print(f"Researching with Perplexity: {query[:100]}...")
        # Increased timeout to 180s for deep research
        response = requests.post(url, headers=headers, json=payload, timeout=180)
        log_debug(f"Perplexity response status: {response.status_code}")
        
        data = response.json()
        
        if 'choices' in data and len(data['choices']) > 0:
            content = data['choices'][0]['message']['content']
            citations = data.get('citations', [])
            
            log_debug(f"✓ Perplexity success! {len(citations)} citations")
            print(f"✓ Research completed. Found {len(citations)} citations")
            for i, cite in enumerate(citations[:3]):
                print(f"  Citation {i+1}: {cite}")
            
            return {
                "research": content,
                "citations": citations
            }
        else:
            log_debug(f"Unexpected Perplexity response structure: {str(data)[:200]}")
            print(f"Unexpected Perplexity response: {data}")
            return {"research": "Research failed", "citations": []}
            
    except Exception as e:
        log_debug(f"Perplexity error: {type(e).__name__} - {str(e)}")
        print(f"Perplexity research error: {e}")
        import traceback
        traceback.print_exc()
        return {"research": f"Error: {str(e)}", "citations": []}


def get_keyword_ideas(seed_keyword, location_code=2840, min_volume=100, limit=20):
    """
    Gets keyword ideas from DataForSEO based on a seed keyword.
    Returns list of keywords scored by (Volume × CPC) / Competition.
    Prioritizes high-intent, low-competition opportunities.
    """
    login = os.environ.get('DATAFORSEO_LOGIN')
    password = os.environ.get('DATAFORSEO_PASSWORD')
    
    if not login or not password:
        print("DataForSEO credentials missing for keyword research")
        return []
    
    try:
        url = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"
        payload = [{
            "keywords": [seed_keyword],
            "location_code": location_code,
            "language_code": "en",
            "include_seed_keyword": True,
            "limit": 100
        }]
        
        print(f"Finding keyword ideas for '{seed_keyword}'...")
        log_debug(f"DataForSEO request: seed='{seed_keyword}', location={location_code}, min_vol={min_volume}")
        response = requests.post(url, auth=(login, password), json=payload, timeout=30)
        log_debug(f"DataForSEO status: {response.status_code}")
        data = response.json()
        
        keywords = []
        if data.get('tasks') and data['tasks'][0].get('result') and data['tasks'][0]['result'][0].get('items'):
            items = data['tasks'][0]['result'][0]['items']
            log_debug(f"DataForSEO returned {len(items)} items")
            
            for item in items:
                kw = item.get('keyword')
                
                # Robust extraction for info
                info = {}
                if 'keyword_info' in item:
                    info = item['keyword_info']
                elif 'keyword_data' in item and 'keyword_info' in item['keyword_data']:
                    info = item['keyword_data']['keyword_info']
                
                if not kw or not info:
                    log_debug(f"Skipping {kw}: Missing info")
                    continue
                    
                volume = info.get('search_volume', 0)
                if volume is None: volume = 0
                
                # Filter by min_volume in Python (can't use filters param)
                if volume < min_volume:
                    log_debug(f"Skipping {kw}: Low volume {volume} < {min_volume}")
                    continue
                
                cpc = info.get('cpc', 0.01) or 0.01
                competition = info.get('competition', 0.5) or 0.5
                
                # Smart scoring: (Volume × CPC) / Competition
                score = (volume * cpc) / max(competition, 0.1)
                
                keywords.append({
                    'keyword': kw,
                    'volume': volume,
                    'cpc': cpc,
                    'competition': competition,
                    'score': round(score, 2)
                })
        else:
            log_debug(f"DataForSEO returned NO items. Response structure: {str(data)[:300]}")
        
        # Sort by score (best opportunities first)
        keywords.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top N
        top_keywords = keywords[:limit]
        
        log_debug(f"Returning {len(top_keywords)} keywords (from {len(keywords)} total)")
        print(f"Found {len(keywords)} keywords, returning top {len(top_keywords)} by opportunity score:")
        for kw in top_keywords[:5]:
            print(f"  {kw['keyword']}: Vol={kw['volume']}, CPC=${kw['cpc']:.2f}, Comp={kw['competition']:.2f}, Score={kw['score']}")
        
        return top_keywords
        
    except Exception as e:
        print(f"Keyword research error: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_serp_competitors(keyword, location_code=2840, limit=5):
    """
    Gets top ranking URLs for a keyword using DataForSEO SERP API.
    Returns list of competitor URLs with titles and domains.
    """
    login = os.environ.get('DATAFORSEO_LOGIN')
    password = os.environ.get('DATAFORSEO_PASSWORD')
    
    if not login or not password:
        log_debug("DataForSEO credentials missing for SERP API")
        return []
    
    try:
        url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
        payload = [{
            "keyword": keyword,
            "location_code": location_code,
            "language_code": "en",
            "depth": 20,
            "device": "desktop"
        }]
        
        log_debug(f"SERP API: Finding competitors for '{keyword}'")
        response = requests.post(url, auth=(login, password), json=payload, timeout=30)
        log_debug(f"SERP API status: {response.status_code}")
        
        data = response.json()
        
        competitors = []
        if data.get('tasks') and data['tasks'][0].get('result'):
            results = data['tasks'][0]['result']
            if results and len(results) > 0 and results[0].get('items'):
                items = results[0]['items']
                log_debug(f"SERP API returned {len(items)} total items")
                
                for item in items:
                    if len(competitors) >= limit:
                        break
                        
                    # Only look at organic results
                    if item.get('type') != 'organic':
                        continue
                        
                    url_data = item.get('url')
                    title = item.get('title', '')
                    domain = item.get('domain', '')
                    
                    # Skip blocklisted domains
                    if any(b in domain for b in ['amazon', 'ebay', 'walmart', 'youtube', 'pinterest', 'instagram', 'facebook', 'reddit', 'quora']):
                        continue
                    
                    if url_data and domain:
                        competitors.append({
                            'url': url_data,
                            'title': title,
                            'domain': domain,
                            'position': item.get('rank_group', 0)
                        })
        
        log_debug(f"SERP API returned {len(competitors)} competitors")
        return competitors
        
    except Exception as e:
        log_debug(f"SERP API error: {type(e).__name__} - {str(e)}")
        print(f"SERP API error: {e}")
        return []


def get_ranked_keywords_for_url(target_url, location_code=2840, limit=100):
    """
    Gets keywords that a specific URL ranks for using DataForSEO Ranked Keywords API.
    This generates the keyword list format: "keyword | intent | secondary intent"
    """
    login = os.environ.get('DATAFORSEO_LOGIN')
    password = os.environ.get('DATAFORSEO_PASSWORD')
    
    if not login or not password:
        log_debug("DataForSEO credentials missing for Ranked Keywords API")
        return []
    
    try:
        url = "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live"
        payload = [{
            "target": target_url,
            "location_code": location_code,
            "language_code": "en",
            "limit": limit
            # Removed order_by - causes 40501 error
        }]
        
        log_debug(f"Ranked Keywords API: Getting keywords for '{target_url[:50]}...'")
        response = requests.post(url, auth=(login, password), json=payload, timeout=30)
        log_debug(f"Ranked Keywords API status: {response.status_code}")
        
        data = response.json()
        
        keywords = []
        if data.get('tasks') and data['tasks'][0].get('result'):
            results = data['tasks'][0]['result']
            if results and len(results) > 0 and results[0].get('items'):
                for item in results[0]['items']:
                    # Robust extraction for keyword
                    keyword = item.get('keyword_data', {}).get('keyword')
                    if not keyword:
                        keyword = item.get('keyword')
                    
                    # Robust extraction for position
                    position = 999
                    if 'metrics' in item and 'organic' in item['metrics']:
                        position = item['metrics']['organic'].get('pos_1', 999)
                    elif 'ranked_serp_element' in item:
                         position = item['ranked_serp_element'].get('serp_item', {}).get('rank_group', 999)
                    
                    # Debug filtering
                    domain = item.get('ranked_serp_element', {}).get('serp_item', {}).get('domain', 'unknown')
                    if position > 30:
                        log_debug(f"Skipping {domain}: Rank {position} > 30")
                        continue
                        
                    # Check blocklist
                    if any(b in domain for b in ['amazon', 'ebay', 'walmart', 'youtube', 'pinterest', 'instagram', 'facebook', 'reddit', 'quora']):
                        log_debug(f"Skipping {domain}: Blocklisted")
                        continue
                        
                    log_debug(f"Keeping {domain} (Rank {position})")
                    
                    # Classify intent
                    kw_lower = keyword.lower()
                    intents = []
                    
                    # Try to get intent from API
                    api_intent = item.get('keyword_data', {}).get('keyword_info', {}).get('search_intent')
                    if api_intent:
                        intent_str = api_intent
                    else:
                        # Fallback to rule-based
                        intents = []
                        if any(w in kw_lower for w in ['buy', 'price', 'shop', 'purchase', 'order', 'discount', 'sale', 'deal', 'cheap', 'cost']):
                            intents.append('transactional')
                        if any(w in kw_lower for w in ['best', 'top', 'review', 'vs', 'compare', 'alternative', 'guide', 'list', 'ranking']):
                            intents.append('commercial')
                        if any(w in kw_lower for w in ['what', 'how', 'benefits', 'made from', 'function', 'define', 'meaning', 'examples']):
                            intents.append('informational')
                        
                        if not intents:
                            intents.append('informational')
                        
                        intent_str = ', '.join(intents)
                    
                    if keyword:
                        keywords.append({
                            'keyword': keyword,
                            'intent': intent_str,
                            'position': position
                        })
        
        log_debug(f"Ranked Keywords API returned {len(keywords)} keywords")
        return keywords
        
    except Exception as e:
        log_debug(f"Ranked Keywords API error: {type(e).__name__} - {str(e)}")
        print(f"Ranked Keywords API error: {e}")
        return []






import uuid # Added for filename generation

@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        try:
            # Read file data
            file_data = file.read()
            filename = f"{uuid.uuid4()}_{file.filename}"
            
            # Upload to Supabase
            public_url = upload_to_supabase(file_data, filename)
            
            return jsonify({"url": public_url})
        except Exception as e:
            print(f"Upload error: {e}")
            return jsonify({"error": str(e)}), 500



@app.route('/api/generate-image', methods=['POST'])
def generate_image_endpoint():
    data = request.json
    prompt = data.get('prompt')
    input_image_url = data.get('input_image_url')
    
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        # 1. Enhance Prompt using Gemini (Text)
        # We can use the new client for this too, or stick to old one. 
        # Let's use the new client for consistency if possible, but mixing is fine for now to minimize risk.
        # Actually, let's just use the new client for image gen as tested.
        
        enhanced_prompt = prompt 
        # (Optional: Add enhancement logic back if needed, but for now direct is fine or we can re-add it)
        # The previous code used `model = genai.GenerativeModel("gemini-2.0-flash-exp")` from old SDK.
        # Let's keep the enhancement logic using the old SDK if it works, or switch to new.
        # To avoid conflict, let's just use the prompt directly for now to ensure image gen works, 
        # or use the new client for text generation too.
        
        UPLOAD_FOLDER = os.path.join('public', 'uploads')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        output_filename = f"gen_{uuid.uuid4()}.png"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        
        print(f"Generating image for prompt: {prompt}")
        
        result_path = gemini_client.generate_image(
            prompt=prompt,
            output_path=output_path,
            model_name="gemini-2.5-flash-image"
        )
        
        if not result_path:
            raise Exception("Gemini Image API failed")
            
        # Continue with existing logic (which expects output_filename)
        # We need to ensure the file exists at output_path, which generate_image does.
        
        UPLOAD_FOLDER = os.path.join('public', 'uploads')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        output_filename = f"gen_{uuid.uuid4()}.png"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        
        image_saved = False
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    data = part.inline_data.data
                    if isinstance(data, str):
                        image_data = base64.b64decode(data)
                    else:
                        image_data = data
                        
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    image_saved = True
                    break
        
        if not image_saved:
            return jsonify({'error': 'No image generated'}), 500

        # Return URL
        output_url = f"/uploads/{output_filename}"
        
        return jsonify({
            'output_image_url': output_url,
            'status': 'Done',
            'enhanced_prompt': prompt 
        })

    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({'error': str(e)}), 500







@app.route('/api/write-article-v2', methods=['POST'])
def write_article_v2():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
        
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        topic = data.get('topic')
        keyword = data.get('keyword')
        parent_page_id = data.get('parent_page_id') # The BoFu page to link to
        
        if not project_id or not topic:
            return jsonify({"error": "project_id and topic are required"}), 400
        
        # 1. Fetch Context
        profile_res = supabase.table('business_profiles').select('*').eq('project_id', project_id).execute()
        profile = profile_res.data[0] if profile_res.data else {}
        
        parent_page = {}
        if parent_page_id:
            page_res = supabase.table('pages').select('*').eq('id', parent_page_id).execute()
            parent_page = page_res.data[0] if page_res.data else {}
            
        print(f"Writing article '{topic}' for project {project_id}...")
            
        # 2. Construct Prompt
        prompt = f"""
        You are a professional content writer for this business:
        Summary: {profile.get('business_summary')}
        ICP: {profile.get('ideal_customer_profile')}
        Voice: {profile.get('brand_voice')}
        
        Task: Write a high-quality, SEO-optimized article.
        Title: {topic}
        Primary Keyword: {keyword}
        
        CRITICAL INSTRUCTION - INTERNAL LINKING:
        You MUST include a natural, persuasive link to our product page within the content.
        Product Page URL: {parent_page.get('url')}
        Product Name: {parent_page.get('title', 'our product')}
        
        The link should not be "Click here". It should be contextual, e.g., "For the best solution, check out [Product Name]." or "Many experts recommend [Product Name] for this."
        
        Format: Markdown.
        Structure:
        - H1 Title
        - Introduction (Hook the ICP)
        - Body Paragraphs (H2s and H3s)
        - Conclusion
        """
        
        # 3. Generate
        # model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        text = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-flash",
            use_grounding=True
        )
        
        if not text:
            raise Exception("Gemini generation failed for Content Strategy")
        
        content = text
        
        # Return content ONLY (No auto-save)
        return jsonify({
            "content": content,
            "meta": {
                "linked_to": parent_page.get('url')
            }
        })

    except Exception as e:
        print(f"Error in write_article_v2: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/save-article', methods=['POST'])
def save_article():
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        print(f"Saving article: {data.get('topic')} for project {data.get('project_id')}")
        
        project_id = data.get('project_id')
        topic = data.get('topic')
        content = data.get('content')
        keyword = data.get('keyword')
        parent_page_id = data.get('parent_page_id')
        
        # Check if brief exists
        existing = supabase.table('content_briefs').select('id').eq('project_id', project_id).eq('topic_title', topic).execute()
        
        if existing.data:
            print(f"Updating existing brief: {existing.data[0]['id']}")
            # Update
            brief_id = existing.data[0]['id']
            supabase.table('content_briefs').update({
                'content_markdown': content,
                'status': 'Draft'
            }).eq('id', brief_id).execute()
        else:
            print("Inserting new brief")
            # Insert new
            supabase.table('content_briefs').insert({
                'project_id': project_id,
                'topic_title': topic,
                'primary_keyword': keyword,
                'parent_page_id': parent_page_id,
                'content_markdown': content,
                'status': 'Draft',
                'funnel_stage': 'MoFu'
            }).execute()
            
        return jsonify({"message": "Article saved successfully"})
    except Exception as e:
        print(f"Error saving article: {e}")
        return jsonify({"error": str(e)}), 500

# ... (generate_image and crawl_project remain unchanged) ...

@app.route('/api/get-articles', methods=['GET'])
def get_articles():
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    project_id = request.args.get('project_id')
    if not project_id: return jsonify({"error": "project_id required"}), 400
    
    try:
        print(f"Fetching articles for project: {project_id}")
        res = supabase.table('content_briefs').select('*').eq('project_id', project_id).in_('status', ['Draft', 'Published']).execute()
        print(f"Found {len(res.data)} articles")
        return jsonify({"articles": res.data})
    except Exception as e:
        print(f"Error fetching articles: {e}")
        return jsonify({"error": str(e)}), 500

import time
import os

@app.route('/api/generate-image', methods=['POST'])
def generate_image():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        
        print(f"Generating image with Gemini 2.5 Flash Image for prompt: {prompt[:100]}...")
        
        # Use gemini_client
        UPLOAD_FOLDER = os.path.join('public', 'generated_images')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = f"gen_{int(time.time())}_{uuid.uuid4()}.png"
        output_path = os.path.join(UPLOAD_FOLDER, filename)
        
        result_path = gemini_client.generate_image(
            prompt=prompt,
            output_path=output_path,
            model_name="gemini-2.5-flash-image"
        )
        
        if not result_path:
            raise Exception("Gemini Image API failed")
            
        return jsonify({"image_url": f"/generated_images/{filename}"})

    except Exception as e:
        error_msg = f"Image generation failed: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500

def scrape_page_content(url):
    """
    Scrapes a URL and returns structured content including body text, title, and meta data.
    Uses Jina Reader as PRIMARY method (renders JavaScript, free, no API key).
    Falls back to BeautifulSoup + Gemini if Jina fails.
    """
    import requests
    import re
    from bs4 import BeautifulSoup

    try:
        print(f"Scraping content for: {url}")
        
        # --- PRIMARY METHOD: JINA READER ---
        # Jina renders JavaScript and returns clean markdown
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        raw_jina_content = None
        page_title = None
        meta_description = ""
        
        try:
            print("DEBUG: Trying Jina Reader...")
            response = requests.get(jina_url, headers=headers, timeout=45)
            
            if response.status_code == 200 and len(response.text) > 500:
                raw_jina_content = response.text
                print(f"DEBUG: Jina returned {len(raw_jina_content)} chars")
                
                # Extract title from Jina markdown (first H1)
                title_match = re.search(r'^#\s+(.+)$', raw_jina_content, re.MULTILINE)
                if title_match:
                    page_title = title_match.group(1).strip()
                
                # Try to extract title from the === underline format too
                if not page_title:
                    title_match2 = re.search(r'\n([^\n]+)\n=+\n', raw_jina_content)
                    if title_match2:
                        page_title = title_match2.group(1).strip()
        except Exception as je:
            print(f"DEBUG: Jina failed: {je}")
            raw_jina_content = None
        
        # --- CHUNKED GEMINI PROCESSING ---
        # Process content in chunks to avoid truncation while keeping Gemini's excellent formatting
        body_content = ""
        
        if raw_jina_content and len(raw_jina_content) > 500:
            # Pre-process: Remove footer sections before chunking
            content = raw_jina_content
            footer_markers = [
                # Keep only truly generic footer items. 
                # user reported 'Complete Your Routine' cuts off Ingredients/FAQ which follow it.
                r'\nJoin Our Community\n.*',
                r'\n## Footer\n.*',
            ]
            for pattern in footer_markers:
                match = re.search(pattern, content, flags=re.DOTALL)
                if match:
                    content = content[:match.start()]
            
            # Remove image markdown links
            content = re.sub(r'!\[Image \d+:[^\]]*\]\(https?://[^\)]+\)', '', content)
            content = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', content)
            
            print(f"DEBUG: Pre-cleaned content: {len(content)} chars")
            
            # Split into chunks (15K each to leave room for prompt)
            chunk_size = 15000
            chunks = []
            for i in range(0, len(content), chunk_size):
                chunks.append(content[i:i + chunk_size])
            
            print(f"DEBUG: Processing {len(chunks)} chunks with Gemini")
            
            processed_chunks = []
            for idx, chunk in enumerate(chunks):
                try:
                    if idx == 0:
                        # First chunk: Smart Start Detection + Formatting
                        prompt = f"""You are a precise content extractor. Your goal is to identify the MAIN PRODUCT CONTENT within this raw text and format it as clean Markdown.

CRITICAL INSTRUCTIONS:

1. **FIND THE START**: 
   - Skip "Cart", "Browse our Bestsellers" lists, Navigation menus, and Header links.
   - Start extracting from the **Main Product Title** (e.g., "Turmeric Shield | SPF 40 PA+++").

2. **FIND THE END**:
   - Keep ALL sections: Description, Benefits, Ingredients, How to Use, Clinical Results, Verified Reviews, FAQ.
   - Stop ONLY when you reach the generic site-wide footer (e.g. "Subscribe", "About 82°E", "Follow us").

3. **STRICT PRESERVATION**:
   - **NO CUTTING**: Do NOT remove any text within the main content boundaries.
   - **NO SUMMARIZING**: Output the content word-for-word.
   - **NO REORDERING**: Keep sections in their original sequence.

4. **FORMATTING**:
   - Use `#` for the Main Title.
   - Use `##` or `###` for section headers.
   - Use `**bold**` for labels.
   - Format lists with `-`.

CONTENT (Part {idx + 1} of {len(chunks)}):
{chunk}

Return the extracted and formatted markdown:"""
                    else:
                        # Subsequent chunks: Continuation with strict rules
                        prompt = f"""Continue processing this content.
RULES:
1. **NO HEADER/NAV REMOVAL** (This is a continuation chunk, so treat as body content).
2. **NO CUTTING / NO SUMMARIZING**.
3. **Format as clean Markdown**.
4. **Keep all Reviews, FAQs, Ingredients**.

CONTENT (Part {idx + 1} of {len(chunks)}):
{chunk}

Return the formatted markdown:"""
                    
                    result = gemini_client.generate_content(
                        prompt=prompt,
                        model_name="gemini-2.5-flash"
                    )
                    
                    if result:
                        cleaned = result.strip().replace('```markdown', '').replace('```', '').strip()
                        processed_chunks.append(cleaned)
                        print(f"DEBUG: Chunk {idx + 1}: {len(chunk)} chars -> {len(cleaned)} chars")
                    else:
                        # Fallback: use raw chunk
                        processed_chunks.append(chunk)
                        print(f"DEBUG: Chunk {idx + 1}: Gemini failed, using raw")
                        
                except Exception as e:
                    print(f"DEBUG: Chunk {idx + 1} error: {e}")
                    processed_chunks.append(chunk)
            
            # Concatenate all processed chunks
            body_content = "\n\n".join(processed_chunks)
            
            # Final cleanup
            body_content = re.sub(r'\n{4,}', '\n\n\n', body_content)
            
            print(f"DEBUG: Final content: {len(body_content)} chars")
        
        # --- FALLBACK: BeautifulSoup + Gemini ---
        if not body_content or len(body_content) < 200:
            print("DEBUG: Jina content insufficient, falling back to BeautifulSoup...")
            
            # Use Robust Scraper Helper
            content, status_code, final_url = fetch_html_robust(url)
            
            if status_code == 200 and content:
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract Title
                if not page_title:
                    if soup.title:
                        page_title = soup.title.get_text(strip=True)
                    elif soup.find('meta', attrs={'property': 'og:title'}):
                        page_title = soup.find('meta', attrs={'property': 'og:title'}).get('content')
                    elif soup.find('h1'):
                        page_title = soup.find('h1').get_text(strip=True)
                
                # Extract Meta Description
                meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
                if meta_desc:
                    meta_description = meta_desc.get('content', '')
                
                # Extract JSON-LD
                json_ld_content = ""
                try:
                    json_scripts = soup.find_all('script', type='application/ld+json')
                    for script in json_scripts:
                        if script.string:
                            try:
                                data = json.loads(script.string)
                                if isinstance(data, list):
                                    for item in data:
                                        if item.get('@type') == 'Product':
                                            json_ld_content += f"\nProduct: {item.get('name')}\nDescription: {item.get('description')}\n"
                                elif isinstance(data, dict) and data.get('@type') == 'Product':
                                    json_ld_content += f"\nProduct: {data.get('name')}\nDescription: {data.get('description')}\n"
                            except: pass
                except: pass
                
                # Clean and extract text
                for unwanted in soup(["script", "style", "svg", "noscript", "iframe", "nav", "footer", "aside"]):
                    unwanted.decompose()
                
                body_content = soup.get_text(separator='\n', strip=True)
                
                # Use Gemini for intelligent extraction if content is messy
                if len(body_content) > 1000:
                    try:
                        extraction_prompt = f"""Extract the main product/page content from this text. 
Remove navigation, headers, footers, and promotional noise.
Return clean markdown with:
- Product/Page Title
- Description
- Key features/benefits
- Ingredients (if product)
- How to use (if applicable)

Text:
{body_content[:8000]}"""
                        
                        gemini_result = gemini_client.generate_content(
                            prompt=extraction_prompt,
                            model_name="gemini-2.5-flash"
                        )
                        if gemini_result and len(gemini_result) > 200:
                            body_content = gemini_result.strip()
                            body_content = body_content.replace('```markdown', '').replace('```', '').strip()
                    except Exception as ge:
                        print(f"DEBUG: Gemini extraction failed: {ge}")
        
        # Final fallback for title
        if not page_title:
            page_title = url.split('/')[-1].replace('-', ' ').replace('_', ' ').title()
        
        if not body_content:
            body_content = "Could not extract meaningful content"
        
        return {
            "title": page_title,
            "body_content": body_content,
            "meta_description": meta_description,
            "json_ld": ""
        }

    except Exception as e:
        print(f"Scraping error: {e}")
        import traceback
        traceback.print_exc()
        return None

@app.route('/api/crawl-project', methods=['POST'])
def crawl_project_endpoint():
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
        
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        
        if not project_id:
            return jsonify({"error": "project_id is required"}), 400
            
        # Fetch domain from project
        project_res = supabase.table('projects').select('domain').eq('id', project_id).execute()
        if not project_res.data:
            return jsonify({"error": "Project not found"}), 404
            
        domain = project_res.data[0]['domain']
        
        print(f"Re-crawling project {project_id} ({domain})...")
        pages = crawl_sitemap(domain, project_id)
        
        if pages:
            supabase.table('pages').insert(pages).execute()
            
        return jsonify({
            "message": f"Crawl complete. Found {len(pages)} pages.",
            "pages_found": len(pages)
        })
    except Exception as e:
        print(f"Error crawling project: {e}")
        return jsonify({"error": str(e)}), 500


def generate_content_via_rest(prompt, api_key, model="gemini-2.5-pro", use_grounding=True):
    """
    Generate content using Gemini REST API directly to avoid SDK crashes.
    Supports Google Search Grounding.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    if use_grounding:
        data["tools"] = [{
            "google_search": {}  # Enable Google Search Grounding
        }]
        
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        # Extract text
        try:
            text = result['candidates'][0]['content']['parts'][0]['text']
            print(f"DEBUG: REST API Success. Text length: {len(text)}", flush=True)
            return text
        except (KeyError, IndexError):
            print(f"DEBUG: Unexpected REST response structure: {result}", flush=True)
            return None
            
    except Exception as e:
        print(f"DEBUG: REST API call failed: {e}")
        if 'response' in locals() and response is not None:
             print(f"DEBUG: Response content: {response.text}")
        raise e

# ============================================================
# SEO ANALYSIS FUNCTION & ENDPOINT
# ============================================================

def perform_seo_analysis(page_id):
    """
    Analyzes a page for SEO issues and returns structured recommendations.
    Returns JSON with critical_issues, ai_search_gaps, content_gaps, structure_issues, overall_score.
    """
    print(f"DEBUG: Starting SEO Analysis for page_id: {page_id}", flush=True)
    
    # Fetch page data
    page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
    if not page_res.data:
        return {"error": "Page not found"}
    
    page = page_res.data
    page_type = page.get('page_type', 'page')
    tech_data = page.get('tech_audit_data', {})
    body_content = tech_data.get('body_content', '')
    page_title = tech_data.get('title', page.get('url', ''))
    meta_desc = tech_data.get('meta_description', '')
    
    # Fetch project settings
    project_loc = 'US'
    project_lang = 'English'
    try:
        project_res = supabase.table('projects').select('location, language').eq('id', page['project_id']).single().execute()
        if project_res.data:
            project_loc = project_res.data.get('location', 'US')
            project_lang = project_res.data.get('language', 'English')
    except Exception as e:
        print(f"DEBUG: Error fetching project settings: {e}")
    
    if not body_content or len(body_content) < 100:
        return {
            "error": "Insufficient content for analysis. Scrape content first.",
            "overall_score": 0
        }
    
    # Build SEO Analysis Prompt
    prompt = f"""You are an expert SEO Analyst. Analyze this {page_type.upper()} page for SEO issues and gaps.

**PAGE DETAILS**:
- URL: {page.get('url', '')}
- Page Type: {page_type}
- Title: {page_title}
- Meta Description: {meta_desc}
- Location Target: {project_loc}
- Language: {project_lang}

**CURRENT PAGE CONTENT**:
{body_content[:8000]}

**ANALYZE FOR**:

1. **CRITICAL SEO ISSUES** (Must Fix):
   - Missing or poor H1 tag
   - Missing/weak meta description (should be 150-160 chars)
   - Keyword stuffing or no keyword focus
   - Missing alt text on images
   - Thin content (<300 words for products, <800 for articles)
   
2. **AI SEARCH OPTIMIZATION** (For Google AI Overview, Bing Copilot):
   - Missing FAQ sections (crucial for AI snippets)
   - No clear answer paragraphs (AI pulls concise answers)
   - Missing structured data opportunities
   - Lack of E-E-A-T signals (Experience, Expertise, Authority, Trust)
   
3. **CONTENT GAPS** (Based on {page_type}):
   - For Products: Missing specs, benefits, use cases, social proof
   - For Categories: Missing comparison points, buyer guides
   - For Blogs: Missing depth, citations, actionable advice
   
4. **INTERNAL LINKING**:
   - Missing opportunities to link to other pages
   
5. **STRUCTURE ISSUES**:
   - Poor heading hierarchy (H2, H3)
   - Wall of text without breaks
   - Missing bullet points or lists

**OUTPUT FORMAT** (Return ONLY valid JSON):
{{
    "critical_issues": [
        {{"issue": "...", "severity": "high|medium|low", "fix": "..."}}
    ],
    "ai_search_gaps": [
        {{"gap": "...", "recommendation": "..."}}
    ],
    "content_gaps": [
        {{"gap": "...", "suggestion": "..."}}
    ],
    "structure_issues": [
        {{"issue": "...", "fix": "..."}}
    ],
    "overall_score": 65,
    "summary": "Brief 2-sentence summary of the biggest problems"
}}
"""
    
    try:
        result = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-flash",
            use_grounding=False  # Pure analysis, no web search
        )
        
        if not result:
            return {"error": "SEO Analysis failed - empty response", "overall_score": 0}
        
        # Clean and parse JSON
        text = result.strip()
        if text.startswith('```json'): text = text[7:]
        if text.startswith('```'): text = text[3:]
        if text.endswith('```'): text = text[:-3]
        
        analysis = json.loads(text.strip())
        print(f"DEBUG: SEO Analysis complete. Score: {analysis.get('overall_score', 'N/A')}", flush=True)
        
        return analysis
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: Failed to parse SEO analysis JSON: {e}")
        return {"error": f"Failed to parse analysis: {e}", "overall_score": 0}
    except Exception as e:
        print(f"DEBUG: SEO Analysis error: {e}")
        return {"error": str(e), "overall_score": 0}


@app.route('/api/analyze-seo', methods=['POST'])
def analyze_seo_endpoint():
    """Endpoint to analyze a page for SEO issues."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.json
        page_id = data.get('page_id')
        
        if not page_id:
            return jsonify({"error": "page_id required"}), 400
        
        # Perform analysis
        analysis = perform_seo_analysis(page_id)
        
        if "error" in analysis and analysis.get("overall_score") == 0:
            return jsonify(analysis), 400
        
        # Save analysis to database
        supabase.table('pages').update({
            'seo_analysis': analysis
        }).eq('id', page_id).execute()
        
        return jsonify(analysis)
        
    except Exception as e:
        print(f"ERROR in analyze-seo: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/batch-update-pages', methods=['POST'])
def batch_update_pages():
    print(f"====== BATCH UPDATE PAGES CALLED ======", flush=True)
    log_debug("Entered batch_update_pages route")
    log_debug(f"Entered batch_update_pages route")
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.json
        log_debug(f"Received batch update data: {data}")
        page_ids = data.get('page_ids', [])
        action = data.get('action')
        
        if not page_ids or not action:
            return jsonify({"error": "page_ids and action required"}), 400
            
        if action == 'trigger_audit':
            # In a real app, this would trigger a background job
            supabase.table('pages').update({"audit_status": "Pending"}).in_('id', page_ids).execute()
            
        elif action == 'trigger_classification':
            supabase.table('pages').update({"classification_status": "Pending"}).in_('id', page_ids).execute()
            
        elif action == 'approve_strategy':
            supabase.table('pages').update({"approval_status": True}).in_('id', page_ids).execute()
            
        elif action == 'scrape_content':
            # Scrape existing content for selected pages
            for page_id in page_ids:
                page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
                if not page_res.data: continue
                page = page_res.data
                
                try:
                    scraped_data = scrape_page_content(page['url'])
                    
                    if scraped_data:
                        # Update tech_audit_data with body_content AND title
                        current_tech_data = page.get('tech_audit_data', {})
                        current_tech_data['body_content'] = scraped_data['body_content']
                        
                        if not current_tech_data.get('title') or current_tech_data.get('title') == 'Untitled':
                             current_tech_data['title'] = scraped_data['title'] or get_title_from_url(page['url'])
                        
                        supabase.table('pages').update({
                            "tech_audit_data": current_tech_data
                        }).eq('id', page_id).execute()
                        print(f"✓ Scraped content for {page['url']}")
                    else:
                        print(f"⚠ Failed to scrape {page['url']}")
                        
                except Exception as e:
                    print(f"Error scraping page {page_id}: {e}")
            
            return jsonify({"message": "Content scraped successfully"})
        elif action == 'generate_content':
            # Product/Category pages use gemini_client for SEO verification
            # Topic pages use gemini_client (no grounding needed - they have research already)
            
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return jsonify({"error": "GEMINI_API_KEY not found"}), 500

            def process_content_generation_background(page_ids, api_key):
                print(f"====== GENERATE_CONTENT BACKGROUND THREAD STARTED ======", flush=True)
                
                for page_id in page_ids:
                    try:
                        # 1. Get Page Data
                        page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
                        if not page_res.data: continue
                        page = page_res.data
                        
                        # 2. Get existing content
                        existing_content = page.get('tech_audit_data', {}).get('body_content', '')
                        if not existing_content:
                            # If no body content, try to scrape it now
                            try:
                                logging.info(f"DEBUG: No existing content for {page['url']}, attempting fresh scrape...")
                                scraped_data = scrape_page_content(page['url'])
                                if scraped_data and scraped_data.get('body_content'):
                                    existing_content = scraped_data['body_content']
                                    logging.info(f"DEBUG: Fresh scrape successful ({len(existing_content)} bytes)")
                                else:
                                    existing_content = "No content available"
                                    logging.info("DEBUG: Fresh scrape returned no content")
                            except Exception as e:
                                logging.error(f"Error scraping content for {page['url']}: {e}")
                                existing_content = "No content available"
                        
                        # 3. Generate improved content
                        page_title = page.get('tech_audit_data', {}).get('title', page.get('url', ''))
                        page_type = page.get('page_type', 'page')

                        # Fetch Project Settings for Localization
                        project_loc = 'US'
                        project_lang = 'English'
                        try:
                            log_debug(f"Fetching project settings for {page['project_id']}...")
                            project_res = supabase.table('projects').select('location, language').eq('id', page['project_id']).single().execute()
                            if project_res.data:
                                project_loc = project_res.data.get('location', 'US')
                                project_lang = project_res.data.get('language', 'English')
                            log_debug(f"Project settings: Loc={project_loc}, Lang={project_lang}")
                        except Exception as proj_err:
                            log_debug(f"Error fetching project settings: {proj_err}")
                        
                        try:
                            log_debug(f"Checking page type for branching: '{page_type}'")
                            
                            # Fetch Parent Page Context (for Internal Linking)
                            parent_context = ""
                            if page.get('source_page_id'):
                                try:
                                    # 1. Fetch Parent (MoFu)
                                    parent_res = supabase.table('pages').select('id, url, tech_audit_data, source_page_id').eq('id', page['source_page_id']).single().execute()
                                    if parent_res.data:
                                        p_data = parent_res.data
                                        p_title = p_data.get('tech_audit_data', {}).get('title', 'Related Page')
                                        p_url = p_data.get('url', '#')
                                        
                                        # 2. Fetch Grandparent (Product) if exists
                                        gp_context = ""
                                        if p_data.get('source_page_id'):
                                            try:
                                                gp_res = supabase.table('pages').select('url, tech_audit_data').eq('id', p_data['source_page_id']).single().execute()
                                                if gp_res.data:
                                                    gp_data = gp_res.data
                                                    gp_title = gp_data.get('tech_audit_data', {}).get('title', 'Main Product')
                                                    gp_url = gp_data.get('url', '#')
                                                    gp_context = f"\n    - ALSO link to the Main Product: [{gp_title}]({gp_url}) (Context: The ultimate solution)."
                                            except Exception:
                                                pass # Ignore grandparent errors

                                        parent_context = f"\n    **INTERNAL LINKING REQUIREMENT**:\n    - You MUST organically mention and link to the parent page: [{p_title}]({p_url}) (Context: Next step in learning).\n{gp_context}"
                                except Exception as parent_err:
                                    log_debug(f"Error fetching parent context: {parent_err}")

                            # ==============================================
                            # AUTO SEO ANALYSIS (for Product/Category pages)
                            # ==============================================
                            seo_issues_str = ""
                            seo_analysis = None
                            if page_type and page_type.lower().strip() in ['product', 'category']:
                                print(f"DEBUG: Running auto SEO analysis for {page_type} page...", flush=True)
                                try:
                                    seo_analysis = perform_seo_analysis(page_id)
                                    
                                    if seo_analysis and not seo_analysis.get('error'):
                                        # Format issues for the prompt
                                        issues_list = []
                                        
                                        # Critical issues
                                        for item in seo_analysis.get('critical_issues', []):
                                            issues_list.append(f"- {item.get('issue')}: {item.get('fix')}")
                                        
                                        # AI search gaps
                                        for item in seo_analysis.get('ai_search_gaps', []):
                                            issues_list.append(f"- {item.get('gap')}: {item.get('recommendation')}")
                                        
                                        # Content gaps
                                        for item in seo_analysis.get('content_gaps', []):
                                            issues_list.append(f"- {item.get('gap')}: {item.get('suggestion')}")
                                        
                                        # Structure issues
                                        for item in seo_analysis.get('structure_issues', []):
                                            issues_list.append(f"- {item.get('issue')}: {item.get('fix')}")
                                        
                                        if issues_list:
                                            seo_issues_str = "\n**SEO ISSUES TO FIX** (from analysis):\n" + "\n".join(issues_list[:10])  # Limit to top 10
                                            print(f"DEBUG: Found {len(issues_list)} SEO issues to fix. Score: {seo_analysis.get('overall_score')}", flush=True)
                                        
                                        # Save analysis to DB
                                        supabase.table('pages').update({
                                            'seo_analysis': seo_analysis
                                        }).eq('id', page_id).execute()
                                        
                                except Exception as seo_err:
                                    print(f"DEBUG: SEO analysis failed (non-blocking): {seo_err}", flush=True)
                                    seo_issues_str = ""

                            # BRANCHING LOGIC: Product vs Category vs Topic
                            generated_text = ""
                            if page_type and page_type.lower().strip() == 'product':
                                log_debug("Entered Product generation block")
                                # PRODUCT PROMPT (Sales & Conversion Focused - Conservative + Grounded)
                                prompt = f"""You are an expert E-commerce Copywriter with access to live Google Search.
                                
            **TASK**: Polish and enhance the content for this **PRODUCT PAGE**. 
            **CRITICAL GOAL**: Improve clarity and persuasion WITHOUT changing the original length or structure significantly.

            **CONTEXT**:
            - Target Audience Location: {project_loc}
            - Target Language: {project_lang}

            **LOCALIZATION RULES (CRITICAL)**:
            1. **Currency**: You MUST use the local currency for **{project_loc}** (e.g., ₹ INR for India). Convert prices if needed.
            2. **Units**: Use the measurement system standard for **{project_loc}**.
            3. **Spelling**: Use the correct spelling dialect (e.g., "Colour" for UK/India).
            4. **Cultural Context**: Use examples relevant to **{project_loc}**.

            **PAGE DETAILS**:
            - URL: {page['url']}
            - Title: {page_title}
            - Product Name: {page_title}

            **EXISTING CONTENT** (Source of Truth):
            ```
            {existing_content if existing_content else "No content"}
            ```
            {seo_issues_str}

            **INSTRUCTIONS**:
            1.  **Strict Polish (NO RESTRUCTURING)**: 
                -   Keep the **exact** original section order (Intro -> Benefits -> Clinical -> Ingredients -> FAQ -> Reviews).
                -   Do NOT merge sections or move them around.
                -   Do NOT remove any reviews or list items. If there are 10 reviews, keep 10.

            2.  **Maintain Length & Detail**: 
                -   The output must be **at least** the same length as the original. 
                -   Do NOT summarize or condense text.
                -   **CRITICAL**: If there is a list of details (e.g., "Ingredient X: Definition Y"), KEEP THE ENTIRE LIST. Do not turn it into a paragraph.
                -   Keep all technical details, ingredient lists, and specs exactly as is.

            3.  **Enhance, Don't Rewrite**: 
                -   Only fix grammar, flow, and punchiness.
                -   Add SEO keywords naturally where they fit, but don't rewrite entire paragraphs just to fit them.

            4.  **STRICT ACCURACY**: 
                -   **DO NOT CHANGE** technical specs, ingredients, dimensions, or "What's Inside".
                -   **DO NOT INVENT** features.

            5.  **Competitive Intelligence** (USE GROUNDING):
                -   Search for similar products to understand competitive positioning
                -   Verify any comparative claims ("best", "top-rated") against live data
                -   Identify unique selling points vs competitors

            **OUTPUT FORMAT** (Markdown):
            -   Return the full page content in Markdown.
            -   Include a **Meta Description** at the top.
            -   Keep the original formatting (H1, H2, bullets) but polished.
            """
                                # Use REST API for Products
                                print(f"DEBUG: Generating content for Product: {page_title} using gemini-2.5-pro (REST)", flush=True)
                                generated_text = generate_content_via_rest(
                                    prompt=prompt,
                                    api_key=api_key,
                                    model="gemini-2.5-pro",
                                    use_grounding=True
                                )
                            
                            elif page_type and page_type.lower() == 'category':
                                # CATEGORY PROMPT (Research-Backed SEO Enhancement - Grounded + Respect Length)
                                prompt = f"""You are an expert E-commerce Copywriter & SEO Specialist.

            **TASK**: Enhance this **CATEGORY/COLLECTION PAGE** using real-time search data.
            **CRITICAL GOAL**: infuse the content with high-value SEO keywords and competitive insights while respecting the original length and structure.

            **CONTEXT**:
            - Target Audience Location: {project_loc}
            - Target Language: {project_lang}

            **LOCALIZATION RULES (CRITICAL)**:
            1. **Currency**: You MUST use the local currency for **{project_loc}** (e.g., ₹ INR for India). Convert prices if needed.
            2. **Units**: Use the measurement system standard for **{project_loc}**.
            3. **Spelling**: Use the correct spelling dialect (e.g., "Colour" for UK/India).
            4. **Cultural Context**: Use examples relevant to **{project_loc}**.

            **PAGE DETAILS**:
            - URL: {page['url']}
            - Title: {page_title}
            - Category Name: {page_title}

            **EXISTING CONTENT** (Source of Truth):
            ```
            {existing_content}
            ```
            {seo_issues_str}

            **INSTRUCTIONS**:
            1.  **Research First (USE GROUNDING)**:
                -   Search for top-ranking competitors for "{page_title}" in **{project_loc}**.
                -   Identify the **primary intent** (e.g., "buy cheap", "luxury", "guide") and align the copy.
                -   Find 3-5 **semantic keywords** competitors are using that are missing here.

            2.  **Enhance & Optimize (The "Better" Part)**:
                -   Rewrite the existing text to include these new keywords naturally.
                -   Improve the value proposition based on what competitors offer.
                -   Make it **better SEO-wise**: clearer headings, stronger hook, better keyword density.

            3.  **Respect Constraints**:
                -   **Length**: Keep it roughly the same length (+/- 10%). Do NOT add massive new sections (like FAQs) unless the original had them.
                -   **Structure**: Maintain the existing flow (Intro -> Products -> Outro).

            4.  **Meta Description**:
                -   Write a new, high-CTR Meta Description (150-160 chars).

            **OUTPUT FORMAT** (Markdown):
            -   Return the full page content in Markdown.
            -   Include a **Meta Description** at the top.
            """
                                # Use REST API for Categories
                                generated_text = generate_content_via_rest(
                                    prompt=prompt,
                                    api_key=api_key,
                                    model="gemini-2.5-pro",
                                    use_grounding=True
                                )
                                
                            elif page_type == 'Topic':
                                # CHUNKED GENERATION LOGIC (New "Best-in-Class" Workflow)
                                print(f"DEBUG: Starting Chunked Workflow for {page_title}...", flush=True)
                                
                                # Get research data
                                research_data = page.get('research_data', {})
                                keyword_cluster = research_data.get('keyword_cluster', [])
                                primary_keyword = research_data.get('primary_keyword', page_title)
                                perplexity_research = research_data.get('perplexity_research', '')
                                citations = research_data.get('citations', [])
                                funnel_stage = page.get('funnel_stage', '')
                                source_page_id = page.get('source_page_id')
                                
                                # Internal Links Logic
                                internal_links = []
                                cta_url = None # URL for the final CTA
                                
                                if source_page_id:
                                    try:
                                        parent_res = supabase.table('pages').select('id, url, tech_audit_data, source_page_id').eq('id', source_page_id).single().execute()
                                        if parent_res.data:
                                            parent = parent_res.data
                                            parent_title = parent.get('tech_audit_data', {}).get('title', parent.get('url'))
                                            if funnel_stage == 'MoFu':
                                                internal_links.append(f"- {parent_title} (Main Product): {parent['url']}")
                                                cta_url = parent['url']
                                            elif funnel_stage == 'ToFu':
                                                # ToFu links: MoFu parent (2x) + Product grandparent (2-3x)
                                                internal_links.append(f"- {parent_title} (In-Depth Guide - USE 2 TIMES): {parent['url']}")
                                                grandparent_id = parent.get('source_page_id')
                                                if grandparent_id:
                                                    gp_res = supabase.table('pages').select('url, tech_audit_data').eq('id', grandparent_id).single().execute()
                                                    if gp_res.data:
                                                        gp_title = gp_res.data.get('tech_audit_data', {}).get('title', gp_res.data.get('url'))
                                                        internal_links.append(f"- {gp_title} (Main Product - USE 2-3 TIMES): {gp_res.data['url']}")
                                                        cta_url = gp_res.data['url'] # Prefer Grandparent (Product) for ToFu CTA
                                                
                                                if not cta_url: cta_url = parent['url'] # Fallback to Parent if no GP
                                    except Exception as e:
                                        print(f"Error fetching internal links: {e}")
                                links_str = '\n'.join(internal_links) if internal_links else "No internal links available"
                                
                                # Format keywords & citations
                                if keyword_cluster:
                                    kw_list = '\n'.join([f"- {kw['keyword']} ({kw['volume']}/mo, Score: {kw.get('score', 0)})" for kw in keyword_cluster[:15]])
                                else:
                                    kw_list = f"- {primary_keyword}"
                                citations_str = '\n'.join([f"[{i+1}] {cite}" for i, cite in enumerate(citations[:10])]) if citations else "No citations available"
                                
                                # Research Section
                                research_section = ""
                                if perplexity_research:
                                    research_section = f"# DEEP RESEARCH BRIEF (Source: Perplexity):\n{perplexity_research}\n\n# CITATIONS:\n{citations_str}"

                                # 1. Generate Dynamic Outline
                                outline = generate_dynamic_outline(page_title, research_section, project_loc, gemini_client)
                                if not outline:
                                    raise Exception("Failed to generate outline")
                                
                                # 2. Generate Sections (Chunked)
                                full_content = generate_sections_chunked(page_title, outline, research_section, project_loc, gemini_client, links_str)
                                
                                # 3. Final Polish (Intro/Outro/Meta)
                                generated_text = final_polish(full_content, page_title, primary_keyword, cta_url, project_loc, gemini_client)

                            if not generated_text:
                                raise Exception("Content generation returned empty string")

                            # Parse Meta Description if present
                            # PRESERVE existing scraped meta_description as default
                            existing_meta = page.get('tech_audit_data', {}).get('meta_description', '')
                            meta_desc = existing_meta if existing_meta else "No description available"
                            
                            # Parse Meta Description using Regex (More Robust)
                            try:
                                # Primary: Look for XML tags <meta-description>...</meta-description>
                                meta_match = re.search(r'<meta-description>\s*(.+?)\s*</meta-description>', generated_text, re.IGNORECASE | re.DOTALL)
                                
                                # Fallback: Look for "Meta Description:" text label
                                if not meta_match:
                                    meta_match = re.search(r'Meta Description.*:\s*(.+)', generated_text, re.IGNORECASE)

                                if meta_match:
                                    extracted_meta = meta_match.group(1).strip()
                                    extracted_meta = extracted_meta.strip('*# ') # Cleanup
                                    if extracted_meta:
                                        meta_desc = extracted_meta
                            except Exception as e:
                                log_debug(f"Meta extraction failed: {e}")
                            
                            # Update Page
                            supabase.table('pages').update({
                                "content": generated_text,
                                "status": "Generated",
                                "product_action": "Idle",
                                "tech_audit_data": {
                                    **page.get('tech_audit_data', {}),
                                    "meta_description": meta_desc
                                }
                            }).eq('id', page_id).execute()
                            
                            log_debug(f"Content generated successfully for {page_title}")

                        except Exception as gen_err:
                            log_debug(f"Generation error for {page_title}: {gen_err}")
                            import traceback
                            traceback.print_exc()
                            # Reset status
                            supabase.table('pages').update({"product_action": "Idle"}).eq('id', page_id).execute()
                            
                    except Exception as e:
                        log_debug(f"Outer error for {page_id}: {e}")
                        try:
                            supabase.table('pages').update({"product_action": "Idle"}).eq('id', page_id).execute()
                        except: pass

            # Update status to Processing IMMEDIATELY (Before thread starts)
            # This ensures frontend sees the loading state
            for pid in page_ids:
                try:
                    supabase.table('pages').update({
                        "product_action": "Processing Content..."
                    }).eq('id', pid).execute()
                except: pass

            # Start background thread
            log_debug("Starting background Content Generation thread...")
            thread = threading.Thread(target=process_content_generation_background, args=(page_ids, api_key))
            thread.start()
            
            return jsonify({"message": "Content generation started in background."}), 202


        elif action == 'conduct_research':
            # SIMPLIFIED: Perplexity Research Brief ONLY
            # (Keywords/Competitors are already done in generate_mofu)
            
            def process_research_background(page_ids, api_key):
                print(f"====== CONDUCT_RESEARCH BACKGROUND THREAD STARTED ======", flush=True)
                log_debug(f"CONDUCT_RESEARCH: Starting for {len(page_ids)} pages")
                
                for page_id in page_ids:
                    print(f"DEBUG: Processing page_id: {page_id}", flush=True)
                    try:
                        # Get the Topic page
                        page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
                        if not page_res.data: continue
                        
                        page = page_res.data
                        topic_title = page.get('tech_audit_data', {}).get('title', '')
                        research_data = page.get('research_data') or {}
                        
                        if not topic_title: continue
                        
                        log_debug(f"Researching topic (Perplexity): {topic_title}")
                        
                        # Get existing keywords/competitors
                        keywords = research_data.get('ranked_keywords', [])
                        competitor_urls = research_data.get('competitor_urls', [])
                        
                        # Fetch Project Settings for Localization
                        project_res = supabase.table('projects').select('location, language').eq('id', page['project_id']).single().execute()
                        project_loc = project_res.data.get('location', 'US') if project_res.data else 'US'
                        project_lang = project_res.data.get('language', 'English') if project_res.data else 'English'
                        
                        # Get funnel stage
                        funnel_stage = page.get('funnel_stage') or 'MoFu'
                        
                        # Fallback: If no keywords (maybe old page), run Gemini now
                        if not keywords:
                            log_debug(f"No keywords found for {topic_title}. Running Gemini fallback (Loc: {project_loc})...")
                            gemini_result = perform_gemini_research(topic_title, location=project_loc, language=project_lang)
                            if gemini_result:
                                keywords = gemini_result.get('keywords', [])
                                competitor_urls = [c['url'] for c in gemini_result.get('competitors', [])]
                                # Update research data immediately
                                research_data.update({
                                    "competitor_urls": competitor_urls,
                                    "ranked_keywords": keywords,
                                    "formatted_keywords": '\n'.join([f"{kw.get('keyword', '')} | {kw.get('intent', 'informational')} |" for kw in keywords])
                                })
                        
                        # Prepare query for Perplexity
                        keyword_list = ", ".join([k.get('keyword', '') for k in keywords[:15]])
                        competitor_list = ", ".join(competitor_urls)
                        
                        research_query = f"""
                        Research Topic: {topic_title}
                        Top Competitors: {competitor_list}
                        Top Keywords: {keyword_list}
                        
                        Create a detailed Content Research Brief for this topic.
                        Analyze the competitors and keywords to find content gaps.
                        Focus on User Pain Points, Key Subtopics, and Scientific/Technical details.
                        """
                        
                        log_debug(f"Starting Perplexity Research for brief (Loc: {project_loc}, Stage: {funnel_stage})...")
                        perplexity_result = research_with_perplexity(research_query, location=project_loc, language=project_lang, stage=funnel_stage)
                        
                        # Update research data with brief
                        research_data.update({
                            "stage": "complete",
                            "mode": "hybrid",
                            "perplexity_research": perplexity_result.get('research', ''),
                            "citations": perplexity_result.get('citations', [])
                        })
                        
                        # Update page
                        supabase.table('pages').update({
                            "research_data": research_data,
                            "product_action": "Idle"
                        }).eq('id', page_id).execute()
                        
                        log_debug(f"Research complete for {topic_title}")
                        
                    except Exception as e:
                        log_debug(f"Research error: {e}")
                        import traceback
                        traceback.print_exc()
                        # Reset status on error
                        try:
                            supabase.table('pages').update({"product_action": "Idle"}).eq('id', page_id).execute()
                        except: pass

            # Update status to Processing IMMEDIATELY (Before thread starts)
            # This ensures frontend sees the loading state
            for pid in page_ids:
                try:
                    supabase.table('pages').update({
                        "product_action": "Processing Research..."
                    }).eq('id', pid).execute()
                except: pass

            # Start background thread
            log_debug("Starting background Research thread...")
            thread = threading.Thread(target=process_research_background, args=(page_ids, os.environ.get("GEMINI_API_KEY")))
            thread.start()
            
            return jsonify({"message": "Research started in background. The status will update to 'Processing...' in the table."}), 202


            return jsonify({"message": "Content generated successfully"})

        elif action == 'generate_mofu':
            print(f"====== GENERATE MOFU ACTION ======", flush=True)
            log_debug(f"GENERATE_MOFU: Starting for {len(page_ids)} pages")
            print(f"DEBUG: Received generate_mofu action for page_ids: {page_ids}")
            print(f"DEBUG: Received generate_mofu action for page_ids: {page_ids}")
            # Use gemini_client with Grounding (ENABLED!)
            # This helps verify that the topic angles are actually trending/relevant.
            # client = genai_new.Client(api_key=os.environ.get("GEMINI_API_KEY")) # REMOVED
            # tool = types.Tool(google_search=types.GoogleSearch()) # REMOVED
            
            def process_mofu_generation(page_ids, api_key):
                log_debug(f"Background MoFu thread started for pages: {page_ids}")
                try:
                    # Use gemini_client with Grounding (ENABLED!)
                    # client = genai_new.Client(api_key=api_key) # REMOVED
                    # tool = types.Tool(google_search=types.GoogleSearch()) # REMOVED
                    
                    for pid in page_ids:
                        print(f"DEBUG: Processing page_id: {pid}")
                        # Get Product Page Data
                        res = supabase.table('pages').select('*').eq('id', pid).single().execute()
                        if not res.data: 
                            print(f"DEBUG: Page {pid} not found")
                            continue
                        product = res.data
                        product_tech = product.get('tech_audit_data', {})


                        
                        print(f"Researching MoFu opportunities for {product.get('url')}...")
                        
                        # === NEW DATA-FIRST WORKFLOW ===
                        
                        # Step 0: Ensure Content Context (Fix for "Memoir vs Candles")
                        body_content = product_tech.get('body_content', '')
                        product_title = product_tech.get('title', 'Untitled')
                        
                        # FIX: If title is "Pending Scan" or generic, force scrape to get REAL title
                        is_bad_title = not product_title or 'pending' in product_title.lower() or 'untitled' in product_title.lower() or 'scan' in product_title.lower()
                        
                        if not body_content or len(body_content) < 100 or is_bad_title:
                            log_debug(f"Content/Title missing or bad ('{product_title}') for {product['url']}, scraping now...")
                            scraped = scrape_page_content(product['url'])
                            if scraped:
                                body_content = scraped['body_content']
                                # Use scraped title if current is bad
                                if is_bad_title and scraped.get('title'):
                                    product_title = scraped['title']
                                    log_debug(f"Updated title from '{product_tech.get('title')}' to '{product_title}'")
                                
                                # Update DB so we don't scrape again
                                current_tech = product.get('tech_audit_data', {})
                                current_tech['body_content'] = body_content
                                current_tech['title'] = product_title # Save real title
                                
                                supabase.table('pages').update({
                                    "tech_audit_data": current_tech
                                }).eq('id', pid).execute()
                                product_tech = current_tech # Update local var
                        
                        log_debug(f"Using Product Title: {product_title}")

                        # Fetch Source Product Page
                        product_res = supabase.table('pages').select('*').eq('id', pid).single().execute()
                        if not product_res.data:
                            print(f"DEBUG: Product page not found for ID: {pid}", flush=True)
                            continue
                        product = product_res.data
                        product_title = product.get('tech_audit_data', {}).get('title', '')
                        print(f"DEBUG: Processing Product: {product_title}", flush=True)
                        
                        # Fetch Project Settings
                        project_res = supabase.table('projects').select('location, language').eq('id', product['project_id']).single().execute()
                        project_loc = project_res.data.get('location', 'US') if project_res.data else 'US'
                        project_lang = project_res.data.get('language', 'English') if project_res.data else 'English'
                        print(f"DEBUG: Project Settings: {project_loc}, {project_lang}", flush=True)

                        # Step 1: Get Keywords
                        keywords = []
                        # (Skipping to where I can inject prints easily)
                        # I'll just add prints around the Gemini call in the next block
                        # Step 1: Generate MULTIPLE Broad Seed Keywords for DataForSEO
                        # Strategy: Don't search for specific product - search for CATEGORY + common queries
                        if not product_title:
                            product_title = get_title_from_url(product['url'])

                        print(f"DEBUG: Analyzing context for: {product_title} (Loc: {project_loc}, Lang: {project_lang})")
                        
                        try:
                            # NEW STRATEGY: Generate multiple broad seeds
                            context_prompt = f"""Analyze this product to generate 3-5 BROAD keyword seeds for DataForSEO research.

        Product Title: "{product_title}"
        Page Content: {body_content[:2000]}

        Task:
        1. Identify the product CATEGORY (e.g., "carrier oils", "lipstick", "sunscreen", "candles")
        2. Generate 3-5 BROAD search terms that people use when researching this category in **{project_loc}**.
        3. DO NOT use the specific product name - use GENERIC category terms

        Examples:
        - Product: "Apricot Kernel Oil" → Seeds: ["carrier oil benefits", "oil for skin", "facial oils", "natural oils skincare"]
        - Product: "MAC Ruby Woo Lipstick" → Seeds: ["red lipstick", "matte lipstick", "long lasting lipstick", "lipstick shades"]
        - Product: "Supergoop Sunscreen" → Seeds: ["face sunscreen", "spf for skin", "sunscreen benefits", "daily sunscreen"]

        OUTPUT: Return ONLY a comma-separated list of 3-5 broad keywords. No explanations.
        Example output: carrier oil benefits, oil for skin, facial oils, natural oils"""
                            
                            seed_res_text = gemini_client.generate_content(
                                prompt=context_prompt,
                                model_name="gemini-2.5-flash",
                                use_grounding=True
                            )
                            seeds_str = seed_res_text.strip().replace('"', '').replace("'", "") if seed_res_text else ""
                            broad_seeds = [s.strip() for s in seeds_str.split(',') if s.strip()]
                            
                            # Fallback if AI fails
                            if not broad_seeds:
                                broad_seeds = [product_title]
                            
                            log_debug(f"Generated {len(broad_seeds)} broad seeds: {broad_seeds}")
                            print(f"DEBUG: Broad seed keywords: {broad_seeds}")
                            
                        except Exception as e:
                            print(f"⚠ Seed generation failed: {e}. Using product title.")
                            broad_seeds = [product_title]

                        
                        # NEW: Use Gemini 2.0 Flash with Grounding as PRIMARY source (User Request)
                        print(f"DEBUG: Using Gemini 2.0 Flash for keyword research (Primary)...")
                        log_debug("Calling perform_gemini_research as PRIMARY source")
                        
                        gemini_result = perform_gemini_research(product_title, location=project_loc, language=project_lang)
                        keywords = []
                        
                        if gemini_result and gemini_result.get('keywords'):
                            print(f"✓ Gemini Research successful. Found {len(gemini_result['keywords'])} keywords.")
                            for k in gemini_result['keywords']:
                                keywords.append({
                                    'keyword': k.get('keyword'),
                                    'volume': 100, # Placeholder volume since Gemini doesn't provide it
                                    'score': 100,
                                    'cpc': 0,
                                    'competition': 0,
                                    'intent': k.get('intent', 'Commercial')
                                })
                        else:
                            print(f"⚠ Gemini Research failed. Using fallback.")
                            keywords = [{'keyword': product_title, 'volume': 0, 'score': 0, 'cpc': 0, 'competition': 0}]


                        
                        # Step 2: Prepare Data for Topic Generation (No Deep Research yet)
                        log_debug("Skipping deep research (will be done in 'Conduct Research' stage).")
                        
                        # Format keyword list for prompt
                        keyword_list = '\n'.join([f"- {k['keyword']} ({k['volume']} searches/month)" for k in keywords[:50]])
                        
                        # Minimal research data for now
                        research_data = {
                            "keywords": keywords,
                            "stage": "research_pending"
                        }


                        # Step 4: Generate Topics from REAL DATA
                        import datetime
                        current_year = datetime.datetime.now().year
                        next_year = current_year + 1
                        
                        topic_prompt = f"""You are an SEO Content Strategist. Generate 6 MoFu (Middle-of-Funnel) article topics based on REAL keyword data.

        **Product**: {product_title}
        **Target Audience**: {project_loc} ({project_lang})

        **VERIFIED HIGH-VOLUME KEYWORDS** (Scored by Opportunity):
        {keyword_list}

        **YOUR TASK**:
        Create 6 MoFu topics. For EACH topic, assign ALL semantically relevant keywords from the list above (could be 3-15 keywords per topic - include as many as naturally fit the angle).

        **Requirements**:
        1. Each topic must target a primary keyword (highest opportunity score for that angle)
        2. Include ALL secondary keywords that semantically match the topic angle
        3. Topics should be Middle-of-Funnel (Comparison, Best Of, Guide, vs)

        **Topic Types**:
        - "Best X for Y in {current_year}" (roundup/comparison)
        - "Product vs Competitor" (head-to-head comparison)
        - "Top Alternatives to X" (alternative guides)  
        - Use cases backed by research

        **Output Format** (JSON):
        {{
          "topics": [
            {{
              "title": "[Exact title - include year {current_year} if relevant]",
              "slug": "url-friendly-slug",
              "description": "2-sentence description of content angle",
              "keyword_cluster": [
                {{"keyword": "[keyword1]", "volume": [INTEGER_FROM_INPUT], "is_primary": true}},
                {{"keyword": "[keyword2]", "volume": [INTEGER_FROM_INPUT], "is_primary": false}},
                ...
              ],
              "research_notes": "Why this topic (reference SERP competitor or research insight)"
            }}
          ]
        }}

        CRITICAL: 
        1. Use EXACT integers for volume from the provided list. DO NOT write "Estimated".
        2. Assign keywords based on semantic relevance. Don't artificially limit - if 12 keywords fit a topic, include all 12.
        """


                        
                        try:
                            text = gemini_client.generate_content(
                                prompt=topic_prompt,
                                model_name="gemini-2.5-flash",
                                use_grounding=True
                            )
                            if not text: raise Exception("Empty response from Gemini")
                            text = text.strip()
                            if text.startswith('```json'): text = text[7:]
                            if text.startswith('```'): text = text[3:]
                            if text.endswith('```'): text = text[:-3]
                            text = text.strip()
                            
                            # Parse JSON with error handling
                            try:
                                data = json.loads(text)
                            except json.JSONDecodeError as json_err:
                                log_debug(f"JSON parse error: {json_err}. Response: {text[:300]}")
                                print(f"✗ Gemini returned invalid JSON. Skipping MoFu for {product_title}")
                                continue  # Skip to next product
                            
                            topics = data.get('topics', [])
                            if not topics:
                                log_debug("No topics in AI response")
                                continue
                            
                            new_pages = []
                            for t in topics:
                                # Handle keyword cluster (multiple keywords per topic)
                                keyword_cluster = t.get('keyword_cluster', [])
                                
                                if keyword_cluster:
                                    # NEW FORMAT: "keyword | intent | secondary intent" (no volume)
                                    # Classify intent based on keyword patterns
                                    def classify_intent(kw_text):
                                        kw_lower = kw_text.lower()
                                        # Transactional indicators
                                        if any(word in kw_lower for word in ['buy', 'price', 'shop', 'purchase', 'best', 'top', 'review', 'vs', 'alternative']):
                                            return 'transactional'
                                        # Commercial indicators
                                        elif any(word in kw_lower for word in ['benefits', 'how to', 'uses', 'guide', 'comparison', 'difference']):
                                            return 'commercial'
                                        # Default: informational
                                        else:
                                            return 'informational'
                                    
                                    keywords_str = '\n'.join([
                                        f"{kw['keyword']} | {classify_intent(kw['keyword'])} |"
                                        for kw in keyword_cluster
                                    ])
                                    # Get primary keyword for research reference
                                    primary_kw = next((kw for kw in keyword_cluster if kw.get('is_primary')), keyword_cluster[0] if keyword_cluster else {})
                                else:
                                    keywords_str = ""
                                    primary_kw = {}
                                
                                # Combine general research with topic-specific notes
                                topic_research = research_data.copy()
                                topic_research['notes'] = t.get('research_notes', '')
                                topic_research['keyword_cluster'] = keyword_cluster
                                topic_research['primary_keyword'] = primary_kw.get('keyword', '')
                                
                                new_pages.append({
                                    "project_id": product['project_id'],
                                    "source_page_id": pid,
                                    "url": f"{product['url'].rstrip('/')}/{t['slug']}",
                                    "page_type": "Topic",
                                    "funnel_stage": "MoFu",
                                    "product_action": "Idle",
                                    "tech_audit_data": {
                                        "title": t['title'],
                                        "meta_description": t['description'],
                                        "meta_title": t['title']
                                    },
                                    "content_description": t['description'],
                                    "keywords": keywords_str,  # Data-backed keywords with volume
                                    "slug": t['slug'],
                                    "research_data": topic_research  # Store all research including citations
                                })
                            
                            
                            
                            if new_pages:
                                print(f"DEBUG: Attempting to insert {len(new_pages)} MoFu topics...", file=sys.stderr)
                                try:
                                    insert_res = supabase.table('pages').insert(new_pages).execute()
                                    print("DEBUG: ✓ MoFu topics inserted successfully.", file=sys.stderr)
                                    
                                    # AUTO-KEYWORD RESEARCH (Gemini)
                                    if insert_res.data:
                                        print(f"DEBUG: Starting Auto-Keyword Research for {len(insert_res.data)} topics...", file=sys.stderr)
                                        for inserted_page in insert_res.data:
                                            try:
                                                p_id = inserted_page['id']
                                                # Handle tech_audit_data being a string or dict
                                                t_data = inserted_page.get('tech_audit_data', {})
                                                if isinstance(t_data, str):
                                                    try: t_data = json.loads(t_data)
                                                    except: t_data = {}
                                                    
                                                p_title = t_data.get('title', '')
                                                if not p_title: continue
                                                
                                                log_debug(f"Auto-Researching keywords for: {p_title} (Loc: {project_loc})")
                                                gemini_result = perform_gemini_research(p_title, location=project_loc, language=project_lang)
                                                
                                                if gemini_result:
                                                    keywords = gemini_result.get('keywords', [])
                                                    formatted_keywords = '\n'.join([
                                                        f"{kw.get('keyword', '')} | {kw.get('intent', 'informational')} |"
                                                        for kw in keywords if kw.get('keyword')
                                                    ])
                                                    
                                                    # Create research data (partial)
                                                    research_data = {
                                                        "stage": "keywords_only", 
                                                        "mode": "hybrid",
                                                        "competitor_urls": [c['url'] for c in gemini_result.get('competitors', [])],
                                                        "ranked_keywords": keywords,
                                                        "formatted_keywords": formatted_keywords
                                                    }
                                                    
                                                    supabase.table('pages').update({
                                                        "keywords": formatted_keywords,
                                                        "research_data": research_data
                                                    }).eq('id', p_id).execute()
                                                    log_debug(f"✓ Keywords saved for {p_title}")
                                            except Exception as research_err:
                                                log_debug(f"Auto-Research failed for {p_title}: {research_err}")
                                except Exception as insert_error:
                                    print(f"DEBUG: Error inserting with research_data: {insert_error}", file=sys.stderr)
                                    # Fallback: Try inserting without research_data (if column missing)
                                    if 'research_data' in str(insert_error) or 'column' in str(insert_error):
                                        print("DEBUG: Retrying insert without research_data column...", file=sys.stderr)
                                        for p in new_pages:
                                            p.pop('research_data', None)
                                        supabase.table('pages').insert(new_pages).execute()
                                        print("DEBUG: ✓ MoFu topics inserted (without research data).", file=sys.stderr)
                                    else:
                                        raise insert_error
                            else:
                                print("DEBUG: No new pages to insert (topics list empty).", file=sys.stderr)
                            
                            # Update Source Page Status
                            supabase.table('pages').update({"product_action": "MoFu Generated"}).eq('id', pid).execute()
                        
                        except Exception as e:
                            print(f"DEBUG: Error generating MoFu topics: {e}", file=sys.stderr)
                            import traceback
                            traceback.print_exc()
                            # Reset status on error so frontend doesn't hang
                            supabase.table('pages').update({"product_action": "Failed"}).eq('id', pid).execute()
                            
                except Exception as e:
                    log_debug(f"MoFu Thread Error: {e}")
                    # Ensure we try to reset status for all pages if the whole thread crashes
                    try:
                        supabase.table('pages').update({"product_action": "Failed"}).in_('id', page_ids).execute()
                    except: pass
                            
                except Exception as e:
                    log_debug(f"MoFu Thread Error: {e}")

            # Set status to Processing immediately
            try:
                log_debug(f"Updating status to Processing for {page_ids}")
                supabase.table('pages').update({"product_action": "Processing..."}).in_('id', page_ids).execute()
            except Exception as e:
                log_debug(f"Failed to update status to Processing: {e}")

            # Start background thread
            log_debug("Starting background MoFu thread...")
            thread = threading.Thread(target=process_mofu_generation, args=(page_ids, os.environ.get("GEMINI_API_KEY")))
            thread.start()
            
            return jsonify({"message": "MoFu generation started in background. The status will update to 'Processing...' in the table."})


        elif action == 'conduct_research':
            # SIMPLIFIED: Perplexity Research Brief ONLY
            # (Keywords/Competitors are already done in generate_mofu)
            
            def process_research_background(page_ids, api_key):
                print(f"====== CONDUCT_RESEARCH BACKGROUND THREAD STARTED ======", flush=True)
                log_debug(f"CONDUCT_RESEARCH: Starting for {len(page_ids)} pages")
                
                for page_id in page_ids:
                    print(f"DEBUG: Processing page_id: {page_id}", flush=True)
                    try:
                        # Update status to Processing
                        supabase.table('pages').update({
                            "product_action": "Processing Research..."
                        }).eq('id', page_id).execute()

                        # Get the Topic page
                        page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
                        if not page_res.data: continue
                        
                        page = page_res.data
                        topic_title = page.get('tech_audit_data', {}).get('title', '')
                        research_data = page.get('research_data') or {}
                        
                        if not topic_title: continue
                        
                        log_debug(f"Researching topic (Perplexity): {topic_title}")
                        
                        # Get existing keywords/competitors
                        keywords = research_data.get('ranked_keywords', [])
                        competitor_urls = research_data.get('competitor_urls', [])
                        
                        # Fetch Project Settings for Localization
                        project_res = supabase.table('projects').select('location, language').eq('id', page['project_id']).single().execute()
                        project_loc = project_res.data.get('location', 'US') if project_res.data else 'US'
                        project_lang = project_res.data.get('language', 'English') if project_res.data else 'English'
                        
                        # Fallback: If no keywords (maybe old page), run Gemini now
                        if not keywords:
                            log_debug(f"No keywords found for {topic_title}. Running Gemini fallback (Loc: {project_loc})...")
                            gemini_result = perform_gemini_research(topic_title, location=project_loc, language=project_lang)
                            if gemini_result:
                                keywords = gemini_result.get('keywords', [])
                                competitor_urls = [c['url'] for c in gemini_result.get('competitors', [])]
                                # Update research data immediately
                                research_data.update({
                                    "competitor_urls": competitor_urls,
                                    "ranked_keywords": keywords,
                                    "formatted_keywords": '\n'.join([f"{kw.get('keyword', '')} | {kw.get('intent', 'informational')} |" for kw in keywords])
                                })
                        
                        # Prepare query for Perplexity
                        keyword_list = ", ".join([k.get('keyword', '') for k in keywords[:15]])
                        competitor_list = ", ".join(competitor_urls)
                        
                        research_query = f"""
                        Research Topic: {topic_title}
                        Top Competitors: {competitor_list}
                        Top Keywords: {keyword_list}
                        
                        Create a detailed Content Research Brief for this topic.
                        Analyze the competitors and keywords to find content gaps.
                        Focus on User Pain Points, Key Subtopics, and Scientific/Technical details.
                        """
                        
                        log_debug(f"Starting Perplexity Research for brief (Loc: {project_loc})...")
                        perplexity_result = research_with_perplexity(research_query, location=project_loc, language=project_lang)
                        
                        # Update research data with brief
                        research_data.update({
                            "stage": "complete",
                            "mode": "hybrid",
                            "perplexity_research": perplexity_result.get('research', ''),
                            "citations": perplexity_result.get('citations', [])
                        })
                        
                        # Update page
                        supabase.table('pages').update({
                            "research_data": research_data,
                            "product_action": "Idle"
                        }).eq('id', page_id).execute()
                        
                        log_debug(f"Research complete for {topic_title}")
                        
                    except Exception as e:
                        log_debug(f"Research error: {e}")
                        import traceback
                        traceback.print_exc()
                        # Reset status on error
                        try:
                            supabase.table('pages').update({"product_action": "Idle"}).eq('id', page_id).execute()
                        except: pass

            # Start background thread
            log_debug("Starting background Research thread...")
            thread = threading.Thread(target=process_research_background, args=(page_ids, os.environ.get("GEMINI_API_KEY")))
            thread.start()
            
            return jsonify({"message": "Research started in background. The status will update to 'Processing...' in the table."}), 202


        elif action == 'generate_tofu':
            # AI ToFu Topic Generation
            
            def process_tofu_generation(page_ids, api_key):
                log_debug(f"Background ToFu thread started for pages: {page_ids}")
                try:

                    
                    for pid in page_ids:
                        # Fetch Source MoFu Page
                        mofu_res = supabase.table('pages').select('*').eq('id', pid).single().execute()
                        if not mofu_res.data: continue
                        mofu = mofu_res.data
                        mofu_tech = mofu.get('tech_audit_data') or {}
                        
                        print(f"Researching ToFu opportunities for MoFu topic: {mofu_tech.get('title')}...")
                        
                        # === NEW DATA-FIRST WORKFLOW FOR TOFU ===
                        
                        # Fetch Project Settings for Localization (Moved UP)
                        project_res = supabase.table('projects').select('location, language').eq('id', mofu['project_id']).single().execute()
                        project_loc = project_res.data.get('location', 'US') if project_res.data else 'US'
                        project_lang = project_res.data.get('language', 'English') if project_res.data else 'English'

                        # Step 1: Get broad keyword ideas based on MoFu topic
                        mofu_title = mofu_tech.get('title', '')
                        print(f"Researching ToFu opportunities for: {mofu_title} (Loc: {project_loc})")
                        
                        # Get keyword opportunities from DataForSEO
                        # For ToFu, we want broader terms, so we might strip "Best" or "Review" from the seed
                        seed_keyword = mofu_title.replace('Best ', '').replace('Review', '').replace(' vs ', ' ').strip()
                        # NEW: Use Gemini 2.0 Flash with Grounding as PRIMARY source (User Request)
                        print(f"DEBUG: Using Gemini 2.0 Flash for ToFu keyword research (Primary)...")
                        
                        gemini_result = perform_gemini_research(seed_keyword, location=project_loc, language=project_lang)
                        keywords = []
                        
                        if gemini_result and gemini_result.get('keywords'):
                            print(f"✓ Gemini Research successful. Found {len(gemini_result['keywords'])} keywords.")
                            for k in gemini_result['keywords']:
                                keywords.append({
                                    'keyword': k.get('keyword'),
                                    'volume': 100, # Placeholder
                                    'score': 100,
                                    'cpc': 0,
                                    'competition': 0,
                                    'intent': k.get('intent', 'Informational')
                                })
                        else:
                            print(f"⚠ Gemini Research failed. Using fallback.")
                            keywords = [{'keyword': seed_keyword, 'volume': 0, 'score': 0, 'cpc': 0, 'competition': 0}]
                        
                        print(f"DEBUG: Proceeding to Topic Generation with {len(keywords)} keywords...", flush=True)
                        
                        # Step 2: Analyze SERP for top 5 keywords (Optional - keeping for context if fast enough, or remove for speed)
                        # For now, we'll keep it lightweight or rely on Gemini Grounding in the prompt.
                        # Let's SKIP DataForSEO SERP to save time/cost, and rely on Gemini Grounding.
                        serp_summary = "Relied on Gemini Grounding for current SERP context."
                        
                        # Step 3: Generate Topics (Lightweight - No Perplexity)
                        import datetime
                        current_year = datetime.datetime.now().year
                        
                        # Format keyword list for prompt
                        keyword_list = '\n'.join([f"- {k['keyword']} ({k['volume']}/mo, Score: {k.get('score', 0)})" for k in keywords[:100]])

                        topic_prompt = f"""
                        You are an SEO Strategist. Generate 5 High-Value Top-of-Funnel (ToFu) topic ideas that lead to: {mofu_tech.get('title')}
                        
                        **CONTEXT**:
                        - Target Audience: People at the beginning of their journey (Problem Aware).
                        - Location: {project_loc}
                        - Language: {project_lang}
                        - Goal: Educate them and naturally lead them to the solution (the MoFu topic).
                        
                        **HIGH-OPPORTUNITY KEYWORDS**:
                        {keyword_list}
                        
                        **INSTRUCTIONS**:
                        1.  **Use Grounding**: Search Google to ensure these topics are currently relevant and not already saturated in **{project_loc}**.
                        2.  **Focus**: "What is", "How to", "Guide to", "Benefits of", "Mistakes to Avoid".
                        3.  **Variety**: specific angles, not just generic guides.
                        
                        **LOCALIZATION RULES (CRITICAL)**:
                        1. **Currency**: You MUST use the local currency for **{project_loc}** (e.g., ₹ INR for India). Convert prices if needed.
                        2. **Units**: Use the measurement system standard for **{project_loc}**.
                        3. **Spelling**: Use the correct spelling dialect (e.g., "Colour" for UK/India).
                        4. **Cultural Context**: Use examples relevant to **{project_loc}**.
                        
                        Current Date: {datetime.datetime.now().strftime("%B %Y")}
                        
                        Return a JSON object with a key "topics" containing a list of objects:
                        - "title": Topic Title (Must include a primary keyword)
                        - "slug": URL friendly slug
                        - "description": Brief content description (intent)
                        - "keyword_cluster": List of ALL semantically relevant keywords from the list (aim for 30+ per topic if relevant)
                        - "primary_keyword": The main keyword targeted
                        """
                        
                        try:
                            text = gemini_client.generate_content(
                                prompt=topic_prompt,
                                model_name="gemini-2.5-flash",
                                use_grounding=True
                            )
                            if not text: raise Exception("Empty response from Gemini")
                            text = text.strip()
                            if text.startswith('```json'): text = text[7:]
                            if text.startswith('```'): text = text[3:]
                            if text.endswith('```'): text = text[:-3]
                            
                            data = json.loads(text)
                            topics = data.get('topics', [])
                            
                            new_pages = []
                            for t in topics:
                                # Map selected keywords back to their data
                                cluster_data = []
                                for k_str in t.get('keyword_cluster', []):
                                    match = next((k for k in keywords if k['keyword'].lower() == k_str.lower()), None)
                                    if match: cluster_data.append(match)
                                    else: cluster_data.append({'keyword': k_str, 'volume': 0, 'score': 0, 'intent': 'Informational'})
                                
                                # Standardized Format: "keyword | intent |" (Matches MoFu style)
                                keywords_str = '\n'.join([
                                    f"{k['keyword']} | {k.get('intent', 'Informational')} |"
                                    for k in cluster_data
                                ])
                                
                                # Minimal research data (No Perplexity yet)
                                topic_research = {
                                    "stage": "topic_generated",
                                    "keyword_cluster": cluster_data,
                                    "primary_keyword": t.get('primary_keyword')
                                }

                                new_pages.append({
                                    "project_id": mofu['project_id'],
                                    "source_page_id": pid,
                                    "url": f"{mofu['url'].rsplit('/', 1)[0]}/{t['slug']}", 
                                    "page_type": "Topic",
                                    "funnel_stage": "ToFu",
                                    "product_action": "Idle", # Ready for manual "Conduct Research"
                                    "tech_audit_data": {
                                        "title": t['title'],
                                        "meta_description": t['description'],
                                        "meta_title": t['title']
                                    },
                                    "content_description": t['description'],
                                    "keywords": keywords_str,
                                    "slug": t['slug'],
                                    "research_data": topic_research
                                })
                            
                            if new_pages:
                                print(f"Attempting to insert {len(new_pages)} ToFu topics...")
                                insert_res = supabase.table('pages').insert(new_pages).execute()
                                print("✓ ToFu topics inserted successfully.")
                                
                                # AUTO-KEYWORD RESEARCH (Gemini) - Architecture Parity with MoFu
                                if insert_res.data:
                                    print(f"DEBUG: Starting Auto-Keyword Research for {len(insert_res.data)} ToFu topics...")
                                    for inserted_page in insert_res.data:
                                        try:
                                            p_id = inserted_page['id']
                                            t_data = inserted_page.get('tech_audit_data', {})
                                            if isinstance(t_data, str):
                                                try: t_data = json.loads(t_data)
                                                except: t_data = {}
                                                
                                            p_title = t_data.get('title', '')
                                            if not p_title: continue
                                            
                                            log_debug(f"Auto-Researching keywords for ToFu: {p_title}")
                                            # Use project location/language for research
                                            gemini_result = perform_gemini_research(p_title, location=project_loc, language=project_lang)
                                            
                                            if gemini_result:
                                                keywords = gemini_result.get('keywords', [])
                                                formatted_keywords = '\n'.join([
                                                    f"{kw.get('keyword', '')} | {kw.get('intent', 'informational')} |"
                                                    for kw in keywords if kw.get('keyword')
                                                ])
                                                
                                                # Create research data (partial)
                                                research_data = {
                                                    "stage": "keywords_only", 
                                                    "mode": "hybrid",
                                                    "competitor_urls": [c['url'] for c in gemini_result.get('competitors', [])],
                                                    "ranked_keywords": keywords,
                                                    "formatted_keywords": formatted_keywords
                                                }
                                                
                                                supabase.table('pages').update({
                                                    "keywords": formatted_keywords,
                                                    "research_data": research_data
                                                }).eq('id', p_id).execute()
                                            log_debug(f"✓ Keywords saved for {p_title}")
                                        except Exception as research_err:
                                            log_debug(f"Auto-Research failed for {p_title}: {research_err}")
                            
                            log_debug(f"ToFu generation complete for {pid}. Updating status...")
                            # Update Source Page Status
                            supabase.table('pages').update({"product_action": "ToFu Generated"}).eq('id', pid).execute()
                            log_debug(f"Status updated to 'ToFu Generated' for {pid}")
                            
                        except Exception as e:
                            print(f"Error generating ToFu topics: {e}")
                            import traceback
                            traceback.print_exc()
                            # Reset status on error so frontend doesn't hang
                            supabase.table('pages').update({"product_action": "Failed"}).eq('id', pid).execute()
                
                except Exception as e:
                    log_debug(f"ToFu Thread Error: {e}")
                    # Ensure we try to reset status for all pages if the whole thread crashes
                    try:
                        supabase.table('pages').update({"product_action": "Failed"}).in_('id', page_ids).execute()
                    except: pass

            # Set status to Processing immediately
            try:
                log_debug(f"Updating status to Processing for {page_ids}")
                supabase.table('pages').update({"product_action": "Processing..."}).in_('id', page_ids).execute()
            except Exception as e:
                log_debug(f"Failed to update status to Processing: {e}")

            # Start background thread
            log_debug("Starting background ToFu thread...")
            thread = threading.Thread(target=process_tofu_generation, args=(page_ids, os.environ.get("GEMINI_API_KEY")))
            thread.start()
            
            return jsonify({"message": "ToFu generation started in background. The status will update to 'Processing...' in the table."})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_page_details():
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        page_id = request.args.get('page_id')
        if not page_id: return jsonify({"error": "page_id required"}), 400
        
        res = supabase.table('pages').select('*').eq('id', page_id).execute()
        if not res.data: return jsonify({"error": "Page not found"}), 404
        
        return jsonify(res.data[0])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        print(f"Error in crawl_project: {e}")
        return jsonify({"error": str(e)}), 500





@app.route('/api/generate-image-prompt', methods=['POST'])
def generate_image_prompt_endpoint():
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        topic = data.get('topic')
        project_id = data.get('project_id') # Ensure frontend sends this
        
        # Fetch Project Settings
        project_loc = 'US'
        if project_id:
            project_res = supabase.table('projects').select('location').eq('id', project_id).single().execute()
            if project_res.data:
                project_loc = project_res.data.get('location', 'US')

        prompt = f"""
        You are an expert AI Art Director.
        Create a detailed, high-quality image generation prompt for a blog post titled: "{topic}".
        
        **CONTEXT**:
        - Target Audience Location: {project_loc} (Ensure cultural relevance, e.g., models, setting)
        
        Style: Photorealistic, Cinematic, High-End Editorial.
        The style should be: "Modern, Minimalist, Tech-focused, 3D Render, High Resolution".
        
        Output: Just the prompt text.
        Return ONLY the prompt text. No "Here is the prompt" or quotes.
        """
        
        # model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # response = model.generate_content(prompt)
        
        text = gemini_client.generate_content(
            prompt=prompt,
            model_name="gemini-2.5-flash"
        )
        
        if not text:
            return jsonify({"error": "Gemini generation failed"}), 500
            
        return jsonify({"prompt": text.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-migration', methods=['POST'])
def run_migration():
    """Run the photoshoots migration SQL"""
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        # Read the SQL file
        migration_path = os.path.join(BASE_DIR, 'migration_photoshoots.sql')
        with open(migration_path, 'r') as f:
            sql = f.read()
            
        # Execute using Supabase RPC or direct SQL if possible
        # Since Supabase-py client doesn't support direct SQL execution easily without RPC,
        # we'll try to use the 'rpc' method if you have a 'exec_sql' function defined in Postgres
        # OR we can just assume the table exists for now and let the user run it in Supabase dashboard.
        
        # However, to be helpful, let's try to create the table using a raw query if the client supports it.
        # The supabase-py client is a wrapper around postgrest. It doesn't support raw SQL.
        # But we can try to use the 'psycopg2' connection if we had the connection string.
        
        # Since we failed to connect with psycopg2 earlier, we can't run it here either.
        
        return jsonify({"message": "Please run the migration_photoshoots.sql file in your Supabase SQL Editor."}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== PRODUCT PHOTOSHOOT ENDPOINTS =====

@app.route('/api/photoshoots', methods=['GET'])
def get_photoshoots():
    """Get all photoshoot tasks for a project"""
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        project_id = request.args.get('project_id')
        if not project_id:
            return jsonify({"error": "project_id required"}), 400
        
        # 1. Fetch manual photoshoots
        res_tasks = supabase.table('photoshoots').select('*').eq('project_id', project_id).order('created_at', desc=True).execute()
        tasks = res_tasks.data or []
        
        # 2. Fetch blog article images
        # We assume pages belong to the project (linked via project_id if applicable, or we filter by project pages)
        # Since pages table might not have project_id directly (it links via project_pages usually?), let's check.
        # Based on previous code, pages seem to be linked to projects.
        # Let's assume we can filter pages by project_id if that column exists, or we fetch all pages for the project.
        # Wait, the `pages` table schema check:
        # It has `project_id`? Let's check `setup_database_refined.sql` or assume it does based on `loadProject`.
        # `loadProject` fetches pages for a project.
        
        res_pages = supabase.table('pages').select('id, title, image_prompt, main_image_url, updated_at').eq('project_id', project_id).not_.is_('main_image_url', 'null').execute()
        page_images = res_pages.data or []
        
        # 3. Merge and Format
        combined = []
        
        # Add Manual Tasks
        for t in tasks:
            combined.append({
                "id": t['id'],
                "type": "manual",
                "prompt": t['prompt'],
                "status": t['status'],
                "output_image": t['output_image'],
                "aspect_ratio": t.get('aspect_ratio', 'auto'),
                "created_at": t['created_at']
            })
            
        # Add Blog Images
        for p in page_images:
            combined.append({
                "id": p['id'], # Page ID
                "type": "article",
                "prompt": p.get('image_prompt') or f"Blog Image: {p.get('title')}",
                "status": "Done",
                "output_image": p['main_image_url'],
                "aspect_ratio": "16:9",
                "created_at": p.get('updated_at')
            })
            
        # Sort by created_at desc (simple string sort for ISO dates works)
        combined.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({"photoshoots": combined})
    except Exception as e:
        print(f"Error fetching photoshoots: {e}")
        return jsonify({"photoshoots": []})

@app.route('/api/photoshoots', methods=['POST'])
def create_photoshoot():
    """Create a new photoshoot task"""
    print("Received create_photoshoot request")
    if not supabase: 
        print("Supabase not configured")
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        print(f"Request data: {data}")
        project_id = data.get('project_id')
        prompt = data.get('prompt', '')
        
        if not project_id:
            return jsonify({"error": "project_id required"}), 400
        
        # Insert into database
        new_task = {
            'project_id': project_id,
            'prompt': prompt,
            'status': 'Pending',
            'output_image': None,
            'aspect_ratio': data.get('aspect_ratio', 'auto')
        }
        
        print(f"Inserting task: {new_task}")
        res = supabase.table('photoshoots').insert(new_task).execute()
        print(f"Insert result: {res}")
        return jsonify({"photoshoot": res.data[0] if res.data else new_task})
    except Exception as e:
        print(f"Error creating photoshoot: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/photoshoots/<photoshoot_id>', methods=['PUT'])
def update_photoshoot(photoshoot_id):
    """Update a photoshoot task"""
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        action = data.get('action')
        
        # Allow updating any field passed in data, excluding 'action' and 'id'
        update_data = {k: v for k, v in data.items() if k not in ['action', 'id', 'project_id']}
        
        # If action is 'run', generate the image
        if action == 'run':


            print(f"Starting generation for task {photoshoot_id}")
            # Get the prompt from the database to be sure
            # Get the prompt and input_image from the database
            current_task = supabase.table('photoshoots').select('prompt, input_image, aspect_ratio').eq('id', photoshoot_id).execute()
            if not current_task.data:
                 return jsonify({"error": "Task not found"}), 404
                 
            task_data = current_task.data[0]
            prompt_text = task_data.get('prompt', '')
            input_image_url = task_data.get('input_image', '')
            db_aspect_ratio = task_data.get('aspect_ratio', '16:9')
            
            if not prompt_text:
                return jsonify({"error": "Prompt is empty"}), 400
                
            # Update status to Processing
            supabase.table('photoshoots').update({'status': 'Processing'}).eq('id', photoshoot_id).execute()
            
            try:
                # content_parts = [prompt_text]
                input_image_b64 = None
                target_aspect = db_aspect_ratio # Use DB value as default
                input_width = None
                input_height = None
                
                # Load input image if it exists
                if input_image_url:
                    try:
                        img = load_image_data(input_image_url)
                        input_width, input_height = img.size
                        print(f"DEBUG: Input image dimensions: {input_width}x{input_height}")
                        
                        # Calculate Aspect Ratio
                        # Logic:
                        # 1. If db_aspect_ratio is 'auto' (or None/empty), we DETECT from input image.
                        # 2. If db_aspect_ratio is explicit (e.g. '16:9', '1:1'), we USE IT directly.
                        
                        if not db_aspect_ratio or db_aspect_ratio == 'auto':
                            ratio = input_width / input_height
                            
                            # Gemini Supported Ratios: 1:1, 3:4, 4:3, 9:16, 16:9
                            # Map to closest
                            if ratio > 1.5: target_aspect = "16:9"
                            elif ratio > 1.1: target_aspect = "4:3"
                            elif ratio < 0.6: target_aspect = "9:16"
                            elif ratio < 0.9: target_aspect = "3:4"
                            else: target_aspect = "1:1"
                            
                            print(f"DEBUG: Auto-Calculated Aspect Ratio: {target_aspect} (from {input_width}x{input_height})")
                        else:
                            # User made an explicit choice (even 16:9)
                            target_aspect = db_aspect_ratio
                            print(f"DEBUG: Using User-Selected Aspect Ratio: {target_aspect}")

                        # CONDITIONAL PROMPT INJECTION
                        # Check if target aspect matches input aspect (approx)
                        input_ratio = input_width / input_height
                        target_ratio_val = 1.0
                        if target_aspect == "16:9": target_ratio_val = 16/9
                        elif target_aspect == "9:16": target_ratio_val = 9/16
                        elif target_aspect == "4:3": target_ratio_val = 4/3
                        elif target_aspect == "3:4": target_ratio_val = 3/4
                        elif target_aspect == "1:1": target_ratio_val = 1.0
                        
                        if abs(input_ratio - target_ratio_val) < 0.1:
                             # Ratios match: Enforce exact dimensions
                             prompt_text += f"\n\nIMPORTANT: The output image MUST be exactly {input_width}x{input_height} pixels. Maintain the exact aspect ratio of the input image."
                        else:
                             # Ratios differ: Enforce target aspect ratio
                             prompt_text += f"\n\nIMPORTANT: The output image MUST be {target_aspect} aspect ratio. Do NOT match the input image dimensions."

                        # Convert PIL Image to Base64
                        import io
                        import base64
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG")
                        input_image_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        # content_parts.append(img)
                    except Exception as e:
                        print(f"Error loading input image: {e}")
                        # Continue without image or fail? Fail seems safer for user expectation
                        return jsonify({"error": f"Failed to load input image: {str(e)}"}), 400
                
                print(f"Generating image with prompt: {prompt_text} and image: {bool(input_image_url)}")
                
                # Save image to Supabase
                filename = f"gen_{photoshoot_id}_{int(time.time())}.png"
                
                # Generate image using gemini_client
                # We need a temporary path for the output
                UPLOAD_FOLDER = os.path.join('public', 'generated_images')
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                temp_output_path = os.path.join(UPLOAD_FOLDER, filename)
                
                result_path = gemini_client.generate_image(
                    prompt=prompt_text,
                    output_path=temp_output_path,
                    model_name="gemini-2.5-flash-image",
                    input_image_data=input_image_b64,
                    aspect_ratio=target_aspect
                )
                
                if not result_path:
                    raise Exception("Gemini Image API failed")
                
                # FORCE RESIZE TO EXACT DIMENSIONS - SMART CONDITION
                # Only resize if the target aspect ratio matches the input aspect ratio (approx)
                # This prevents squashing if user selects 1:1 but input is 16:9
                if input_width and input_height:
                    try:
                        input_ratio = input_width / input_height
                        
                        # Parse target_aspect string to float
                        target_ratio_val = 1.0
                        if target_aspect == "16:9": target_ratio_val = 16/9
                        elif target_aspect == "9:16": target_ratio_val = 9/16
                        elif target_aspect == "4:3": target_ratio_val = 4/3
                        elif target_aspect == "3:4": target_ratio_val = 3/4
                        elif target_aspect == "1:1": target_ratio_val = 1.0
                        
                        # Check if ratios match within tolerance
                        if abs(input_ratio - target_ratio_val) < 0.1:
                            from PIL import Image
                            print(f"DEBUG: Ratios match ({input_ratio:.2f} vs {target_ratio_val:.2f}). Resizing output to match input: {input_width}x{input_height}")
                            with Image.open(result_path) as gen_img:
                                resized_img = gen_img.resize((input_width, input_height), Image.Resampling.LANCZOS)
                                resized_img.save(result_path)
                        else:
                            print(f"DEBUG: Ratios mismatch ({input_ratio:.2f} vs {target_ratio_val:.2f}). Skipping resize to preserve aspect ratio.")
                            
                    except Exception as resize_err:
                        print(f"Error resizing generated image: {resize_err}")
                    except Exception as resize_err:
                        print(f"Error resizing generated image: {resize_err}")

                # Read the generated image data
                with open(result_path, 'rb') as f:
                    image_data = f.read()
                
                # Upload to Supabase Storage
                public_url = upload_to_supabase(image_data, filename, bucket_name='photoshoots')
                
                # Update task with output image URL
                supabase.table('photoshoots').update({
                    'status': 'Completed', 
                    'output_image': public_url
                }).eq('id', photoshoot_id).execute()
                
                return jsonify({"message": "Image generated successfully", "url": public_url})
                
            except Exception as e:
                print(f"Generation error: {e}")
                supabase.table('photoshoots').update({'status': 'Failed'}).eq('id', photoshoot_id).execute()
                return jsonify({"error": str(e)}), 500

        elif action == 'upscale':
            print(f"Starting upscale for task {photoshoot_id}")
            
            # Get the output_image from the database
            current_task = supabase.table('photoshoots').select('output_image').eq('id', photoshoot_id).execute()
            if not current_task.data:
                 return jsonify({"error": "Task not found"}), 404
                 
            task_data = current_task.data[0]
            output_image_url = task_data.get('output_image', '')
            
            if not output_image_url:
                return jsonify({"error": "No output image to upscale"}), 400
                
            # Update status to Processing
            supabase.table('photoshoots').update({'status': 'Processing'}).eq('id', photoshoot_id).execute()
            
            try:
                # Load the output image
                print(f"Loading image for upscale from: {output_image_url}")
                img = load_image_data(output_image_url)
                
                # Convert to base64
                import io
                import base64
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG")
                input_image_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                upscale_prompt = "Generate a high resolution, 4k, highly detailed, photorealistic version of this image. Maintain the exact composition and details but improve quality and sharpness."
                
                # content_parts = [upscale_prompt, img]
                
                print(f"Generating upscale...")
                # Generate image using gemini_client
                
                filename = f"enhanced_{photoshoot_id}_{int(time.time())}.png"
                UPLOAD_FOLDER = os.path.join('public', 'generated_images')
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                temp_output_path = os.path.join(UPLOAD_FOLDER, filename)
                
                result_path = gemini_client.generate_image(
                    prompt=upscale_prompt,
                    output_path=temp_output_path,
                    model_name="gemini-2.5-flash-image",
                    input_image_data=input_image_b64
                )
                
                if not result_path:
                    raise Exception("Gemini Upscale failed")
                
                print("Upscale response received")
                
                # Read the generated image data
                with open(result_path, 'rb') as f:
                    image_data = f.read()
                
                # Upload to Supabase Storage
                public_url = upload_to_supabase(image_data, filename, bucket_name='photoshoots')
                
                # Update task
                supabase.table('photoshoots').update({
                    'status': 'Completed', 
                    'output_image': public_url
                }).eq('id', photoshoot_id).execute()
                
                return jsonify({"message": "Image upscaled successfully", "url": public_url})

            except Exception as e:
                print(f"Upscale error: {e}")
                supabase.table('photoshoots').update({'status': 'Failed'}).eq('id', photoshoot_id).execute()
                return jsonify({"error": str(e)}), 500

                
        # Update the task with final status
        if update_data: # Ensure there's data to update before executing
            res = supabase.table('photoshoots').update(update_data).eq('id', photoshoot_id).execute()
            return jsonify({"photoshoot": res.data[0] if res.data else {}})
        
        return jsonify({"message": "No updates"})
    except Exception as e:
        print(f"Error updating photoshoot: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/photoshoots/<photoshoot_id>', methods=['DELETE'])
def delete_photoshoot(photoshoot_id):
    """Delete a photoshoot task"""
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        supabase.table('photoshoots').delete().eq('id', photoshoot_id).execute()
        return jsonify({"message": "Deleted successfully"})
    except Exception as e:
        print(f"Error deleting photoshoot: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project and all associated data"""
    if not supabase: return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        # Delete the project (cascading should handle related data if configured in DB, 
        # otherwise we might need to delete related rows first. Assuming cascade for now or simple delete)
        supabase.table('projects').delete().eq('id', project_id).execute()
        return jsonify({"message": "Project deleted successfully"})
    except Exception as e:
        print(f"Error deleting project: {e}")
        return jsonify({"error": str(e)}), 500

        return jsonify({"error": str(e)}), 500

@app.route('/api/webflow/sites', methods=['POST'])
def webflow_list_sites():
    try:
        data = request.json
        api_key = data.get('api_key')
        if not api_key: return jsonify({"error": "Missing API Key"}), 400
        sites = webflow_client.list_sites(api_key)
        return jsonify({"sites": sites})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/webflow/collections', methods=['POST'])
def webflow_list_collections():
    try:
        data = request.json
        api_key = data.get('api_key')
        site_id = data.get('site_id')
        if not api_key or not site_id: return jsonify({"error": "Missing API Key or Site ID"}), 400
        collections = webflow_client.list_collections(api_key, site_id)
        return jsonify({"collections": collections})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-blog-image', methods=['POST'])
def generate_blog_image_endpoint():
    data = request.json
    page_id = data.get('page_id')
    custom_prompt = data.get('prompt')
    
    if not page_id: return jsonify({"error": "page_id required"}), 400
    
    try:
        # Fetch page
        page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
        if not page_res.data: return jsonify({"error": "Page not found"}), 404
        page = page_res.data
        
        tech_data = page.get('tech_audit_data') or {}
        topic = tech_data.get('title') or page.get('url') or 'Untitled'
        content = page.get('content') or ''
        summary = content[:500] if content else ''
        
        # Generate Prompt if not provided
        if not custom_prompt:
            prompt = generate_image_prompt(topic, summary)
        else:
            prompt = custom_prompt
            
        # Generate Image
        image_url = nano_banana_client.generate_image(prompt)
        
        # Update Page
        supabase.table('pages').update({
            'main_image_url': image_url,
            'image_prompt': prompt
        }).eq('id', page_id).execute()
        
        return jsonify({
            "message": "Image generated successfully",
            "image_url": image_url,
            "prompt": prompt
        })
        
    except Exception as e:
        print(f"Error generating blog image: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-html-content', methods=['POST'])
def get_html_content():
    """Get HTML-formatted content for copy-paste (same logic as Webflow publish)"""
    data = request.json
    page_id = data.get('page_id')
    
    if not page_id:
        return jsonify({"error": "Missing page_id"}), 400
        
    try:
        # Fetch page
        page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
        if not page_res.data: 
            return jsonify({"error": "Page not found"}), 404
        page = page_res.data
        
        # Get raw markdown content
        content_md = page.get('content', '')
        if not content_md:
            return jsonify({"error": "No content to convert"}), 400
        
        # ==== SAME MARKDOWN PRE-PROCESSING AS WEBFLOW PUBLISH ====
        import re
        
        # 0. Fix space between ] and ( in markdown links
        content_md = re.sub(r'\]\s+\(', '](', content_md)
        content_md = re.sub(r'\*\*\s*\]', '**]', content_md)
        
        # 1. Fix malformed links with asterisks
        def clean_link_text(match):
            link_text = match.group(1)
            url = match.group(2)
            clean_text = link_text.replace('*', '')
            return f'[{clean_text}]({url})'
        content_md = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', clean_link_text, content_md)
        
        # 2. Fix raw URL display after links
        content_md = re.sub(r'\]\(([^)]+)\)\s*\(\1\)', r'](\1)', content_md)
        
        # 3. Fix raw URLs displayed in parentheses after links
        content_md = re.sub(r'\]\(([^)]+)\)\s*\(https?://[^)]+\)', r'](\1)', content_md)
        
        # 4. Ensure headings have proper spacing
        content_md = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', content_md)
        
        # 5. Fix excessive heading levels
        content_md = re.sub(r'^#{5,}\s', '### ', content_md, flags=re.MULTILINE)
        content_md = re.sub(r'^#{4}\s', '### ', content_md, flags=re.MULTILINE)
        
        # 6. Table formatting: ensure blank lines before/after tables
        lines = content_md.split('\n')
        processed_lines = []
        in_table = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            is_table_line = stripped.startswith('|') and stripped.endswith('|') and '|' in stripped[1:-1]
            
            if is_table_line and not in_table:
                if processed_lines and processed_lines[-1].strip():
                    processed_lines.append('')
                in_table = True
            elif not is_table_line and in_table:
                if stripped:
                    processed_lines.append('')
                in_table = False
            
            processed_lines.append(line)
        
        content_md = '\n'.join(processed_lines)
        
        # 7. Fix bullet points
        content_md = re.sub(r'^(\s*)\*\s+', r'\1- ', content_md, flags=re.MULTILINE)
        
        # Convert to HTML
        content_html = markdown.markdown(
            content_md, 
            extensions=['tables', 'nl2br', 'fenced_code', 'sane_lists']
        )
        
        # POST-PROCESSING: Fix links appearing on own line
        content_html = re.sub(r'<br\s*/?>\s*(<a\s)', r'\1', content_html)
        content_html = re.sub(r'<br\s*/?>(s*<a\s)', r'\1', content_html)
        content_html = re.sub(r'(</a>)\s*<br\s*/?>', r'\1', content_html)
        content_html = re.sub(r'(</a>)<br\s*/?>\s*', r'\1 ', content_html)
        content_html = re.sub(r'\n\s*(<a\s)', r' \1', content_html)
        content_html = re.sub(r'(</a>)\s*\n', r'\1 ', content_html)
        
        # Force display:inline on all anchor tags
        content_html = re.sub(r'<a href=', r'<a style="display:inline;" href=', content_html)
        
        # Add inline styles for tables
        content_html = content_html.replace(
            '<table>', 
            '<table style="width:100%;border-collapse:collapse;margin:20px 0;">'
        )
        content_html = content_html.replace(
            '<th>', 
            '<th style="border:1px solid #ddd;padding:12px;text-align:left;background-color:#f5f5f5;font-weight:bold;">'
        )
        content_html = content_html.replace(
            '<td>', 
            '<td style="border:1px solid #ddd;padding:12px;text-align:left;">'
        )
        
        return jsonify({"html": content_html, "title": page.get('tech_audit_data', {}).get('title', '')})
        
    except Exception as e:
        print(f"Error getting HTML content: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-findings-report', methods=['POST'])
def generate_findings_report():
    """Generate AI-powered SEO recommendations based on audit findings using Gemini"""
    data = request.json
    domain = data.get('domain', 'the website')
    findings = data.get('findings', {})
    sample_urls = data.get('sampleUrls', {})
    
    try:
        # Build comprehensive prompt for Gemini
        prompt = f"""You are an expert SEO consultant. Analyze the following technical audit findings for {domain} and provide a comprehensive, actionable report.

## Audit Summary
- Total Pages: {findings.get('total', 0)}
- Pages Audited: {findings.get('audited', 0)}
- Average OnPage Score: {findings.get('avgScore', 0)}%
- Average Load Time: {findings.get('avgLoadTime', 0)}ms

## Issues Found
- Missing H1 Tags: {findings.get('missingH1', 0)} pages
- Missing Meta Descriptions: {findings.get('missingMeta', 0)} pages
- Slow Loading Pages (>3s): {findings.get('slowLoading', 0)} pages
- Pages with Missing Alt Text: {findings.get('missingAlt', 0)} pages
- 4xx Errors: {findings.get('errors4xx', 0)} pages
- 5xx Server Errors: {findings.get('errors5xx', 0)} pages
- Redirects: {findings.get('redirects', 0)} pages
- Canonical Mismatches: {findings.get('canonicalMismatch', 0)} pages
- Missing Schema Markup: {findings.get('missingSchema', 0)} pages

## Sample URLs with Issues
{chr(10).join([f"- Missing H1: {url}" for url in sample_urls.get('missingH1', [])]) or "None"}
{chr(10).join([f"- Missing Meta: {url}" for url in sample_urls.get('missingMeta', [])]) or "None"}
{chr(10).join([f"- Slow Loading: {url}" for url in sample_urls.get('slowLoading', [])]) or "None"}

Please provide a report with the following sections formatted in clean, modern HTML. Do not use Markdown (no hashes or asterisks). Use <h3> for section headers, <ul>/<li> for lists, and <strong> for emphasis. Use emojis where appropriate.

<h3>🎯 Executive Summary</h3>
[Brief 2-3 sentence overview]

<h3>🚨 Critical Issues (Fix Immediately)</h3>
[List critical issues]

<h3>⚠️ Important Improvements</h3>
[Medium-priority issues]

<h3>💡 Quick Wins</h3>
[Easy fixes]

<h3>📋 Recommended Action Plan</h3>
[Prioritized step-by-step plan]

<h3>📊 Expected Impact</h3>
[Expected SEO improvements]

Keep the response concise but actionable. Use simple language. Do not wrap the response in ```html``` or ```json``` blocks, just return the raw HTML code."""

        # Call Gemini
        report_text = gemini_client.generate_content(prompt)
        
        if not report_text:
            report_text = """## Unable to Generate Report

The AI analysis could not be completed. Please ensure:
1. Pages have been audited (run "Perform Audit" first)
2. Your Gemini API key is configured correctly

Try clicking "Generate AI Report" again."""
        
        return jsonify({"report": report_text})
        
    except Exception as e:
        print(f"Error generating findings report: {e}")
        return jsonify({"error": str(e), "report": f"Error generating report: {str(e)}"}), 500

@app.route('/api/generate-audit-slides', methods=['POST'])
def generate_audit_slides():
    """Generate a Google Slides presentation from audit findings"""
    data = request.json
    domain = data.get('domain', 'Website')
    findings = data.get('findings', {})
    folder_id = data.get('folder_id')  # Optional Drive folder
    
    try:
        # First, generate AI recommendations using Gemini
        prompt = f"""You are an SEO expert. Based on these audit findings for {domain}, provide 5 brief, actionable recommendations.

Issues found:
- Missing H1 Tags: {len(findings.get('missingH1', []))} pages
- Missing Meta Descriptions: {len(findings.get('missingMeta', []))} pages
- Low OnPage Scores: {len(findings.get('lowScores', []))} pages
- Missing Alt Text: {len(findings.get('missingAlt', []))} pages
- Slow Loading Pages: {len(findings.get('slowLoading', []))} pages

Format as numbered list, max 2 sentences each. Plain text only, no markdown."""

        recommendations = gemini_client.generate_content(prompt) or "Run a full audit to generate recommendations."
        
        # Import slides generator and auth module (from same api/ folder)
        from api.slides_generator import create_audit_slides
        from api.google_auth import get_google_credentials, is_production, credentials_from_session, get_service_account_credentials
        
        # Get credentials based on environment
        creds = None
        
        # Try Service Account first (works everywhere, no user login needed)
        creds = get_service_account_credentials()
        
        if not creds:
            # In production, use web OAuth flow via session
            if is_production():
                creds = credentials_from_session(session.get('google_credentials'))
                if not creds:
                    # User needs to authenticate
                    return jsonify({
                        "success": False,
                        "needs_auth": True,
                        "message": "Please sign in with Google to create slides"
                    }), 401
            else:
                # Local development - use Desktop OAuth
                creds = get_google_credentials()
        
        presentation_url = create_audit_slides(
            findings=findings,
            domain=domain,
            recommendations=recommendations,
            folder_id=folder_id,
            creds=creds
        )
        
        return jsonify({
            "success": True,
            "presentation_url": presentation_url,
            "message": "Slides presentation created successfully"
        })
        
    except FileNotFoundError as e:
        print(f"Google OAuth not configured: {e}")
        return jsonify({
            "success": False,
            "error": "Google OAuth not configured. Please add client_secret.json to the project root.",
            "setup_instructions": "1. Go to console.cloud.google.com\n2. Create OAuth credentials (Desktop App)\n3. Download and save as client_secret.json"
        }), 400
    except Exception as e:
        print(f"Error generating audit slides: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============ OAuth Routes for Google Slides (Production) ============

@app.route('/oauth/start')
def oauth_start():
    """Start OAuth flow - redirects user to Google login"""
    from api.google_auth import get_auth_url, is_production
    
    # Store the return path so we can redirect back after auth
    session['oauth_return_path'] = request.args.get('return_path', '/')
    session['oauth_pending_data'] = request.args.get('return_data', '{}')
    
    # Build callback URL - must match EXACTLY what's in Google Cloud Console
    if is_production():
        # Use HTTPS explicitly (Railway may report HTTP in request.host_url)
        host = request.host  # e.g., web-production-74d2.up.railway.app
        callback_url = f'https://{host}/oauth/callback'
    else:
        callback_url = 'http://localhost:5003/oauth/callback'
    
    try:
        auth_url, state = get_auth_url(callback_url)
        session['oauth_state'] = state
        return redirect(auth_url)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback from Google"""
    from api.google_auth import exchange_code_for_credentials, credentials_to_session_data, is_production
    
    code = request.args.get('code')
    if not code:
        return "Authorization failed: No code received", 400
    
    # Build callback URL (must match what was used in /oauth/start)
    if is_production():
        host = request.host
        callback_url = f'https://{host}/oauth/callback'
    else:
        callback_url = 'http://localhost:5003/oauth/callback'
    
    try:
        creds = exchange_code_for_credentials(code, callback_url)
        session['google_credentials'] = credentials_to_session_data(creds)
        
        # Redirect back to the original page
        return_path = session.pop('oauth_return_path', '/')
        return redirect(return_path + '?oauth_success=true')
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return f"Authorization failed: {str(e)}", 400


@app.route('/oauth/status')
def oauth_status():
    """Check if user is authenticated with Google"""
    from api.google_auth import credentials_from_session
    
    creds = credentials_from_session(session.get('google_credentials'))
    return jsonify({
        "authenticated": creds is not None,
        "has_token": 'google_credentials' in session
    })

@app.route('/api/publish-webflow', methods=['POST'])
def webflow_publish():
    data = request.json
    page_id = data.get('page_id')
    api_key = data.get('api_key')
    collection_id = data.get('collection_id')
    field_mapping = data.get('field_mapping', {}) # { 'wf_field_slug': 'data_key' }
    
    if not all([page_id, api_key, collection_id]):
        return jsonify({"error": "Missing required fields"}), 400
        
    try:
        # Fetch page
        page_res = supabase.table('pages').select('*').eq('id', page_id).single().execute()
        if not page_res.data: return jsonify({"error": "Page not found"}), 404
        page = page_res.data
        
        # Prepare content
        content_md = page.get('content', '')
        
        # ==== COMPREHENSIVE MARKDOWN PRE-PROCESSING (Ported from seo-saas-brain) ====
        # Fix common Gemini output issues before converting to HTML
        import re
        
        # 0. Fix space between ] and ( in markdown links: [text] (url) -> [text](url)
        content_md = re.sub(r'\]\s+\(', '](', content_md)
        content_md = re.sub(r'\*\*\s*\]', '**]', content_md) # Bold inside link fix sometimes
        
        # 1. Fix malformed links with asterisks: [*text*](url) or [text*](url) -> [text](url)
        # Pattern: Find markdown links and clean asterisks from the link text
        def clean_link_text(match):
            link_text = match.group(1)
            url = match.group(2)
            # Remove asterisks from link text
            clean_text = link_text.replace('*', '')
            return f'[{clean_text}]({url})'
        content_md = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', clean_link_text, content_md)
        
        # 2. Fix raw URL display after links: [text](url) (url) -> [text](url)
        content_md = re.sub(r'\]\(([^)]+)\)\s*\(\1\)', r'](\1)', content_md)
        
        # 3. Fix raw URLs displayed in parentheses after links
        content_md = re.sub(r'\]\(([^)]+)\)\s*\(https?://[^)]+\)', r'](\1)', content_md)
        
        # 4. Ensure headings have proper spacing (add newline before if missing)
        content_md = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', content_md)
        
        # 5. Fix #### raw heading chars appearing as text
        # Replace multiple # followed by space at start of line with proper H2/H3
        content_md = re.sub(r'^#{5,}\s', '### ', content_md, flags=re.MULTILINE)
        content_md = re.sub(r'^#{4}\s', '### ', content_md, flags=re.MULTILINE)
        
        # 6. Table formatting: ensure blank lines before/after tables
        lines = content_md.split('\n')
        processed_lines = []
        in_table = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            is_table_line = stripped.startswith('|') and stripped.endswith('|') and '|' in stripped[1:-1]
            
            if is_table_line and not in_table:
                # Starting a table - add blank line before if previous line isn't blank
                if processed_lines and processed_lines[-1].strip():
                    processed_lines.append('')
                in_table = True
            elif not is_table_line and in_table:
                # Ending a table - add blank line after
                if stripped:  # Only add blank if next line isn't already blank
                    processed_lines.append('')
                in_table = False
            
            processed_lines.append(line)
        
        content_md = '\n'.join(processed_lines)
        
        # 7. Ensure proper list formatting (bullet points need consistent spacing)
        # Fix asterisk-as-text becoming bullet: line starting with * followed by space
        content_md = re.sub(r'^(\s*)\*\s+', r'\1- ', content_md, flags=re.MULTILINE)
        
        # Use extensions: tables, nl2br (for line breaks in lists), fenced_code, sane_lists
        content_html = markdown.markdown(
            content_md, 
            extensions=['tables', 'nl2br', 'fenced_code', 'sane_lists']
        )
        
        # POST-PROCESSING: Aggressive fix for links appearing on their own line
        # 1. Remove <br> or <br/> right BEFORE anchor tags
        content_html = re.sub(r'<br\s*/?>\s*(<a\s)', r'\1', content_html)
        content_html = re.sub(r'<br\s*/?>(\s*<a\s)', r'\1', content_html)
        
        # 2. Remove <br> or <br/> right AFTER closing anchor tags  
        content_html = re.sub(r'(</a>)\s*<br\s*/?>', r'\1', content_html)
        content_html = re.sub(r'(</a>)<br\s*/?>\s*', r'\1 ', content_html)
        
        # 3. Remove literal newlines around anchor tags in the HTML itself
        content_html = re.sub(r'\n\s*(<a\s)', r' \1', content_html)
        content_html = re.sub(r'(</a>)\s*\n', r'\1 ', content_html)
        
        # 4. Force display:inline on all anchor tags - Webflow Rich Text may render them as block
        content_html = re.sub(r'<a href=', r'<a style="display:inline;" href=', content_html)
        
        # Add inline styles for tables (Webflow rich text needs inline styles)
        content_html = content_html.replace(
            '<table>', 
            '<table style="width:100%;border-collapse:collapse;margin:20px 0;">'
        )
        content_html = content_html.replace(
            '<th>', 
            '<th style="border:1px solid #ddd;padding:12px;text-align:left;background-color:#f5f5f5;font-weight:bold;">'
        )
        content_html = content_html.replace(
            '<td>', 
            '<td style="border:1px solid #ddd;padding:12px;text-align:left;">'
        )
        
        # Prepare fields
        site_id = data.get('site_id')  # Frontend needs to pass this
        image_wf_field = None
        image_url = None
        
        fields = {}
        for wf_field, data_key in field_mapping.items():
            value = None
            if data_key == 'title':
                value = page.get('tech_audit_data', {}).get('title') or page.get('url')
            elif data_key == 'slug':
                value = page.get('slug')
            elif data_key == 'content':
                value = content_html
            elif data_key == 'meta_description':
                value = page.get('tech_audit_data', {}).get('meta_description')
            elif data_key == 'main_image':
                # Store for later processing - we need to upload the image first
                image_wf_field = wf_field
                image_url = page.get('main_image_url')
                continue  # Don't add to fields yet
            
            if value:
                fields[wf_field] = value
        
        # Handle image upload if present
        if image_url and site_id and image_wf_field:
            try:
                import tempfile
                import requests as req
                
                # Download image from Supabase URL
                print(f"DEBUG: Downloading image from {image_url}", flush=True)
                img_response = req.get(image_url, timeout=30)
                img_response.raise_for_status()
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                    tmp.write(img_response.content)
                    tmp_path = tmp.name
                
                print(f"DEBUG: Image downloaded to {tmp_path}", flush=True)
                
                # Upload to Webflow
                asset = webflow_client.upload_asset(api_key, site_id, tmp_path)
                
                # Use asset ID (or URL) in the field
                # Webflow v2 API might use 'fileId' or 'url' - check the asset response
                if 'id' in asset:
                    fields[image_wf_field] = asset['id']
                    print(f"DEBUG: Using asset ID: {asset['id']}", flush=True)
                elif 'url' in asset:
                    fields[image_wf_field] = asset['url']
                    print(f"DEBUG: Using asset URL: {asset['url']}", flush=True)
                
                # Clean up temp file
                import os
                os.unlink(tmp_path)
                
            except Exception as img_error:
                print(f"WARNING: Failed to upload image to Webflow: {img_error}", flush=True)
                # Continue without image rather than failing entire publish
                
        # Publish
        with open('debug_payload.json', 'w') as f:
            json.dump(fields, f, indent=2)
        print(f"DEBUG: Webflow Payload: {json.dumps(fields, indent=2)}", flush=True)
        try:
            res = webflow_client.create_item(api_key, collection_id, fields, is_draft=True)
        except Exception as e:
            # Check for 409 Conflict (Slug already exists)
            error_msg = str(e)
            if "409" in error_msg or "Conflict" in error_msg:
                print(f"DEBUG: Slug conflict detected. Searching for existing item to update...", flush=True)
                
                target_slug = fields.get('slug')
                existing_item = None
                
                # Paginate through items to find the conflicting one
                limit = 100
                offset = 0
                max_pages = 20 # Search up to 2000 items (safety limit)
                
                for _ in range(max_pages):
                    print(f"DEBUG: Searching items offset={offset}...", flush=True)
                    items = webflow_client.list_items(api_key, collection_id, limit=limit, offset=offset)
                    
                    if not items:
                        break # End of list
                        
                    found = False
                    for item in items:
                        # Webflow V2: check fieldData.slug
                        if item.get('fieldData', {}).get('slug') == target_slug:
                            existing_item = item
                            found = True
                            break
                    
                    if found:
                        break
                        
                    if len(items) < limit:
                        break # Last page
                        
                    offset += limit

                if existing_item:
                    print(f"DEBUG: Found existing item {existing_item['id']}. Updating to Draft...", flush=True)
                    res = webflow_client.update_item(api_key, collection_id, existing_item['id'], fields, is_draft=True)
                else:
                    raise Exception(f"Conflict detected for slug '{target_slug}' but could not find existing item (checked {offset + limit} items). Please manually delete the item in Webflow or change the slug.")
            else:
                raise e

        
        # Update status
        supabase.table('pages').update({'status': 'Published'}).eq('id', page_id).execute()
        
        return jsonify({"message": "Published successfully", "webflow_response": res})
        
    except Exception as e:
        print(f"Error publishing to Webflow: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-image', methods=['GET'])
def download_image():
    """
    Download an image with PIL re-encoding to ensure valid JPEG format.
    This fixes corrupt images generated before the PIL fix.
    """
    image_url = request.args.get('url')
    if not image_url:
        return jsonify({"error": "url parameter required"}), 400
    
    try:
        import requests as req
        import tempfile
        from PIL import Image
        import io
        
        print(f"DEBUG: download_image called with URL: {image_url}", flush=True)
        print(f"DEBUG: URL starts with '/': {image_url.startswith('/')}", flush=True)
        
        # Handle relative URLs (e.g., /generated-images/...)
        if image_url.startswith('/'):
            # It's a relative path - read directly from disk
            # Note: URLs use /generated-images/ but directory is generated_images
            clean_path = image_url.lstrip('/').replace('generated-images/', 'generated_images/')
            file_path = os.path.join(BASE_DIR, 'public', clean_path)
            print(f"DEBUG: Reading local file for re-encoding: {file_path}", flush=True)
            print(f"DEBUG: File exists: {os.path.exists(file_path)}", flush=True)
            
            if not os.path.exists(file_path):
                print(f"ERROR: File not found at {file_path}", flush=True)
                return jsonify({"error": f"File not found: {image_url}"}), 404
            
            with open(file_path, 'rb') as f:
                image_data = f.read()
            print(f"DEBUG: Read {len(image_data)} bytes from disk", flush=True)
        else:
            # It's an absolute URL - download it
            print(f"DEBUG: Downloading image for re-encoding: {image_url}", flush=True)
            response = req.get(image_url, timeout=30)
            response.raise_for_status()
            image_data = response.content
            print(f"DEBUG: Downloaded {len(image_data)} bytes", flush=True)
        
        # Load and re-encode with PIL
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, 'JPEG', quality=95, optimize=True)
        buffer.seek(0)
        
        # Generate filename from URL or default
        from urllib.parse import urlparse
        parsed = urlparse(image_url)
        filename = os.path.basename(parsed.path) or 'image.jpg'
        if not filename.endswith('.jpg'):
            filename = filename.rsplit('.', 1)[0] + '.jpg'
        
        # Return as download
        from flask import send_file
        return send_file(
            buffer,
            mimetype='image/jpeg',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Error downloading image: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
