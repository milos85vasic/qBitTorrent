"""
Runtime image must carry the phase-3 concurrency/safety dependencies.

The container builds from ``download-proxy/requirements.txt``.  Tests pin
these deps in ``tests/requirements.txt`` so the host test harness has them,
but the running merge service also needs them at runtime.  This test
parses ``download-proxy/requirements.txt`` and asserts the four packages
added in commit 6 are present.
"""

from __future__ import annotations

import os
import re

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REQS = os.path.join(_REPO_ROOT, "download-proxy", "requirements.txt")

# Package -> minimum version floor that must appear.
REQUIRED = {
    "cachetools": "5.3.0",
    "filelock": "3.15.0",
    "tenacity": "8.4.0",
    "pybreaker": "1.2.0",
}


def _parse_requirements(path: str) -> dict[str, str]:
    """Return ``{package_lower: version_spec}`` from a requirements file.

    Only parses simple ``name>=ver`` / ``name==ver`` / bare-name lines.
    Comments, blank lines and ``-r``/``-e`` directives are skipped.
    """
    out: dict[str, str] = {}
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Strip inline comments.
            line = line.split("#", 1)[0].strip()
            # Split on version specifier.
            m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([<>=!~].*)?$", line)
            if not m:
                continue
            name = m.group(1).lower().replace("_", "-")
            spec = (m.group(2) or "").strip()
            out[name] = spec
    return out


def test_runtime_requirements_has_phase3_deps():
    assert os.path.isfile(_REQS), f"expected {_REQS} to exist"
    parsed = _parse_requirements(_REQS)

    missing = [pkg for pkg in REQUIRED if pkg not in parsed]
    assert not missing, (
        f"download-proxy/requirements.txt is missing phase-3 deps: {missing!r}. "
        f"Have: {sorted(parsed)!r}"
    )


def test_runtime_requirements_meets_minimum_versions():
    parsed = _parse_requirements(_REQS)

    def _floor(spec: str) -> tuple[int, ...]:
        m = re.search(r"(\d+(?:\.\d+)*)", spec or "")
        if not m:
            return ()
        return tuple(int(p) for p in m.group(1).split("."))

    for pkg, min_ver in REQUIRED.items():
        spec = parsed.get(pkg, "")
        floor = _floor(spec)
        target = tuple(int(p) for p in min_ver.split("."))
        assert floor >= target, (
            f"{pkg} version floor in download-proxy/requirements.txt is {spec!r}; "
            f"tests/requirements.txt pins >={min_ver}"
        )
