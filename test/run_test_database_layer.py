# ============================================================================
# FILE: test/run_test_database_layer.py
# Master test runner for Database Layer tests ONLY
# ============================================================================

import subprocess
import sys
import os

def run_database_layer_tests():
    """Run all Database Layer tests with detailed output."""
    
    print("=" * 80)
    print("🚀 RUNNING DATABASE LAYER TESTS")
    print("=" * 80)
    print(f"Test Database: bot_framework_test")
    print(f"Test Directory: test/database_layer/")
    print(f"Coverage: All database models, connections, and schemas")
    print("=" * 80)
    print()
    
    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/database_layer/",
        "-v",                    # Verbose
        "--tb=short",            # Short traceback
        "--color=yes",           # Colored output
        "-x",                    # Stop on first failure
        "--durations=10",        # Show 10 slowest tests
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL DATABASE LAYER TESTS PASSED")
    else:
        print("❌ SOME DATABASE LAYER TESTS FAILED")
    print("=" * 80)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_database_layer_tests())