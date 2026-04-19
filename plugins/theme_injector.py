"""Shared HTML / CSS / JS bridge for applying the project's design-system
palette to any HTTP response we proxy.

Both the legacy download-proxy (``plugins/download_proxy.py`` on port
7186) and the private-tracker WebUI bridge (``webui-bridge.py`` on
port 7188) import this module. The bridge was previously untreated,
which meant opening the qBittorrent WebUI through :7188 produced an
unthemed qBittorrent page — even while :7186 was correctly skinned.

Contract
--------

* :func:`inject_theme_assets` — idempotently inserts a ``<link>`` +
  ``<script>`` pointing at ``/__qbit_theme__/skin.css`` and
  ``/__qbit_theme__/bootstrap.js`` immediately before ``</head>``.
* :func:`serve_theme_asset` — returns the bytes for those two bridge
  assets on demand (CSS + JS).
* :func:`rewrite_csp` — relaxes qBittorrent's CSP so the bootstrap can
  reach the merge service.
* :func:`maybe_decode_body` — gzip/deflate decode so injection can
  mutate the HTML bytes.
* :func:`theme_injection_disabled` — ``DISABLE_THEME_INJECTION=1``
  escape hatch.

Palette catalog is materialised inside ``bootstrap.js`` so the bridge
never needs a second cross-origin fetch just to know what the palettes
look like. It is kept in lockstep with
``frontend/src/app/models/palette.model.ts`` by
``tests/unit/test_palette_catalog_python_mirror.py``.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import zlib
from typing import Tuple
from urllib.parse import urlparse

MERGE_SERVICE_URL = os.environ.get("MERGE_SERVICE_URL", "http://localhost:7187")


# ---------------------------------------------------------------------------
# Palette catalog — mirrors frontend/src/app/models/palette.model.ts
# ---------------------------------------------------------------------------


def _build_palette_catalog() -> dict:
    # Re-use the catalog shipped by plugins/download_proxy.py so there is
    # exactly one source of truth in Python. We import lazily to avoid
    # circular imports at module load time.
    import importlib
    import sys
    from pathlib import Path

    plugin_path = Path(__file__).resolve().with_name("download_proxy.py")
    spec = importlib.util.spec_from_file_location(
        "_theme_injector_catalog_donor", plugin_path
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_theme_injector_catalog_donor"] = mod
    spec.loader.exec_module(mod)
    return mod.THEME_PALETTES  # noqa: SLF001 — intentional backdoor


# If the donor module cannot be imported (e.g. if someone reorders
# imports), fall back to the Darcula-only catalog so the bridge never
# ships with an empty catalogue.
try:
    THEME_PALETTES = _build_palette_catalog()
except Exception:  # pragma: no cover
    THEME_PALETTES = {
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
    }


# ---------------------------------------------------------------------------
# Public bridge assets
# ---------------------------------------------------------------------------

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
    catalog_json = json.dumps(THEME_PALETTES, indent=2)
    merge_url = MERGE_SERVICE_URL
    return f"""\
// qBittorrent WebUI theme bridge. Fetches the active palette from the
// merge service and subscribes to live updates via SSE so palette
// swaps made in the Angular dashboard mirror here without a manual
// refresh. Shipped by BOTH :7186 (download-proxy) and :7188 (bridge).

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
    }} catch (_) {{}}
  }}
  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", boot);
  }} else {{
    boot();
  }}
}})();
"""


THEME_BOOTSTRAP_JS = _build_theme_bootstrap_js()

THEME_INJECTION_MARKER = "/__qbit_theme__/skin.css"
_THEME_HEAD_TAGS = (
    '<link rel="stylesheet" href="/__qbit_theme__/skin.css">\n'
    '<script src="/__qbit_theme__/bootstrap.js" defer></script>\n'
)
_HEAD_CLOSE_RE = re.compile(rb"</head\s*>", re.IGNORECASE)


def theme_injection_disabled() -> bool:
    return os.environ.get("DISABLE_THEME_INJECTION") == "1"


def merge_service_origin() -> str:
    parsed = urlparse(MERGE_SERVICE_URL)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 7187)
    return f"{scheme}://{host}:{port}"


def rewrite_csp(header_value: str) -> str:
    if not header_value or theme_injection_disabled():
        return header_value
    origin = merge_service_origin()
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
        default_src = next((v for n, v in directives if n == "default-src"), "'self'")
        if origin not in default_src.split():
            default_src = (default_src + " " + origin).strip()
        new_directives.append(("connect-src", default_src))
    return "; ".join(f"{n} {v}".strip() for n, v in new_directives)


def maybe_decode_body(body: bytes, content_encoding: str) -> Tuple[bytes, bool]:
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
    except Exception:  # pragma: no cover — defensive
        pass
    return body, False


def inject_theme_assets(body: bytes, content_type: str) -> bytes:
    """Return ``body`` with the two theme-bridge tags injected before
    ``</head>``. Passes through unchanged when:

    * ``body`` is not HTML,
    * ``body`` already contains the sentinel (idempotency),
    * there is no ``</head>`` tag,
    * the ``DISABLE_THEME_INJECTION=1`` escape hatch is active.
    """
    if theme_injection_disabled():
        return body
    if not content_type or not content_type.lower().startswith("text/html"):
        return body
    if THEME_INJECTION_MARKER.encode("ascii") in body:
        return body
    match = _HEAD_CLOSE_RE.search(body)
    if not match:
        return body
    insertion = _THEME_HEAD_TAGS.encode("utf-8")
    return body[: match.start()] + insertion + body[match.start():]


def serve_theme_asset(path: str) -> Tuple[int, dict, bytes]:
    """(status, headers, body) for ``/__qbit_theme__/*``."""
    if path == "/__qbit_theme__/skin.css":
        payload = THEME_SKIN_CSS.encode("utf-8")
        return 200, {
            "Content-Type": "text/css; charset=utf-8",
            "Cache-Control": "no-cache",
            "Content-Length": str(len(payload)),
        }, payload
    if path == "/__qbit_theme__/bootstrap.js":
        payload = THEME_BOOTSTRAP_JS.encode("utf-8")
        return 200, {
            "Content-Type": "application/javascript; charset=utf-8",
            "Cache-Control": "no-cache",
            "Content-Length": str(len(payload)),
        }, payload
    payload = b"Not Found"
    return 404, {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Length": str(len(payload)),
    }, payload
