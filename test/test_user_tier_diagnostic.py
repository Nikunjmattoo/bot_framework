# ============================================================================
# FILE: test/test_user_tier_diagnostic.py
# Diagnostic test to determine where Bug #1 is coming from
# ============================================================================

import pytest
from sqlalchemy import text
from db.models.users import UserModel
from db.models.user_identifiers import UserIdentifierModel
from message_handler.services.identity_service import (
    create_user_with_identifiers,
    resolve_user_web_app,
    resolve_user_whatsapp,
    create_guest_user
)


class TestUserTierDiagnostic:
    """Diagnostic tests to identify user_tier bug location."""
    
    def test_01_database_column_default(self, db_session):
        """Check if database has a default value for user_tier column."""
        print("\n" + "="*70)
        print("TEST 1: Database Column Default Check")
        print("="*70)
        
        # Query database metadata for user_tier column
        query = text("""
            SELECT column_name, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'users' 
            AND column_name = 'user_tier'
        """)
        
        result = db_session.execute(query).fetchone()
        
        if result:
            col_name, col_default, is_nullable = result
            print(f"\nColumn: {col_name}")
            print(f"Default: {col_default}")
            print(f"Nullable: {is_nullable}")
            
            if col_default and 'guest' in str(col_default).lower():
                print("\n⚠️  FOUND THE BUG!")
                print(f"   Database has default: {col_default}")
                print("   This overrides Python code!")
                assert False, f"Database has user_tier default: {col_default} - Remove this default!"
            else:
                print("\n✅ Database column has no default (correct)")
        else:
            print("\n❌ Could not query column metadata")
    
    def test_02_sqlalchemy_model_default(self, db_session):
        """Check if SQLAlchemy model has a Python-level default."""
        print("\n" + "="*70)
        print("TEST 2: SQLAlchemy Model Default Check")
        print("="*70)
        
        # Check column definition
        user_tier_col = UserModel.__table__.columns['user_tier']
        
        print(f"\nColumn: {user_tier_col.name}")
        print(f"Type: {user_tier_col.type}")
        print(f"Nullable: {user_tier_col.nullable}")
        print(f"Default: {user_tier_col.default}")
        print(f"Server Default: {user_tier_col.server_default}")
        
        if user_tier_col.default is not None:
            print(f"\n⚠️  SQLAlchemy has default: {user_tier_col.default}")
            print("   This should be None!")
            assert False, f"SQLAlchemy model has user_tier default: {user_tier_col.default}"
        else:
            print("\n✅ SQLAlchemy model has no default (correct)")
    
    def test_03_direct_model_creation(self, db_session):
        """Test creating user directly with UserModel."""
        print("\n" + "="*70)
        print("TEST 3: Direct UserModel Creation")
        print("="*70)
        
        # Create user without specifying user_tier
        user_without_tier = UserModel(
            acquisition_channel="test"
        )
        db_session.add(user_without_tier)
        db_session.flush()
        db_session.refresh(user_without_tier)
        
        print(f"\nUser created WITHOUT user_tier:")
        print(f"  user_tier value: {user_without_tier.user_tier}")
        
        if user_without_tier.user_tier == "guest":
            print("\n⚠️  FOUND THE BUG!")
            print("   User gets 'guest' when user_tier not specified")
            print("   Either database default or model default is set")
        elif user_without_tier.user_tier is None:
            print("\n✅ User gets NULL when user_tier not specified (correct)")
        
        # Create user WITH user_tier
        user_with_tier = UserModel(
            acquisition_channel="test",
            user_tier="standard"
        )
        db_session.add(user_with_tier)
        db_session.flush()
        db_session.refresh(user_with_tier)
        
        print(f"\nUser created WITH user_tier='standard':")
        print(f"  user_tier value: {user_with_tier.user_tier}")
        
        assert user_with_tier.user_tier == "standard", \
            f"Expected 'standard' but got '{user_with_tier.user_tier}'"
        
        print("\n✅ Explicit user_tier works correctly")
    
    def test_04_create_user_with_identifiers_api_channel(self, db_session, test_brand):
        """Test create_user_with_identifiers with API channel."""
        print("\n" + "="*70)
        print("TEST 4: create_user_with_identifiers (API channel)")
        print("="*70)
        
        user = create_user_with_identifiers(
            db=db_session,
            phone_e164="+15551234567",
            channel="api",
            brand_id=test_brand.id
        )
        
        print(f"\nUser created via create_user_with_identifiers:")
        print(f"  user_id: {user.id}")
        print(f"  channel: {user.acquisition_channel}")
        print(f"  user_tier: {user.user_tier}")
        print(f"  expected: 'standard'")
        
        if user.user_tier != "standard":
            print(f"\n❌ BUG CONFIRMED!")
            print(f"   Expected: 'standard'")
            print(f"   Got: '{user.user_tier}'")
            print(f"\n   This means identity_service.py is not setting user_tier correctly")
            print(f"   OR database default is overriding it")
            assert False, f"Expected user_tier='standard', got '{user.user_tier}'"
        
        print("\n✅ API channel user gets 'standard' tier (correct)")
    
    def test_05_create_user_with_identifiers_whatsapp_channel(self, db_session, test_brand):
        """Test create_user_with_identifiers with WhatsApp channel."""
        print("\n" + "="*70)
        print("TEST 5: create_user_with_identifiers (WhatsApp channel)")
        print("="*70)
        
        user = create_user_with_identifiers(
            db=db_session,
            phone_e164="+15559876543",
            channel="whatsapp",
            brand_id=test_brand.id
        )
        
        print(f"\nUser created via create_user_with_identifiers:")
        print(f"  user_id: {user.id}")
        print(f"  channel: {user.acquisition_channel}")
        print(f"  user_tier: {user.user_tier}")
        print(f"  expected: 'verified'")
        
        if user.user_tier != "verified":
            print(f"\n❌ BUG CONFIRMED!")
            print(f"   Expected: 'verified'")
            print(f"   Got: '{user.user_tier}'")
            assert False, f"Expected user_tier='verified', got '{user.user_tier}'"
        
        print("\n✅ WhatsApp channel user gets 'verified' tier (correct)")
    
    def test_06_create_guest_user(self, db_session):
        """Test create_guest_user function."""
        print("\n" + "="*70)
        print("TEST 6: create_guest_user")
        print("="*70)
        
        user = create_guest_user(db=db_session, channel="web")
        
        print(f"\nGuest user created:")
        print(f"  user_id: {user.id}")
        print(f"  channel: {user.acquisition_channel}")
        print(f"  user_tier: {user.user_tier}")
        print(f"  expected: 'guest'")
        
        assert user.user_tier == "guest", \
            f"Expected user_tier='guest', got '{user.user_tier}'"
        
        print("\n✅ Guest user gets 'guest' tier (correct)")
    
    def test_07_resolve_user_web_app_new_user(self, db_session, test_brand, test_instance):
        """Test resolve_user_web_app creating a new user."""
        print("\n" + "="*70)
        print("TEST 7: resolve_user_web_app (new user)")
        print("="*70)
        
        user = resolve_user_web_app(
            db=db_session,
            phone_e164="+15551112222",
            brand_id=test_brand.id,
            channel="api",
            accept_guest_users=True
        )
        
        print(f"\nUser resolved/created via resolve_user_web_app:")
        print(f"  user_id: {user.id}")
        print(f"  channel: {user.acquisition_channel}")
        print(f"  user_tier: {user.user_tier}")
        print(f"  expected: 'standard'")
        
        if user.user_tier != "standard":
            print(f"\n❌ BUG CONFIRMED in resolve_user_web_app!")
            print(f"   Expected: 'standard'")
            print(f"   Got: '{user.user_tier}'")
            assert False, f"Expected user_tier='standard', got '{user.user_tier}'"
        
        print("\n✅ resolve_user_web_app creates 'standard' tier user (correct)")
    
    def test_08_resolve_user_whatsapp_new_user(self, db_session, test_brand):
        """Test resolve_user_whatsapp creating a new user."""
        print("\n" + "="*70)
        print("TEST 8: resolve_user_whatsapp (new user)")
        print("="*70)
        
        user = resolve_user_whatsapp(
            db=db_session,
            phone_e164="+15553334444",
            brand_id=test_brand.id,
            accept_guest_users=True
        )
        
        print(f"\nUser resolved/created via resolve_user_whatsapp:")
        print(f"  user_id: {user.id}")
        print(f"  channel: {user.acquisition_channel}")
        print(f"  user_tier: {user.user_tier}")
        print(f"  expected: 'verified'")
        
        if user.user_tier != "verified":
            print(f"\n❌ BUG CONFIRMED in resolve_user_whatsapp!")
            print(f"   Expected: 'verified'")
            print(f"   Got: '{user.user_tier}'")
            assert False, f"Expected user_tier='verified', got '{user.user_tier}'"
        
        print("\n✅ resolve_user_whatsapp creates 'verified' tier user (correct)")
    
    def test_09_fixture_user_tier(self, test_user):
        """Test the test_user fixture from conftest.py."""
        print("\n" + "="*70)
        print("TEST 9: test_user Fixture")
        print("="*70)
        
        print(f"\ntest_user fixture:")
        print(f"  user_id: {test_user.id}")
        print(f"  channel: {test_user.acquisition_channel}")
        print(f"  user_tier: {test_user.user_tier}")
        print(f"  expected: 'standard'")
        
        assert test_user.user_tier == "standard", \
            f"Fixture should create user with tier='standard', got '{test_user.user_tier}'"
        
        print("\n✅ test_user fixture creates 'standard' tier user (correct)")
    
    def test_10_check_identity_service_code(self):
        """Verify identity_service.py has the correct code."""
        print("\n" + "="*70)
        print("TEST 10: Code Inspection")
        print("="*70)
        
        import inspect
        source = inspect.getsource(create_user_with_identifiers)
        
        print("\nChecking create_user_with_identifiers source code...")
        
        # Check if user_tier is calculated
        has_calculation = "user_tier = " in source and '"verified"' in source
        print(f"  Has user_tier calculation: {has_calculation}")
        
        # Check if user_tier is passed to UserModel
        has_parameter = "user_tier=user_tier" in source
        print(f"  Passes user_tier to UserModel: {has_parameter}")
        
        if not has_calculation:
            print("\n❌ BUG: user_tier is not being calculated!")
            assert False, "user_tier calculation missing in create_user_with_identifiers"
        
        if not has_parameter:
            print("\n❌ BUG FOUND: user_tier is calculated but NOT passed to UserModel constructor!")
            print("\n   FIX: Add 'user_tier=user_tier' to UserModel() in identity_service.py")
            assert False, "user_tier parameter missing in UserModel constructor"
        
        print("\n✅ Code looks correct - user_tier is calculated and passed")


def test_summary_report(db_session, test_brand):
    """Run all tests and provide summary."""
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)
    
    print("\nThis diagnostic will identify where Bug #1 is coming from.")
    print("Run: pytest test/test_user_tier_diagnostic.py -v -s")
    print("\nThe failing test will show you exactly where the bug is:")
    print("  - Test 1 fails → Database default is set")
    print("  - Test 2 fails → SQLAlchemy model has default")
    print("  - Test 3 fails → Database or model issue")
    print("  - Test 4-8 fail → identity_service.py not setting user_tier")
    print("  - Test 10 fails → Code is missing user_tier parameter")
    print("="*70)


# ============================================================================
# HOW TO RUN THIS TEST
# ============================================================================
"""
Run with verbose output to see diagnostic information:

    pytest test/test_user_tier_diagnostic.py -v -s

The -s flag shows print statements so you can see the diagnostic output.

Expected output if everything is working:
    ✅ All tests pass
    ✅ user_tier is set correctly in all scenarios

If Bug #1 exists, one of these tests will fail and show you:
    ❌ Where the bug is (database, model, or code)
    ❌ What the actual value is vs expected
    ❌ How to fix it
"""