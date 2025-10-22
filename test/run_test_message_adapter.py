#!/usr/bin/env python3
# ============================================================================
# FILE: test/run_test_message_adapter.py
# Master test runner for Message Adapter tests (Category D)
# ============================================================================

import subprocess
import sys
import os
from pathlib import Path


def run_message_adapter_tests():
    """Run all Message Adapter tests with detailed output."""
    
    print("=" * 80)
    print("🚀 RUNNING MESSAGE ADAPTER TESTS (CATEGORY D)")
    print("=" * 80)
    print(f"Test Database: bot_framework_test")
    print(f"Test Directory: test/message_handler_adapters/")
    print(f"Module: message_handler/adapters/message_adapter.py")
    print(f"Test Coverage: build_message_adapter, validate_adapter, sanitize_adapter")
    print("=" * 80)
    print()
    
    # Get the project root directory
    test_dir = Path(__file__).parent / "message_handler_adapters"
    project_root = Path(__file__).parent.parent
    
    # Verify test directory exists
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        return 1
    
    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(test_dir),
        "-v",                    # Verbose
        "--tb=short",            # Short traceback
        "--color=yes",           # Colored output
        "-x",                    # Stop on first failure
        "--durations=10",        # Show 10 slowest tests
        "-ra",                   # Show summary of all test outcomes
        f"--rootdir={project_root}",
    ], cwd=str(project_root))
    
    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ ALL MESSAGE ADAPTER TESTS PASSED")
    else:
        print("❌ SOME MESSAGE ADAPTER TESTS FAILED")
    print("=" * 80)
    
    return result.returncode


def run_specific_test(test_name: str):
    """
    Run a specific test or test class.
    
    Args:
        test_name: Test name pattern (e.g., "test_missing_session", "TestBuildMessageAdapter")
    
    Examples:
        python test/run_test_message_adapter.py test_missing_session
        python test/run_test_message_adapter.py TestValidateAdapter
    """
    test_dir = Path(__file__).parent / "message_handler_adapters"
    project_root = Path(__file__).parent.parent
    
    print(f"🔍 Running specific test pattern: {test_name}")
    print()
    
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(test_dir),
        "-v",
        "-k", test_name,          # Filter by test name
        "--tb=short",
        "--color=yes",
        f"--rootdir={project_root}",
    ], cwd=str(project_root))
    
    return result.returncode


def run_with_coverage():
    """Run tests with coverage report."""
    test_dir = Path(__file__).parent / "message_handler_adapters"
    project_root = Path(__file__).parent.parent
    
    print("📊 Running tests with coverage analysis...")
    print()
    
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(test_dir),
        "-v",
        "--cov=message_handler.adapters",
        "--cov-report=html",
        "--cov-report=term-missing",
        f"--rootdir={project_root}",
    ], cwd=str(project_root))
    
    if result.returncode == 0:
        print()
        print("📈 Coverage report generated in: htmlcov/index.html")
    
    return result.returncode


def show_test_summary():
    """Show summary of available tests."""
    print("=" * 80)
    print("MESSAGE ADAPTER TEST SUITE SUMMARY")
    print("=" * 80)
    print()
    print("📁 Test File: test/message_handler_adapters/test_message_adapter.py")
    print()
    print("🧪 Test Sections:")
    print("  • D1: build_message_adapter Tests")
    print("    - Input validation (session, user, instance, message, db)")
    print("    - Template loading and validation")
    print("    - LLM model configuration")
    print("    - Session context extraction")
    print("    - Token plan initialization")
    print("    - Adapter structure building")
    print("    - Critical: Empty string validation for api_model_name & provider")
    print()
    print("  • D2: validate_adapter Tests")
    print("    - Required fields validation")
    print("    - Field type validation")
    print("    - Adapter size limits")
    print()
    print("  • D3: sanitize_adapter Tests")
    print("    - Sensitive key removal")
    print("    - String length limits")
    print("    - Dict item limits")
    print()
    print("📊 Total Test Count: ~40+ tests")
    print()
    print("🔴 Critical Tests:")
    print("  • Empty api_model_name validation")
    print("  • Empty provider validation")
    print("  • Missing template_set handling")
    print("  • Missing llm_model handling")
    print()
    print("=" * 80)


def main():
    """Main entry point with command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Message Adapter Test Suite Runner (Category D)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all adapter tests
  python test/run_test_message_adapter.py
  
  # Run specific test
  python test/run_test_message_adapter.py -t test_missing_session
  
  # Run with coverage
  python test/run_test_message_adapter.py --coverage
  
  # Show test summary
  python test/run_test_message_adapter.py --summary
  
  # Run specific test class
  python test/run_test_message_adapter.py -t TestBuildMessageAdapter
        """
    )
    
    parser.add_argument(
        '-t', '--test',
        type=str,
        help='Run specific test by name pattern'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run tests with coverage report'
    )
    
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show test suite summary'
    )
    
    args = parser.parse_args()
    
    # Show summary and exit
    if args.summary:
        show_test_summary()
        return 0
    
    # Run with coverage
    if args.coverage:
        return run_with_coverage()
    
    # Run specific test
    if args.test:
        return run_specific_test(args.test)
    
    # Run all tests (default)
    return run_message_adapter_tests()


if __name__ == "__main__":
    sys.exit(main())