# ============================================================================
# FILE: test/message_handler_services/test_user_context_service.py
# Tests for message_handler/services/user_context_service.py (Section C5)
# ============================================================================

import pytest
import uuid

from message_handler.services.user_context_service import (
    prepare_user_context,
    prepare_whatsapp_user_context
)
from message_handler.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    UnauthorizedError,
    ErrorCode
)


# ============================================================================
# SECTION C5.1: prepare_user_context Tests
# ============================================================================

class TestPrepareUserContext:
    """Test prepare_user_context function."""
    
    def test_instance_not_found_raises_resource_not_found_error(self, db_session):
        """✓ Instance not found → ResourceNotFoundError"""
        fake_id = str(uuid.uuid4())
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            prepare_user_context(
                db_session,
                instance_id=fake_id
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "instance" in str(exc_info.value).lower()
    
    def test_config_not_found_raises_resource_not_found_error(
        self, db_session, test_brand
    ):
        """✓ Config not found → ResourceNotFoundError"""
        # Create instance without config
        from db.models.instances import InstanceModel
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="No Config",
            channel="api",
            is_active=True
        )
        db_session.add(instance)
        db_session.commit()
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            prepare_user_context(
                db_session,
                instance_id=str(instance.id)
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "config" in str(exc_info.value).lower()
    
    def test_missing_brand_id_raises_resource_not_found_error(
        self, db_session, test_template_set, test_brand
    ):
        """✓ Missing brand_id → ResourceNotFoundError"""
        # We can't actually create instance with brand_id=None due to DB constraint
        # So test the service behavior when brand lookup fails
        from db.models.instances import InstanceModel
        from db.models.instance_configs import InstanceConfigModel
        
        # Create instance with valid brand but then test brand resolution failure
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="Test Instance",
            channel="api",
            is_active=True
        )
        db_session.add(instance)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=instance.id,
            template_set_id=test_template_set.id,
            is_active=True
        )
        db_session.add(config)
        db_session.commit()
        
        # Delete the brand to simulate missing brand_id
        db_session.delete(test_brand)
        db_session.commit()
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            prepare_user_context(
                db_session,
                instance_id=str(instance.id)
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
    
    def test_resolve_user_via_identifiers(self, db_session, test_instance, test_brand):
        """✓ Resolve user via identifiers"""
        user_details = {
            "phone_e164": "+1234567890",
            "brand_id": test_brand.id
        }
        
        # First call creates user
        user = prepare_user_context(
            db_session,
            instance_id=str(test_instance.id),
            user_details=user_details,
            channel="api"
        )
        
        assert user is not None
        
        # Verify phone identifier was created
        from db.models.user_identifiers import UserIdentifierModel
        identifier = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user.id,
            UserIdentifierModel.identifier_type == "phone_e164"
        ).first()
        
        assert identifier is not None
    
    def test_create_guest_if_no_identifiers_and_accept_guest(
        self, db_session, test_instance
    ):
        """✓ Create guest if no identifiers + accept_guest"""
        # No user_details provided, instance accepts guests
        user = prepare_user_context(
            db_session,
            instance_id=str(test_instance.id),
            user_details=None,
            channel="api"
        )
        
        assert user is not None
        assert user.user_tier == "guest"
    
    def test_fail_if_no_identifiers_and_no_accept_guest_raises_unauthorized_error(
        self, db_session, test_instance_no_guest
    ):
        """✓ Fail if no identifiers + !accept_guest → UnauthorizedError"""
        with pytest.raises(UnauthorizedError) as exc_info:
            prepare_user_context(
                db_session,
                instance_id=str(test_instance_no_guest.id),
                user_details=None,
                channel="api"
            )
        
        assert exc_info.value.error_code == ErrorCode.UNAUTHORIZED
    
    def test_get_or_create_session(self, db_session, test_instance, test_brand):
        """✓ Get/create session"""
        user_details = {
            "phone_e164": "+9999999999"
        }
        
        user = prepare_user_context(
            db_session,
            instance_id=str(test_instance.id),
            user_details=user_details,
            channel="api"
        )
        
        # Should have session attached
        assert hasattr(user, 'session')
        assert user.session is not None
        assert hasattr(user, 'session_id')
        assert user.session_id is not None
    
    def test_attach_session_instance_config_to_user(
        self, db_session, test_instance, test_brand
    ):
        """✓ Attach session, instance, config to user"""
        user_details = {
            "phone_e164": "+8888888888"
        }
        
        user = prepare_user_context(
            db_session,
            instance_id=str(test_instance.id),
            user_details=user_details,
            channel="api"
        )
        
        # Verify all attachments
        assert hasattr(user, 'session')
        assert user.session is not None
        assert hasattr(user, 'session_id')
        assert user.session_id is not None
        assert hasattr(user, 'instance')
        assert user.instance is not None
        assert hasattr(user, 'instance_config')
        assert user.instance_config is not None


# ============================================================================
# SECTION C5.2: prepare_whatsapp_user_context Tests
# ============================================================================

class TestPrepareWhatsappUserContext:
    """Test prepare_whatsapp_user_context function."""
    
    def test_missing_from_raises_validation_error(self, db_session):
        """✓ Missing 'from' → ValidationError"""
        whatsapp_data = {
            "to": "+9876543210"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            prepare_whatsapp_user_context(
                db_session,
                whatsapp_data=whatsapp_data
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "from" in str(exc_info.value).lower()
    
    def test_missing_to_raises_validation_error(self, db_session):
        """✓ Missing 'to' → ValidationError"""
        whatsapp_data = {
            "from": "+1234567890"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            prepare_whatsapp_user_context(
                db_session,
                whatsapp_data=whatsapp_data
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "to" in str(exc_info.value).lower()
    
    def test_resolve_instance_by_recipient_number(
        self, db_session, test_whatsapp_instance
    ):
        """✓ Resolve instance by recipient_number"""
        whatsapp_data = {
            "from": "+1234567890",
            "to": test_whatsapp_instance.recipient_number
        }
        
        user = prepare_whatsapp_user_context(
            db_session,
            whatsapp_data=whatsapp_data
        )
        
        assert user is not None
        assert user.instance.id == test_whatsapp_instance.id
    
    def test_resolve_instance_by_instance_id(
        self, db_session, test_whatsapp_instance
    ):
        """✓ Resolve instance by instance_id"""
        whatsapp_data = {
            "from": "+1234567890",
            "to": "+9876543210"
        }
        
        user = prepare_whatsapp_user_context(
            db_session,
            whatsapp_data=whatsapp_data,
            instance_id=str(test_whatsapp_instance.id)
        )
        
        assert user is not None
        assert user.instance.id == test_whatsapp_instance.id
    
    def test_config_not_found_raises_resource_not_found_error(
        self, db_session, test_brand
    ):
        """✓ Config not found → ResourceNotFoundError"""
        # Create WhatsApp instance without config
        from db.models.instances import InstanceModel
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="WhatsApp No Config",
            channel="whatsapp",
            recipient_number="+5555555555",
            is_active=True
        )
        db_session.add(instance)
        db_session.commit()
        
        whatsapp_data = {
            "from": "+1234567890",
            "to": "+5555555555"
        }
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            prepare_whatsapp_user_context(
                db_session,
                whatsapp_data=whatsapp_data
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "config" in str(exc_info.value).lower()
    
    def test_missing_brand_id_raises_resource_not_found_error(
        self, db_session, test_template_set, test_brand
    ):
        """✓ Missing brand_id → ResourceNotFoundError"""
        # We can't create instance with brand_id=None due to DB constraint
        # So test the service behavior when brand lookup fails
        from db.models.instances import InstanceModel
        from db.models.instance_configs import InstanceConfigModel
        
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="WhatsApp Test",
            channel="whatsapp",
            recipient_number="+6666666666",
            is_active=True
        )
        db_session.add(instance)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=instance.id,
            template_set_id=test_template_set.id,
            is_active=True
        )
        db_session.add(config)
        db_session.commit()
        
        # Delete the brand to simulate missing brand_id scenario
        db_session.delete(test_brand)
        db_session.commit()
        
        whatsapp_data = {
            "from": "+1234567890",
            "to": "+6666666666"
        }
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            prepare_whatsapp_user_context(
                db_session,
                whatsapp_data=whatsapp_data
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
    
    def test_resolve_whatsapp_user(self, db_session, test_whatsapp_instance):
        """✓ Resolve WhatsApp user"""
        whatsapp_data = {
            "from": "+7777777777",
            "to": test_whatsapp_instance.recipient_number
        }
        
        user = prepare_whatsapp_user_context(
            db_session,
            whatsapp_data=whatsapp_data
        )
        
        assert user is not None
        assert user.user_tier == "verified"  # WhatsApp users are verified
    
    def test_get_or_create_session(self, db_session, test_whatsapp_instance):
        """✓ Get/create session"""
        whatsapp_data = {
            "from": "+8888888888",
            "to": test_whatsapp_instance.recipient_number
        }
        
        user = prepare_whatsapp_user_context(
            db_session,
            whatsapp_data=whatsapp_data
        )
        
        assert hasattr(user, 'session')
        assert user.session is not None
        assert hasattr(user, 'session_id')
        assert user.session_id is not None
    
    def test_attach_session_instance_config_to_user(
        self, db_session, test_whatsapp_instance
    ):
        """✓ Attach session, instance, config to user"""
        whatsapp_data = {
            "from": "+9999999999",
            "to": test_whatsapp_instance.recipient_number
        }
        
        user = prepare_whatsapp_user_context(
            db_session,
            whatsapp_data=whatsapp_data
        )
        
        # Verify all attachments
        assert hasattr(user, 'session')
        assert user.session is not None
        assert hasattr(user, 'session_id')
        assert user.session_id is not None
        assert hasattr(user, 'instance')
        assert user.instance is not None
        assert user.instance_config is not None