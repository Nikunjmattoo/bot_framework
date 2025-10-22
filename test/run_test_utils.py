# ============================================================================
# FILE: test/run_test_utils.py
# Master test runner for Utils tests ONLY
# ============================================================================

import subprocess
import sys
import os

def run_utils_tests():
    """Run all Utils tests with detailed output."""
    
    print("=" * 80)
    print("🚀 RUNNING UTILS TESTS")
    print("=" * 80)
    print(f"Test Database: bot_framework_test")
    print(f"Test Directory: test/utils/")
    print(f"Coverage: All 11 Utils modules")
    print("=" * 80)
    print()
    
    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/utils/",
        "-v",                    # Verbose
        "--tb=short",            # Short traceback
        "--color=yes",           # Colored output
        "-x",                    # Stop on first failure
        "--durations=10",        # Show 10 slowest tests
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL UTILS TESTS PASSED")
    else:
        print("❌ SOME UTILS TESTS FAILED")
    print("=" * 80)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_utils_tests())