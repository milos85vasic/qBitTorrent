import json
import os
import sys
import threading

_src = os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from api.routes import _save_qbit_credentials  # noqa: E402


class TestCredentialFileSafety:
    def test_concurrent_writes_no_corruption(self, tmp_path):
        creds_file = str(tmp_path / "qbittorrent_creds.json")
        errors: list[str] = []
        num_writers = 50

        def writer(idx: int):
            try:
                _save_qbit_credentials(
                    creds_file,
                    {"username": f"user_{idx}", "password": f"pass_{idx}"},
                )
            except Exception as e:
                errors.append(f"writer {idx}: {e}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors during concurrent writes: {errors}"

        with open(creds_file) as f:
            data = json.load(f)

        assert "username" in data
        assert "password" in data
        assert data["username"].startswith("user_")
        assert data["password"].startswith("pass_")
