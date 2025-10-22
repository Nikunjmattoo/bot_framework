# tests/sync_test_db.py
"""
Sync Test Database by copying Production Database

This script:
1. Drops test database
2. Creates fresh test database
3. Copies entire production database to test

Usage:
    python tests/sync_test_db.py
"""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database credentials
DB_HOST = "localhost"
DB_PORT = "5432"
DB_USER = "postgres"
DB_PASSWORD = "admin"
PROD_DB = "bot_framework"
TEST_DB = "bot_framework_test"

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_step(message):
    print(f"{Colors.BLUE}{Colors.BOLD}➜ {message}{Colors.END}")

def print_success(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def run_command(cmd, env=None):
    """Run a shell command and return success status."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            env=env or os.environ.copy()
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def drop_test_database():
    """Drop and recreate test database."""
    print_step("Dropping test database...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_PASSWORD
    
    # Drop database (ignore error if doesn't exist)
    cmd = f'psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d postgres -c "DROP DATABASE IF EXISTS {TEST_DB};"'
    success, output = run_command(cmd, env)
    
    if success:
        print_success("Test database dropped")
    else:
        print_error(f"Failed to drop: {output}")
        return False
    
    # Create fresh database
    print_step("Creating fresh test database...")
    cmd = f'psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d postgres -c "CREATE DATABASE {TEST_DB};"'
    success, output = run_command(cmd, env)
    
    if success:
        print_success("Test database created")
        return True
    else:
        print_error(f"Failed to create: {output}")
        return False


def copy_production_to_test():
    """Dump production and restore to test database."""
    print_step("Dumping production database...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_PASSWORD
    
    dump_file = Path(__file__).parent / "temp_dump.sql"
    
    # Dump production database
    cmd = f'pg_dump -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d {PROD_DB} -f "{dump_file}"'
    success, output = run_command(cmd, env)
    
    if not success:
        print_error(f"Failed to dump production: {output}")
        return False
    
    print_success(f"Production dumped to {dump_file}")
    
    # Restore to test database
    print_step("Restoring to test database...")
    cmd = f'psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d {TEST_DB} -f "{dump_file}"'
    success, output = run_command(cmd, env)
    
    if not success:
        print_error(f"Failed to restore: {output}")
        return False
    
    print_success("Restored to test database")
    
    # Clean up dump file
    try:
        dump_file.unlink()
        print_success("Cleaned up dump file")
    except:
        pass
    
    return True


def verify_copy():
    """Verify test database has same data as production."""
    print_step("Verifying copy...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_PASSWORD
    
    tables = [
        'brands', 'llm_models', 'template_sets', 'templates',
        'instances', 'instance_configs', 'users', 'user_identifiers',
        'sessions', 'messages'
    ]
    
    all_match = True
    
    for table in tables:
        # Count production
        cmd_prod = f'psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d {PROD_DB} -t -c "SELECT COUNT(*) FROM {table};"'
        success_prod, output_prod = run_command(cmd_prod, env)
        
        # Count test
        cmd_test = f'psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d {TEST_DB} -t -c "SELECT COUNT(*) FROM {table};"'
        success_test, output_test = run_command(cmd_test, env)
        
        if success_prod and success_test:
            count_prod = int(output_prod.strip())
            count_test = int(output_test.strip())
            
            if count_prod == count_test:
                print_success(f"  ✓ {table}: {count_test} rows")
            else:
                print_error(f"  ✗ {table}: MISMATCH (prod={count_prod}, test={count_test})")
                all_match = False
        else:
            print_error(f"  ✗ {table}: Failed to verify")
            all_match = False
    
    return all_match


def main():
    """Main sync process."""
    print()
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}  TEST DATABASE SYNC (COPY FROM PRODUCTION){Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print()
    
    # Step 1: Drop and recreate test database
    if not drop_test_database():
        print_error("Failed to prepare test database")
        sys.exit(1)
    
    # Step 2: Copy production to test
    if not copy_production_to_test():
        print_error("Failed to copy database")
        sys.exit(1)
    
    # Step 3: Verify
    if not verify_copy():
        print_error("Verification failed - data mismatch")
        sys.exit(1)
    
    # Success
    print()
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.GREEN}{Colors.BOLD}✅ TEST DATABASE SYNC COMPLETE{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print()
    print(f"{Colors.BOLD}Production DB:{Colors.END} {PROD_DB}")
    print(f"{Colors.BOLD}Test DB:{Colors.END} {TEST_DB}")
    print()
    print(f"{Colors.BOLD}Ready to run tests:{Colors.END}")
    print(f"  pytest tests/test_a_api_layer/ -v")
    print()


if __name__ == "__main__":
    main()