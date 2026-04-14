#!/usr/bin/env python3
"""
WebUI Bridge for qBittorrent Private Tracker Support

This module solves the WebUI download issue by creating a bridge between
WebUI and nova2dl.py. It intercepts download requests and handles them
with proper authentication.

Author: Milos Vasic
Version: 2.0.0
License: Apache 2.0
"""

import os
import sys
import json
import time
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse

# Configuration
QBITTORRENT_HOST = os.environ.get("QBITTORRENT_HOST", "localhost")
QBITTORRENT_PORT = int(os.environ.get("QBITTORRENT_PORT", "79085"))
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "78666"))

# Private tracker URL patterns
PRIVATE_TRACKERS = {
    "rutracker": ["rutracker.org", "rutracker.net", "rutracker.nl"],
    "kinozal": ["kinozal.tv"],
    "nnmclub": ["nnmclub.to", "nnmclub.ro", "nnm-club.me"],
    "iptorrents": ["iptorrents.com", "iptorrents.me"],
}


class WebUIBridgeHandler(BaseHTTPRequestHandler):
    """Handle WebUI requests with private tracker support."""

    def log_message(self, format, *args):
        """Custom logging."""
        print(f"[WebUI-Bridge] {self.address_string()} - {format % args}")

    def do_POST(self):
        """Handle POST requests."""
        self.handle_request()

    def do_GET(self):
        """Handle GET requests."""
        self.handle_request()

    def handle_request(self):
        """Main request handler."""
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)

            # Check if this is a torrent download
            if "urls" in query:
                urls = query.get("urls", [""])[0]
                if urls:
                    self.handle_torrent_download(urls)
                    return

            # Proxy to qBittorrent
            self.proxy_to_qbittorrent()

        except Exception as e:
            self.send_error(500, str(e))

    def handle_torrent_download(self, url):
        """Handle torrent download with private tracker support."""
        url = urllib.parse.unquote(url)

        # Identify if this is a private tracker
        plugin = self.identify_plugin(url)

        if plugin:
            print(f"[WebUI-Bridge] Private tracker detected: {plugin}")
            print(f"[WebUI-Bridge] URL: {url[:80]}...")

            # Use nova2dl.py for private trackers
            torrent_file = self.download_via_nova2dl(plugin, url)

            if torrent_file:
                # Upload to qBittorrent
                success = self.upload_to_qbittorrent(torrent_file)

                if success:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"OK")

                    # Cleanup
                    try:
                        os.unlink(torrent_file)
                    except OSError as e:
                        print(f"[WebUI-Bridge] Cleanup error: {e}")
                    return

        # Not a private tracker or download failed, proxy to qBittorrent
        self.proxy_to_qbittorrent()

    def identify_plugin(self, url):
        """Identify which plugin to use."""
        url_lower = url.lower()
        for plugin, patterns in PRIVATE_TRACKERS.items():
            for pattern in patterns:
                if pattern in url_lower:
                    return plugin
        return None

    def download_via_nova2dl(self, plugin, url):
        """Download using nova2dl.py."""
        try:
            cmd = ["python3", "/config/qBittorrent/nova3/nova2dl.py", plugin, url]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                output = result.stdout.strip()
                if " " in output:
                    return output.split(" ")[0]

            print(f"[WebUI-Bridge] nova2dl failed: {result.stderr}")
            return None

        except Exception as e:
            print(f"[WebUI-Bridge] Error: {e}")
            return None

    def upload_to_qbittorrent(self, filepath):
        """Upload torrent file to qBittorrent."""
        try:
            url = f"http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}/api/v2/torrents/add"

            # Create multipart request
            boundary = "----WebKitFormBoundary" + str(int(time.time()))

            with open(filepath, "rb") as f:
                file_data = f.read()

            body = []
            body.append(f"------{boundary}".encode())
            body.append(b'Content-Disposition: form-data; name="torrents"; filename="torrent.torrent"')
            body.append(b"Content-Type: application/x-bittorrent")
            body.append(b"")
            body.append(file_data)
            body.append(f"------{boundary}--".encode())

            body = b"\r\n".join(body)

            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Content-Type": f"multipart/form-data; boundary=----{boundary}",
                    "Content-Length": len(body),
                },
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status == 200

        except Exception as e:
            print(f"[WebUI-Bridge] Upload error: {e}")
            return False

    def proxy_to_qbittorrent(self):
        """Proxy request to qBittorrent."""
        try:
            target = f"http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}{self.path}"

            # Read body if POST
            body = None
            if self.command == "POST":
                length = int(self.headers.get("Content-Length", 0))
                if length > 0:
                    body = self.rfile.read(length)

            req = urllib.request.Request(target, data=body, method=self.command)

            for header, value in self.headers.items():
                if header.lower() not in ["host", "content-length"]:
                    req.add_header(header, value)

            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for header, value in resp.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(resp.read())

        except urllib.error.HTTPError as e:
            self.send_error(e.code, e.reason)


def run_bridge():
    """Start the WebUI bridge server."""
    server = HTTPServer(("", BRIDGE_PORT), WebUIBridgeHandler)

    print("=" * 70)
    print("qBittorrent WebUI Bridge Server")
    print("=" * 70)
    print(f"Bridge Port: {BRIDGE_PORT}")
    print(f"qBittorrent: http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}")
    print("=" * 70)
    print("This bridge enables private tracker downloads in WebUI")
    print("=" * 70)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_bridge()
