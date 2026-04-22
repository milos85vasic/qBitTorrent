"""Docker‑compose fixtures for integration tests.

Provides a session‑scoped ``compose_up`` fixture that ensures the
``docker‑compose.yml`` stack (qbittorrent + proxy) is healthy before
any test that depends on it.

The fixture checks if the services are already running; if not,
it starts them using ``podman compose up -d`` (or ``docker compose``).
"""

import os
import socket
import subprocess
import time
from typing import Any

import pytest

# Remove duplicate fixture definitions; they are provided by conftest.py
# Pytest will use the fixtures defined in conftest.py


def _detect_container_runtime() -> tuple[str, str]:
    """Detect podman or docker and return (runtime, compose_cmd)."""
    if subprocess.run(["which", "podman"], capture_output=True).returncode == 0:
        runtime = "podman"
        # Try podman-compose first, then podman compose
        if subprocess.run(["which", "podman-compose"], capture_output=True).returncode == 0:
            compose_cmd = "podman-compose"
        else:
            compose_cmd = "podman compose"
    elif subprocess.run(["which", "docker"], capture_output=True).returncode == 0:
        runtime = "docker"
        # Try docker compose (v2), then docker-compose (v1)
        result = subprocess.run(["docker", "compose", "version"], capture_output=True)
        if result.returncode == 0:
            compose_cmd = "docker compose"
        else:
            compose_cmd = "docker-compose"
    else:
        raise RuntimeError("Neither podman nor docker found in PATH")
    return runtime, compose_cmd


def _is_port_listening(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if a TCP connection can be made to the given port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError):
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 300.0) -> None:
    """Wait until a TCP port is accepting connections."""
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        if _is_port_listening(port, host):
            return
        time.sleep(0.5)
    raise TimeoutError(f"Port {port} on {host} did not become responsive within {timeout}s")


def _start_compose_stack(compose_cmd: str, compose_file: str, project_name: str) -> None:
    """Run `compose_cmd up -d`."""
    import shlex
    cmd = f"{compose_cmd} -f {shlex.quote(compose_file)} -p {shlex.quote(project_name)} up -d"
    print(f"Starting compose stack: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start compose stack: {result.stderr}")


@pytest.fixture(scope="session")
def compose_up(pytestconfig: Any) -> dict[str, str]:
    """Ensure docker‑compose stack is healthy and return service URLs.

    This fixture is session‑scoped: if the stack is already running,
    it just verifies health; otherwise it starts the stack.
    The stack is NOT torn down after tests (persists across sessions).
    """
    # Port configuration
    proxy_port = int(os.environ.get("PROXY_PORT", "7186"))
    merge_port = int(os.environ.get("MERGE_SERVICE_PORT", "7187"))
    qbittorrent_port = 7185  # internal, but accessible via host network

    # Check if services are already listening
    ports = [qbittorrent_port, proxy_port, merge_port]
    all_listening = all(_is_port_listening(port) for port in ports)
    
    if not all_listening:
        # Need to start the stack
        runtime, compose_cmd = _detect_container_runtime()
        compose_file = os.path.join(str(pytestconfig.rootdir), "docker-compose.yml")
        project_name = "qbittorrent"
        _start_compose_stack(compose_cmd, compose_file, project_name)
        # Wait for ports
        for port in ports:
            _wait_for_port(port, timeout=120.0)
    
    # Verify health by making HTTP requests
    import requests
    # Merge service health
    merge_url = f"http://localhost:{merge_port}"
    for _ in range(30):
        try:
            resp = requests.get(f"{merge_url}/health", timeout=2)
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError(f"Merge service not healthy at {merge_url}")
    
    # qBittorrent proxy health (just check it responds)
    proxy_url = f"http://localhost:{proxy_port}"
    for _ in range(30):
        try:
            resp = requests.get(proxy_url, timeout=2)
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError(f"Proxy not healthy at {proxy_url}")
    
    return {
        "merge_service": merge_url,
        "qbittorrent_proxy": proxy_url,
    }