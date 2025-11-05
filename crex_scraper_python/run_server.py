#!/usr/bin/env python
"""
Startup script for the Cricket Scraper Service with structured logging.
"""

import sys
import os

# Add both current directory and parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

from src.crex_main_url import app, initialize_database

if __name__ == "__main__":
    print("Starting Cricket Scraper Service...")
    print("Initializing database...")
    initialize_database()
    print("Database initialized successfully")
    print("\nServer starting on http://0.0.0.0:5000")
    print("Press CTRL+C to quit\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
