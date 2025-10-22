# ============================================================================
# FILE: test/message_handler_services/test_identity_service.py
# Tests for message_handler/services/identity_service.py (Section C1)
# ============================================================================

import pytest
import uuid
from datetime import datetime, timezone

from message_handler.services.identity_service import (
    resolve_user_web_app,
    resolve_user_whatsapp,
    resolve_user_guest,
    get_user_by_identifier,
    update_user_identifiers,
    create_guest_user,
    create_user_with_identifiers
)
from message_handler.exceptions import (
    ValidationError,
    UnauthorizedError,
    DatabaseError,
    ErrorCode
)
from db.models.users import UserModel
from db.models.user_identifiers import UserIdentifierModel


# ============================================================================
# SECTION C1.1: resolve_user_web_app Tests
# ============================================================================

class TestResolveUserWebApp:
    """Test resolve_user_web_app function."""
    
    def test_missing_brand_id_raises_validation_error(self, db_session):
        """✔ Missing brand_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            resolve_user_web_app(
                db_session,
                phone_e164="+1234567890",
                brand_id=None
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "brand" in str(exc_info.value).lower()
    
    def test_valid_phone_e164_resolves_user(self, db_session, test_brand, test_user):
        """✔ Valid phone_e164 → resolve user (highest priority)"""
        # Add phone identifier with DIFFERENT phone than fixture
        phone_id = UserIdentifierModel(
            user_id=test_user.id,
            brand_id=test_brand.id,
            identifier_type="phone_e164",
            identifier_value="+9998887777",  # Use different phone
            channel="api",
            verified=True
        )
        db_session.add(phone_id)
        db_session.commit()
        
        # ✅ FIX: Query with the SAME phone we just created
        user = resolve_user_web_app(
            db_session,
            phone_e164="+9998887777",  # ✅ FIXED: Match the identifier above
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert user is not None
        assert user.id == test_user.id
    
    def test_valid_email_resolves_user(self, db_session, test_brand):
        """✔ Valid email → resolve user (2nd priority)"""
        # Create user with email
        user = create_user_with_identifiers(
            db_session,
            email="test@example.com",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        resolved = resolve_user_web_app(
            db_session,
            email="test@example.com",
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert resolved is not None
        assert resolved.id == user.id
    
    def test_valid_device_id_resolves_user(self, db_session, test_brand):
        """✔ Valid device_id → resolve user (3rd priority)"""
        # Create user with device_id
        user = create_user_with_identifiers(
            db_session,
            device_id="device-123",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        resolved = resolve_user_web_app(
            db_session,
            device_id="device-123",
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert resolved is not None
        assert resolved.id == user.id
    
    def test_valid_auth_token_resolves_user(self, db_session, test_brand):
        """✔ Valid auth_token → resolve user (4th priority)"""
        # Create user with auth_token
        user = create_user_with_identifiers(
            db_session,
            auth_token="token-xyz",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        resolved = resolve_user_web_app(
            db_session,
            auth_token="token-xyz",
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert resolved is not None
        assert resolved.id == user.id
    
    def test_multiple_identifiers_uses_priority_order(self, db_session, test_brand):
        """✔ Multiple identifiers → use priority order"""
        # Create user with phone
        user1 = create_user_with_identifiers(
            db_session,
            phone_e164="+1111111111",
            brand_id=test_brand.id,
            channel="api"
        )
        
        # Create different user with email
        user2 = create_user_with_identifiers(
            db_session,
            email="other@example.com",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        # Provide both phone and email - phone should win (higher priority)
        resolved = resolve_user_web_app(
            db_session,
            phone_e164="+1111111111",
            email="other@example.com",
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert resolved is not None
        assert resolved.id == user1.id  # Phone wins
    
    def test_no_identifiers_accept_guest_creates_guest(self, db_session, test_brand):
        """✔ No identifiers + accept_guest → create guest"""
        user = resolve_user_web_app(
            db_session,
            brand_id=test_brand.id,
            channel="api",
            accept_guest_users=True
        )
        
        assert user is not None
        assert user.user_tier == "guest"
        assert user.acquisition_channel == "api"
    
    def test_no_identifiers_no_accept_guest_returns_none(self, db_session, test_brand):
        """✔ No identifiers + !accept_guest → None"""
        user = resolve_user_web_app(
            db_session,
            brand_id=test_brand.id,
            channel="api",
            accept_guest_users=False
        )
        
        assert user is None
    
    def test_invalid_phone_format_raises_validation_error(self, db_session, test_brand):
        """✔ Invalid phone format → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            resolve_user_web_app(
                db_session,
                phone_e164="1234567890",  # Missing +
                brand_id=test_brand.id,
                channel="api"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_invalid_email_format_raises_validation_error(self, db_session, test_brand):
        """✔ Invalid email format → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            resolve_user_web_app(
                db_session,
                email="not-an-email",
                brand_id=test_brand.id,
                channel="api"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_add_missing_identifiers_to_existing_user(self, db_session, test_brand):
        """✔ Add missing identifiers to existing user"""
        # Create user with phone only
        user = create_user_with_identifiers(
            db_session,
            phone_e164="+2222222222",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        # Resolve with phone + new email
        resolved = resolve_user_web_app(
            db_session,
            phone_e164="+2222222222",
            email="newemail@example.com",
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert resolved.id == user.id
        
        # Check email was added
        email_identifier = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user.id,
            UserIdentifierModel.identifier_type == "email",
            UserIdentifierModel.identifier_value == "newemail@example.com"
        ).first()
        
        assert email_identifier is not None
    
    def test_skip_identifier_if_belongs_to_another_user(self, db_session, test_brand):
        """✔ Skip identifier if belongs to another user"""
        # Create user1 with phone
        user1 = create_user_with_identifiers(
            db_session,
            phone_e164="+3333333333",
            brand_id=test_brand.id,
            channel="api"
        )
        
        # Create user2 with email
        user2 = create_user_with_identifiers(
            db_session,
            email="user2@example.com",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        # Try to add user2's email to user1 - should be skipped
        resolved = resolve_user_web_app(
            db_session,
            phone_e164="+3333333333",
            email="user2@example.com",  # Belongs to user2
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert resolved.id == user1.id
        
        # Verify email was NOT added to user1
        email_for_user1 = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user1.id,
            UserIdentifierModel.identifier_type == "email"
        ).first()
        
        assert email_for_user1 is None


# ============================================================================
# SECTION C1.2: resolve_user_whatsapp Tests
# ============================================================================

class TestResolveUserWhatsapp:
    """Test resolve_user_whatsapp function."""
    
    def test_missing_brand_id_raises_validation_error(self, db_session):
        """✔ Missing brand_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            resolve_user_whatsapp(
                db_session,
                phone_e164="+1234567890",
                brand_id=None
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_missing_phone_raises_validation_error(self, db_session, test_brand):
        """✔ Missing phone → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            resolve_user_whatsapp(
                db_session,
                phone_e164=None,
                brand_id=test_brand.id
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_valid_phone_resolves_user(self, db_session, test_brand):
        """✔ Valid phone → resolve user"""
        # Create WhatsApp user
        user = create_user_with_identifiers(
            db_session,
            phone_e164="+5555555555",
            brand_id=test_brand.id,
            channel="whatsapp"
        )
        db_session.commit()
        
        resolved = resolve_user_whatsapp(
            db_session,
            phone_e164="+5555555555",
            brand_id=test_brand.id
        )
        
        assert resolved is not None
        assert resolved.id == user.id
    
    def test_new_phone_accept_guest_creates_user(self, db_session, test_brand):
        """✔ New phone + accept_guest → create user"""
        user = resolve_user_whatsapp(
            db_session,
            phone_e164="+6666666666",
            brand_id=test_brand.id,
            accept_guest_users=True
        )
        
        assert user is not None
        assert user.user_tier == "verified"  # WhatsApp users are verified
    
    def test_new_phone_no_accept_guest_returns_none(self, db_session, test_brand):
        """✔ New phone + !accept_guest → None"""
        user = resolve_user_whatsapp(
            db_session,
            phone_e164="+7777777777",
            brand_id=test_brand.id,
            accept_guest_users=False
        )
        
        assert user is None
    
    def test_invalid_phone_format_raises_validation_error(self, db_session, test_brand):
        """✔ Invalid phone format → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            resolve_user_whatsapp(
                db_session,
                phone_e164="invalid-phone",
                brand_id=test_brand.id
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR


# ============================================================================
# SECTION C1.3: resolve_user_guest Tests
# ============================================================================

class TestResolveUserGuest:
    """Test resolve_user_guest function."""
    
    def test_always_creates_guest_user(self, db_session):
        """✔ Always creates guest user"""
        user = resolve_user_guest(db_session, channel="web")
        
        assert user is not None
        assert user.user_tier == "guest"
    
    def test_user_tier_is_guest(self, db_session):
        """✔ user_tier = guest"""
        user = resolve_user_guest(db_session)
        
        assert user.user_tier == "guest"
    
    def test_no_identifiers_created(self, db_session):
        """✔ No identifiers"""
        user = resolve_user_guest(db_session)
        
        identifiers = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user.id
        ).all()
        
        assert len(identifiers) == 0


# ============================================================================
# SECTION C1.4: get_user_by_identifier Tests
# ============================================================================

class TestGetUserByIdentifier:
    """Test get_user_by_identifier function."""
    
    def test_valid_identifier_returns_user(self, db_session, test_brand):
        """✔ Valid identifier → return user"""
        user = create_user_with_identifiers(
            db_session,
            phone_e164="+8888888888",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        found = get_user_by_identifier(
            db_session,
            "phone",
            "+8888888888",
            "api",
            test_brand.id
        )
        
        assert found is not None
        assert found.id == user.id
    
    def test_invalid_identifier_returns_none(self, db_session, test_brand):
        """✔ Invalid identifier → None"""
        found = get_user_by_identifier(
            db_session,
            "phone",
            "+9999999999",
            "api",
            test_brand.id
        )
        
        assert found is None
    
    def test_brand_scoped_same_identifier_different_brands_different_users(
        self, db_session, test_brand
    ):
        """✔ Brand-scoped (same identifier, different brands → different users)"""
        # Create second brand
        from db.models.brands import BrandModel
        brand2 = BrandModel(
            name="Brand 2",
            phone_number="+0987654321",
            website="https://brand2.com"
        )
        db_session.add(brand2)
        db_session.commit()
        
        # Create user A in brand 1 with phone
        user_a = create_user_with_identifiers(
            db_session,
            phone_e164="+1111111111",
            brand_id=test_brand.id,
            channel="api"
        )
        
        # Create user B in brand 2 with SAME phone
        user_b = create_user_with_identifiers(
            db_session,
            phone_e164="+1111111111",
            brand_id=brand2.id,
            channel="api"
        )
        db_session.commit()
        
        # Resolve for brand 1
        found_a = get_user_by_identifier(
            db_session,
            "phone",
            "+1111111111",
            "api",
            test_brand.id
        )
        
        # Resolve for brand 2
        found_b = get_user_by_identifier(
            db_session,
            "phone",
            "+1111111111",
            "api",
            brand2.id
        )
        
        assert found_a.id == user_a.id
        assert found_b.id == user_b.id
        assert found_a.id != found_b.id


# ============================================================================
# SECTION C1.5: update_user_identifiers Tests
# ============================================================================

class TestUpdateUserIdentifiers:
    """Test update_user_identifiers function."""
    
    def test_add_new_phone_success(self, db_session, test_brand, test_user):
        """✔ Add new phone → success"""
        result = update_user_identifiers(
            db_session,
            test_user.id,
            test_brand.id,
            "api",
            phone_e164="+2222222222"
        )
        
        assert result is True
        
        phone_id = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == test_user.id,
            UserIdentifierModel.identifier_type == "phone_e164",
            UserIdentifierModel.identifier_value == "+2222222222"
        ).first()
        
        assert phone_id is not None
    
    def test_add_new_email_success(self, db_session, test_brand, test_user):
        """✔ Add new email → success"""
        result = update_user_identifiers(
            db_session,
            test_user.id,
            test_brand.id,
            "api",
            email="new@example.com"
        )
        
        assert result is True
        
        email_id = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == test_user.id,
            UserIdentifierModel.identifier_type == "email",
            UserIdentifierModel.identifier_value=="new@example.com"
        ).first()
        
        assert email_id is not None
    
    def test_add_new_device_id_success(self, db_session, test_brand, test_user):
        """✔ Add new device_id → success"""
        result = update_user_identifiers(
            db_session,
            test_user.id,
            test_brand.id,
            "api",
            device_id="device-999"
        )
        
        assert result is True
        
        device_id_obj = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == test_user.id,
            UserIdentifierModel.identifier_type == "device_id",
            UserIdentifierModel.identifier_value == "device-999"
        ).first()
        
        assert device_id_obj is not None
    
    def test_skip_if_identifier_belongs_to_another_user(self, db_session, test_brand):
        """✔ Skip if identifier belongs to another user"""
        # Create user1 with phone
        user1 = create_user_with_identifiers(
            db_session,
            phone_e164="+3333333333",
            brand_id=test_brand.id,
            channel="api"
        )
        
        # Create user2
        user2 = UserModel(
            acquisition_channel="api",
            user_tier="standard"
        )
        db_session.add(user2)
        db_session.commit()
        
        # Try to add user1's phone to user2 - should be skipped
        result = update_user_identifiers(
            db_session,
            user2.id,
            test_brand.id,
            "api",
            phone_e164="+3333333333"  # Already belongs to user1
        )
        
        # Function returns False or True, but phone should not be added to user2
        phone_for_user2 = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user2.id,
            UserIdentifierModel.identifier_type == "phone_e164"
        ).first()
        
        assert phone_for_user2 is None
    
    def test_skip_if_already_exists_for_this_user(self, db_session, test_brand, test_user):
        """✔ Skip if already exists for this user"""
        # Add phone first time
        update_user_identifiers(
            db_session,
            test_user.id,
            test_brand.id,
            "api",
            phone_e164="+4444444444"
        )
        db_session.commit()
        
        # Try to add same phone again
        result = update_user_identifiers(
            db_session,
            test_user.id,
            test_brand.id,
            "api",
            phone_e164="+4444444444"
        )
        
        # Should return False (no new identifiers added)
        assert result is False


# ============================================================================
# SECTION C1.6: create_guest_user Tests
# ============================================================================

class TestCreateGuestUser:
    """Test create_guest_user function."""
    
    def test_creates_user_with_tier_guest(self, db_session):
        """✔ Creates user with tier=guest"""
        user = create_guest_user(db_session, channel="api")
        
        assert user is not None
        assert user.user_tier == "guest"
    
    def test_no_identifiers_created(self, db_session):
        """✔ No identifiers created"""
        user = create_guest_user(db_session)
        
        identifiers = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user.id
        ).all()
        
        assert len(identifiers) == 0
    
    def test_returns_user(self, db_session):
        """✔ Returns user"""
        user = create_guest_user(db_session)
        
        assert isinstance(user, UserModel)
        assert user.id is not None


# ============================================================================
# SECTION C1.7: create_user_with_identifiers Tests
# ============================================================================

class TestCreateUserWithIdentifiers:
    """Test create_user_with_identifiers function."""
    
    def test_missing_brand_id_raises_validation_error(self, db_session):
        """✔ Missing brand_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            create_user_with_identifiers(
                db_session,
                phone_e164="+1234567890",
                brand_id=None,
                channel="api"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_no_identifiers_raises_validation_error(self, db_session, test_brand):
        """✔ No identifiers → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            create_user_with_identifiers(
                db_session,
                brand_id=test_brand.id,
                channel="api"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_creates_user_and_identifiers(self, db_session, test_brand):
        """✔ Creates user + identifiers"""
        user = create_user_with_identifiers(
            db_session,
            phone_e164="+5555555555",
            email="test@example.com",
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert user is not None
        
        # Check identifiers were created
        identifiers = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user.id
        ).all()
        
        assert len(identifiers) == 2
    
    def test_whatsapp_channel_tier_verified(self, db_session, test_brand):
        """✔ WhatsApp channel → tier=verified"""
        user = create_user_with_identifiers(
            db_session,
            phone_e164="+6666666666",
            brand_id=test_brand.id,
            channel="whatsapp"
        )
        
        assert user.user_tier == "verified"
    
    def test_other_channels_tier_standard(self, db_session, test_brand):
        """✔ Other channels → tier=standard"""
        user = create_user_with_identifiers(
            db_session,
            phone_e164="+7777777777",
            brand_id=test_brand.id,
            channel="api"
        )
        
        assert user.user_tier == "standard"


# ============================================================================
# SECTION C1.8: Brand Scoping Tests
# ============================================================================

class TestBrandScoping:
    """Test brand-scoped identity management."""
    
    def test_same_phone_brand_a_user_a(self, db_session, test_brand):
        """✔ Same phone, Brand A → User A"""
        user_a = create_user_with_identifiers(
            db_session,
            phone_e164="+1111111111",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        found = get_user_by_identifier(
            db_session,
            "phone",
            "+1111111111",
            "api",
            test_brand.id
        )
        
        assert found.id == user_a.id
    
    def test_same_phone_brand_b_user_b(self, db_session, test_brand):
        """✔ Same phone, Brand B → User B"""
        from db.models.brands import BrandModel
        
        brand_b = BrandModel(
            name="Brand B",
            phone_number="+9999999999",
            website="https://brandb.com"
        )
        db_session.add(brand_b)
        db_session.commit()
        
        # Create user in brand A
        user_a = create_user_with_identifiers(
            db_session,
            phone_e164="+2222222222",
            brand_id=test_brand.id,
            channel="api"
        )
        
        # Create user in brand B with SAME phone
        user_b = create_user_with_identifiers(
            db_session,
            phone_e164="+2222222222",
            brand_id=brand_b.id,
            channel="api"
        )
        db_session.commit()
        
        assert user_a.id != user_b.id
    
    def test_unique_constraint_on_identifier_brand_channel(self, db_session, test_brand):
        """✔ Unique constraint on (identifier_type, identifier_value, channel, brand_id)"""
        # Create first user with phone
        user1 = create_user_with_identifiers(
            db_session,
            phone_e164="+3333333333",
            brand_id=test_brand.id,
            channel="api"
        )
        db_session.commit()
        
        # Try to create another identifier with same values - should fail
        from sqlalchemy.exc import IntegrityError
        
        duplicate_id = UserIdentifierModel(
            user_id=uuid.uuid4(),  # Different user
            brand_id=test_brand.id,
            identifier_type="phone_e164",
            identifier_value="+3333333333",
            channel="api",
            verified=True
        )
        db_session.add(duplicate_id)
        
        with pytest.raises(IntegrityError):
            db_session.commit()