# Test Suite - Regression Testing Guide

## Overview

This test suite is designed to detect bugs introduced when adding new modules to the codebase. All tests are organized in subfolders with a single master test runner at the root.

## Test Organization

```
test/
├── run_all_tests.py          # MASTER TEST RUNNER (use this!)
├── conftest.py               # Pytest fixtures
├── sync_test_db.py           # Database sync utility
│
├── api_layer/                # Category A: API endpoints, middleware
├── database_layer/           # Category E: Database models, connections
├── integration/              # Categories G, H, I: End-to-end, performance, security
├── message_handler_adapters/ # Category D: Message adapter building
├── message_handler_core/     # Category B: Core processing logic
├── message_handler_services/ # Category C: Identity, session, token services
└── utils/                    # Category F: Utility functions
```

## Running Tests

### Run All Tests (Regression Testing)

To check for bugs after adding a new module, run all test suites:

```bash
python test/run_all_tests.py
```

This will:
- Run all 7 test suites in sequence
- Continue running even if failures are found (no early exit)
- Generate a comprehensive bug report at the end
- Show which tests passed/failed and execution time

### Run Specific Test Suite

To test a specific module:

```bash
# Run only integration tests
python test/run_all_tests.py --suite integration

# Run only utils tests
python test/run_all_tests.py --suite utils

# Run only API layer tests
python test/run_all_tests.py --suite api
```

Available suites:
- `utils` - Utils (datetime, validation, JSON, telemetry)
- `database` - Database Layer (models, connections)
- `services` - Message Handler Services
- `adapters` - Message Handler Adapters
- `core` - Message Handler Core
- `api` - API Layer (endpoints, middleware)
- `integration` - Integration Tests (G, H, I - end-to-end, performance, security)

### Run with Coverage Analysis

To see code coverage:

```bash
python test/run_all_tests.py --coverage
```

Coverage report will be generated in `htmlcov/index.html`

### Get Help

```bash
python test/run_all_tests.py --help
```

## Regression Testing Workflow

### When Adding a New Module

1. **Before implementing**: Run all tests to establish baseline
   ```bash
   python test/run_all_tests.py
   ```

2. **During implementation**: Run specific suite to verify your module
   ```bash
   python test/run_all_tests.py --suite <your-module>
   ```

3. **After implementation**: Run all tests again to detect regressions
   ```bash
   python test/run_all_tests.py
   ```

4. **Check the bug report**: The runner will show all failures with:
   - File location
   - Test class and name
   - Error message
   - Execution time

### Example Output

```
🚀 COMPREHENSIVE TEST SUITE RUNNER
Project: Bot Framework
Database: bot_framework_test
Test Suites: 7
Purpose: Regression testing - detect bugs from new modules

✅ PASSED - Utils (Category F) (3.67s) (408 tests)
✅ PASSED - Database Layer (Category E) (5.23s) (47 tests)
✅ PASSED - Message Handler Services (Category C) (8.91s) (89 tests)
...

Total Tests: 650
Passed Tests: 650
Total Duration: 45.23s

✅ ALL TEST SUITES PASSED
```

## Test Categories

### Category A: API Layer (17 tests)
- Health endpoints (/healthz, /ready, /live)
- Message endpoints (POST /api/messages)
- WhatsApp endpoints (POST /whatsapp/webhook)
- Broadcast endpoints (POST /api/broadcast)
- Exception handling and middleware

### Category B: Message Handler Core (12 tests)
- Core processor logic
- Handler orchestration

### Category C: Message Handler Services (89 tests)
- Identity service (brand-scoped user identification)
- Instance service (bot instance resolution)
- Session service (session lifecycle)
- Message service (message persistence)
- Token service (token budget management)
- Idempotency service (duplicate detection)
- User context service

### Category D: Message Handler Adapters (8 tests)
- Message adapter building
- Validation and sanitization

### Category E: Database Layer (47 tests)
- Database models
- Connections and schemas
- Transactions

### Category F: Utils (408 tests)
- Datetime operations and timezone handling
- Validation (basic and content)
- JSON utilities
- Telemetry and logging
- Error handling

### Category G: Integration - End-to-End Flows (32 tests)
- New user first message
- Existing user messages
- Idempotent requests (duplicate detection)
- WhatsApp messages
- Broadcast messages
- Guest user handling
- Brand-scoped identity
- Session timeouts
- Token budget tracking

### Category H: Integration - Monitoring & Observability (18 tests)
- Structured logging (trace_id, request_id, duration)
- Distributed tracing (Langfuse integration)
- Metrics (request count, latency, token usage, cost)

### Category I: Integration - Edge Cases & Bug Fixes (29 tests)
- Idempotency race conditions
- Empty string validation
- Token service type handling (Decimal→float, temperature defaults)
- Core processor environment handling
- Session service token plan lifecycle
- Idempotency scope (per-session)
- WhatsApp performance optimization
- Integrity error detection

### Category J: Integration - Performance (14 tests)
- Throughput testing (100+ req/s)
- Latency percentiles (p50, p95, p99)
- Database connection pool management
- Memory leak detection
- Token plan initialization
- Cache performance
- Idempotency cache cleanup

### Category K: Integration - Security (18 tests)
- SQL injection protection
- XSS prevention
- Sensitive data handling (no passwords in logs)
- Input validation (length, format)
- Authorization validation (guest users, inactive instances)
- Data leakage prevention
- Header security (trace_id, request_id)

### Category L: Integration - Error Scenarios (20 tests)
- Invalid instance handling
- Missing configuration
- Invalid templates
- Orchestrator timeout/errors
- Database connection errors
- Deadlock detection and retry
- Concurrent idempotency
- Invalid request validation
- WhatsApp errors
- Broadcast errors

## Database Setup

Before running integration tests, ensure the test database is set up:

```bash
python test/sync_test_db.py
```

This copies the production schema to `bot_framework_test` database.

## Notes

- **No individual runner files**: All `run_test_*.py` files have been removed. Use `run_all_tests.py` instead.
- **Runs all tests**: The runner does NOT stop on first failure - it runs ALL tests to give you a complete bug report.
- **Structured output**: Clear color-coded output with timing information.
- **Bug reports**: Automatically generates detailed bug reports when failures are found.
- **Purpose-built**: Designed specifically for regression testing when adding new modules.
