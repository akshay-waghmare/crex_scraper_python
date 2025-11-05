import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import requests
from src.cricket_data_service import CricketDataService
import threading
import time
import sqlite3
import sys
import os

# Add parent directory to path to import root-level crex_scraper
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)
from crex_scraper import fetchData as fetch_match_data  # The detailed match scraper
from src.shared import scraping_tasks
from src.logging.adapters import configure_logging, get_logger, bind_correlation_id

app = Flask(__name__)
CORS(app, resources={
    r"/add-lead": {
        "origins": "*",
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Configure structured JSON logging
configure_logging(level=logging.DEBUG)
logger = get_logger(component="crex_main_url")

class ScrapeError(Exception):
    pass

class NetworkError(ScrapeError):
    pass

class DOMChangeError(ScrapeError):
    pass

DB_FILE = 'url_state.db'

def initialize_database():
    """Creates database and tables if they don't exist."""
    logger.info("database.init", metadata={"message": "Initializing database"})
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_urls (
                url TEXT PRIMARY KEY,
                deletion_attempts INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('DELETE FROM scraped_urls')
        
        # Add leads table creation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website TEXT,
                contact_email TEXT,
                phone_number TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logger.info("database.clear", metadata={"message": "All URLs removed from the table"})
        logger.info("database.init_complete", metadata={"message": "Database initialized successfully"})
    except Exception as e:
        logger.error("database.init_error", metadata={"error": str(e)})
    finally:
        conn.close()

def store_urls(urls):
    logger.info("urls.store", metadata={"url_count": len(urls)})
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executemany("INSERT INTO scraped_urls (url, deletion_attempts) VALUES (?, 0) ON CONFLICT(url) DO UPDATE SET deletion_attempts = 0", [(url,) for url in urls])
        conn.commit()
        logger.info("urls.store_complete", metadata={"message": "URLs stored successfully"})
    except Exception as e:
        logger.error("urls.store_error", metadata={"error": str(e)})
    finally:
        conn.close()
    

def load_previous_urls():
    logger.info("urls.load", metadata={"message": "Loading previous URLs"})
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM scraped_urls")
        results = cursor.fetchall()
        logger.info("urls.load_complete", metadata={"count": len(results)})
        return [row[0] for row in results]
    except Exception as e:
        logger.error("urls.load_error", metadata={"error": str(e)})
        return []
    finally:
        conn.close()

def get_changes(new_urls):
    logger.info("urls.diff", metadata={"new_url_count": len(new_urls)})
    previous_urls = load_previous_urls()
    added_urls = set(new_urls) - set(previous_urls)
    deleted_urls = set(previous_urls) - set(new_urls)
    logger.info("urls.diff_complete", metadata={"added": len(added_urls), "deleted": len(deleted_urls)})
    return added_urls, deleted_urls

def job():
    correlation_id = bind_correlation_id()
    logger.info("job.start", metadata={"correlation_id": correlation_id, "message": "Starting scraping job"})
    url = "https://crex.com"
    with sync_playwright() as p:
            browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            page = browser.new_page()

            while True:
                try:
                    url = "https://crex.com"
                    scrape(page, url)
                    time.sleep(60)
                except Exception as e:
                    logging.error(f"Error in periodic task: {e}")
                    
def scrape(page, url):
    logging.info(f"Scraping URL: {url}")
    try:
        page.goto(url)
        page.wait_for_timeout(10000)
        
        if not page.query_selector("div.live-card"):  
            raise DOMChangeError("Cannot locate essential 'div.live-card' element")
        
        live_divs = page.query_selector_all("div.live-card .live")

        urls = []
        for live_div in live_divs:
            parent_element = live_div.query_selector(":scope >> xpath=..")
            grandparent_element = parent_element.query_selector(":scope >> xpath=..")
            sibling_element = grandparent_element.query_selector(":scope >> xpath=following-sibling::*[1]")
            url = sibling_element.get_attribute('href')
            urls.append(url)

        logging.info(f"Scraped URLs: {urls}")

        # Convert relative URLs to absolute URLs
        urls = ['https://crex.com' + url for url in urls]
        logging.info(f"Full URLs: {urls}")
        
        previous_urls = load_previous_urls()
        added_urls, deleted_urls = get_changes(urls)    
        if not previous_urls:
            added_urls = urls
            deleted_urls = []
        store_urls(urls)
        
        # CRITICAL: Sync complete list of live matches with backend on EVERY scrape
        # This allows backend to mark old/finished matches for deletion
        try:
            logger.info("backend.sync_live_matches.start", metadata={"url_count": len(urls)})
            token = CricketDataService.get_bearer_token()
            if token:
                CricketDataService.add_live_matches(urls, token)
                logger.info("backend.sync_live_matches.complete", metadata={"url_count": len(urls), "synced": True})
            else:
                logger.warning("backend.sync_live_matches.skipped", metadata={"reason": "No bearer token available"})
        except Exception as e:
            logger.warning("backend.sync_live_matches.error", metadata={"error": str(e), "message": "Backend sync failed, continuing with local scraping"})
        
        if added_urls or deleted_urls:
            if added_urls:
                logger.info("matches.new_detected", metadata={"count": len(added_urls), "urls": list(added_urls)})
                for i, url in enumerate(added_urls):
                    # URL is already absolute (contains https://crex.com)
                    logger.info("matches.trigger_scrape", metadata={"url": url, "index": i+1, "total": len(added_urls)})
                    
                    # Add a small delay between requests to avoid overwhelming the system
                    if i > 0:
                        time.sleep(2)
                    
                    response = requests.post('http://127.0.0.1:5000/start-scrape', json={'url': url})
                    if response.status_code == 200:
                        logger.info("matches.scrape_started", metadata={"url": url})
                    else:
                        logger.error("matches.scrape_failed", metadata={"url": url, "status_code": response.status_code})
                
        time.sleep(60)                
        return {'status': 'Scraping finished', 'match_urls': urls}
    except NetworkError as ne:
        logging.error(f"Network error occurred: {ne}")
        raise ne
    except DOMChangeError as de:
        logging.error(f"DOM change error occurred: {de}")
        raise de
    except Exception as e:
        logging.error(f"Error during navigation: {e}")
        raise ScrapeError(f"Error during navigation: {e}")


@app.route('/scrape-live-matches-link', methods=['GET'])
def scrape_live_matches():
    try:
        logging.info("Received request to scrape live matches")
        scraping_thread = threading.Thread(target=job)
        scraping_thread.daemon = True
        scraping_thread.start()

        return jsonify({'status': 'Scraping started'})
    except ScrapeError as se:
        logging.error(f"Scraping error occurred: {se}")
        return jsonify({'status': 'Scraping error', 'error_message': str(se)})
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({'status': 'Error occurred', 'error_message': str(e)})

@app.route('/start-scrape', methods=['POST'])
def start_scrape():
    url = request.json.get('url')
    
    if not url:
        logger.warning("scrape.request.no_url", metadata={"source": "start_scrape"})
        response = jsonify({'status': 'No url provided'}), 400
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    
    # Bind correlation ID for this scraping job
    correlation_id = bind_correlation_id()
    logger.info("scrape.request.received", metadata={"url": url, "correlation_id": correlation_id})
    
    # Wrapper function to maintain correlation ID in thread
    def scrape_with_context():
        bind_correlation_id(correlation_id)
        try:
            fetch_match_data(url)  # Use the detailed match scraper
            logger.info("scrape.job.complete", metadata={"url": url})
        except KeyboardInterrupt:
            logger.warning("scrape.job.interrupted", metadata={"url": url})
        except Exception as e:
            logger.error("scrape.job.failed", metadata={"url": url, "error": str(e), "error_type": type(e).__name__})
        finally:
            # Update task status
            if url in scraping_tasks:
                scraping_tasks[url]['status'] = 'stopped'
    
    thread = threading.Thread(target=scrape_with_context, daemon=True)
    scraping_tasks[url] = {'thread': thread, 'status': 'running'}
    thread.start()
    
    logger.info("scrape.job.started", metadata={"url": url, "thread_id": str(thread.ident)})
    
    response = jsonify({'status': 'Scraping started for url: ' + url, 'correlation_id': correlation_id})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
    
@app.route('/stop-scrape', methods=['POST'])
def stop_scrape():
    url = request.json.get('url')
    if url:
        logging.info(f"Received request to stop scraping for URL: {url}")
        if url in scraping_tasks:
            task_data = scraping_tasks.get(url)
            if task_data:
                logging.info(f"Stopping scraping for url: {url}")
                task_data['status'] = 'stopping'
                thread = task_data['thread']
                thread.join(timeout=10)
                if thread.is_alive():
                    logging.warning("Thread is still alive after timeout, may need further investigation check again after some time.")                    
                else:
                    logging.info(f"Scraping stopped for url: {url}")
                    
                scraping_tasks.pop(url)
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM scraped_urls WHERE url=?", (url,))

                return jsonify({'status': f'Stopped scraping for url: {url}'})
            else:
                return jsonify({'status': 'No scraping task found for url: ' + url}), 400
        else:
            return jsonify({'status': 'No scraping task found for url: ' + url}), 400
    else:
        return jsonify({'status': 'No url provided'}), 400

@app.route("/api/v1/scraper/health", methods=["GET"])
def scraper_health():
    """Health endpoint for scraper observability."""
    try:
        health_data = {
            "status": "running",
            "active_jobs": len(scraping_tasks),
            "jobs": {}
        }
        
        for url, task_info in scraping_tasks.items():
            health_data["jobs"][url] = {
                "state": "running" if task_info.get("thread") and task_info["thread"].is_alive() else "stopped",
                "thread_id": str(task_info["thread"].ident) if task_info.get("thread") else None
            }
        
        logger.info("health.check", metadata={"active_jobs": health_data["active_jobs"]})
        return jsonify(health_data), 200
    except Exception as e:
        logger.error("health.check_error", metadata={"error": str(e)})
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/add-lead", methods=["POST", "OPTIONS"])
def add_lead():
    if request.method == "OPTIONS":
        response = jsonify({"message": "OK"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        data = request.json
        company_name = data.get("company_name")
        website = data.get("website")
        contact_email = data.get("contact_email", "")
        phone_number = data.get("phone_number", "")
        notes = data.get("notes", "")

        if not company_name or not website:
            return jsonify({"error": "Company name and website are required"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads (company_name, website, contact_email, phone_number, notes) 
            VALUES (?, ?, ?, ?, ?)""",
            (company_name, website, contact_email, phone_number, notes))
        conn.commit()
        lead_id = cursor.lastrowid
        conn.close()

        logging.info(f"New lead added: {company_name}")
        response = jsonify({"message": "Lead added successfully", "lead_id": lead_id})
        return response, 201

    except Exception as e:
        logging.error(f"Error adding lead: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/view-leads", methods=["GET"])
def view_leads():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, company_name, website, contact_email, phone_number, notes, created_at 
            FROM leads 
            ORDER BY created_at DESC""")
        leads = cursor.fetchall()
        conn.close()

        lead_list = []
        for lead in leads:
            lead_list.append({
                "id": lead[0],
                "company_name": lead[1],
                "website": lead[2],
                "contact_email": lead[3],
                "phone_number": lead[4],
                "notes": lead[5],
                "created_at": lead[6]
            })

        return jsonify({"leads": lead_list}), 200

    except Exception as e:
        logging.error(f"Error fetching leads: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/update-lead/<int:lead_id>", methods=["PUT"])
def update_lead(lead_id):
    try:
        data = request.json
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Lead not found"}), 404

        update_fields = []
        values = []
        for field in ["company_name", "website", "contact_email", "phone_number", "notes"]:
            if field in data:
                update_fields.append(f"{field} = ?")
                values.append(data[field])
        
        if update_fields:
            values.append(lead_id)
            query = f"UPDATE leads SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            
        conn.close()
        logging.info(f"Lead {lead_id} updated successfully")
        return jsonify({"message": "Lead updated successfully"}), 200

    except Exception as e:
        logging.error(f"Error updating lead: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/delete-lead/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Lead not found"}), 404

        cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()
        
        logging.info(f"Lead {lead_id} deleted successfully")
        return jsonify({"message": "Lead deleted successfully"}), 200

    except Exception as e:
        logging.error(f"Error deleting lead: {e}")
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port=5000, debug=True)