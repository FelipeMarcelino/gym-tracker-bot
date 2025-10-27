#!/usr/bin/env python3
"""Comprehensive test runner for Gym Tracker Bot

This script runs all tests with proper reporting and error handling.
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def check_dependencies():
    """Check if required test dependencies are installed"""
    required_packages = ["pytest", "pytest-asyncio","sqlalchemy"]
    missing = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)

    if missing:
        print(f"❌ Missing test dependencies: {', '.join(missing)}")
        print("Install with: pip install pytest pytest-asyncio")
        return False

    return True


def run_test_suite(test_type="all", verbose=False, stop_on_fail=False):
    """Run the test suite
    
    Args:
        test_type: "all", "unit", "integration", or specific test file
        verbose: Enable verbose output
        stop_on_fail: Stop on first failure

    """
    print("🧪 **GYM TRACKER BOT - TEST SUITE**")
    print("🕐", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    if not check_dependencies():
        return False

    # Build pytest command
    cmd = ["python", "-m", "pytest"]

    # Test selection
    if test_type == "unit":
        cmd.append("tests/unit/")
        print("🔬 Running unit tests only...")
    elif test_type == "integration":
        cmd.append("tests/integration/")
        print("🔗 Running integration tests only...")
    elif test_type == "all":
        cmd.append("tests/")
        print("🎯 Running all tests...")
    else:
        # Specific test file or pattern
        cmd.append(test_type)
        print(f"📝 Running specific tests: {test_type}")

    # Options
    if verbose:
        cmd.extend(["-v", "-s"])
    else:
        cmd.append("-v")

    if stop_on_fail:
        cmd.append("-x")

    # Always show short traceback and colors
    cmd.extend(["--tb=short", "--color=yes"])

    print(f"🚀 Command: {' '.join(cmd)}")
    print("-" * 40)

    start_time = time.time()

    try:
        # Run tests
        result = subprocess.run(cmd, check=False, cwd=os.path.dirname(__file__))

        duration = time.time() - start_time
        print("-" * 40)
        print(f"⏱️  Tests completed in {duration:.2f}s")

        if result.returncode == 0:
            print("✅ All tests passed!")
            return True
        print("❌ Some tests failed!")
        return False

    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return False


def run_coverage_report():
    """Run tests with coverage reporting"""
    print("\n📊 **RUNNING COVERAGE ANALYSIS**")
    print("-" * 40)

    try:
        # Check if pytest-cov is available
        subprocess.run(["python", "-c", "import pytest_cov"], check=True, capture_output=True)

        cmd = [
            "python", "-m", "pytest",
            "tests/",
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=70",
        ]

        result = subprocess.run(cmd, check=False, cwd=os.path.dirname(__file__))

        if result.returncode == 0:
            print("✅ Coverage analysis completed!")
            print("📁 HTML report generated in htmlcov/")
            return True
        print("❌ Coverage analysis failed or below threshold")
        return False

    except subprocess.CalledProcessError:
        print("⚠️  pytest-cov not installed, skipping coverage")
        print("Install with: pip install pytest-cov")
        return False
    except Exception as e:
        print(f"❌ Error running coverage: {e}")
        return False


def check_test_files():
    """Check which test files exist and provide overview"""
    print("📁 **TEST FILE OVERVIEW**")
    print("-" * 40)

    test_dir = Path("tests")
    if not test_dir.exists():
        print("❌ Tests directory not found!")
        return False

    unit_tests = list(test_dir.glob("unit/test_*.py"))
    integration_tests = list(test_dir.glob("integration/test_*.py"))

    print(f"🔬 Unit tests: {len(unit_tests)} files")
    for test in unit_tests:
        print(f"   • {test.name}")

    print(f"\n🔗 Integration tests: {len(integration_tests)} files")
    for test in integration_tests:
        print(f"   • {test.name}")

    total = len(unit_tests) + len(integration_tests)
    print(f"\n📊 Total test files: {total}")

    return True


def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Run Gym Tracker Bot tests")
    parser.add_argument(
        "type",
        nargs="?",
        default="all",
        choices=["all", "unit", "integration", "coverage", "list"],
        help="Type of tests to run",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "-x", "--stop-on-fail",
        action="store_true",
        help="Stop on first failure",
    )
    parser.add_argument(
        "--file",
        help="Run specific test file",
    )

    args = parser.parse_args()

    if args.type == "list":
        return check_test_files()
    if args.type == "coverage":
        success = run_test_suite("all", args.verbose, args.stop_on_fail)
        if success:
            return run_coverage_report()
        return False
    if args.file:
        return run_test_suite(args.file, args.verbose, args.stop_on_fail)
    return run_test_suite(args.type, args.verbose, args.stop_on_fail)


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test runner error: {e}")
        sys.exit(1)

