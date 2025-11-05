import requests
from src.logging.adapters import get_logger

logger = get_logger(component="cricket_data_service")

class CricketDataService:
    BASE_URL = "https://api.cricketdata.com"

    @staticmethod
    def get_bearer_token():
        """Fetches the bearer token for authentication."""
        logger.info("auth.token.start")
        try:
            response = requests.post(f"{CricketDataService.BASE_URL}/auth/token")
            response.raise_for_status()
            token = response.json().get("token")
            logger.info("auth.token.success")
            return token
        except Exception as e:
            logger.error("auth.token.error", metadata={"error": str(e)})
            raise

    @staticmethod
    def add_live_matches(urls, token):
        """Adds live match URLs to the cricket data service."""
        logger.info("matches.add.start", metadata={"url_count": len(urls)})
        try:
            headers = {"Authorization": f"Bearer {token}"}
            for url in urls:
                response = requests.post(f"{CricketDataService.BASE_URL}/matches/live", json={"url": url}, headers=headers)
                response.raise_for_status()
                logger.info("matches.add.success", metadata={"url": url})
        except Exception as e:
            logger.error("matches.add.error", metadata={"error": str(e)})
            raise

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