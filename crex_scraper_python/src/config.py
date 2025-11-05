import os

class Config:
    """Configuration settings for the application."""
    
    DEBUG = os.getenv('DEBUG', 'False') == 'True'
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///url_state.db')
    LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'DEBUG')
    API_BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:5000')
    SCRAPING_INTERVAL = int(os.getenv('SCRAPING_INTERVAL', 60))  # in seconds
    ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')
    
    # Logging and diagnostics configuration
    SCRAPER_LOG_FORMAT = os.getenv('SCRAPER_LOG_FORMAT', 'json')
    SCRAPER_DEBUG_MODE = os.getenv('SCRAPER_DEBUG_MODE', 'False') == 'True'
    SCRAPER_ARTIFACT_ROOT = os.getenv('SCRAPER_ARTIFACT_ROOT', 'artifacts')
    SCRAPER_ARTIFACT_RETENTION_DAYS = int(os.getenv('SCRAPER_ARTIFACT_RETENTION_DAYS', 14))

    @staticmethod
    def init_app(app):
        """Initialize the app with the configuration."""
        pass  # Additional initialization can be done here if needed