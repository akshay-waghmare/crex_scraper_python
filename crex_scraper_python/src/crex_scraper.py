import requests
import time
from playwright.sync_api import sync_playwright, Page
from src.logging.adapters import get_logger
from src.logging.diagnostics import capture_html_snapshot

logger = get_logger(component="crex_scraper")

class ScrapeError(Exception):
    pass

class NetworkError(ScrapeError):
    pass

class DOMChangeError(ScrapeError):
    pass

def scrape(url):
    start_time = time.time()
    stage_timings = {}
    
    logger.info("scrape.start", metadata={"url": url})
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Navigation stage
            nav_start = time.time()
            logger.info("navigation.start", metadata={"url": url})
            page.goto(url)
            page.wait_for_timeout(5000)
            stage_timings["navigation"] = time.time() - nav_start
            logger.info("navigation.complete", metadata={"url": url, "duration_ms": int(stage_timings["navigation"] * 1000)})

            # DOM validation stage
            dom_start = time.time()
            logger.info("dom.check", metadata={"selector": "div.live-card"})
            if not page.query_selector("div.live-card"):
                # Capture HTML snapshot for DOM drift analysis
                html_content = page.content()
                artifact_path = capture_html_snapshot(html_content)
                logger.warning(
                    "dom.selector.missing",
                    metadata={
                        "selector": "div.live-card",
                        "url": url,
                        "artifact": str(artifact_path),
                        "remediation": "Check if site markup changed or selector needs update"
                    }
                )
                raise DOMChangeError("Cannot locate essential 'div.live-card' element")
            
            stage_timings["dom_eval"] = time.time() - dom_start
            logger.info("dom.ready", metadata={"duration_ms": int(stage_timings["dom_eval"] * 1000)})

            # Extraction stage
            extract_start = time.time()
            logger.info("extraction.start")
            live_divs = page.query_selector_all("div.live-card .live")
            data = []
            for idx, live_div in enumerate(live_divs):
                parent_element = live_div.query_selector(":scope >> xpath=..")
                grandparent_element = parent_element.query_selector(":scope >> xpath=..")
                sibling_element = grandparent_element.query_selector(":scope >> xpath=following-sibling::*[1]")
                item_url = sibling_element.get_attribute('href')
                data.append(item_url)
            
            stage_timings["extraction"] = time.time() - extract_start
            total_duration = time.time() - start_time
            
            logger.info(
                "extraction.complete",
                metadata={
                    "url_count": len(data),
                    "duration_ms": int(stage_timings["extraction"] * 1000),
                    "total_duration_ms": int(total_duration * 1000),
                    "stage_timings": {k: int(v * 1000) for k, v in stage_timings.items()}
                }
            )
            return data

    except NetworkError as ne:
        logger.error("network.error", metadata={"error": str(ne), "url": url})
        raise ne
    except DOMChangeError as de:
        # HTML already captured in the warning log above
        logger.error("dom.change_error", metadata={"error": str(de), "url": url})
        raise de
    except Exception as e:
        logger.error("scrape.error", metadata={"error": str(e), "url": url})
        raise ScrapeError(f"Error during scraping: {e}")


# Backward compatibility alias
fetchData = scrape