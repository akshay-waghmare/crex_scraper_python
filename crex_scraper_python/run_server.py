#!/usr/bin/env python
"""
Startup script for the Cricket Scraper Service with structured logging.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.crex_main_url import app, initialize_database

if __name__ == "__main__":
    print("Starting Cricket Scraper Service...")
    print("Initializing database...")
    initialize_database()
    print("Database initialized successfully")
    print("\nServer starting on http://0.0.0.0:5000")
    print("Press CTRL+C to quit\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
