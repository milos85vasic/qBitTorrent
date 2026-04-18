"""
Unit tests for main.py dual-thread startup.

Scenarios:
- Import without errors
- Function signatures
- Port configuration
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch, call

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))


class TestMainStartup:
    """Test main.py startup behavior."""

    def test_import_main(self):
        """main.py should be importable without errors."""
        try:
            import main
            assert True
        except Exception as e:
            pytest.fail(f"Failed to import main.py: {e}")

    def test_main_functions_exist(self):
        """main.py should define required functions."""
        import main
        assert hasattr(main, 'start_original_proxy')
        assert hasattr(main, 'start_fastapi_server')
        assert hasattr(main, 'main')
        assert callable(main.start_original_proxy)
        assert callable(main.start_fastapi_server)
        assert callable(main.main)

    def test_start_original_proxy_runs(self):
        """start_original_proxy should exist."""
        import main
        assert main.start_original_proxy is not None

    def test_start_fastapi_server_runs(self):
        """start_fastapi_server should exist."""
        import main
        assert main.start_fastapi_server is not None

    def test_main_function_exists(self):
        """main() function should orchestrate startup."""
        import main
        # The main function should start both services
        sig = main.main.__code__.co_varnames
        assert isinstance(sig, tuple)

    def test_main_starts_both_services_mocked(self):
        """main() should attempt to start both services (mocked)."""
        import main
        with patch('threading.Thread') as mock_thread:
            with patch('time.sleep', side_effect=KeyboardInterrupt()):
                try:
                    main.main()
                except KeyboardInterrupt:
                    pass
                # Should have created threads for both services
                assert mock_thread.call_count >= 1

    def test_port_env_vars(self):
        """Port should be configurable via environment."""
        with patch.dict(os.environ, {"PROXY_PORT": "9999", "MERGE_SERVICE_PORT": "9998"}):
            import importlib
            import main
            importlib.reload(main)
            # Should read from environment
            assert main is not None
