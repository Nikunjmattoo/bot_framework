# 🚀 Complete Setup & Test Execution Guide

**Target**: Run all 123 conversation_orchestrator tests
**Database**: PostgreSQL (as configured in `test/conftest.py`)
**Your Test DB**: `postgresql+psycopg2://postgres:admin@localhost:5432/bot_framework_test`

---

## 📋 Prerequisites Checklist

- [ ] PostgreSQL installed and running
- [ ] Python 3.11+ installed
- [ ] All dependencies installed (`requirements.txt`)
- [ ] Test database created

---

## Step 1: Verify PostgreSQL is Running

```bash
# Check if PostgreSQL is installed
psql --version

# Check if PostgreSQL server is running
pg_isready -h localhost -p 5432

# If not running, start it:
# Ubuntu/Debian:
sudo service postgresql start

# macOS:
brew services start postgresql

# Windows:
# Use Services app to start PostgreSQL
```

**Expected output**:
```
localhost:5432 - accepting connections
```

---

## Step 2: Create Test Database

```bash
# Method 1: Using psql command line
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE bot_framework_test;"

# Method 2: Interactive psql
psql -U postgres -h localhost
postgres=# CREATE DATABASE bot_framework_test;
postgres=# \q

# Verify database exists
psql -U postgres -h localhost -l | grep bot_framework_test
```

**Expected output**:
```
 bot_framework_test | postgres | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
```

---

## Step 3: Set Database Password (If Needed)

Your test configuration expects password: `admin`

```bash
# Set password for postgres user
psql -U postgres -h localhost
postgres=# ALTER USER postgres WITH PASSWORD 'admin';
postgres=# \q
```

**OR** update `test/conftest.py` with your actual password:
```python
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/bot_framework_test"
)
```

---

## Step 4: Install Python Dependencies

```bash
# Navigate to project root
cd /path/to/bot_framework

# Install all dependencies
pip install -r requirements.txt

# Install test dependencies (if not in requirements.txt)
pip install pytest pytest-asyncio pytest-cov pytest-xdist
```

---

## Step 5: Initialize Test Database Schema

The test suite will auto-create tables, but you can pre-load the schema:

```bash
# Option A: Let pytest create tables automatically (RECOMMENDED)
# The conftest.py fixture will handle this

# Option B: Manually load schema (if you want)
psql -U postgres -h localhost -d bot_framework_test -f dump-new_db.sql
```

---

## Step 6: Run Tests

### Quick Test (Models & Parser Only - 62 tests)

These tests don't need database and should pass immediately:

```bash
# From project root
pytest test/conversation_orchestrator/test_models.py test/conversation_orchestrator/test_parser.py -v
```

**Expected**: ✅ 62 passed in ~0.2s

---

### Full Orchestrator Tests (All 123 tests)

```bash
# Method 1: Using the test runner script
python test/conversation_orchestrator/run_tests.py

# Method 2: Using pytest directly
pytest test/conversation_orchestrator/ -v --tb=short

# Method 3: With coverage report
python test/conversation_orchestrator/run_tests.py --coverage
```

**Expected**: ✅ 123 passed (or close to it)

---

### Run Specific Test Categories

```bash
# Models only
python test/conversation_orchestrator/run_tests.py models

# Parser only
python test/conversation_orchestrator/run_tests.py parser

# Detector only
python test/conversation_orchestrator/run_tests.py detector

# Orchestrator only
python test/conversation_orchestrator/run_tests.py orchestrator

# Integration only
python test/conversation_orchestrator/run_tests.py integration
```

---

### Run ALL Tests (Entire Framework)

```bash
# Run all test suites including orchestrator
python test/run_all_tests.py

# Run only orchestrator suite
python test/run_all_tests.py --suite orchestrator

# Run with coverage
python test/run_all_tests.py --coverage
```

---

## 🐛 Troubleshooting

### Issue 1: "peer authentication failed"

**Error**:
```
psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed:
FATAL:  Peer authentication failed for user "postgres"
```

**Solution**: Edit `pg_hba.conf` to allow password authentication:

```bash
# Find pg_hba.conf location
psql -U postgres -h localhost -t -P format=unaligned -c 'show hba_file'

# Edit the file (Ubuntu example)
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Change this line:
# local   all             postgres                                peer
# To:
local   all             postgres                                md5

# Restart PostgreSQL
sudo service postgresql restart
```

---

### Issue 2: "database does not exist"

**Error**:
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError)
FATAL:  database "bot_framework_test" does not exist
```

**Solution**: Create the database (see Step 2)

---

### Issue 3: "password authentication failed"

**Error**:
```
psycopg2.OperationalError: FATAL:  password authentication failed for user "postgres"
```

**Solution**: Either:
- Set the password to `admin` (see Step 3)
- OR update TEST_DATABASE_URL with correct password
- OR set environment variable:
  ```bash
  export TEST_DATABASE_URL="postgresql+psycopg2://postgres:CORRECT_PASSWORD@localhost:5432/bot_framework_test"
  ```

---

### Issue 4: "max_overflow error with SQLite"

If you see:
```
TypeError: Invalid argument(s) 'max_overflow' sent to create_engine()
```

This means SQLite is being used. Solution:
```bash
# Explicitly set PostgreSQL
export TEST_DATABASE_URL="postgresql+psycopg2://postgres:admin@localhost:5432/bot_framework_test"

# Then run tests
python test/conversation_orchestrator/run_tests.py
```

---

### Issue 5: "Module not found" errors

**Error**:
```
ModuleNotFoundError: No module named 'sqlalchemy'
```

**Solution**:
```bash
# Install all dependencies
pip install -r requirements.txt

# Or install individually
pip install sqlalchemy fastapi uvicorn pydantic psycopg2-binary pytest langfuse
```

---

## 📊 Expected Test Results

### If Everything Works ✅

```
========================= test session starts ==========================
collecting ... collected 123 items

test/conversation_orchestrator/test_models.py::...          [  27%]
test/conversation_orchestrator/test_parser.py::...          [  50%]
test/conversation_orchestrator/test_detector.py::...        [  63%]
test/conversation_orchestrator/test_orchestrator.py::...    [  91%]
test/conversation_orchestrator/test_integration.py::...     [100%]

===================== 123 passed in 35.43s ========================
```

### Current Status (Without PostgreSQL)

```
========================= 62 passed, 61 errors in 35.43s ==============
```

- ✅ 62 tests pass (models + parser)
- ❌ 61 tests error (need PostgreSQL for JSONB columns)

---

## 🎯 Success Criteria

**You've succeeded when**:
- [ ] PostgreSQL is running on localhost:5432
- [ ] Database `bot_framework_test` exists
- [ ] All 123 tests run (no "errors", only "passed" or "failed")
- [ ] Pass rate is >95% (ideally 100%)
- [ ] No database connection errors
- [ ] Test duration is <60 seconds

---

## 📝 Test Execution Checklist

Run through this checklist:

```bash
# 1. Check PostgreSQL
pg_isready -h localhost -p 5432
# Expected: localhost:5432 - accepting connections

# 2. Check database
psql -U postgres -h localhost -l | grep bot_framework_test
# Expected: bot_framework_test row appears

# 3. Test database connection
psql -U postgres -h localhost -d bot_framework_test -c "SELECT version();"
# Expected: PostgreSQL version info

# 4. Set environment (if needed)
export TEST_DATABASE_URL="postgresql+psycopg2://postgres:admin@localhost:5432/bot_framework_test"

# 5. Run quick test (no DB needed)
pytest test/conversation_orchestrator/test_models.py -v
# Expected: 34 passed

# 6. Run full test suite
python test/conversation_orchestrator/run_tests.py
# Expected: 123 passed

# 7. Check test report
cat test/conversation_orchestrator/TEST_REPORT.md
```

---

## 🚀 Quick Start (If PostgreSQL Already Set Up)

```bash
# One-liner to run all tests
cd /path/to/bot_framework && \
export TEST_DATABASE_URL="postgresql+psycopg2://postgres:admin@localhost:5432/bot_framework_test" && \
python test/conversation_orchestrator/run_tests.py
```

---

## 📧 Report Back

After running tests, share:

1. **Test output**: Copy the final summary line
   ```
   ===================== XXX passed, YYY failed in Z.ZZs ========================
   ```

2. **Any errors**: If tests failed, share the error messages

3. **Environment info**:
   ```bash
   python --version
   psql --version
   pip list | grep -E "(sqlalchemy|pytest|fastapi)"
   ```

---

## 🎓 What to Expect

### Best Case Scenario ✅
- All 123 tests pass
- Duration: 30-40 seconds
- No errors or warnings (except 3 Pydantic deprecation warnings - expected)

### Realistic Scenario ⚠️
- 120-123 tests pass (~98-100% pass rate)
- 0-3 tests might fail due to:
  - Timing issues (performance tests)
  - Environment differences
  - Mock configuration

### Worst Case Scenario ❌
- Many tests fail
- Database errors
- Configuration issues

**If worst case happens**: Share the error output and we'll debug together!

---

**Created**: 2025-10-27
**Last Updated**: 2025-10-27
**Status**: Ready for execution
