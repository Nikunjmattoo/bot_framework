# ============================================================================
# FILE: test/run_test_message_handler_services.py
# Master test runner for all Services Layer tests (Category C)
# ============================================================================

import sys
import pytest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_all_services_tests():
    """
    Run all Category C: Services Layer tests.
    
    Test files in test/message_handler_services/:
        - test_identity_service.py (C1) - 41 tests
        - test_instance_service.py (C2) - 29 tests
        - test_session_service.py (C3) - 34 tests
        - test_message_service.py (C4) - 39 tests
        - test_user_context_service.py (C5) - 18 tests
        - test_idempotency_service.py (C6) - 42 tests (includes xfail for critical bugs)
        - test_token_service.py (C7) - 54 tests
    
    Total: 257 tests
    """
    
    # Test directory
    test_dir = project_root / "test" / "message_handler_services"
    
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        print(f"   Current directory: {Path.cwd()}")
        return 1
    
    print(f"📁 Test directory: {test_dir}")
    print(f"📊 Running all services layer tests...")
    print()
    
    # Run pytest with options
    exit_code = pytest.main([
        str(test_dir),                    # Run all tests in this directory
        "-v",                              # Verbose output
        "--tb=short",                      # Short traceback format
        "--strict-markers",                # Strict marker validation
        "-ra",                             # Show summary of all test outcomes
        "--color=yes",                     # Colored output
        "--maxfail=10",                    # Stop after 10 failures (safety limit)
        f"--rootdir={project_root}",      # Set root directory
        "-W", "ignore::DeprecationWarning", # Ignore deprecation warnings
    ])
    
    return exit_code


def run_specific_service_test(service_name: str):
    """
    Run tests for a specific service.
    
    Args:
        service_name: One of: identity, instance, session, message, 
                     user_context, idempotency, token
    
    Examples:
        run_specific_service_test('identity')
        run_specific_service_test('idempotency')
    """
    test_dir = project_root / "test" / "message_handler_services"
    test_file = test_dir / f"test_{service_name}_service.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        print(f"\n Available service tests:")
        for f in test_dir.glob("test_*_service.py"):
            print(f"   - {f.stem.replace('test_', '').replace('_service', '')}")
        return 1
    
    print(f"🧪 Running tests for {service_name} service...")
    print(f"📄 File: {test_file.name}")
    print()
    
    exit_code = pytest.main([
        str(test_file),
        "-v",
        "--tb=short",
        "-ra",
        "--color=yes",
        f"--rootdir={project_root}",
        "-W", "ignore::DeprecationWarning",
    ])
    
    return exit_code


def run_with_coverage():
    """Run all tests with coverage report."""
    test_dir = project_root / "test" / "message_handler_services"
    
    print("📊 Running tests with coverage analysis...")
    print()
    
    exit_code = pytest.main([
        str(test_dir),
        "-v",
        "--cov=message_handler.services",
        "--cov-report=html",
        "--cov-report=term-missing",
        f"--rootdir={project_root}",
        "-W", "ignore::DeprecationWarning",
    ])
    
    if exit_code == 0:
        print()
        print("📈 Coverage report generated in: htmlcov/index.html")
    
    return exit_code


def run_only_failing_tests():
    """Run only tests that failed in the last run."""
    test_dir = project_root / "test" / "message_handler_services"
    
    print("🔄 Running only previously failed tests...")
    print()
    
    exit_code = pytest.main([
        str(test_dir),
        "-v",
        "--lf",  # Run last failed
        "--tb=short",
        f"--rootdir={project_root}",
        "-W", "ignore::DeprecationWarning",
    ])
    
    return exit_code


def run_critical_bug_tests():
    """Run only xfail tests (documented critical bugs)."""
    test_dir = project_root / "test" / "message_handler_services"
    
    print("🔴 Running tests for documented CRITICAL bugs (xfail)...")
    print()
    
    exit_code = pytest.main([
        str(test_dir),
        "-v",
        "-m", "xfail",
        "--tb=short",
        "--runxfail",  # Run xfail tests to see current status
        f"--rootdir={project_root}",
        "-W", "ignore::DeprecationWarning",
    ])
    
    return exit_code


if __name__ == "__main__":
    """
    Usage Examples:
    
    1. Run all services tests:
       python test/run_test_message_handler_services.py
    
    2. Run specific service:
       python -c "from test.run_test_message_handler_services import run_specific_service_test; run_specific_service_test('identity')"
    
    3. Run with coverage:
       python -c "from test.run_test_message_handler_services import run_with_coverage; run_with_coverage()"
    
    4. Run only failed tests from last run:
       python -c "from test.run_test_message_handler_services import run_only_failing_tests; run_only_failing_tests()"
    
    5. Run only critical bug tests:
       python -c "from test.run_test_message_handler_services import run_critical_bug_tests; run_critical_bug_tests()"
    
    Or use pytest directly:
       pytest test/message_handler_services/ -v
       pytest test/message_handler_services/test_idempotency_service.py -v
    """
    
    print("=" * 80)
    print("🚀 SERVICES LAYER TEST SUITE (CATEGORY C)")
    print("=" * 80)
    print(f"📂 Project root: {project_root}")
    print()
    
    # Check if specific service requested via command line
    if len(sys.argv) > 1:
        service_name = sys.argv[1]
        print(f"Running specific service: {service_name}")
        print()
        exit_code = run_specific_service_test(service_name)
    else:
        # Run all tests
        exit_code = run_all_services_tests()
    
    print()
    print("=" * 80)
    if exit_code == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ TESTS FAILED (exit code: {exit_code})")
    print("=" * 80)
    
    sys.exit(exit_code)