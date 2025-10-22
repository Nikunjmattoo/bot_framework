# ============================================================================
# FILE: test/run_all_tests.py
# MASTER TEST RUNNER - Executes all test suites with detailed bug reporting
# ============================================================================

import subprocess
import sys
import os
from pathlib import Path
import time
from datetime import datetime
import re

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title):
    """Print a formatted header."""
    print()
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title.center(80)}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 80}{Colors.END}")
    print()

def print_section(title):
    """Print a section divider."""
    print()
    print(f"{Colors.BLUE}{Colors.BOLD}{'─' * 80}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}▶ {title}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'─' * 80}{Colors.END}")
    print()

def print_result(name, passed, duration, failed_count=0, total_count=0):
    """Print test suite result with failure details."""
    if passed:
        status = f"{Colors.GREEN}✅ PASSED{Colors.END}"
        detail = f"({total_count} tests)"
    else:
        status = f"{Colors.RED}❌ FAILED{Colors.END}"
        detail = f"({failed_count}/{total_count} failed)"
    
    print(f"  {status} - {Colors.BOLD}{name}{Colors.END} ({duration:.2f}s) {detail}")

def parse_pytest_output(output):
    """
    Parse pytest output to extract test results and failures.
    
    Returns:
        dict: {
            'total': int,
            'passed': int,
            'failed': int,
            'failures': [{'test': str, 'file': str, 'line': int, 'error': str}]
        }
    """
    result = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'failures': []
    }
    
    # Extract summary line: "1 failed, 28 passed, 3 warnings in 0.99s"
    summary_match = re.search(r'(\d+) failed.*?(\d+) passed', output)
    if summary_match:
        result['failed'] = int(summary_match.group(1))
        result['passed'] = int(summary_match.group(2))
        result['total'] = result['failed'] + result['passed']
    else:
        # Try just passed
        passed_match = re.search(r'(\d+) passed', output)
        if passed_match:
            result['passed'] = int(passed_match.group(1))
            result['total'] = result['passed']
    
    # Extract failed test details
    # Pattern: FAILED test/path/file.py::TestClass::test_name - AssertionError: ...
    failed_pattern = r'FAILED (.*?)::(.*?)::(.*?) - (.*?)(?:\n|$)'
    for match in re.finditer(failed_pattern, output):
        failure = {
            'file': match.group(1),
            'class': match.group(2),
            'test': match.group(3),
            'error': match.group(4).strip()
        }
        result['failures'].append(failure)
    
    return result

def run_test_suite(name, test_dir, description):
    """
    Run a single test suite and capture detailed results.
    
    Args:
        name: Name of the test suite
        test_dir: Directory containing tests
        description: Short description
    
    Returns:
        dict: {
            'passed': bool,
            'duration': float,
            'total': int,
            'failed': int,
            'failures': list
        }
    """
    print_section(f"Running {name}")
    print(f"  📁 Directory: {test_dir}")
    print(f"  📝 Description: {description}")
    print()
    
    start_time = time.time()
    
    # Run pytest and capture output
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        test_dir,
        "-v",                    # Verbose
        "--tb=short",            # Short traceback
        "--color=yes",           # Colored output
        # NO -x flag - run all tests
        "--durations=5",         # Show 5 slowest tests
        "-W", "ignore::DeprecationWarning",  # Ignore deprecation warnings
    ], 
    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    capture_output=True,
    text=True)
    
    duration = time.time() - start_time
    passed = result.returncode == 0
    
    # Print the output
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    # Parse test results
    test_results = parse_pytest_output(result.stdout)
    
    return {
        'name': name,
        'passed': passed,
        'duration': duration,
        'total': test_results['total'],
        'failed': test_results['failed'],
        'failures': test_results['failures']
    }

def run_all_tests():
    """Run all test suites in order and generate comprehensive bug report."""
    
    # Test suites configuration
    # Order: Database → Services → Adapters → Core → API
    test_suites = [
        {
            "name": "Database Layer (Category E)",
            "dir": "test/database_layer/",
            "description": "Database models, connections, schemas"
        },
        {
            "name": "Message Handler Services (Category C)",
            "dir": "test/message_handler_services/",
            "description": "Identity, Instance, Session, Message, Token services"
        },
        {
            "name": "Message Handler Adapters (Category D)",
            "dir": "test/message_handler_adapters/",
            "description": "Message adapter building and validation"
        },
        {
            "name": "Message Handler Core (Category B)",
            "dir": "test/message_handler_core/",
            "description": "Core processing logic and orchestrator integration"
        },
        {
            "name": "API Layer (Category A)",
            "dir": "test/api_layer/",
            "description": "FastAPI endpoints, middleware, exception handling"
        }
    ]
    
    # Print startup banner
    print_header("🚀 COMPREHENSIVE TEST SUITE RUNNER")
    print(f"{Colors.BOLD}Project:{Colors.END} Bot Framework")
    print(f"{Colors.BOLD}Database:{Colors.END} bot_framework_test")
    print(f"{Colors.BOLD}Test Suites:{Colors.END} {len(test_suites)}")
    print(f"{Colors.BOLD}Started:{Colors.END} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all test suites (NO STOPPING ON FAILURE - RUN ALL)
    results = []
    total_start = time.time()
    
    for suite in test_suites:
        result = run_test_suite(
            suite["name"],
            suite["dir"],
            suite["description"]
        )
        results.append(result)
    
    total_duration = time.time() - total_start
    
    # Print summary
    print_header("📊 TEST EXECUTION SUMMARY")
    
    print(f"{Colors.BOLD}Results:{Colors.END}")
    print()
    for result in results:
        print_result(
            result["name"], 
            result["passed"], 
            result["duration"],
            result["failed"],
            result["total"]
        )
    
    print()
    print(f"{Colors.BOLD}{'─' * 80}{Colors.END}")
    
    # Count results
    total_suites = len(results)
    passed_suites = sum(1 for r in results if r["passed"])
    failed_suites = total_suites - passed_suites
    
    total_tests = sum(r["total"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_passed = total_tests - total_failed
    
    print()
    print(f"{Colors.BOLD}Test Suites:{Colors.END} {total_suites}")
    print(f"{Colors.GREEN}{Colors.BOLD}Passed Suites:{Colors.END} {passed_suites}")
    if failed_suites > 0:
        print(f"{Colors.RED}{Colors.BOLD}Failed Suites:{Colors.END} {failed_suites}")
    
    print()
    print(f"{Colors.BOLD}Total Tests:{Colors.END} {total_tests}")
    print(f"{Colors.GREEN}{Colors.BOLD}Passed Tests:{Colors.END} {total_passed}")
    if total_failed > 0:
        print(f"{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.END} {total_failed}")
    print(f"{Colors.BOLD}Total Duration:{Colors.END} {total_duration:.2f}s")
    
    # Print detailed bug report if there are failures
    if total_failed > 0:
        print_header("🐛 DETAILED BUG REPORT")
        
        bug_number = 1
        for result in results:
            if result["failed"] > 0:
                print(f"{Colors.RED}{Colors.BOLD}Suite: {result['name']}{Colors.END}")
                print(f"  Failed: {result['failed']}/{result['total']} tests")
                print()
                
                for failure in result["failures"]:
                    print(f"  {Colors.YELLOW}Bug #{bug_number}:{Colors.END}")
                    print(f"    File:  {failure['file']}")
                    print(f"    Class: {failure['class']}")
                    print(f"    Test:  {failure['test']}")
                    print(f"    Error: {Colors.RED}{failure['error']}{Colors.END}")
                    print()
                    bug_number += 1
        
        print(f"{Colors.BOLD}{'─' * 80}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}Total Bugs Found: {total_failed}{Colors.END}")
        print()
    
    # Final status
    print()
    if failed_suites == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}{'=' * 80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL TEST SUITES PASSED{Colors.END}".center(90))
        print(f"{Colors.GREEN}{Colors.BOLD}{'=' * 80}{Colors.END}")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}{'=' * 80}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}❌ {failed_suites} TEST SUITE(S) FAILED - {total_failed} BUG(S) FOUND{Colors.END}".center(90))
        print(f"{Colors.RED}{Colors.BOLD}{'=' * 80}{Colors.END}")
        return 1

def run_specific_suite(suite_name):
    """
    Run a specific test suite by name.
    
    Args:
        suite_name: Name of the test suite (e.g., 'database', 'services', 'api')
    """
    suite_map = {
        "database": ("test/database_layer/", "Database Layer"),
        "services": ("test/message_handler_services/", "Message Handler Services"),
        "adapters": ("test/message_handler_adapters/", "Message Handler Adapters"),
        "core": ("test/message_handler_core/", "Message Handler Core"),
        "api": ("test/api_layer/", "API Layer")
    }
    
    if suite_name.lower() not in suite_map:
        print(f"{Colors.RED}❌ Unknown test suite: {suite_name}{Colors.END}")
        print()
        print(f"{Colors.BOLD}Available suites:{Colors.END}")
        for key in suite_map.keys():
            print(f"  - {key}")
        return 1
    
    test_dir, name = suite_map[suite_name.lower()]
    
    print_header(f"🧪 Running {name}")
    
    result = run_test_suite(name, test_dir, f"Single suite: {name}")
    
    print()
    print_header("📊 SUMMARY")
    
    print_result(
        result["name"],
        result["passed"],
        result["duration"],
        result["failed"],
        result["total"]
    )
    
    # Show failures if any
    if result["failed"] > 0:
        print()
        print(f"{Colors.RED}{Colors.BOLD}🐛 FAILURES:{Colors.END}")
        print()
        
        for i, failure in enumerate(result["failures"], 1):
            print(f"  {Colors.YELLOW}Bug #{i}:{Colors.END}")
            print(f"    File:  {failure['file']}")
            print(f"    Class: {failure['class']}")
            print(f"    Test:  {failure['test']}")
            print(f"    Error: {Colors.RED}{failure['error']}{Colors.END}")
            print()
    
    print()
    if result["passed"]:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ {name} PASSED{Colors.END} ({result['duration']:.2f}s)")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ {name} FAILED - {result['failed']} BUG(S) FOUND{Colors.END} ({result['duration']:.2f}s)")
        return 1

def run_with_coverage():
    """Run all tests with coverage analysis."""
    print_header("📈 RUNNING TESTS WITH COVERAGE")
    
    start_time = time.time()
    
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "test/",
        "-v",
        "--cov=api",
        "--cov=message_handler",
        "--cov=db",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--tb=short",
        "-W", "ignore::DeprecationWarning",
    ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    duration = time.time() - start_time
    
    print()
    if result.returncode == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ TESTS PASSED WITH COVERAGE{Colors.END} ({duration:.2f}s)")
        print()
        print(f"{Colors.BOLD}Coverage report:{Colors.END} htmlcov/index.html")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ TESTS FAILED{Colors.END} ({duration:.2f}s)")
        return 1

def show_help():
    """Show help information."""
    print_header("📚 TEST RUNNER HELP")
    
    print(f"{Colors.BOLD}USAGE:{Colors.END}")
    print("  python test/run_all_tests.py [options]")
    print()
    
    print(f"{Colors.BOLD}OPTIONS:{Colors.END}")
    print("  (no args)           Run all test suites in sequence")
    print("  --suite <name>      Run specific test suite")
    print("  --coverage          Run with coverage analysis")
    print("  --help, -h          Show this help message")
    print()
    
    print(f"{Colors.BOLD}AVAILABLE TEST SUITES:{Colors.END}")
    print("  database            Database Layer (models, connections)")
    print("  services            Message Handler Services")
    print("  adapters            Message Handler Adapters")
    print("  core                Message Handler Core")
    print("  api                 API Layer (endpoints, middleware)")
    print()
    
    print(f"{Colors.BOLD}EXAMPLES:{Colors.END}")
    print("  # Run all tests")
    print("  python test/run_all_tests.py")
    print()
    print("  # Run specific suite")
    print("  python test/run_all_tests.py --suite database")
    print()
    print("  # Run with coverage")
    print("  python test/run_all_tests.py --coverage")
    print()

if __name__ == "__main__":
    """
    Main entry point.
    
    Examples:
        python test/run_all_tests.py
        python test/run_all_tests.py --suite database
        python test/run_all_tests.py --coverage
        python test/run_all_tests.py --help
    """
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            show_help()
            sys.exit(0)
        elif sys.argv[1] == "--coverage":
            sys.exit(run_with_coverage())
        elif sys.argv[1] == "--suite" and len(sys.argv) > 2:
            sys.exit(run_specific_suite(sys.argv[2]))
        else:
            print(f"{Colors.RED}❌ Unknown option: {sys.argv[1]}{Colors.END}")
            print()
            show_help()
            sys.exit(1)
    else:
        # Run all tests
        sys.exit(run_all_tests())