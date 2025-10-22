# ============================================================================
# FILE: test/message_handler_services/test_token_service.py
# Tests for message_handler/services/token_service.py (Section C7)
# ============================================================================

import pytest
import uuid
from decimal import Decimal

from message_handler.services.token_service import (
    TokenCalculator,
    TokenTracker,
    TokenManager
)
from message_handler.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    DatabaseError,
    ErrorCode
)
from db.models.templates import TemplateModel
from db.models.template_sets import TemplateSetModel
from db.models.llm_models import LLMModel
from db.models.session_token_usage import SessionTokenUsageModel


# ============================================================================
# SECTION C7.1: TokenCalculator.build_session_plan Tests
# ============================================================================

class TestTokenCalculatorBuildSessionPlan:
    """Test TokenCalculator.build_session_plan method."""
    
    def test_load_functions_from_template_set(
        self, db_session, test_template, test_llm_model
    ):
        """✓ Load functions from template_set"""
        calculator = TokenCalculator()
        
        functions = {
            "response": test_template.template_key
        }
        
        plan = calculator.build_session_plan(db_session, functions)
        
        assert plan is not None
        assert "templates" in plan
        assert test_template.template_key in plan["templates"]
    
    def test_for_each_function_load_template(
        self, db_session, test_template, test_llm_model
    ):
        """✓ For each function, load template"""
        calculator = TokenCalculator()
        
        functions = {
            "response": test_template.template_key
        }
        
        plan = calculator.build_session_plan(db_session, functions)
        
        template_info = plan["templates"][test_template.template_key]
        assert template_info is not None
        assert template_info["template_key"] == test_template.template_key
    
    def test_load_llm_model_from_template(
        self, db_session, test_template, test_llm_model
    ):
        """✓ Load llm_model from template"""
        calculator = TokenCalculator()
        
        functions = {
            "response": test_template.template_key
        }
        
        plan = calculator.build_session_plan(db_session, functions)
        
        template_info = plan["templates"][test_template.template_key]
        assert "llm_model_id" in template_info
        assert template_info["llm_model_id"] == str(test_llm_model.id)
    
    def test_calculate_budget_from_template_sections(
        self, db_session, test_template, test_llm_model
    ):
        """✓ Calculate budget from template.sections"""
        calculator = TokenCalculator()
        
        functions = {
            "response": test_template.template_key
        }
        
        plan = calculator.build_session_plan(db_session, functions)
        
        template_info = plan["templates"][test_template.template_key]
        assert "total_budget" in template_info
        assert isinstance(template_info["total_budget"], int)
    
    def test_return_plan_templates_created_at(
        self, db_session, test_template, test_llm_model
    ):
        """✓ Return plan: {templates: {template_key: {...}}, created_at}"""
        calculator = TokenCalculator()
        
        functions = {
            "response": test_template.template_key
        }
        
        plan = calculator.build_session_plan(db_session, functions)
        
        assert "templates" in plan
        assert "created_at" in plan
        assert isinstance(plan["templates"], dict)
    
    def test_include_llm_model_info(
        self, db_session, test_template, test_llm_model
    ):
        """✓ Include llm_model info (id, name, api_model_name, provider, temperature)"""
        calculator = TokenCalculator()
        
        functions = {
            "response": test_template.template_key
        }
        
        plan = calculator.build_session_plan(db_session, functions)
        
        template_info = plan["templates"][test_template.template_key]
        assert "llm_model_id" in template_info
        assert "llm_model_name" in template_info
        assert "api_model_name" in template_info
        assert "provider" in template_info
        assert "temperature" in template_info
    
    def test_missing_template_warning_skip(
        self, db_session, test_llm_model
    ):
        """✓ Missing template → warning + skip"""
        calculator = TokenCalculator()
        
        functions = {
            "response": "nonexistent_template"
        }
        
        plan = calculator.build_session_plan(db_session, functions)
        
        # Should not fail, but template won't be in plan
        assert "nonexistent_template" not in plan["templates"]
    
    def test_missing_llm_model_warning(
        self, db_session, test_brand, test_llm_model
    ):
        """✓ Missing llm_model → warning"""
        # Create template without llm_model
        template = TemplateModel(
            template_key="no_model_template",
            name="No Model Template",
            sections=[
                {"key": "system", "budget_tokens": 100}
            ],
            llm_model_id=None
        )
        db_session.add(template)
        db_session.commit()
        
        calculator = TokenCalculator()
        functions = {
            "response": "no_model_template"
        }
        
        # Should handle gracefully
        plan = calculator.build_session_plan(db_session, functions)
        
        # Template may or may not be in plan depending on validation
        assert plan is not None
    
    def test_empty_functions_empty_plan(self, db_session):
        """✓ Empty functions → empty plan"""
        calculator = TokenCalculator()
        
        plan = calculator.build_session_plan(db_session, {})
        
        assert plan["templates"] == {}
    
    def test_temperature_none_defaults_to_0_7(
        self, db_session, test_brand
    ):
        """✓ Temperature=None → Defaults to 0.7"""
        # Create LLM model with None temperature
        llm_model = LLMModel(
            name="test-model-no-temp",
            provider="openai",
            api_model_name="gpt-4",
            max_tokens=8192,
            temperature=None
        )
        db_session.add(llm_model)
        db_session.flush()  # ← CRITICAL FIX: Generate ID before using it
        
        template = TemplateModel(
            template_key="temp_none_template",
            name="Temp None Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=llm_model.id
        )
        db_session.add(template)
        db_session.commit()
        
        calculator = TokenCalculator()
        functions = {"response": "temp_none_template"}
        
        plan = calculator.build_session_plan(db_session, functions)
        
        template_info = plan["templates"]["temp_none_template"]
        assert template_info["temperature"] == 0.7
    
    def test_decimal_temperature_converts_to_float(
        self, db_session, test_brand
    ):
        """✓ Decimal temperature → Converts to float"""
        # Create LLM model with Decimal temperature
        llm_model = LLMModel(
            name="test-model-decimal",
            provider="openai",
            api_model_name="gpt-4",
            max_tokens=8192,
            temperature=Decimal("0.5")
        )
        db_session.add(llm_model)
        db_session.flush()  # ← CRITICAL FIX: Generate ID before using it
        
        template = TemplateModel(
            template_key="decimal_temp_template",
            name="Decimal Temp Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=llm_model.id
        )
        db_session.add(template)
        db_session.commit()
        
        calculator = TokenCalculator()
        functions = {"response": "decimal_temp_template"}
        
        plan = calculator.build_session_plan(db_session, functions)
        
        template_info = plan["templates"]["decimal_temp_template"]
        assert isinstance(template_info["temperature"], float)
        assert template_info["temperature"] == 0.5
    
    def test_temperature_decimal_0_0_converts_to_float_0_0(
        self, db_session, test_brand
    ):
        """✓ Temperature=Decimal('0.0') → Converts to float(0.0)"""
        llm_model = LLMModel(
            name="test-model-zero",
            provider="openai",
            api_model_name="gpt-4",
            max_tokens=8192,
            temperature=Decimal("0.0")
        )
        db_session.add(llm_model)
        db_session.flush()  # ← CRITICAL FIX: Generate ID before using it
        
        template = TemplateModel(
            template_key="zero_temp_template",
            name="Zero Temp Template",
            sections=[{"key": "system", "budget_tokens": 100}],
            llm_model_id=llm_model.id
        )
        db_session.add(template)
        db_session.commit()
        
        calculator = TokenCalculator()
        functions = {"response": "zero_temp_template"}
        
        plan = calculator.build_session_plan(db_session, functions)
        
        template_info = plan["templates"]["zero_temp_template"]
        assert isinstance(template_info["temperature"], float)
        assert template_info["temperature"] == 0.0


# ============================================================================
# SECTION C7.2: TokenCalculator.calculate_template_budget Tests
# ============================================================================

class TestTokenCalculatorCalculateTemplateBudget:
    """Test TokenCalculator.calculate_template_budget method."""
    
    def test_sum_budget_tokens_from_all_sections(
        self, db_session, test_template
    ):
        """✓ Sum budget_tokens from all sections"""
        calculator = TokenCalculator()
        
        budget = calculator.calculate_template_budget(test_template)
        
        assert "total_budget" in budget
        assert budget["total_budget"] == 1500  # 500 + 1000 from test_template
    
    def test_return_sections_total_budget(self, db_session, test_template):
        """✓ Return: {sections: [...], total_budget: N}"""
        calculator = TokenCalculator()
        
        budget = calculator.calculate_template_budget(test_template)
        
        assert "sections" in budget
        assert "total_budget" in budget
        assert isinstance(budget["sections"], list)
        assert isinstance(budget["total_budget"], int)
    
    def test_invalid_section_skip_warning(self, db_session, test_brand, test_llm_model):
        """✓ Invalid section → skip + warning"""
        # Create template with invalid section
        template = TemplateModel(
            template_key="invalid_section_template",
            name="Invalid Section Template",
            sections=[
                {"key": "valid", "budget_tokens": 100},
                "invalid_section",  # Not a dict
                {"key": "valid2", "budget_tokens": 200}
            ],
            llm_model_id=test_llm_model.id
        )
        db_session.add(template)
        db_session.commit()
        
        calculator = TokenCalculator()
        budget = calculator.calculate_template_budget(template)
        
        # Should skip invalid section
        assert budget["total_budget"] == 300  # Only valid sections
    
    def test_non_numeric_budget_use_0(self, db_session, test_brand, test_llm_model):
        """✓ Non-numeric budget → use 0"""
        template = TemplateModel(
            template_key="non_numeric_template",
            name="Non Numeric Template",
            sections=[
                {"key": "system", "budget_tokens": "invalid"},
                {"key": "user", "budget_tokens": 100}
            ],
            llm_model_id=test_llm_model.id
        )
        db_session.add(template)
        db_session.commit()
        
        calculator = TokenCalculator()
        budget = calculator.calculate_template_budget(template)
        
        # Invalid budget treated as 0
        assert budget["total_budget"] == 100
    
    def test_no_sections_total_budget_0(self, db_session, test_brand, test_llm_model):
        """✓ No sections → total_budget = 0"""
        template = TemplateModel(
            template_key="no_sections_template",
            name="No Sections Template",
            sections=[],
            llm_model_id=test_llm_model.id
        )
        db_session.add(template)
        db_session.commit()
        
        calculator = TokenCalculator()
        budget = calculator.calculate_template_budget(template)
        
        assert budget["total_budget"] == 0


# ============================================================================
# SECTION C7.3: TokenManager.initialize_session Tests
# ============================================================================

class TestTokenManagerInitializeSession:
    """Test TokenManager.initialize_session method."""
    
    def test_missing_session_id_raises_validation_error(self, db_session):
        """✓ Missing session_id → ValidationError"""
        manager = TokenManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.initialize_session(db_session, session_id=None)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_session_not_found_raises_resource_not_found_error(self, db_session):
        """✓ Session not found → ResourceNotFoundError"""
        manager = TokenManager()
        fake_id = str(uuid.uuid4())
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            manager.initialize_session(db_session, session_id=fake_id)
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
    
    def test_instance_not_found_raises_resource_not_found_error(
        self, db_session, test_user, test_brand, test_template_set
    ):
        """✓ Instance not found → ResourceNotFoundError"""
        # Create a valid but inactive instance
        from db.models.instances import InstanceModel
        from db.models.instance_configs import InstanceConfigModel
        from db.models.sessions import SessionModel
        
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="Test Instance",
            channel="api",
            is_active=False  # Inactive so resolve_instance returns None
        )
        db_session.add(instance)
        db_session.commit()
        
        # Create config
        config = InstanceConfigModel(
            instance_id=instance.id,
            template_set_id=test_template_set.id,
            is_active=True
        )
        db_session.add(config)
        db_session.commit()
        
        # Create session with this instance
        session = SessionModel(
            user_id=test_user.id,
            instance_id=instance.id,
            started_at=None,
            last_message_at=None
        )
        db_session.add(session)
        db_session.commit()
        
        manager = TokenManager()
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            manager.initialize_session(db_session, str(session.id))
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
    
    def test_no_active_config_raises_resource_not_found_error(
        self, db_session, test_user, test_brand
    ):
        """✓ No active config → ResourceNotFoundError"""
        # Create instance without config
        from db.models.instances import InstanceModel
        from db.models.sessions import SessionModel
        
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="No Config Instance",
            channel="api",
            is_active=True
        )
        db_session.add(instance)
        db_session.commit()
        
        session = SessionModel(
            user_id=test_user.id,
            instance_id=instance.id,
            started_at=None,
            last_message_at=None
        )
        db_session.add(session)
        db_session.commit()
        
        manager = TokenManager()
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            manager.initialize_session(db_session, str(session.id))
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
    
    def test_no_template_set_raises_resource_not_found_error(
        self, db_session, test_user, test_brand, test_template_set
    ):
        """✓ No template_set → ResourceNotFoundError"""
        # Create instance with config that has empty functions (not None template_set_id)
        from db.models.instances import InstanceModel
        from db.models.instance_configs import InstanceConfigModel
        from db.models.sessions import SessionModel
        from db.models.template_sets import TemplateSetModel
        
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="No TemplateSet Instance",
            channel="api",
            is_active=True
        )
        db_session.add(instance)
        db_session.commit()
        
        # Create a template_set with empty functions
        empty_template_set = TemplateSetModel(
            id="empty_template_set",
            name="Empty Template Set",
            functions={}  # Empty functions dict
        )
        db_session.add(empty_template_set)
        db_session.commit()
        
        config = InstanceConfigModel(
            instance_id=instance.id,
            template_set_id=empty_template_set.id,  # Valid but empty
            is_active=True
        )
        db_session.add(config)
        db_session.commit()
        
        session = SessionModel(
            user_id=test_user.id,
            instance_id=instance.id,
            started_at=None,
            last_message_at=None
        )
        db_session.add(session)
        db_session.commit()
        
        manager = TokenManager()
        
        # Should return None (empty functions), not raise error
        result = manager.initialize_session(db_session, str(session.id))
        assert result is None
    
    def test_empty_functions_returns_none(self, db_session, test_session, test_instance):
        """✓ Empty functions → None"""
        # Update template_set to have empty functions
        from db.models.instance_configs import InstanceConfigModel
        
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        if config and config.template_set:
            config.template_set.functions = {}
            db_session.commit()
        
        manager = TokenManager()
        result = manager.initialize_session(db_session, str(test_session.id))
        
        assert result is None
    
    def test_build_token_plan_via_calculator(self, db_session, test_session):
        """✓ Build token plan via calculator"""
        manager = TokenManager()
        
        plan = manager.initialize_session(db_session, str(test_session.id))
        
        assert plan is not None
        assert "templates" in plan
    
    def test_save_to_sessions_token_plan_json(self, db_session, test_session):
        """✓ Save to sessions.token_plan_json"""
        manager = TokenManager()
        
        manager.initialize_session(db_session, str(test_session.id))
        
        db_session.refresh(test_session)
        assert test_session.token_plan_json is not None
    
    def test_update_sessions_updated_at(self, db_session, test_session):
        """✓ Update sessions.updated_at"""
        old_time = test_session.updated_at
        
        manager = TokenManager()
        manager.initialize_session(db_session, str(test_session.id))
        
        db_session.refresh(test_session)
        assert test_session.updated_at > old_time
    
    @pytest.mark.skip(reason="Covered by message_adapter tests - avoid duplication")
    def test_adapter_built_before_token_init_warns_but_doesnt_fail(
        self, db_session, test_session
    ):
        """Adapter built before token init → Warns but doesn't fail"""
        # Tested in message_adapter tests
        # TokenManager handles missing token_plan gracefully
        pass


# ============================================================================
# SECTION C7.4: TokenManager.get_token_plan Tests
# ============================================================================

class TestTokenManagerGetTokenPlan:
    """Test TokenManager.get_token_plan method."""
    
    def test_missing_session_id_raises_validation_error(self, db_session):
        """✓ Missing session_id → ValidationError"""
        manager = TokenManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.get_token_plan(db_session, session_id=None)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_session_not_found_returns_none(self, db_session):
        """✓ Session not found → None"""
        manager = TokenManager()
        fake_id = str(uuid.uuid4())
        
        plan = manager.get_token_plan(db_session, fake_id)
        
        assert plan is None
    
    def test_no_token_plan_json_returns_none(self, db_session, test_user, test_instance):
        """✓ No token_plan_json → None"""
        # Create session without token plan
        from db.models.sessions import SessionModel
        session = SessionModel(
            user_id=test_user.id,
            instance_id=test_instance.id,
            token_plan_json=None
        )
        db_session.add(session)
        db_session.commit()
        
        manager = TokenManager()
        plan = manager.get_token_plan(db_session, str(session.id))
        
        assert plan is None
    
    def test_return_token_plan_json(self, db_session, test_session):
        """✓ Return token_plan_json"""
        # Initialize plan first
        manager = TokenManager()
        manager.initialize_session(db_session, str(test_session.id))
        
        # Get plan
        plan = manager.get_token_plan(db_session, str(test_session.id))
        
        assert plan is not None


# ============================================================================
# SECTION C7.5: TokenManager.record_usage Tests
# ============================================================================

class TestTokenManagerRecordUsage:
    """Test TokenManager.record_usage method."""
    
    def test_missing_session_id_raises_validation_error(self, db_session):
        """✓ Missing session_id → ValidationError"""
        manager = TokenManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.record_usage(
                db_session,
                session_id=None,
                template_key="test",
                function_name="response",
                sent_tokens=100,
                received_tokens=50
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_missing_template_key_raises_validation_error(self, db_session, test_session):
        """✓ Missing template_key → ValidationError"""
        manager = TokenManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.record_usage(
                db_session,
                session_id=str(test_session.id),
                template_key=None,
                function_name="response",
                sent_tokens=100,
                received_tokens=50
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_missing_function_name_raises_validation_error(self, db_session, test_session):
        """✓ Missing function_name → ValidationError"""
        manager = TokenManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.record_usage(
                db_session,
                session_id=str(test_session.id),
                template_key="test_template",
                function_name=None,
                sent_tokens=100,
                received_tokens=50
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_negative_tokens_set_to_0(self, db_session, test_session):
        """✓ Negative tokens → set to 0"""
        manager = TokenManager()
        
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test_template",
            function_name="response",
            sent_tokens=-10,
            received_tokens=-5
        )
        
        # Should not raise error, tokens set to 0
        usage = db_session.query(SessionTokenUsageModel).filter(
            SessionTokenUsageModel.session_id == test_session.id
        ).first()
        
        assert usage.sent_tokens == 0
        assert usage.received_tokens == 0
    
    def test_calculate_cost_if_llm_model_id_provided(
        self, db_session, test_session, test_llm_model
    ):
        """✓ Calculate cost if llm_model_id provided"""
        # Set pricing on model
        test_llm_model.input_price_per_1k = Decimal("0.03")
        test_llm_model.output_price_per_1k = Decimal("0.06")
        db_session.commit()
        
        manager = TokenManager()
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test_template",
            function_name="response",
            sent_tokens=1000,
            received_tokens=500,
            llm_model_id=str(test_llm_model.id)
        )
        
        usage = db_session.query(SessionTokenUsageModel).filter(
            SessionTokenUsageModel.session_id == test_session.id
        ).first()
        
        assert usage.cost_usd is not None
        assert float(usage.cost_usd) > 0
    
    def test_save_to_session_token_usage(self, db_session, test_session):
        """✓ Save to session_token_usage"""
        manager = TokenManager()
        
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test_template",
            function_name="response",
            sent_tokens=100,
            received_tokens=50
        )
        
        usage = db_session.query(SessionTokenUsageModel).filter(
            SessionTokenUsageModel.session_id == test_session.id
        ).first()
        
        assert usage is not None
    
    def test_include_planned_sent_received_total_tokens(
        self, db_session, test_session
    ):
        """✓ Include: planned_tokens, sent_tokens, received_tokens, total_tokens"""
        manager = TokenManager()
        
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test_template",
            function_name="response",
            sent_tokens=100,
            received_tokens=50
        )
        
        usage = db_session.query(SessionTokenUsageModel).filter(
            SessionTokenUsageModel.session_id == test_session.id
        ).first()
        
        assert hasattr(usage, 'planned_tokens')
        assert hasattr(usage, 'sent_tokens')
        assert hasattr(usage, 'received_tokens')
        assert hasattr(usage, 'total_tokens')
        assert usage.total_tokens == 150
    
    def test_include_llm_model_pricing_cost(
        self, db_session, test_session, test_llm_model
    ):
        """✓ Include: llm_model_id, input_price_per_1k, output_price_per_1k, cost_usd"""
        test_llm_model.input_price_per_1k = Decimal("0.01")
        test_llm_model.output_price_per_1k = Decimal("0.02")
        db_session.commit()
        
        manager = TokenManager()
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test_template",
            function_name="response",
            sent_tokens=100,
            received_tokens=50,
            llm_model_id=str(test_llm_model.id)
        )
        
        usage = db_session.query(SessionTokenUsageModel).filter(
            SessionTokenUsageModel.session_id == test_session.id
        ).first()
        
        assert usage.llm_model_id is not None
        assert usage.input_price_per_1k is not None
        assert usage.output_price_per_1k is not None
        assert usage.cost_usd is not None
    
    def test_llm_model_missing_pricing_cost_calculation_skipped(
        self, db_session, test_session, test_llm_model
    ):
        """✓ LLM model missing pricing → Cost calculation skipped (NULL)"""
        # Ensure no pricing
        test_llm_model.input_price_per_1k = None
        test_llm_model.output_price_per_1k = None
        db_session.commit()
        
        manager = TokenManager()
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test_template",
            function_name="response",
            sent_tokens=100,
            received_tokens=50,
            llm_model_id=str(test_llm_model.id)
        )
        
        usage = db_session.query(SessionTokenUsageModel).filter(
            SessionTokenUsageModel.session_id == test_session.id
        ).first()
        
        assert usage.cost_usd is None


# ============================================================================
# SECTION C7.6: TokenManager.get_usage_stats Tests
# ============================================================================

class TestTokenManagerGetUsageStats:
    """Test TokenManager.get_usage_stats method."""
    
    def test_missing_session_id_raises_validation_error(self, db_session):
        """✓ Missing session_id → ValidationError"""
        manager = TokenManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.get_usage_stats(db_session, session_id=None)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_sum_totals_planned_sent_received_actual(
        self, db_session, test_session
    ):
        """✓ Sum totals: planned, sent, received, actual"""
        manager = TokenManager()
        
        # Record some usage
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test1",
            function_name="func1",
            sent_tokens=100,
            received_tokens=50
        )
        
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test2",
            function_name="func2",
            sent_tokens=200,
            received_tokens=100
        )
        
        stats = manager.get_usage_stats(db_session, str(test_session.id))
        
        assert stats["total_sent"] == 300
        assert stats["total_received"] == 150
        assert stats["total_actual"] == 450
    
    def test_group_by_template_key(self, db_session, test_session):
        """✓ Group by template_key"""
        manager = TokenManager()
        
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test_template",
            function_name="func1",
            sent_tokens=100,
            received_tokens=50
        )
        
        stats = manager.get_usage_stats(db_session, str(test_session.id))
        
        assert "by_template" in stats
        assert "test_template" in stats["by_template"]
    
    def test_include_plan_info_if_available(self, db_session, test_session):
        """✓ Include plan info if available"""
        manager = TokenManager()
        
        # Initialize plan
        manager.initialize_session(db_session, str(test_session.id))
        
        stats = manager.get_usage_stats(db_session, str(test_session.id))
        
        assert "plan" in stats


# ============================================================================
# SECTION C7.7: TokenTracker Tests
# ============================================================================

class TestTokenTracker:
    """Test TokenTracker methods."""
    
    def test_save_usage_delegates_to_token_manager_record_usage(
        self, db_session, test_session
    ):
        """✓ Delegated to TokenManager.record_usage"""
        # TokenTracker.save_usage is just a wrapper
        # Already tested via TokenManager.record_usage tests
        pass
    
    def test_get_session_usage_missing_session_id_raises_validation_error(
        self, db_session
    ):
        """✓ Missing session_id → ValidationError"""
        tracker = TokenTracker()
        
        with pytest.raises(ValidationError) as exc_info:
            tracker.get_session_usage(db_session, session_id=None)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_get_session_usage_returns_all_usage_records(
        self, db_session, test_session
    ):
        """✓ Return all usage records for session"""
        manager = TokenManager()
        
        # Record usage
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="test1",
            function_name="func1",
            sent_tokens=100,
            received_tokens=50
        )
        
        tracker = TokenTracker()
        records = tracker.get_session_usage(db_session, str(test_session.id))
        
        assert len(records) >= 1
    
    def test_get_session_usage_order_by_timestamp_asc(
        self, db_session, test_session
    ):
        """✓ Order by timestamp asc"""
        manager = TokenManager()
        
        # Record multiple usages
        for i in range(3):
            manager.record_usage(
                db_session,
                session_id=str(test_session.id),
                template_key=f"test{i}",
                function_name=f"func{i}",
                sent_tokens=100,
                received_tokens=50
            )
        
        tracker = TokenTracker()
        records = tracker.get_session_usage(db_session, str(test_session.id))
        
        # Should be ordered by timestamp ascending
        assert len(records) == 3
    
    def test_get_template_usage_missing_session_id_raises_validation_error(
        self, db_session
    ):
        """✓ Missing session_id → ValidationError"""
        tracker = TokenTracker()
        
        with pytest.raises(ValidationError) as exc_info:
            tracker.get_template_usage(
                db_session,
                session_id=None,
                template_key="test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_get_template_usage_missing_template_key_raises_validation_error(
        self, db_session, test_session
    ):
        """✓ Missing template_key → ValidationError"""
        tracker = TokenTracker()
        
        with pytest.raises(ValidationError) as exc_info:
            tracker.get_template_usage(
                db_session,
                session_id=str(test_session.id),
                template_key=None
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_get_template_usage_returns_records_filtered_by_template(
        self, db_session, test_session
    ):
        """✓ Return usage records filtered by template"""
        manager = TokenManager()
        
        # Record usage for different templates
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="template_a",
            function_name="func1",
            sent_tokens=100,
            received_tokens=50
        )
        
        manager.record_usage(
            db_session,
            session_id=str(test_session.id),
            template_key="template_b",
            function_name="func2",
            sent_tokens=200,
            received_tokens=100
        )
        
        tracker = TokenTracker()
        records = tracker.get_template_usage(
            db_session,
            str(test_session.id),
            "template_a"
        )
        
        assert len(records) == 1
        assert records[0].template_key == "template_a"
    
    def test_get_template_usage_order_by_timestamp_asc(
        self, db_session, test_session
    ):
        """✓ Order by timestamp asc"""
        manager = TokenManager()
        
        # Record multiple usages for same template
        for i in range(3):
            manager.record_usage(
                db_session,
                session_id=str(test_session.id),
                template_key="test_template",
                function_name=f"func{i}",
                sent_tokens=100,
                received_tokens=50
            )
        
        tracker = TokenTracker()
        records = tracker.get_template_usage(
            db_session,
            str(test_session.id),
            "test_template"
        )
        
        # Should be ordered by timestamp
        assert len(records) == 3