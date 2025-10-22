# ============================================================================
# FILE: test/run_test_integration.py
# Master test runner for Integration Tests (Category G) ONLY
# ============================================================================

import subprocess
import sys
import os


def run_integration_tests():
    """Run all Integration tests with detailed output."""

    print("=" * 80)
    print("🚀 RUNNING INTEGRATION TESTS (CATEGORY G)")
    print("=" * 80)
    print(f"Test Database: bot_framework_test")
    print(f"Test Directory: test/integration/")
    print()
    print("Test Categories:")
    print("  G1. End-to-End Flows")
    print("  G2. Error Scenarios")
    print("  G3. Performance Testing")
    print("  G4. Security Testing")
    print("=" * 80)
    print()

    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/integration/",
        "-v",                    # Verbose
        "--tb=short",            # Short traceback
        "--color=yes",           # Colored output
        "-x",                    # Stop on first failure
        "--durations=10",        # Show 10 slowest tests
        "-m", "not performance", # Skip performance tests by default (run manually)
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL INTEGRATION TESTS PASSED")
    else:
        print("❌ SOME INTEGRATION TESTS FAILED")
    print("=" * 80)

    return result.returncode


def run_performance_tests():
    """Run performance tests separately (they take longer)."""

    print("\n")
    print("=" * 80)
    print("🚀 RUNNING PERFORMANCE TESTS (CATEGORY G3)")
    print("=" * 80)
    print(f"Test Directory: test/integration/")
    print("⚠️  WARNING: Performance tests may take several minutes")
    print("=" * 80)
    print()

    # Run only performance tests
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/integration/test_performance.py",
        "-v",
        "--tb=short",
        "--color=yes",
        "-m", "performance",  # Only performance tests
        "--durations=20",     # Show 20 slowest tests
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL PERFORMANCE TESTS PASSED")
    else:
        print("❌ SOME PERFORMANCE TESTS FAILED")
    print("=" * 80)

    return result.returncode


def run_security_tests():
    """Run security tests separately."""

    print("\n")
    print("=" * 80)
    print("🚀 RUNNING SECURITY TESTS (CATEGORY G4)")
    print("=" * 80)
    print(f"Test Directory: test/integration/")
    print("=" * 80)
    print()

    # Run only security tests
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/integration/test_security.py",
        "-v",
        "--tb=short",
        "--color=yes",
        "-m", "security",  # Only security tests
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL SECURITY TESTS PASSED")
    else:
        print("❌ SOME SECURITY TESTS FAILED")
    print("=" * 80)

    return result.returncode


def run_all_integration_tests_including_performance():
    """Run ALL integration tests including performance and security."""

    print("=" * 80)
    print("🚀 RUNNING ALL INTEGRATION TESTS (INCLUDING PERFORMANCE & SECURITY)")
    print("=" * 80)
    print()

    # Run all tests
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/integration/",
        "-v",
        "--tb=short",
        "--color=yes",
        "--durations=20",
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL INTEGRATION TESTS PASSED")
    else:
        print("❌ SOME INTEGRATION TESTS FAILED")
    print("=" * 80)

    return result.returncode


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run integration tests")
    parser.add_argument(
        "--mode",
        choices=["default", "performance", "security", "all"],
        default="default",
        help="Test mode: default (skip performance), performance, security, or all"
    )

    args = parser.parse_args()

    if args.mode == "performance":
        exit_code = run_performance_tests()
    elif args.mode == "security":
        exit_code = run_security_tests()
    elif args.mode == "all":
        exit_code = run_all_integration_tests_including_performance()
    else:
        exit_code = run_integration_tests()

    sys.exit(exit_code)
