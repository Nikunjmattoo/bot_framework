# ============================================================================
# FILE: test/run_test_api_layer.py
# Master test runner for API Layer tests ONLY
# ============================================================================

import subprocess
import sys
import os

def run_api_layer_tests():
    """Run all API Layer tests with detailed output."""
    
    print("=" * 80)
    print("🚀 RUNNING API LAYER TESTS")
    print("=" * 80)
    print(f"Test Database: bot_framework_test")
    print(f"Test Directory: test/api_layer/")
    print("=" * 80)
    print()
    
    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/api_layer/",
        "-v",                    # Verbose
        "--tb=short",            # Short traceback
        "--color=yes",           # Colored output
        "-x",                    # Stop on first failure
        "--durations=10",        # Show 10 slowest tests
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL API LAYER TESTS PASSED")
    else:
        print("❌ SOME API LAYER TESTS FAILED")
    print("=" * 80)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_api_layer_tests())