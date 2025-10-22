# 🔄 Sync and Test Instructions

## Problem: Merge Conflicts in Local Files

Your local repository has **merge conflicts** that are causing test failures. The files contain conflict markers like `<<<<<<< HEAD` which are invalid Python syntax.

## ✅ Solution: Properly Sync with Remote

Follow these steps **in order**:

### Step 1: Discard Local Changes and Accept Remote
```bash
cd C:\Projects\bot_framework

# Accept remote version for conflicted files
git checkout --theirs test/integration/test_error_scenarios.py
git checkout --theirs test/integration/test_security.py
git checkout --theirs test/api_layer/test_message_endpoints.py

# Mark as resolved
git add test/integration/test_error_scenarios.py
git add test/integration/test_security.py
git add test/api_layer/test_message_endpoints.py

# Pull latest changes
git pull origin claude/session-management-research-011CUNn7zVTvVde9KTr1rWan
```

### Step 2: Verify No Conflicts
```bash
# Check for conflict markers
findstr /S /C:"<<<<<<<" test\*.py
findstr /S /C:"=======" test\*.py
findstr /S /C:">>>>>>>" test\*.py

# Should return nothing. If it finds any, repeat Step 1.
```

### Step 3: Run Tests

**Option A: Run All Tests (Organized Output)**
```bash
python test/run_all_tests.py
```

**Option B: Run Specific Suite**
```bash
# Database tests only
python test/run_all_tests.py --suite database

# API tests only
python test/run_all_tests.py --suite api

# Available suites: database, services, adapters, core, api
```

**Option C: Run with Coverage**
```bash
python test/run_all_tests.py --coverage
```

**Option D: Run with pytest directly**
```bash
# All tests
pytest test/ -v

# Specific file
pytest test/integration/test_end_to_end_flows.py -v

# Specific test
pytest test/integration/test_end_to_end_flows.py::TestNewUserFirstMessage::test_new_user_first_message_success -v
```

## 📊 Expected Test Results (After Sync)

After syncing, you should see:
- **~970 tests passed**
- **~10 tests skipped** (PII detector, concurrent tests)
- **0 xfailed, 0 xpassed** (removed all xfail markers)
- **Clean output** (thanks to pytest.ini configuration)

## 🐛 Current Known Issues (Still Fixing)

These 5 tests may still fail - working on them:

1. **test_new_user_first_message_success** - User tier issue (guest vs standard)
2. **test_existing_user_new_message** - Session ID mismatch
3. **test_invalid_template_reference** - May pass now (we fixed the 500→422)
4. **test_template_without_llm_model** - May pass now (we fixed the 500→422)
5. **test_invalid_phone_format** - Should be skipped now

## 📁 Test Organization

Tests are organized by layer:
```
test/
├── api_layer/              # FastAPI endpoints
├── database_layer/         # Database models
├── integration/            # End-to-end tests
├── message_handler_core/   # Core processing
├── message_handler_services/  # Business logic
├── message_handler_adapters/  # Message adapters
├── utils/                  # Utility functions
└── run_all_tests.py        # Master test runner
```

## 🔧 Test Configuration

New pytest.ini provides:
- **Short tracebacks** with local variables
- **Progress bar** output
- **Filtered warnings** (no deprecation spam)
- **Test markers** (slow, integration, security, etc.)

## ❓ Help

```bash
# Show test runner help
python test/run_all_tests.py --help

# Show pytest help
pytest --help
```

## 🚀 Quick Start (TL;DR)

```bash
# 1. Accept remote changes
git checkout --theirs test/integration/*.py test/api_layer/test_message_endpoints.py
git add test/integration/*.py test/api_layer/test_message_endpoints.py

# 2. Pull latest
git pull origin claude/session-management-research-011CUNn7zVTvVde9KTr1rWan

# 3. Run tests
python test/run_all_tests.py
```

Done! ✅
