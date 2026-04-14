#!/usr/bin/env python3
"""
Download Proxy for qBittorrent WebUI - Fixed version
Intercepts RuTracker URLs and downloads via nova2dl.py with authentication
Passes through all other requests (including magnet links)
"""

import sys
import os
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import subprocess
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

QBITTORRENT_HOST = os.environ.get("QBITTORRENT_HOST", "localhost")
QBITTORRENT_PORT = os.environ.get("QBITTORRENT_PORT", "7185")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "7186"))

PLUGIN_PATTERNS = {
    "rutracker": [r"rutracker\.org", r"rutracker\.net", r"rutracker\.nl"],
}

COMPILED_PATTERNS = {plugin: [re.compile(p, re.I) for p in patterns] for plugin, patterns in PLUGIN_PATTERNS.items()}


def identify_plugin(url):
    for plugin, patterns in COMPILED_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(url):
                return plugin
    return None


def download_via_nova2dl(plugin, url):
    """Download torrent using nova2dl.py with authentication."""
    try:
        cmd = ["python3", "/config/qBittorrent/nova3/nova2dl.py", plugin, url]
        logger.info(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            logger.error(f"nova2dl.py failed: {result.stderr}")
            return None

        output = result.stdout.strip()
        if not output:
            logger.error("nova2dl.py returned empty output")
            return None

        parts = output.split(" ", 1)
        if len(parts) != 2:
            logger.error(f"Unexpected output: {output}")
            return None

        torrent_path = parts[0]
        if not os.path.exists(torrent_path):
            logger.error(f"Torrent file not found: {torrent_path}")
            return None

        logger.info(f"Downloaded to: {torrent_path}")
        return torrent_path
    except subprocess.TimeoutExpired:
        logger.error("nova2dl.py timed out")
        return None
    except Exception as e:
        logger.error(f"Error in download_via_nova2dl: {e}")
        return None


class DownloadHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        if "/api/" in self.path:
            logger.info(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        self.handle_request(None)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        self.handle_request(body)

    def _is_multipart_file_upload(self):
        content_type = self.headers.get("Content-Type", "")
        return "multipart/form-data" in content_type

    def _is_torrent_file_field(self, body):
        content_disposition = self.headers.get("Content-Disposition", "")
        return False

    def handle_request(self, body):
        try:
            path = urllib.parse.urlparse(self.path).path

            if path == "/api/v2/torrents/add" and self.command == "POST" and body:
                if self._is_multipart_file_upload():
                    logger.info("Multipart file upload detected, passing through directly")
                    self.proxy_to_qbittorrent(body)
                    return

                try:
                    body_str = body.decode("utf-8")
                except (UnicodeDecodeError, ValueError):
                    logger.info("Binary body detected, passing through directly")
                    self.proxy_to_qbittorrent(body)
                    return

                params = urllib.parse.parse_qs(body_str)
                urls = params.get("urls", [""])[0]

                if urls:
                    plugin = identify_plugin(urls)
                    if plugin:
                        logger.info(f"Intercepting {plugin} URL: {urls[:80]}...")

                        torrent_file = download_via_nova2dl(plugin, urls)

                        if torrent_file:
                            params["urls"] = [f"file://{torrent_file}"]
                            new_body = urllib.parse.urlencode(params, doseq=True).encode("utf-8")

                            self.proxy_to_qbittorrent(new_body)

                            try:
                                os.unlink(torrent_file)
                            except:
                                pass
                            return
                        else:
                            logger.error("Failed to download torrent")
                            self.send_error(502, "Failed to download torrent")
                            return

            self.proxy_to_qbittorrent(body)

        except Exception as e:
            logger.error(f"Error handling request: {e}")
            try:
                self.send_error(500, str(e))
            except:
                pass

    def proxy_to_qbittorrent(self, body):
        try:
            target_url = f"http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}{self.path}"
            req = urllib.request.Request(target_url, data=body, method=self.command)

            for header, value in self.headers.items():
                header_lower = header.lower()
                if header_lower not in ["host", "content-length"]:
                    if header_lower == "referer":
                        value = f"http://localhost:{QBITTORRENT_PORT}"
                    elif header_lower == "origin":
                        value = f"http://localhost:{QBITTORRENT_PORT}"
                    req.add_header(header, value)

            with urllib.request.urlopen(req, timeout=30) as response:
                self.send_response(response.status)
                for header, value in response.headers.items():
                    if header.lower() not in ["transfer-encoding"]:
                        self.send_header(header, value)
                self.end_headers()

                content = response.read()
                self.wfile.write(content)

        except urllib.request.HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.reason}")
            try:
                self.send_error(e.code, e.reason)
            except:
                pass
        except Exception as e:
            logger.error(f"Error proxying to qBittorrent: {e}")
            try:
                self.send_error(502, "Bad Gateway")
            except:
                pass


def run_server():
    server_address = ("", PROXY_PORT)
    httpd = ThreadingHTTPServer(server_address, DownloadHandler)

    logger.info("=" * 60)
    logger.info("Download Proxy Server Started")
    logger.info(f"Proxy Port: {PROXY_PORT}")
    logger.info(f"qBittorrent: http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}")
    logger.info(f"Supported trackers: {list(PLUGIN_PATTERNS.keys())}")
    logger.info("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
