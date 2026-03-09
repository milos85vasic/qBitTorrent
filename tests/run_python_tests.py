#!/usr/bin/env python3
"""Run all Python tests for RuTracker plugin."""

import os
import sys
import subprocess
import argparse


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'=' * 70}")
    print(f"Running: {description}")
    print(f"{'=' * 70}\n")

    result = subprocess.run(cmd, shell=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run RuTracker plugin tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument(
        "--integration", action="store_true", help="Run integration tests only"
    )
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(script_dir, "tests")

    if not any([args.unit, args.integration, args.e2e, args.all]):
        args.all = True

    results = {}
    verbosity = "2" if args.verbose else "1"

    if args.unit or args.all:
        test_file = os.path.join(tests_dir, "test_plugin_unit.py")
        if os.path.exists(test_file):
            success = run_command(
                [
                    sys.executable,
                    "-m",
                    "pytest" if _has_pytest() else "unittest",
                    test_file,
                    "-v" if args.verbose else "",
                    verbosity,
                ],
                "Unit Tests",
            )
            results["unit"] = success
        else:
            print(f"Warning: {test_file} not found")
            results["unit"] = False

    if args.integration or args.all:
        test_file = os.path.join(tests_dir, "test_plugin_integration.py")
        if os.path.exists(test_file):
            success = run_command([sys.executable, test_file], "Integration Tests")
            results["integration"] = success
        else:
            print(f"Warning: {test_file} not found")
            results["integration"] = False

    if args.e2e or args.all:
        test_file = os.path.join(tests_dir, "test_e2e_download.py")
        if os.path.exists(test_file):
            success = run_command(
                [sys.executable, test_file, "--direct"], "End-to-End Tests"
            )
            results["e2e"] = success
        else:
            print(f"Warning: {test_file} not found")
            results["e2e"] = False

    print(f"\n{'=' * 70}")
    print("TEST RESULTS SUMMARY")
    print(f"{'=' * 70}")

    for test_type, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{test_type.upper():20} {status}")

    print(f"{'=' * 70}\n")

    all_passed = all(results.values()) if results else False

    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1


def _has_pytest():
    """Check if pytest is available."""
    try:
        import pytest

        return True
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main())

def run_download_tests():
    """Run comprehensive download tests."""
    print("\n" + "=" * 70)
    print("Running RuTracker Plugin Download Tests")
    print("=" * 70)
    
    result = subprocess.run(
        [sys.executable, os.path.join(tests_dir, "test_download_comprehensive.py"), "--run"],
        cwd=tests_dir
    )
    
    return result.returncode == 0

if __name__ == "__main__":
    # Add download tests to the main test suite
    if "--download" in sys.argv or "--all" in sys.argv:
        success = run_download_tests()
        sys.exit(0 if success else 1)
