#!/usr/bin/env python3
"""
Download Proxy for qBittorrent WebUI

This proxy solves the WebUI download issue for private trackers.
It intercepts download requests and uses nova2dl.py with proper authentication.
"""

import sys
import os
import json
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import tempfile
import threading
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
QBITTORRENT_HOST = os.environ.get('QBITTORRENT_HOST', 'localhost')
QBITTORRENT_PORT = os.environ.get('QBITTORRENT_PORT', '8085')
PROXY_PORT = int(os.environ.get('PROXY_PORT', '8666'))

# Plugin mapping for nova2dl.py
PLUGIN_URL_PATTERNS = {
    'rutracker': ['rutracker.org', 'rutracker.net', 'rutracker.nl'],
    'kinozal': ['kinozal.tv'],
    'nnmclub': ['nnmclub.to'],
}


def identify_plugin(url):
    """Identify which plugin to use for a given URL."""
    url_lower = url.lower()
    for plugin, patterns in PLUGIN_URL_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return plugin
    return None


def download_via_nova2dl(plugin, url):
    """Download torrent using nova2dl.py with authentication."""
    try:
        # Build nova2dl.py command
        cmd = [
            'python3',
            '/config/qBittorrent/nova3/nova2dl.py',
            plugin,
            url
        ]
        
        logger.info(f"Executing: {' '.join(cmd)}")
        
        # Run nova2dl.py
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"nova2dl.py failed: {result.stderr}")
            return None
        
        # Parse output: "filepath url"
        output = result.stdout.strip()
        if not output:
            logger.error("nova2dl.py returned empty output")
            return None
        
        parts = output.split(' ', 1)
        if len(parts) != 2:
            logger.error(f"Unexpected output format: {output}")
            return None
        
        torrent_path = parts[0]
        
        if not os.path.exists(torrent_path):
            logger.error(f"Torrent file not found: {torrent_path}")
            return None
        
        logger.info(f"Successfully downloaded to: {torrent_path}")
        return torrent_path
        
    except subprocess.TimeoutExpired:
        logger.error("nova2dl.py timed out")
        return None
    except Exception as e:
        logger.error(f"Error in download_via_nova2dl: {e}")
        return None


class DownloadHandler(BaseHTTPRequestHandler):
    """HTTP handler for download requests."""
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def do_GET(self):
        """Handle GET requests."""
        self.handle_request()
    
    def do_POST(self):
        """Handle POST requests."""
        self.handle_request()
    
    def handle_request(self):
        """Main request handler."""
        try:
            # Parse URL
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            
            logger.info(f"Handling request: {self.command} {path}")
            
            # Check if this is a torrent download request
            if path == '/download' or 'urls' in query:
                # Extract URL from query
                urls = query.get('urls', [None])[0]
                if not urls:
                    self.send_error(400, "Missing URLs parameter")
                    return
                
                # Decode URL
                torrent_url = urllib.parse.unquote(urls)
                logger.info(f"Download request for: {torrent_url}")
                
                # Check if this is a private tracker URL
                plugin = identify_plugin(torrent_url)
                
                if plugin:
                    logger.info(f"Identified as {plugin} plugin, using nova2dl.py")
                    
                    # Download via nova2dl.py
                    torrent_file = download_via_nova2dl(plugin, torrent_url)
                    
                    if torrent_file:
                        # Return the torrent file
                        self.send_torrent_file(torrent_file)
                        
                        # Clean up temp file after sending
                        try:
                            os.unlink(torrent_file)
                        except:
                            pass
                        return
                    else:
                        logger.error("Failed to download via nova2dl.py")
                        self.send_error(502, "Failed to download torrent")
                        return
                else:
                    # Not a private tracker, proxy to qBittorrent
                    logger.info("Not a private tracker, proxying to qBittorrent")
                    self.proxy_to_qbittorrent()
                    return
            
            # Default: proxy to qBittorrent
            self.proxy_to_qbittorrent()
            
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self.send_error(500, str(e))
    
    def send_torrent_file(self, filepath):
        """Send torrent file as response."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-bittorrent')
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
            
            logger.info(f"Sent torrent file ({len(data)} bytes)")
            
        except Exception as e:
            logger.error(f"Error sending torrent file: {e}")
            self.send_error(500, "Error reading torrent file")
    
    def proxy_to_qbittorrent(self):
        """Proxy request to qBittorrent."""
        try:
            # Build target URL
            target_url = f"http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}{self.path}"
            
            # Read request body if POST
            body = None
            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    body = self.rfile.read(content_length)
            
            # Create request
            req = urllib.request.Request(
                target_url,
                data=body,
                method=self.command
            )
            
            # Copy headers
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'content-length']:
                    req.add_header(header, value)
            
            # Forward request
            with urllib.request.urlopen(req, timeout=30) as response:
                # Send response
                self.send_response(response.status)
                for header, value in response.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                
                # Forward body
                self.wfile.write(response.read())
                
        except urllib.error.HTTPError as e:
            self.send_error(e.code, e.reason)
        except Exception as e:
            logger.error(f"Error proxying to qBittorrent: {e}")
            self.send_error(502, "Bad Gateway")


def run_server():
    """Run the download proxy server."""
    server_address = ('', PROXY_PORT)
    httpd = HTTPServer(server_address, DownloadHandler)
    
    logger.info(f"="*70)
    logger.info(f"Download Proxy Server Starting")
    logger.info(f"="*70)
    logger.info(f"Proxy Port: {PROXY_PORT}")
    logger.info(f"qBittorrent: http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}")
    logger.info(f"Supported private trackers: {', '.join(PLUGIN_URL_PATTERNS.keys())}")
    logger.info(f"="*70)
    logger.info(f"Server running on port {PROXY_PORT}")
    logger.info(f"Press Ctrl+C to stop")
    logger.info(f"="*70)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        httpd.shutdown()


if __name__ == '__main__':
    run_server()
