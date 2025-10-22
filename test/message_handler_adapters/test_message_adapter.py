# ============================================================================
# FILE: test/message_handler_adapters/test_message_adapter.py
# Tests for message_handler/adapters/message_adapter.py (Category D)
# ============================================================================

import pytest
import uuid
from datetime import datetime, timezone

from message_handler.adapters.message_adapter import (
    build_message_adapter,
    validate_adapter,
    sanitize_adapter
)
from message_handler.exceptions import (
    ValidationError,
    ErrorCode
)
from db.models.messages import MessageModel
from db.models.templates import TemplateModel
from db.models.template_sets import TemplateSetModel
from db.models.llm_models import LLMModel
from db.models.instance_configs import InstanceConfigModel


# ============================================================================
# SECTION D1: build_message_adapter Tests
# ============================================================================

class TestBuildMessageAdapter:
    """Test build_message_adapter function."""
    
    def test_missing_session_raises_validation_error(self, db_session, test_user, test_instance):
        """✓ Missing session → ValidationError"""
        # Get existing config from test_instance
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=uuid.uuid4(),  # Fake session
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=None,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "session" in str(exc_info.value).lower()
    
    def test_missing_user_raises_validation_error(self, db_session, test_session, test_instance):
        """✓ Missing user → ValidationError"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_session.user_id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=None,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "user" in str(exc_info.value).lower()
    
    def test_missing_instance_raises_validation_error(self, db_session, test_session, test_user):
        """✓ Missing instance → ValidationError"""
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=uuid.uuid4(),
            content="Test message",
            role="user"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=None,
                instance_config=None,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "instance" in str(exc_info.value).lower()
    
    def test_missing_message_raises_validation_error(self, db_session, test_session, test_user, test_instance):
        """✓ Missing message → ValidationError"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=None,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "message" in str(exc_info.value).lower()
    
    def test_missing_db_raises_validation_error(self, test_session, test_user, test_instance):
        """✓ Missing db → ValidationError"""
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=None,
                message=message,
                db=None
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "db" in str(exc_info.value).lower()
    
    def test_load_routing_plan(self, db_session, test_session, test_user, test_instance):
        """✓ Load routing plan"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        assert "plan_key" in adapter
        assert adapter["plan_key"] is not None
    
    def test_determine_user_type_guest(self, db_session, test_session, test_instance):
        """✓ Determine user_type (guest/verified)"""
        from db.models.users import UserModel
        
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        # Create guest user
        guest_user = UserModel(
            acquisition_channel="api",
            user_tier="guest"
        )
        db_session.add(guest_user)
        db_session.commit()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=guest_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=guest_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        assert adapter["is_guest"] is True
        assert adapter["user_type"] == "guest"
    
    def test_determine_user_type_verified(self, db_session, test_session, test_user, test_instance):
        """✓ Determine user_type (verified)"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        assert adapter["is_guest"] is False
        assert adapter["user_type"] == "verified"
    
    def test_extract_channel_from_metadata(self, db_session, test_session, test_user, test_instance):
        """✓ Extract channel from metadata"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user",
            metadata_json={"channel": "whatsapp"}
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        assert adapter["message"]["channel"] == "whatsapp"
    
    def test_load_template_set_from_instance_config(self, db_session, test_session, test_user, test_instance):
        """✓ Load template_set from instance_config"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        assert adapter["template"] is not None
        assert "id" in adapter["template"]
        assert "json" in adapter["template"]
    
    def test_missing_template_set_raises_validation_error(self, db_session, test_session, test_user, test_instance, test_brand):
        """✓ Missing template_set → ValidationError"""
        # Create config without template_set
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id="nonexistent",
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
    
    def test_empty_functions_raises_validation_error(self, db_session, test_session, test_user, test_instance, test_brand):
        """✓ Empty functions → ValidationError"""
        # Create template_set with empty functions
        empty_template_set = TemplateSetModel(
            id="empty_functions_set",
            name="Empty Functions Set",
            functions={}
        )
        db_session.add(empty_template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id=empty_template_set.id,
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
        assert "functions" in str(exc_info.value).lower()
    
    def test_load_primary_template_response_compose_first(self, db_session, test_session, test_user, test_instance):
        """✓ Load primary template (response > compose > first)"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        # Should have loaded template info
        assert adapter["template"] is not None
        assert adapter["model"] is not None
        assert adapter["llm_runtime"] is not None
    
    def test_template_not_found_raises_validation_error(self, db_session, test_session, test_user, test_instance, test_brand, test_llm_model):
        """✓ Template not found → ValidationError"""
        # Create template_set with non-existent template
        bad_template_set = TemplateSetModel(
            id="bad_template_set",
            name="Bad Template Set",
            functions={"response": "nonexistent_template"}
        )
        db_session.add(bad_template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id=bad_template_set.id,
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
        assert "template" in str(exc_info.value).lower()
    
    def test_missing_llm_model_raises_validation_error(self, db_session, test_session, test_user, test_instance, test_brand):
        """✓ Missing llm_model → ValidationError"""
        # Create template without llm_model
        template_no_model = TemplateModel(
            template_key="no_model_template",
            name="No Model Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=None
        )
        db_session.add(template_no_model)
        db_session.commit()
        
        template_set = TemplateSetModel(
            id="no_model_set",
            name="No Model Set",
            functions={"response": "no_model_template"}
        )
        db_session.add(template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id=template_set.id,
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
        assert "llm_model" in str(exc_info.value).lower()
    
    def test_missing_api_model_name_raises_validation_error(self, db_session, test_session, test_user, test_instance, test_brand):
        """✓ Missing api_model_name → ValidationError"""
        # Create LLM model without api_model_name
        llm_no_api_name = LLMModel(
            name="no-api-name-model",
            provider="openai",
            api_model_name=None,
            max_tokens=8192
        )
        db_session.add(llm_no_api_name)
        db_session.flush()
        
        template = TemplateModel(
            template_key="no_api_name_template",
            name="No API Name Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=llm_no_api_name.id
        )
        db_session.add(template)
        db_session.commit()
        
        template_set = TemplateSetModel(
            id="no_api_name_set",
            name="No API Name Set",
            functions={"response": "no_api_name_template"}
        )
        db_session.add(template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id=template_set.id,
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
        assert "api_model_name" in str(exc_info.value).lower()
    
    def test_missing_provider_raises_validation_error(self, db_session, test_session, test_user, test_instance, test_brand):
        """✓ Missing provider → ValidationError"""
        # Create LLM model without provider
        llm_no_provider = LLMModel(
            name="no-provider-model",
            provider=None,
            api_model_name="gpt-4",
            max_tokens=8192
        )
        db_session.add(llm_no_provider)
        db_session.flush()
        
        template = TemplateModel(
            template_key="no_provider_template",
            name="No Provider Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=llm_no_provider.id
        )
        db_session.add(template)
        db_session.commit()
        
        template_set = TemplateSetModel(
            id="no_provider_set",
            name="No Provider Set",
            functions={"response": "no_provider_template"}
        )
        db_session.add(template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id=template_set.id,
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
        assert "provider" in str(exc_info.value).lower()
    
    @pytest.mark.parametrize("invalid_value", ["", "   ", "\t", "\n"])
    def test_empty_api_model_name_raises_validation_error(
        self, db_session, test_session, test_user, test_instance, test_brand, invalid_value
    ):
        """🔥 CRITICAL: api_model_name="" (empty string) → ValidationError"""
        # Create LLM model with empty api_model_name
        llm_empty_api = LLMModel(
            name=f"empty-api-model-{uuid.uuid4()}",
            provider="openai",
            api_model_name=invalid_value,
            max_tokens=8192
        )
        db_session.add(llm_empty_api)
        db_session.flush()
        
        template = TemplateModel(
            template_key=f"empty_api_template_{uuid.uuid4()}",
            name="Empty API Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=llm_empty_api.id
        )
        db_session.add(template)
        db_session.commit()
        
        template_set = TemplateSetModel(
            id=f"empty_api_set_{uuid.uuid4()}",
            name="Empty API Set",
            functions={"response": template.template_key}
        )
        db_session.add(template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id=template_set.id,
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
        assert "api_model_name" in str(exc_info.value).lower()
    
    @pytest.mark.parametrize("invalid_value", ["", "   ", "\t", "\n"])
    def test_empty_provider_raises_validation_error(
        self, db_session, test_session, test_user, test_instance, test_brand, invalid_value
    ):
        """🔥 CRITICAL: provider="" (empty string) → ValidationError"""
        # Create LLM model with empty provider
        llm_empty_provider = LLMModel(
            name=f"empty-provider-model-{uuid.uuid4()}",
            provider=invalid_value,
            api_model_name="gpt-4",
            max_tokens=8192
        )
        db_session.add(llm_empty_provider)
        db_session.flush()
        
        template = TemplateModel(
            template_key=f"empty_provider_template_{uuid.uuid4()}",
            name="Empty Provider Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=llm_empty_provider.id
        )
        db_session.add(template)
        db_session.commit()
        
        template_set = TemplateSetModel(
            id=f"empty_provider_set_{uuid.uuid4()}",
            name="Empty Provider Set",
            functions={"response": template.template_key}
        )
        db_session.add(template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=test_instance.id,
            template_set_id=template_set.id,
            is_active=False  # Not active to avoid conflict
        )
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            build_message_adapter(
                session=test_session,
                user=test_user,
                instance=test_instance,
                instance_config=config,
                message=message,
                db=db_session
            )
        
        assert exc_info.value.error_code == ErrorCode.INSTANCE_CONFIGURATION_ERROR
        assert "provider" in str(exc_info.value).lower()
    
    def test_extract_session_timestamps_timezone_aware(self, db_session, test_session, test_user, test_instance):
        """✓ Extract session timestamps (timezone-aware)"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        # Ensure session has timestamps
        test_session.created_at = datetime.now(timezone.utc)
        test_session.last_message_at = datetime.now(timezone.utc)
        db_session.commit()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        assert "session_context" in adapter
        assert "started_at" in adapter["session_context"]
        assert "last_message_at" in adapter["session_context"]
        # Should be ISO format strings
        assert adapter["session_context"]["started_at"] is not None
        assert adapter["session_context"]["last_message_at"] is not None
    
    def test_get_initialize_token_plan(self, db_session, test_session, test_user, test_instance):
        """✓ Get/initialize token_plan"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        # Should have token_plan (initialized if not exists)
        assert "token_plan" in adapter
    
    def test_build_adapter_structure_complete(self, db_session, test_session, test_user, test_instance):
        """✓ Build adapter structure"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        # Check all required fields
        assert "session_id" in adapter
        assert "session_context" in adapter
        assert "user_id" in adapter
        assert "is_guest" in adapter
        assert "user_type" in adapter
        assert "message" in adapter
        assert "routing" in adapter
        assert "template" in adapter
        assert "model" in adapter
        assert "llm_runtime" in adapter
        assert "token_plan" in adapter
        assert "plan_key" in adapter
        assert "policy" in adapter
        assert "trace_id" in adapter
        assert "_meta" in adapter
    
    def test_sanitize_adapter_called(self, db_session, test_session, test_user, test_instance):
        """✓ Sanitize adapter"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        # Adapter should not contain any sensitive keys
        adapter_str = str(adapter)
        assert "password" not in adapter_str.lower()
        assert "secret" not in adapter_str.lower()
    
    def test_validate_adapter_called(self, db_session, test_session, test_user, test_instance):
        """✓ Validate adapter"""
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id,
            InstanceConfigModel.is_active == True
        ).first()
        
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            content="Test message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()
        
        # Should not raise any errors
        adapter = build_message_adapter(
            session=test_session,
            user=test_user,
            instance=test_instance,
            instance_config=config,
            message=message,
            db=db_session
        )
        
        assert adapter is not None


# ============================================================================
# SECTION D2: validate_adapter Tests
# ============================================================================

class TestValidateAdapter:
    """Test validate_adapter function."""
    
    def test_missing_required_fields_raises_validation_error(self):
        """✓ Missing required fields → ValidationError"""
        incomplete_adapter = {
            "session_id": "test",
            # Missing user_id, message, routing
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_adapter(incomplete_adapter)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "missing" in str(exc_info.value).lower()
    
    def test_invalid_message_type_raises_validation_error(self):
        """✓ Invalid message type → ValidationError"""
        adapter = {
            "session_id": "test",
            "user_id": "test",
            "message": "not a dict",  # Should be dict
            "routing": {}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_adapter(adapter)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "message" in str(exc_info.value).lower()
    
    def test_missing_message_content_raises_validation_error(self):
        """✓ Missing message.content → ValidationError"""
        adapter = {
            "session_id": "test",
            "user_id": "test",
            "message": {},  # Missing content
            "routing": {"instance_id": "test"}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_adapter(adapter)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "content" in str(exc_info.value).lower()
    
    def test_invalid_routing_type_raises_validation_error(self):
        """✓ Invalid routing type → ValidationError"""
        adapter = {
            "session_id": "test",
            "user_id": "test",
            "message": {"content": "test"},
            "routing": "not a dict"  # Should be dict
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_adapter(adapter)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "routing" in str(exc_info.value).lower()
    
    def test_missing_routing_instance_id_raises_validation_error(self):
        """✓ Missing routing.instance_id → ValidationError"""
        adapter = {
            "session_id": "test",
            "user_id": "test",
            "message": {"content": "test"},
            "routing": {}  # Missing instance_id
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_adapter(adapter)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "instance_id" in str(exc_info.value).lower()
    
    def test_adapter_size_exceeds_1mb_raises_validation_error(self):
        """✓ Adapter size > 1MB → ValidationError"""
        # Create a very large adapter
        large_content = "x" * (1024 * 1024 + 1000)  # > 1MB
        
        adapter = {
            "session_id": "test",
            "user_id": "test",
            "message": {"content": large_content},
            "routing": {"instance_id": "test"}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_adapter(adapter)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_valid_adapter_passes(self):
        """✓ Valid adapter passes"""
        adapter = {
            "session_id": "test",
            "user_id": "test",
            "message": {"content": "test message"},
            "routing": {"instance_id": "test"}
        }
        
        # Should not raise
        validate_adapter(adapter)


# ============================================================================
# SECTION D3: sanitize_adapter Tests
# ============================================================================

class TestSanitizeAdapter:
    """Test sanitize_adapter function."""
    
    def test_remove_sensitive_keys(self):
        """✓ Remove sensitive keys (password, token, secret)"""
        adapter = {
            "session_id": "test",
            "password": "secret123",
            "token": "abc123",
            "secret": "hidden",
            "message": {"content": "test"}
        }
        
        sanitized = sanitize_adapter(adapter)
        
        assert "password" not in sanitized
        assert "token" not in sanitized
        assert "secret" not in sanitized
        assert "session_id" in sanitized
    
    def test_limit_string_length(self):
        """✓ Limit string length (10000)"""
        long_string = "x" * 15000
        
        adapter = {
            "session_id": "test",
            "message": {"content": long_string}
        }
        
        sanitized = sanitize_adapter(adapter)
        
        # String should be truncated
        assert len(sanitized["message"]["content"]) <= 10000
    
    def test_limit_dict_items(self):
        """✓ Limit dict items (100)"""
        large_dict = {f"key_{i}": f"value_{i}" for i in range(150)}
        
        adapter = {
            "session_id": "test",
            "large_dict": large_dict,
            "message": {"content": "test"}
        }
        
        sanitized = sanitize_adapter(adapter)
        
        # Dict should be limited
        assert len(sanitized["large_dict"]) <= 100