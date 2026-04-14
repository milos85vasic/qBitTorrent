#!/usr/bin/env python3
"""
Main entry point for the Merge Search Service.

Starts both:
1. The original download proxy (HTTP server)
2. The FastAPI merge service (REST API)
"""

import os
import sys
import threading
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def start_original_proxy():
    """Start the original download_proxy.py."""
    logger.info("Starting original download proxy...")
    try:
        engines_dir = "/config/qBittorrent/nova3/engines"
        if engines_dir not in sys.path:
            sys.path.insert(0, engines_dir)
        from download_proxy import run_server

        run_server()
    except Exception as e:
        logger.error(f"Original proxy failed: {e}")


def start_fastapi_server():
    """Start the FastAPI merge service."""
    logger.info("Starting FastAPI merge service...")
    try:
        # Add merge service to path
        sys.path.insert(0, "/config/download-proxy/src")

        import uvicorn
        from api import app

        # Configure uvicorn
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8086,  # Different port from proxy (8085)
            log_level="info",
        )
        server = uvicorn.Server(config)

        # Run in async mode
        import asyncio

        asyncio.run(server.serve())
    except Exception as e:
        logger.error(f"FastAPI server failed: {e}")


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Merge Search Service Starting")
    logger.info("=" * 60)

    # Start both servers in separate threads
    proxy_thread = threading.Thread(target=start_original_proxy, daemon=True)
    fastapi_thread = threading.Thread(target=start_fastapi_server, daemon=True)

    proxy_thread.start()
    logger.info("Original proxy thread started")

    fastapi_thread.start()
    logger.info("FastAPI thread started")

    # Keep main thread alive
    try:
        while True:
            import time

            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
