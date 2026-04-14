"""
Shared environment variable loader.

Single implementation used by plugins and the merge service.
Search order: os.environ → ./env file paths
"""

import os


def load_env_files(*extra_paths: str):
    """Load .env-style files into os.environ (first wins, no overrides)."""
    default_paths = [
        "/config/.env",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
        os.path.expanduser("~/.qbit.env"),
        "/root/.qbit.env",
    ]
    for path in list(extra_paths) + default_paths:
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip('"').strip("'")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


def get_env(key: str, default: str = "") -> str:
    """Get env var, loading from .env files if not already set."""
    val = os.environ.get(key)
    if val is None:
        load_env_files()
        val = os.environ.get(key, default)
    return val
