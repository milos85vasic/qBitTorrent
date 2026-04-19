#!/usr/bin/env python3
"""
Download Proxy for qBittorrent WebUI - Fixed version
Intercepts RuTracker URLs and downloads via nova2dl.py with authentication
Passes through all other requests (including magnet links).

Also injects a two-file theme bridge
(``/__qbit_theme__/skin.css`` + ``/__qbit_theme__/bootstrap.js``)
into every HTML response so the qBittorrent WebUI picks up the
palette chosen in the Angular dashboard at :7187. See
docs/CROSS_APP_THEME_PLAN.md.
"""

import sys
import os
import json
import gzip
import zlib
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
# Where the bridge can find the merge service (default port 7187).
MERGE_SERVICE_URL = os.environ.get("MERGE_SERVICE_URL", "http://localhost:7187")

PLUGIN_PATTERNS = {
    "rutracker": [r"rutracker\.org", r"rutracker\.net", r"rutracker\.nl"],
    "kinozal": [r"kinozal\.tv", r"kinozal\.me"],
    "nnmclub": [r"nnmclub\.to", r"nnm-club\.me"],
    "iptorrents": [r"iptorrents\.(com|me|org)"],
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


# ---------------------------------------------------------------------- theme
#
# The qBittorrent WebUI is qBittorrent's own code — it ignores our
# design system. To keep the two ports visually consistent, every HTML
# response flowing through this proxy is rewritten so a tiny CSS + JS
# pair is loaded from ``/__qbit_theme__/``. The bridge pulls the active
# palette from the merge service at :7187 and applies the tokens to
# ``document.documentElement`` plus a handful of high-level overrides.
#
# The palette catalog below mirrors
# ``frontend/src/app/models/palette.model.ts`` — a lockstep test
# (``tests/unit/test_palette_catalog_python_mirror.py``) keeps the two
# copies in sync.

THEME_PALETTES: dict[str, dict[str, dict[str, str]]] = {
    "darcula": {
        "dark": {
            "bgPrimary": "#2b2b2b",
            "bgSecondary": "#3c3f41",
            "bgTertiary": "#4e5254",
            "border": "#555555",
            "textPrimary": "#a9b7c6",
            "textSecondary": "#808080",
            "accent": "#9d001e",
            "accentHover": "#c4002a",
            "contrast": "#d9a441",
            "success": "#6a8759",
            "danger": "#cc7832",
            "warning": "#d9a441",
            "info": "#6897bb",
            "purple": "#9876aa",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#ffffff",
            "bgSecondary": "#f2f2f2",
            "bgTertiary": "#e4e4e4",
            "border": "#c9c9c9",
            "textPrimary": "#1c1c1c",
            "textSecondary": "#555555",
            "accent": "#9d001e",
            "accentHover": "#7d0017",
            "contrast": "#b07d1f",
            "success": "#0a7b28",
            "danger": "#c9302c",
            "warning": "#b07d1f",
            "info": "#1e6fa8",
            "purple": "#6f42c1",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
    "dracula": {
        "dark": {
            "bgPrimary": "#282a36",
            "bgSecondary": "#343746",
            "bgTertiary": "#44475a",
            "border": "#6272a4",
            "textPrimary": "#f8f8f2",
            "textSecondary": "#bfbfbf",
            "accent": "#ff79c6",
            "accentHover": "#ff92d0",
            "contrast": "#bd93f9",
            "success": "#50fa7b",
            "danger": "#ff5555",
            "warning": "#f1fa8c",
            "info": "#8be9fd",
            "purple": "#bd93f9",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#f8f8f2",
            "bgSecondary": "#eeeeec",
            "bgTertiary": "#e0e0da",
            "border": "#c9c9c0",
            "textPrimary": "#282a36",
            "textSecondary": "#6272a4",
            "accent": "#d6336c",
            "accentHover": "#bd255a",
            "contrast": "#7048e8",
            "success": "#2b8a3e",
            "danger": "#c92a2a",
            "warning": "#b08900",
            "info": "#1c7ed6",
            "purple": "#6741d9",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
    "solarized": {
        "dark": {
            "bgPrimary": "#002b36",
            "bgSecondary": "#073642",
            "bgTertiary": "#0a4453",
            "border": "#586e75",
            "textPrimary": "#93a1a1",
            "textSecondary": "#657b83",
            "accent": "#268bd2",
            "accentHover": "#2aa198",
            "contrast": "#b58900",
            "success": "#859900",
            "danger": "#dc322f",
            "warning": "#b58900",
            "info": "#268bd2",
            "purple": "#6c71c4",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#fdf6e3",
            "bgSecondary": "#eee8d5",
            "bgTertiary": "#d9d2bf",
            "border": "#93a1a1",
            "textPrimary": "#073642",
            "textSecondary": "#657b83",
            "accent": "#268bd2",
            "accentHover": "#1d70ad",
            "contrast": "#b58900",
            "success": "#859900",
            "danger": "#dc322f",
            "warning": "#b58900",
            "info": "#268bd2",
            "purple": "#6c71c4",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
    "nord": {
        "dark": {
            "bgPrimary": "#2e3440",
            "bgSecondary": "#3b4252",
            "bgTertiary": "#434c5e",
            "border": "#4c566a",
            "textPrimary": "#eceff4",
            "textSecondary": "#d8dee9",
            "accent": "#88c0d0",
            "accentHover": "#8fbcbb",
            "contrast": "#ebcb8b",
            "success": "#a3be8c",
            "danger": "#bf616a",
            "warning": "#ebcb8b",
            "info": "#81a1c1",
            "purple": "#b48ead",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#eceff4",
            "bgSecondary": "#e5e9f0",
            "bgTertiary": "#d8dee9",
            "border": "#b8c0ce",
            "textPrimary": "#2e3440",
            "textSecondary": "#4c566a",
            "accent": "#5e81ac",
            "accentHover": "#4c6e95",
            "contrast": "#d08770",
            "success": "#5b8c3a",
            "danger": "#bf616a",
            "warning": "#b08900",
            "info": "#81a1c1",
            "purple": "#b48ead",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
    "monokai": {
        "dark": {
            "bgPrimary": "#272822",
            "bgSecondary": "#383830",
            "bgTertiary": "#49483e",
            "border": "#75715e",
            "textPrimary": "#f8f8f2",
            "textSecondary": "#cfcfc2",
            "accent": "#f92672",
            "accentHover": "#ff4890",
            "contrast": "#a6e22e",
            "success": "#a6e22e",
            "danger": "#f92672",
            "warning": "#fd971f",
            "info": "#66d9ef",
            "purple": "#ae81ff",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#fafaf5",
            "bgSecondary": "#ededeb",
            "bgTertiary": "#dddbcf",
            "border": "#b0ad9e",
            "textPrimary": "#272822",
            "textSecondary": "#75715e",
            "accent": "#d63384",
            "accentHover": "#b5256e",
            "contrast": "#689822",
            "success": "#689822",
            "danger": "#c02450",
            "warning": "#c6660a",
            "info": "#2a9ab4",
            "purple": "#7a4ddb",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
    "gruvbox": {
        "dark": {
            "bgPrimary": "#282828",
            "bgSecondary": "#3c3836",
            "bgTertiary": "#504945",
            "border": "#665c54",
            "textPrimary": "#ebdbb2",
            "textSecondary": "#a89984",
            "accent": "#fb4934",
            "accentHover": "#cc241d",
            "contrast": "#fabd2f",
            "success": "#b8bb26",
            "danger": "#fb4934",
            "warning": "#fabd2f",
            "info": "#83a598",
            "purple": "#d3869b",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#fbf1c7",
            "bgSecondary": "#ebdbb2",
            "bgTertiary": "#d5c4a1",
            "border": "#bdae93",
            "textPrimary": "#3c3836",
            "textSecondary": "#665c54",
            "accent": "#9d0006",
            "accentHover": "#79111e",
            "contrast": "#b57614",
            "success": "#79740e",
            "danger": "#9d0006",
            "warning": "#b57614",
            "info": "#076678",
            "purple": "#8f3f71",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
    "one-dark": {
        "dark": {
            "bgPrimary": "#282c34",
            "bgSecondary": "#353b45",
            "bgTertiary": "#3e4451",
            "border": "#4b5263",
            "textPrimary": "#abb2bf",
            "textSecondary": "#7f848e",
            "accent": "#61afef",
            "accentHover": "#4e96d6",
            "contrast": "#e5c07b",
            "success": "#98c379",
            "danger": "#e06c75",
            "warning": "#e5c07b",
            "info": "#56b6c2",
            "purple": "#c678dd",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#fafafa",
            "bgSecondary": "#eaeaeb",
            "bgTertiary": "#d3d3d5",
            "border": "#a0a1a7",
            "textPrimary": "#383a42",
            "textSecondary": "#696c77",
            "accent": "#4078f2",
            "accentHover": "#2e62cc",
            "contrast": "#986801",
            "success": "#50a14f",
            "danger": "#e45649",
            "warning": "#c18401",
            "info": "#0184bc",
            "purple": "#a626a4",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
    "tokyo-night": {
        "dark": {
            "bgPrimary": "#1a1b26",
            "bgSecondary": "#24283b",
            "bgTertiary": "#2f344d",
            "border": "#414868",
            "textPrimary": "#c0caf5",
            "textSecondary": "#a9b1d6",
            "accent": "#7aa2f7",
            "accentHover": "#6a91e6",
            "contrast": "#e0af68",
            "success": "#9ece6a",
            "danger": "#f7768e",
            "warning": "#e0af68",
            "info": "#7dcfff",
            "purple": "#bb9af7",
            "shadow": "rgba(0,0,0,0.55)",
        },
        "light": {
            "bgPrimary": "#e6e7ed",
            "bgSecondary": "#d5d6db",
            "bgTertiary": "#c4c7d0",
            "border": "#989caf",
            "textPrimary": "#343b58",
            "textSecondary": "#565a6e",
            "accent": "#34548a",
            "accentHover": "#2a4471",
            "contrast": "#8f5e15",
            "success": "#485e30",
            "danger": "#8c4351",
            "warning": "#8f5e15",
            "info": "#2a6194",
            "purple": "#5a3e8e",
            "shadow": "rgba(0,0,0,0.12)",
        },
    },
}


THEME_SKIN_CSS = """\
/* qBittorrent WebUI theme bridge.
 * Populated with the Darcula-dark fallback; bootstrap.js overrides
 * these with the live palette (and reacts to SSE theme events).
 */
:root {
  --color-bg-primary:     #2b2b2b;
  --color-bg-secondary:   #3c3f41;
  --color-bg-tertiary:    #4e5254;
  --color-border:         #555555;
  --color-text-primary:   #a9b7c6;
  --color-text-secondary: #808080;
  --color-accent:         #9d001e;
  --color-accent-hover:   #c4002a;
  --color-contrast:       #d9a441;
  --color-success:        #6a8759;
  --color-danger:         #cc7832;
  --color-warning:        #d9a441;
  --color-info:           #6897bb;
  --color-purple:         #9876aa;
  --color-shadow:         rgba(0,0,0,0.55);
}

/* qBittorrent WebUI overrides — target its actual class/id names. */
html, body {
  background: var(--color-bg-primary) !important;
  color: var(--color-text-primary) !important;
}
#desktop, #mainWindowTabs, #filterTitle, .sidebar,
.scroll_container, dialog, .MochaMenu, .propContent,
#rssFeedFixedHeightContainer, #tabs, .MochaTab {
  background: var(--color-bg-secondary) !important;
  color: var(--color-text-primary) !important;
  border-color: var(--color-border) !important;
}
a { color: var(--color-accent); }
a:hover { color: var(--color-accent-hover); }
button, input[type="button"], input[type="submit"], .mochaToolButtonText {
  background: var(--color-accent);
  color: #fff;
  border: 1px solid var(--color-accent-hover);
}
button:hover, input[type="button"]:hover, input[type="submit"]:hover {
  background: var(--color-accent-hover);
}
.dynamicTable_pane, .dynamicTable {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}
.dynamicTable th, .dynamicTable_headerBackgroundContainer {
  background: var(--color-bg-tertiary);
  color: var(--color-accent);
}
"""


def _build_theme_bootstrap_js() -> str:
    """Materialise bootstrap.js with the palette catalog inlined.

    The catalog is emitted as a Python dict via ``json.dumps`` so the
    bytes sent to the browser are always valid JSON, regardless of how
    the catalog grows. Keeping the catalog inline avoids a second
    CORS round-trip from the :7186 origin.
    """
    catalog_json = json.dumps(THEME_PALETTES, indent=2)
    merge_url = MERGE_SERVICE_URL
    js = f"""\
// qBittorrent WebUI theme bridge — loaded on every HTML page served by
// the download-proxy on :7186. Fetches the active palette from the
// merge service and subscribes to live updates via SSE so palette swaps
// made in the Angular dashboard mirror here without a manual refresh.

(function () {{
  "use strict";
  var MERGE = (window.__MERGE_SERVICE_URL__ || {merge_url!r});
  var CATALOG = {catalog_json};
  window.__QBIT_PALETTE_CATALOG__ = CATALOG;

  var KEYS = [
    "bg-primary","bg-secondary","bg-tertiary","border","text-primary",
    "text-secondary","accent","accent-hover","contrast","success","danger",
    "warning","info","purple","shadow"
  ];
  function camel(k) {{
    return k.replace(/-([a-z])/g, function (_, c) {{ return c.toUpperCase(); }});
  }}
  function apply(tokens) {{
    var doc = document.documentElement;
    for (var i = 0; i < KEYS.length; i++) {{
      var k = KEYS[i];
      var v = tokens[camel(k)];
      if (v) doc.style.setProperty("--color-" + k, v);
    }}
  }}
  function tokensFor(paletteId, mode) {{
    var entry = CATALOG[paletteId] || CATALOG["darcula"];
    return entry[mode] || entry["dark"];
  }}
  var lastUpdatedAt = null;
  function adopt(state) {{
    if (!state || !state.paletteId || !state.mode) return;
    if (lastUpdatedAt && state.updatedAt && state.updatedAt === lastUpdatedAt) return;
    lastUpdatedAt = state.updatedAt || null;
    apply(tokensFor(state.paletteId, state.mode));
    var doc = document.documentElement;
    doc.setAttribute("data-palette", state.paletteId);
    doc.setAttribute("data-mode", state.mode);
    doc.style.setProperty("color-scheme", state.mode);
    window.__qbitTheme = state;
  }}
  function boot() {{
    // Preseed with Darcula dark so unstyled flashes are minimal.
    apply(tokensFor("darcula", "dark"));
    if (typeof fetch !== "function") return;
    fetch(MERGE + "/api/v1/theme", {{credentials: "omit"}})
      .then(function (r) {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }})
      .then(adopt)
      .catch(function (e) {{ try {{ console.warn("qbit-theme: using fallback", e); }} catch (_) {{}} }});
    try {{
      var es = new EventSource(MERGE + "/api/v1/theme/stream");
      es.addEventListener("theme", function (ev) {{
        try {{ adopt(JSON.parse(ev.data)); }} catch (_) {{}}
      }});
    }} catch (_) {{
      /* no live updates available */
    }}
  }}
  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", boot);
  }} else {{
    boot();
  }}
}})();
"""
    return js


THEME_BOOTSTRAP_JS = _build_theme_bootstrap_js()

THEME_INJECTION_MARKER = "/__qbit_theme__/skin.css"
_THEME_HEAD_TAGS = (
    '<link rel="stylesheet" href="/__qbit_theme__/skin.css">\n'
    '<script src="/__qbit_theme__/bootstrap.js" defer></script>\n'
)
_HEAD_CLOSE_RE = re.compile(rb"</head\s*>", re.IGNORECASE)


def _merge_service_origin() -> str:
    """Return the origin of the merge service for CSP whitelisting.

    qBittorrent ships a strict CSP header (``default-src 'self'; ...``)
    that, without the ``connect-src`` directive, blocks the bridge's
    ``fetch('/api/v1/theme')`` + ``EventSource(...)`` calls cross-origin.
    We whitelist the merge-service origin in the CSP the browser sees.
    """
    from urllib.parse import urlparse

    parsed = urlparse(MERGE_SERVICE_URL)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 7187)
    return f"{scheme}://{host}:{port}"


MERGE_SERVICE_ORIGIN = _merge_service_origin()


_CSP_DIRECTIVE_RE = re.compile(r"\s*([^;\s]+)(?:\s+([^;]*))?\s*;?", re.I)


def rewrite_csp(header_value: str) -> str:
    """Relax qBittorrent's Content-Security-Policy so the theme bridge
    can talk to the merge service.

    Adds the merge-service origin to ``connect-src`` (creating the
    directive if qBittorrent didn't set one). Idempotent. If the input
    is blank, returns it unchanged.
    """
    if not header_value or _theme_injection_disabled():
        return header_value
    origin = MERGE_SERVICE_ORIGIN
    directives: list[tuple[str, str]] = []
    for part in header_value.split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, rest = part.partition(" ")
        directives.append((name.lower(), rest.strip()))

    seen_connect = False
    new_directives: list[tuple[str, str]] = []
    for name, value in directives:
        if name == "connect-src":
            seen_connect = True
            if origin not in value.split():
                value = (value + " " + origin).strip()
        new_directives.append((name, value))
    if not seen_connect:
        # Fall back to default-src if present, extended with our origin.
        default_src = next((v for n, v in directives if n == "default-src"), "'self'")
        if origin not in default_src.split():
            default_src = (default_src + " " + origin).strip()
        new_directives.append(("connect-src", default_src))
    return "; ".join(f"{n} {v}".strip() for n, v in new_directives)


def _theme_injection_disabled() -> bool:
    return os.environ.get("DISABLE_THEME_INJECTION") == "1"


def _maybe_decode_body(body: bytes, content_encoding: str) -> tuple[bytes, bool]:
    """Return (decoded_bytes, decoded_flag).

    ``decoded_flag`` is True only when we successfully turned a gzip /
    deflate payload back into plain text so the injector can mutate
    it. Anything we can't decode (br, zstd, unknown) is returned as
    the original bytes with the flag False — the caller should then
    skip the rewrite and pass the response through untouched.
    """
    if not content_encoding:
        return body, True
    enc = content_encoding.lower().strip()
    try:
        if enc == "gzip":
            return gzip.decompress(body), True
        if enc == "deflate":
            try:
                return zlib.decompress(body), True
            except zlib.error:
                return zlib.decompress(body, -zlib.MAX_WBITS), True
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug(f"could not decompress {enc}: {exc}")
    return body, False


def inject_theme_assets(body: bytes, content_type: str) -> bytes:
    """Return ``body`` with the two theme-bridge tags injected before
    ``</head>``. Passes through unchanged when:

    * ``body`` is not HTML (``content_type`` doesn't start with ``text/html``),
    * ``body`` already contains our sentinel (idempotency),
    * there is no ``</head>`` tag,
    * the ``DISABLE_THEME_INJECTION=1`` escape hatch is active.
    """
    if _theme_injection_disabled():
        return body
    if not content_type or not content_type.lower().startswith("text/html"):
        return body
    if THEME_INJECTION_MARKER.encode("ascii") in body:
        return body
    match = _HEAD_CLOSE_RE.search(body)
    if not match:
        return body
    # Inject just before the </head> tag preserving the original casing.
    insertion = _THEME_HEAD_TAGS.encode("utf-8")
    return body[: match.start()] + insertion + body[match.start():]


def serve_theme_asset(path: str) -> tuple[int, dict[str, str], bytes]:
    """Return (status, headers, body) for a ``/__qbit_theme__/*`` request.

    Kept as a pure function so unit tests can poke it without
    standing up the HTTP server.
    """
    if path == "/__qbit_theme__/skin.css":
        payload = THEME_SKIN_CSS.encode("utf-8")
        headers = {
            "Content-Type": "text/css; charset=utf-8",
            "Cache-Control": "no-cache",
            "Content-Length": str(len(payload)),
        }
        return 200, headers, payload
    if path == "/__qbit_theme__/bootstrap.js":
        payload = THEME_BOOTSTRAP_JS.encode("utf-8")
        headers = {
            "Content-Type": "application/javascript; charset=utf-8",
            "Cache-Control": "no-cache",
            "Content-Length": str(len(payload)),
        }
        return 200, headers, payload
    payload = b"Not Found"
    return 404, {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Length": str(len(payload)),
    }, payload


class DownloadHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        if "/api/" in self.path:
            logger.info(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        if self._serve_theme_bridge():
            return
        self.handle_request(None)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        self.handle_request(body)

    def _serve_theme_bridge(self) -> bool:
        """Short-circuit the two proxy-local theme routes."""
        try:
            path = urllib.parse.urlparse(self.path).path
        except Exception:
            return False
        if not path.startswith("/__qbit_theme__/"):
            return False
        status, headers, payload = serve_theme_asset(path)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except BrokenPipeError:
            pass
        return True

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
                            except OSError:
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
            except Exception:
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
                content_type = response.headers.get("Content-Type", "") or ""
                content_encoding = (response.headers.get("Content-Encoding") or "").lower().strip()
                content = response.read()

                # Inject the theme bridge into HTML responses so the
                # qBittorrent WebUI picks up the dashboard's palette.
                is_html = content_type.lower().startswith("text/html")
                decoded_for_injection = False
                if is_html:
                    decoded, decoded_for_injection = _maybe_decode_body(content, content_encoding)
                    if decoded_for_injection:
                        new_decoded = inject_theme_assets(decoded, content_type)
                        if new_decoded is not decoded:
                            # Serve the response un-encoded so the browser
                            # doesn't misinterpret our plain-text insertion.
                            content = new_decoded
                            content_encoding = ""
                    else:
                        content = inject_theme_assets(content, content_type)

                self.send_response(response.status)
                for header, value in response.headers.items():
                    h = header.lower()
                    if h in ("transfer-encoding", "content-length"):
                        continue
                    # Drop Content-Encoding if we rewrote the body in place.
                    if h == "content-encoding" and is_html and decoded_for_injection and not content_encoding:
                        continue
                    # Relax qBittorrent's CSP so the injected bridge
                    # can fetch + stream from the merge service on
                    # :7187 without being blocked by connect-src.
                    if is_html and h == "content-security-policy":
                        value = rewrite_csp(value)
                    self.send_header(header, value)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()

                self.wfile.write(content)

        except urllib.request.HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.reason}")
            try:
                self.send_error(e.code, e.reason)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error proxying to qBittorrent: {e}")
            try:
                self.send_error(502, "Bad Gateway")
            except Exception:
                pass


def run_server():
    server_address = ("", PROXY_PORT)
    httpd = ThreadingHTTPServer(server_address, DownloadHandler)

    logger.info("=" * 60)
    logger.info("Download Proxy Server Started")
    logger.info(f"Proxy Port: {PROXY_PORT}")
    logger.info(f"qBittorrent: http://{QBITTORRENT_HOST}:{QBITTORRENT_PORT}")
    logger.info(f"Supported trackers: {list(PLUGIN_PATTERNS.keys())}")
    logger.info(f"Theme bridge -> {MERGE_SERVICE_URL}")
    logger.info("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
