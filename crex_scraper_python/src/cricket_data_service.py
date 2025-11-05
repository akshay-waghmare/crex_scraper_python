import requests
import os
from src.logging.adapters import get_logger

logger = get_logger(component="cricket_data_service")

class CricketDataService:
    BASE_URL = os.getenv('BACKEND_URL', 'http://127.0.0.1:8099')
    TOKEN_URL = os.getenv('TOKEN_URL', 'http://127.0.0.1:8099/token/generate-token')

    @staticmethod
    def get_bearer_token():
        """Fetches the bearer token for authentication from local backend."""
        logger.info("auth.token.start")
        
        credentials = {
            "username": os.getenv('BACKEND_USERNAME', 'tanmay'),
            "password": os.getenv('BACKEND_PASSWORD', 'tanmay')
        }
        
        try:
            response = requests.post(CricketDataService.TOKEN_URL, json=credentials)
            response.raise_for_status()
            token = response.json().get("token")
            logger.info("auth.token.success")
            return token
        except Exception as e:
            logger.error("auth.token.error", metadata={"error": str(e)})
            return None  # Don't raise, just return None so scraping can continue

    @staticmethod
    def add_live_matches(urls, token):
        """Adds live match URLs to the local backend service."""
        if not token:
            logger.warning("matches.add.skipped", metadata={"reason": "No bearer token"})
            return
            
        logger.info("matches.add.start", metadata={"url_count": len(urls)})
        
        add_matches_url = os.getenv('ADD_LIVE_MATCHES_URL', 'http://127.0.0.1:8099/cricket-data/add-live-matches')
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
            response = requests.post(add_matches_url, json=urls, headers=headers)
            response.raise_for_status()
            logger.info("matches.add.success", metadata={"url_count": len(urls)})
        except Exception as e:
            logger.error("matches.add.error", metadata={"error": str(e), "url": add_matches_url})
            # Don't raise - allow scraping to continue even if backend sync fails

    @staticmethod
    def fetch_match_data(match_id, token):
        """Fetches data for a specific match."""
        logger.info("matches.fetch.start", metadata={"match_id": match_id})
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{CricketDataService.BASE_URL}/matches/{match_id}", headers=headers)
            response.raise_for_status()
            match_data = response.json()
            logger.info("matches.fetch.success", metadata={"match_id": match_id})
            return match_data
        except Exception as e:
            logger.error("matches.fetch.error", metadata={"error": str(e), "match_id": match_id})
            raise