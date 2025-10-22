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

def print_result(name, passed, duration, failed_count=0, skipped_count=0, total_count=0):
    """Print test suite result with failure and skip details."""
    if passed:
        status = f"{Colors.GREEN}✅ PASSED{Colors.END}"
        if skipped_count > 0:
            detail = f"({total_count} tests, {skipped_count} skipped)"
        else:
            detail = f"({total_count} tests)"
    else:
        status = f"{Colors.RED}❌ FAILED{Colors.END}"
        if skipped_count > 0:
            detail = f"({failed_count} failed, {skipped_count} skipped, {total_count} total)"
        else:
            detail = f"({failed_count}/{total_count} failed)"

    print(f"  {status} - {Colors.BOLD}{name}{Colors.END} ({duration:.2f}s) {detail}")

def parse_pytest_output(output):
    """
    Parse pytest output to extract test results, failures, and skipped tests.

    Returns:
        dict: {
            'total': int,
            'passed': int,
            'failed': int,
            'skipped': int,
            'failures': [{'test': str, 'file': str, 'class': str, 'error': str}],
            'skipped_tests': [{'test': str, 'file': str, 'class': str, 'reason': str}]
        }
    """
    result = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'failures': [],
        'skipped_tests': []
    }

    # Extract summary line: "1 failed, 28 passed, 3 skipped, 3 warnings in 0.99s"
    # Try multiple patterns to catch different combinations

    # Pattern 1: failed + passed + skipped
    summary_match = re.search(r'(\d+) failed.*?(\d+) passed.*?(\d+) skipped', output)
    if summary_match:
        result['failed'] = int(summary_match.group(1))
        result['passed'] = int(summary_match.group(2))
        result['skipped'] = int(summary_match.group(3))
        result['total'] = result['failed'] + result['passed'] + result['skipped']
    else:
        # Pattern 2: failed + passed (no skipped)
        summary_match = re.search(r'(\d+) failed.*?(\d+) passed', output)
        if summary_match:
            result['failed'] = int(summary_match.group(1))
            result['passed'] = int(summary_match.group(2))
            result['total'] = result['failed'] + result['passed']
        else:
            # Pattern 3: passed + skipped (no failures)
            summary_match = re.search(r'(\d+) passed.*?(\d+) skipped', output)
            if summary_match:
                result['passed'] = int(summary_match.group(1))
                result['skipped'] = int(summary_match.group(2))
                result['total'] = result['passed'] + result['skipped']
            else:
                # Pattern 4: just passed
                passed_match = re.search(r'(\d+) passed', output)
                if passed_match:
                    result['passed'] = int(passed_match.group(1))
                    result['total'] = result['passed']

                # Check for skipped separately
                skipped_match = re.search(r'(\d+) skipped', output)
                if skipped_match:
                    result['skipped'] = int(skipped_match.group(1))
                    result['total'] += result['skipped']

    # Extract failed test details
    # Pattern: FAILED test/path/file.py::TestClass::test_name - Error message
    failed_pattern = r'FAILED (.*?)::(.*?)::(.*?) - (.*?)(?:\n|$)'
    for match in re.finditer(failed_pattern, output):
        # Extract short file name (just the filename, not full path)
        full_file = match.group(1)
        short_file = full_file.split('/')[-1] if '/' in full_file else full_file

        # Truncate long error messages
        error_msg = match.group(4).strip()
        if len(error_msg) > 100:
            error_msg = error_msg[:97] + '...'

        failure = {
            'file': short_file,
            'class': match.group(2),
            'test': match.group(3),
            'error': error_msg
        }
        result['failures'].append(failure)

    # Extract skipped test details
    # Strategy: Parse both the test list and summary section separately, then merge

    # Step 1: Get all skipped test names from the verbose output
    # Pattern: test/path/file.py::TestClass::test_name SKIPPED
    skipped_tests_list = []
    skipped_list_pattern = r'(test/.*?)::(.*?)::(.*?)\s+SKIPPED'
    for match in re.finditer(skipped_list_pattern, output):
        full_path = match.group(1)
        short_file = full_path.split('/')[-1] if '/' in full_path else full_path
        skipped_tests_list.append({
            'file': short_file,
            'full_path': full_path,
            'class': match.group(2),
            'test': match.group(3),
            'reason': 'No reason provided'
        })

    # Step 2: Get skip reasons from summary section
    # Pattern: SKIPPED [1] test/path/file.py:123: Reason text
    skipped_reasons = {}
    skipped_reason_pattern = r'SKIPPED \[\d+\] (test/.*?\.py):(\d+): (.+?)$'
    for match in re.finditer(skipped_reason_pattern, output, re.MULTILINE):
        file_path = match.group(1)
        line_num = match.group(2)
        reason = match.group(3).strip()
        # Truncate long reasons
        if len(reason) > 80:
            reason = reason[:77] + '...'
        # Store reason by file:line
        key = f"{file_path}:{line_num}"
        skipped_reasons[key] = reason

    # Step 3: Match reasons to tests
    # We'll match by file path - assign each reason to tests from that file in order
    if skipped_tests_list and skipped_reasons:
        # Group tests by file
        tests_by_file = {}
        for test in skipped_tests_list:
            if test['full_path'] not in tests_by_file:
                tests_by_file[test['full_path']] = []
            tests_by_file[test['full_path']].append(test)

        # Assign reasons to tests
        for file_path, tests in tests_by_file.items():
            # Get all reasons for this file
            file_reasons = [v for k, v in skipped_reasons.items() if file_path in k]
            # Assign reasons to tests in order
            for i, test in enumerate(tests):
                if i < len(file_reasons):
                    test['reason'] = file_reasons[i]

    result['skipped_tests'] = skipped_tests_list

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
            'skipped': int,
            'failures': list,
            'skipped_tests': list
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
        "-rs",                   # Show skip reasons
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
        'skipped': test_results['skipped'],
        'failures': test_results['failures'],
        'skipped_tests': test_results['skipped_tests']
    }

def run_all_tests():
    """Run all test suites in order and generate comprehensive bug report."""
    
    # Test suites configuration
    # Order: Utils → Database → Services → Adapters → Core → API → Integration
    test_suites = [
        {
            "name": "Utils (Category F)",
            "dir": "test/utils/",
            "description": "Utility functions: datetime, validation, JSON, telemetry"
        },
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
        },
        {
            "name": "Integration Tests (Categories G, H, I)",
            "dir": "test/integration/",
            "description": "End-to-end flows, performance, security, monitoring, edge cases"
        }
    ]
    
    # Print startup banner
    print_header("🚀 COMPREHENSIVE TEST SUITE RUNNER")
    print(f"{Colors.BOLD}Project:{Colors.END} Bot Framework")
    print(f"{Colors.BOLD}Database:{Colors.END} bot_framework_test")
    print(f"{Colors.BOLD}Test Suites:{Colors.END} {len(test_suites)}")
    print(f"{Colors.BOLD}Purpose:{Colors.END} Regression testing - detect bugs from new modules")
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
            result["skipped"],
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
    total_skipped = sum(r["skipped"] for r in results)
    total_passed = total_tests - total_failed - total_skipped

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
    if total_skipped > 0:
        print(f"{Colors.YELLOW}{Colors.BOLD}Skipped Tests:{Colors.END} {total_skipped}")
    print(f"{Colors.BOLD}Total Duration:{Colors.END} {total_duration:.2f}s")

    # Print detailed bug report if there are failures
    if total_failed > 0:
        print_header("🐛 FAILED TESTS - MINIMAL DETAILS")

        bug_number = 1
        for result in results:
            if result["failed"] > 0:
                print(f"{Colors.RED}{Colors.BOLD}Suite: {result['name']}{Colors.END}")
                print(f"  Failed: {result['failed']}/{result['total']} tests")
                print()

                for failure in result["failures"]:
                    print(f"  {Colors.YELLOW}#{bug_number}:{Colors.END} {Colors.BOLD}{failure['test']}{Colors.END}")
                    print(f"      📄 {failure['file']} :: {failure['class']}")
                    print(f"      ❌ {failure['error']}")
                    print()
                    bug_number += 1

        print(f"{Colors.BOLD}{'─' * 80}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}Total Failed: {total_failed}{Colors.END}")
        print()

    # Print skipped tests report if there are any
    if total_skipped > 0:
        print_header("⏭️  SKIPPED TESTS - MINIMAL DETAILS")

        skip_number = 1
        for result in results:
            if result["skipped"] > 0:
                print(f"{Colors.YELLOW}{Colors.BOLD}Suite: {result['name']}{Colors.END}")
                print(f"  Skipped: {result['skipped']}/{result['total']} tests")
                print()

                for skipped in result["skipped_tests"]:
                    print(f"  {Colors.CYAN}#{skip_number}:{Colors.END} {Colors.BOLD}{skipped['test']}{Colors.END}")
                    print(f"      📄 {skipped['file']} :: {skipped['class']}")
                    print(f"      ⏭️  {skipped['reason']}")
                    print()
                    skip_number += 1

        print(f"{Colors.BOLD}{'─' * 80}{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}Total Skipped: {total_skipped}{Colors.END}")
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
        "utils": ("test/utils/", "Utils"),
        "database": ("test/database_layer/", "Database Layer"),
        "services": ("test/message_handler_services/", "Message Handler Services"),
        "adapters": ("test/message_handler_adapters/", "Message Handler Adapters"),
        "core": ("test/message_handler_core/", "Message Handler Core"),
        "api": ("test/api_layer/", "API Layer"),
        "integration": ("test/integration/", "Integration Tests (G, H, I)")
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
        result["skipped"],
        result["total"]
    )

    # Show failures if any
    if result["failed"] > 0:
        print()
        print(f"{Colors.RED}{Colors.BOLD}🐛 FAILED TESTS:{Colors.END}")
        print()

        for i, failure in enumerate(result["failures"], 1):
            print(f"  {Colors.YELLOW}#{i}:{Colors.END} {Colors.BOLD}{failure['test']}{Colors.END}")
            print(f"      📄 {failure['file']} :: {failure['class']}")
            print(f"      ❌ {failure['error']}")
            print()

    # Show skipped tests if any
    if result["skipped"] > 0:
        print()
        print(f"{Colors.YELLOW}{Colors.BOLD}⏭️  SKIPPED TESTS:{Colors.END}")
        print()

        for i, skipped in enumerate(result["skipped_tests"], 1):
            print(f"  {Colors.CYAN}#{i}:{Colors.END} {Colors.BOLD}{skipped['test']}{Colors.END}")
            print(f"      📄 {skipped['file']} :: {skipped['class']}")
            print(f"      ⏭️  {skipped['reason']}")
            print()

    print()
    if result["passed"]:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ {name} PASSED{Colors.END} ({result['duration']:.2f}s)")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ {name} FAILED - {result['failed']} FAILED{Colors.END} ({result['duration']:.2f}s)")
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
    print("  utils               Utils (datetime, validation, JSON, telemetry)")
    print("  database            Database Layer (models, connections)")
    print("  services            Message Handler Services")
    print("  adapters            Message Handler Adapters")
    print("  core                Message Handler Core")
    print("  api                 API Layer (endpoints, middleware)")
    print("  integration         Integration Tests (G, H, I - end-to-end, performance, security)")
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