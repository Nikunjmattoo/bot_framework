# ============================================================================
# FILE: test/run_test_message_handler_core.py
# Master test runner for Message Handler Core tests ONLY
# ============================================================================

import subprocess
import sys
import os

def run_message_handler_core_tests():
    """Run all Message Handler Core tests with detailed output."""
    
    print("=" * 80)
    print("🚀 RUNNING MESSAGE HANDLER CORE TESTS")
    print("=" * 80)
    print(f"Test Database: bot_framework_test")
    print(f"Test Directory: test/message_handler_core/")
    print(f"Coverage: All 13 Message Handler Core modules")
    print("=" * 80)
    print()
    
    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/message_handler_core/",
        "-v",                    # Verbose
        "--tb=short",            # Short traceback
        "--color=yes",           # Colored output
        "-x",                    # Stop on first failure
        "--durations=10",        # Show 10 slowest tests
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL MESSAGE HANDLER CORE TESTS PASSED")
    else:
        print("❌ SOME MESSAGE HANDLER CORE TESTS FAILED")
    print("=" * 80)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_message_handler_core_tests())