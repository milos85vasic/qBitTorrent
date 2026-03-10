#!/usr/bin/env python3
"""
Download Proxy for qBittorrent WebUI - Fixed version with proper header handling
"""

import sys
import os
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import logging
import tempfile
import threading

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

QBITTORRENT_HOST = os.environ.get("QBITTORRENT_HOST", "localhost")
QBITTORRENT_PORT = os.environ.get("QBITTORRENT_PORT", "8085")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8666"))

PLUGIN_URL_PATTERNS = {
    "rutracker": ["rutracker.org", "rutracker.net", "rutracker.nl"],
    "kinozal": ["kinozal.tv"],
    "nnmclub": ["nnmclub.to"],
}


def identify_plugin(url):
    url_lower = url.lower()
    for plugin, patterns in PLUGIN_URL_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return plugin
    return None


def download_via_nova2dl(plugin, url):
    """Download torrent using nova2dl.py with authentication."""
    try:
        cmd = ["python3", "/config/qBittorrent/nova3/nova2dl.py", plugin, url]
        logger.info(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.error(f"nova2dl.py failed: {result.stderr}")
            return None

        output = result.stdout.strip()
        if not output:
            logger.error("nova2dl.py returned empty output")
            return None

        parts = output.split(" ", 1)
        if len(parts) != 2:
            logger.error(f"Unexpected output format: {output}")
            return None

        torrent_path = parts[0]
        if not os.path.exists(torrent_path):
            logger.error(f"Torrent file not found: {torrent_path}")
            return None

        logger.info(f"Successfully downloaded to: {torrent_path}")
        return torrent_path
    except Exception as e:
        logger.error(f"Error in download_via_nova2dl: {e}")
        return None


class DownloadHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)

            # Only log non-static file requests
            if not any(
                path.endswith(ext)
                for ext in [".css", ".js", ".png", ".jpg", ".ico", ".svg"]
            ):
                logger.info(f"Handling request: {self.command} {path}")

            # Intercept /api/v2/torrents/add for private trackers
            if path == "/api/v2/torrents/add" and self.command == "POST":
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 0:
                    body = self.rfile.read(content_length)
                    body_str = body.decode("utf-8")
                    params = urllib.parse.parse_qs(body_str)
                    urls = params.get("urls", [""])[0]

                    if urls:
                        plugin = identify_plugin(urls)
                        if plugin:
                            logger.info(
                                f"Intercepted torrents/add for {plugin}: {urls}"
                            )

                            # Download via nova2dl.py - this saves to shared-tmp
                            torrent_file = download_via_nova2dl(plugin, urls)

                            if torrent_file:
                                logger.info(
                                    f"Downloaded to {torrent_file}, forwarding to qBittorrent"
                                )
                                params["urls"] = [f"file://{torrent_file}"]
                                new_body = urllib.parse.urlencode(
                                    params, doseq=True
                                ).encode("utf-8")
                                self.proxy_to_qbittorrent_with_body(new_body)

                                # Clean up after forwarding
                                try:
                                    os.unlink(torrent_file)
                                except:
                                    pass
                                return
                            else:
                                logger.error("Failed to download via nova2dl.py")
                                self.send_error(502, "Failed to download torrent")
                                return

            # Default: proxy to qBittorrent
            self.proxy_to_qbittorrent()

        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self.send_error(500, str(e))

    def proxy_to_qbittorrent(self):
        body = None
        if self.command == "POST":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
        self.proxy_to_qbittorrent_with_body(body)

    def proxy_to_qbittorrent_with_body(self, body):
        try:
            target_url = f"http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}{self.path}"
            req = urllib.request.Request(target_url, data=body, method=self.command)

            # Copy headers, but fix Referer and Origin to match qBittorrent's expected origin
            for header, value in self.headers.items():
                header_lower = header.lower()
                if header_lower not in ["host", "content-length"]:
                    # Rewrite referer and origin headers to match qBittorrent's port
                    if header_lower == "referer":
                        value = value.replace(f":{PROXY_PORT}", f":{QBITTORRENT_PORT}")
                    elif header_lower == "origin":
                        value = value.replace(f":{PROXY_PORT}", f":{QBITTORRENT_PORT}")
                    req.add_header(header, value)

            with urllib.request.urlopen(req, timeout=30) as response:
                self.send_response(response.status)
                for header, value in response.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())

        except urllib.request.HTTPError as e:
            self.send_error(e.code, e.reason)
        except Exception as e:
            logger.error(f"Error proxying to qBittorrent: {e}")
            self.send_error(502, "Bad Gateway")


def run_server():
    """Run the download proxy server."""
    server_address = ("", PROXY_PORT)
    httpd = ThreadingHTTPServer(server_address, DownloadHandler)

    logger.info(f"=" * 70)
    logger.info(f"Download Proxy Server Starting")
    logger.info(f"=" * 70)
    logger.info(f"Proxy Port: {PROXY_PORT}")
    logger.info(f"qBittorrent: http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}")
    logger.info(f"Supported private trackers: {', '.join(PLUGIN_URL_PATTERNS.keys())}")
    logger.info(f"=" * 70)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
