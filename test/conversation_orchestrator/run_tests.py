#!/usr/bin/env python3
"""
Test runner for conversation orchestrator tests.

Usage:
    python test/conversation_orchestrator/run_tests.py              # Run all tests
    python test/conversation_orchestrator/run_tests.py models       # Run model tests only
    python test/conversation_orchestrator/run_tests.py parser       # Run parser tests only
    python test/conversation_orchestrator/run_tests.py detector     # Run detector tests only
    python test/conversation_orchestrator/run_tests.py orchestrator # Run orchestrator tests only
    python test/conversation_orchestrator/run_tests.py integration  # Run integration tests only
    python test/conversation_orchestrator/run_tests.py --coverage   # Run with coverage
"""

import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def run_all_tests():
    """Run all orchestrator tests."""
    print_header("🧪 RUNNING ALL ORCHESTRATOR TESTS")
    
    test_dir = Path(__file__).parent
    
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(test_dir),
        "-v",
        "--tb=short",
        "--color=yes",
        "-ra",
        "-W", "ignore::DeprecationWarning",
    ])
    
    return result.returncode


def run_specific_tests(test_file):
    """Run specific test file."""
    test_dir = Path(__file__).parent
    test_path = test_dir / f"test_{test_file}.py"
    
    if not test_path.exists():
        print(f"❌ Test file not found: {test_path}")
        print(f"\nAvailable test files:")
        for f in test_dir.glob("test_*.py"):
            print(f"  - {f.stem.replace('test_', '')}")
        return 1
    
    print_header(f"🧪 RUNNING {test_file.upper()} TESTS")
    
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(test_path),
        "-v",
        "--tb=short",
        "--color=yes",
        "-ra",
        "-W", "ignore::DeprecationWarning",
    ])
    
    return result.returncode


def run_with_coverage():
    """Run tests with coverage report."""
    print_header("📊 RUNNING TESTS WITH COVERAGE")
    
    test_dir = Path(__file__).parent
    
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(test_dir),
        "-v",
        "--cov=conversation_orchestrator",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--tb=short",
        "--color=yes",
        "-W", "ignore::DeprecationWarning",
    ])
    
    if result.returncode == 0:
        print("\n📈 Coverage report generated in: htmlcov/index.html")
    
    return result.returncode


def main():
    """Main test runner."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--coverage":
            return run_with_coverage()
        elif arg in ["models", "parser", "detector", "orchestrator", "integration"]:
            return run_specific_tests(arg)
        else:
            print(f"❌ Unknown argument: {arg}")
            print("\nUsage:")
            print("  python run_tests.py              # Run all tests")
            print("  python run_tests.py models       # Run model tests")
            print("  python run_tests.py parser       # Run parser tests")
            print("  python run_tests.py detector     # Run detector tests")
            print("  python run_tests.py orchestrator # Run orchestrator tests")
            print("  python run_tests.py integration  # Run integration tests")
            print("  python run_tests.py --coverage   # Run with coverage")
            return 1
    else:
        return run_all_tests()


if __name__ == "__main__":
    sys.exit(main())