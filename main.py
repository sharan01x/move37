#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LifeScribe Main Application Entry Point

This module serves as the entry point for the LifeScribe application, 
which processes user data packages containing text, voice, and/or files.
"""

import uvicorn
import signal
import sys
import os
import threading
import time

from app.api.main import app

def signal_handler(sig, frame):
    """Handle termination signals by forcibly exiting."""
    print("\nSIGINT received. Shutting down gracefully...")
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
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        print(f"Error running server: {e}")
        sys.exit(1)