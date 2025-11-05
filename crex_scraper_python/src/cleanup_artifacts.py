#!/usr/bin/env python3
"""Cleanup script for expired diagnostic artifacts.

Run this script via cron or scheduled task to enforce retention policies.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging.adapters import configure_logging, get_logger
from src.logging.diagnostics import prune_expired_artifacts

configure_logging()
logger = get_logger(component="artifact_cleanup")

def main():
    """Execute artifact cleanup based on configured retention."""
    logger.info("cleanup.start")
    
    try:
        prune_expired_artifacts()
        logger.info("cleanup.complete")
        return 0
    except Exception as e:
        logger.error("cleanup.error", metadata={"error": str(e)})
        return 1

if __name__ == "__main__":
    sys.exit(main())
