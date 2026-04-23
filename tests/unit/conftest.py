import os
import shutil

import pytest

_angular_dist_path = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src", "ui", "dist", "frontend", "browser")
)
_angular_index_path = os.path.join(_angular_dist_path, "index.html")
_stubs_created = False


def _ensure_angular_stub():
    global _stubs_created
    if os.path.isfile(_angular_index_path):
        return
    os.makedirs(_angular_dist_path, exist_ok=True)
    stub_html = (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"></head>\n'
        "<body>\n"
        "<app-root></app-root>\n"
        '<script src="main-ABC123.js" type="module"></script>\n'
        "</body></html>"
    )
    with open(_angular_index_path, "w") as f:
        f.write(stub_html)
    _stubs_created = True


_ensure_angular_stub()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_angular_stub():
    yield
    if _stubs_created:
        dist_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src", "ui", "dist")
        )
        shutil.rmtree(dist_root, ignore_errors=True)
