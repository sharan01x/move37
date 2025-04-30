#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Move 37 Main Application Entry Point

This module serves as the entry point for the Move 37 application, 
which processes user data packages containing text, voice, and/or files.
"""

import uvicorn
import signal
import sys
import os
import threading
import time

from app.api.main import app
from app.core.config import API_HOST, API_PORT

def signal_handler(sig, frame):
    """Handle termination signals by forcibly exiting."""
    print("\nShutting down gracefully...")
    # Force kill after a short timeout if normal shutdown doesn't work
    def force_exit():
        time.sleep(5)
        print("Forcing exit...")
        os._exit(1)
        
    threading.Thread(target=force_exit, daemon=True).start()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # For macOS, also handle SIGBREAK if available
    try:
        signal.signal(signal.SIGBREAK, signal_handler)
    except AttributeError:
        pass
    
    try:
        uvicorn.run(app, host=API_HOST, port=API_PORT)
    except Exception as e:
        print(f"Error running server: {e}")
        sys.exit(1)