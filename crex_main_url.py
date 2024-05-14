import logging
from flask import Flask, jsonify , request
from playwright.sync_api import sync_playwright
import requests
import cricket_data_service
import threading
import time
import sqlite3
from crex_scraper import fetchData
from shared import scraping_tasks
app = Flask(__name__)



# Configure logging
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ScrapeError(Exception):
    pass

class NetworkError(ScrapeError):
    pass

class DOMChangeError(ScrapeError):
    pass

DB_FILE = 'url_state.db'

def initialize_database():
    """Creates database and table if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
     # Create the table with the necessary columns upfront if possible
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraped_urls (
            url TEXT PRIMARY KEY,
            deletion_attempts INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def store_urls(urls):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.executemany("INSERT INTO scraped_urls (url, deletion_attempts) VALUES (?, 0) ON CONFLICT(url) DO UPDATE SET deletion_attempts = 0", [(url,) for url in urls])
    conn.commit()
    conn.close()

def load_previous_urls():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM scraped_urls")
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

def get_changes(new_urls):
    previous_urls = load_previous_urls()
    added_urls = set(new_urls) - set(previous_urls)
    deleted_urls = set(previous_urls) - set(new_urls)
    return added_urls, deleted_urls

def job():
    url = "https://crex.live"
    with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            while True:
                try:
                    url = "https://crex.live"
                    scrape(page, url)
                    time.sleep(60)
                except Exception as e:
                    logging.error(f"Error in periodic task: {e}")
                    
def scrape(page , url):
    
    try:
        page.goto(url)
        # wait for 10 seconds before clicking on the button
        page.wait_for_timeout(10000)
        
        # DOM Change Detection
        if not page.query_selector("div.live-card"):  
            raise DOMChangeError("Cannot locate essential 'div.live-card' element")
        
        # Evaluate JavaScript on the page to get all div.live elements and print them out
        live_divs = page.query_selector_all("div.live-card .live")

        urls = []
        for live_div in live_divs:
            # Get the parent of live_div using querySelector and then get the parent of the parent
            parent_element = live_div.query_selector(":scope >> xpath=..")
            grandparent_element = parent_element.query_selector(":scope >> xpath=..")
            sibling_element = grandparent_element.query_selector(":scope >> xpath=following-sibling::*[1]")
            url = sibling_element.get_attribute('href')
            urls.append(url)

        logging.info(f"Scraped URLs: {urls}")

        for url in urls:
            # Prepend 'https://crex.live' to the URL
            url = 'https://crex.live' + url
        # Find changes - first, before updating state 
        previous_urls = load_previous_urls()
        added_urls, deleted_urls = get_changes(urls)    
        # Treat all as added on the first run 
        if not previous_urls:   # Check if there were no previous URLs
            added_urls = urls
            deleted_urls = []
        # Now, update the database state    
        store_urls(urls)
        
        if added_urls or deleted_urls:
            # Send the URLs to your Spring Boot app
            # fetch the bearer token from cricket-data-service
            # start scraping if url is added 
                # Start scraping if url is added
                
                
                if added_urls:
                    token = cricket_data_service.get_bearer_token()
                    cricket_data_service.add_live_matches(urls, token)
                    
                    for url in added_urls:
                        # append https://crex.live to the url
                        url = 'https://crex.live' + url
                        response = requests.post('http://localhost:5000/start-scrape', json={'url': url})
                    if response.status_code == 200:
                        logging.info(f"Scraping started for url from scrape function: {url}")
                    else:
                        logging.error(f"Failed to start scraping for url: {url}")
                        # try scraping for other urls if one fails
                
                if deleted_urls:
                    token = cricket_data_service.get_bearer_token()
                    cricket_data_service.add_live_matches(urls, token)

                """ if deleted_urls:
                    for url in deleted_urls:
                        url = 'https://crex.live' + url
                        response = requests.post('http://localhost:5000/stop-scrape', json={'url': url})
                    if response.status_code == 200:
                        logging.info(f"Scraping stopped for url from scrape function: {url}")
                    else:
                        logging.error(f"Failed to stop scraping for url: {url}")   """
                # if deleted url check for these urls are deleted 3 times by maintaining count in the next loops
                               
        time.sleep(60)                
        # Consider updating to reflect actual scraping state
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

        # Background scraping thread to prevent API blocking
        scraping_thread = threading.Thread(target=job)
        scraping_thread.daemon = True  # Mark as daemon thread
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
    if url:
        thread = threading.Thread(target=fetchData, args=(url,))
        scraping_tasks[url] = {'thread': thread, 'status': 'running'}
        thread.start()  # Start the thread
        logging.info(f"Scraping started for url: {url}")
        return jsonify({'status': 'Scraping started for url: ' + url})
    else:
        return jsonify({'status': 'No url provided'}), 400

@app.route('/stop-scrape', methods=['POST'])
def stop_scrape():
    url = request.json.get('url')
    if url:
        if url in scraping_tasks:
            task_data = scraping_tasks.get(url)
            if task_data:
                logging.info(f"Stopping scraping for url: {url}")
                task_data['status'] = 'stopping'  # Signal the thread to stop
                thread = task_data['thread']
                thread.join(timeout=10)  # Add a timeout (in seconds)
                if thread.is_alive():
                    logging.warning("Thread is still alive after timeout, may need further investigation check again after some time.")                    
                else:
                    logging.info(f"Scraping stopped for url: {url}")
                    
                scraping_tasks.pop(url)
                #delete url from scraped_urls table
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
    
if __name__ == "__main__":
    initialize_database()
    app.run()
