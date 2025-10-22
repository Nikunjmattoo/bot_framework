"""
Token Manager Service for LLM budget control.

This module provides comprehensive token budget management including:
- Initialization of token plans from template configurations
- Calculation of token budgets from template modules
- Tracking of actual token usage
- Usage statistics and reporting

The TokenManager coordinates between TokenCalculator (budget planning)
and TokenTracker (usage recording) to provide complete token management.
"""
from typing import Dict, Any, Optional, List, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import uuid

from message_handler.exceptions import (
    ValidationError, ResourceNotFoundError, DatabaseError, ErrorCode
)
from message_handler.utils.logging import get_context_logger
from message_handler.utils.transaction import retry_transaction
from message_handler.utils.datetime_utils import get_current_datetime


# ============================================================================
# TOKEN CALCULATOR
# ============================================================================

class TokenCalculator:
    """Calculator for token budgets from template modules."""
    
    def build_session_plan(
        self,
        db: Session,
        functions: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build complete token plan for a session from functions mapping.
        
        Args:
            db: Database session
            functions: Dict mapping function_name -> config
                      Config can be:
                      - {"model": "uuid", "template": "template_key"} (new format)
                      - "template_key" (old format, just string)
            trace_id: Trace ID for logging
            
        Returns:
            Token plan with structure:
            {
                "templates": {
                    "intent_v1": {
                        "function": "intent",
                        "template_key": "intent_v1",
                        "llm_model_id": "...",
                        "llm_model_name": "...",
                        "sections": [...],
                        "total_budget": 950
                    },
                    "response_v1": {...}
                },
                "created_at": "2025-10-19T..."
            }
        """
        
        logger = get_context_logger("token_calculator", trace_id=trace_id)
        
        try:
            from db.models.templates import TemplateModel
            from db.models.llm_models import LLMModel
            
            plan = {
                "templates": {},
                "created_at": get_current_datetime().isoformat()
            }
            
            logger.info(f"Building token plan from {len(functions)} functions")
            
            # Process each function -> template mapping
            for function_name, function_config in functions.items():
                # Extract template_key and model_id from config
                if isinstance(function_config, dict):
                    template_key = function_config.get('template')
                    model_id = function_config.get('model')
                    logger.debug(
                        f"Processing function={function_name}, "
                        f"template={template_key}, model={model_id}"
                    )
                else:
                    # Fallback for old format (just string)
                    template_key = function_config
                    model_id = None
                    logger.debug(f"Processing function={function_name}, template={template_key} (legacy format)")
                
                if not template_key:
                    logger.warning(f"No template_key for function {function_name}, skipping")
                    continue
                
                # Load template
                template = db.query(TemplateModel).filter(
                    TemplateModel.template_key == template_key,
                    TemplateModel.is_active == True
                ).first()
                
                if not template:
                    logger.warning(f"Template not found: {template_key}, skipping function {function_name}")
                    continue
                
                logger.info(f"Found template: {template_key} (id={template.id})")
                
                # Get LLM model info
                llm_model = None
                if template.llm_model_id:
                    llm_model = db.query(LLMModel).filter(
                        LLMModel.id == template.llm_model_id
                    ).first()
                    
                    if llm_model:
                        logger.debug(f"Template uses LLM model: {llm_model.name}")
                
                # Calculate budget for this template
                template_budget = self.calculate_template_budget(template, trace_id=trace_id)
                
                # Skip if no LLM model (can't process without model)
                if not llm_model:
                    logger.warning(f"Template {template_key} has no LLM model, skipping")
                    continue
                
                # Add to plan
                plan["templates"][template_key] = {
                    "function": function_name,
                    "template_key": template_key,
                    "llm_model_id": str(llm_model.id),
                    "llm_model_name": llm_model.name,
                    "api_model_name": llm_model.api_model_name,
                    "provider": llm_model.provider,
                    "temperature": float(llm_model.temperature) if llm_model.temperature is not None else 0.7,  # ✅ FIX: Use 'is not None'
                    "sections": template_budget["sections"],
                    "total_budget": template_budget["total_budget"]
                }
                
                logger.info(
                    f"✓ Added template {template_key}: "
                    f"{len(template_budget['sections'])} sections, "
                    f"total={template_budget['total_budget']} tokens, "
                    f"llm={llm_model.name if llm_model else 'None'}"
                )
            
            if not plan["templates"]:
                logger.warning("No templates added to plan - all functions skipped or failed")
            else:
                logger.info(f"✓ Built token plan with {len(plan['templates'])} templates")
            
            return plan
            
        except Exception as e:
            error_msg = f"Error building session plan: {str(e)}"
            logger.exception(error_msg)
            raise
    
    def calculate_template_budget(
        self,
        template: Any,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate token budget for a template from its sections.
        
        Args:
            template: TemplateModel instance
            trace_id: Trace ID for logging
            
        Returns:
            {
                "sections": [
                    {
                        "key": "system_instructions",
                        "budget_tokens": 500,
                        "type": "static",
                        "sequence": 1
                    },
                    ...
                ],
                "total_budget": 1500
            }
        """
        logger = get_context_logger("token_calculator", trace_id=trace_id)
        
        result = {
            "sections": [],
            "total_budget": 0
        }
        
        # Extract sections from template
        sections = template.sections if hasattr(template, 'sections') else []
        
        if not sections:
            logger.warning(f"Template {template.template_key} has no sections")
            return result
        
        if not isinstance(sections, list):
            logger.error(f"Template {template.template_key} sections is not a list: {type(sections)}")
            return result
        
        logger.debug(f"Processing {len(sections)} sections for template {template.template_key}")
        
        # Process each section
        for idx, section in enumerate(sections):
            if not isinstance(section, dict):
                logger.warning(f"Invalid section at index {idx}, skipping")
                continue
            
            # Extract budget
            budget_tokens = section.get("budget_tokens", 0)
            section_type = section.get("type", "static")
            sequence = section.get("sequence", 0)
            key = section.get("key", f"section_{idx}")
            
            # Validate budget is a number
            if not isinstance(budget_tokens, (int, float)):
                logger.warning(f"Invalid budget for section {key}: {budget_tokens}, using 0")
                budget_tokens = 0
            
            budget_tokens = int(budget_tokens)
            
            # Add to result
            result["sections"].append({
                "key": key,
                "budget_tokens": budget_tokens,
                "type": section_type,
                "sequence": sequence,
                "fetch": section.get("fetch")  # Include fetch config if exists
            })
            
            # Add to total
            result["total_budget"] += budget_tokens
            
            logger.debug(f"Section {key}: {budget_tokens} tokens ({section_type})")
        
        logger.info(
            f"Calculated budget for template {template.template_key}: "
            f"{len(result['sections'])} sections, total={result['total_budget']} tokens"
        )
        
        return result


# ============================================================================
# TOKEN TRACKER
# ============================================================================

class TokenTracker:
    """Tracker for actual token usage."""
    
    def save_usage(
        self,
        db: Session,
        session_id: str,
        template_key: str,
        function_name: str,
        planned_tokens: int,
        sent_tokens: int,
        received_tokens: int,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Save token usage record to database.
        
        Args:
            db: Database session
            session_id: Session ID
            template_key: Template key
            function_name: Function name
            planned_tokens: Planned/budgeted tokens
            sent_tokens: Actual tokens sent (prompt)
            received_tokens: Actual tokens received (completion)
            trace_id: Trace ID for logging (optional)
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ValidationError: If inputs are invalid
            DatabaseError: If database operation fails
        """
        logger = get_context_logger(
            "token_tracker",
            trace_id=trace_id,
            session_id=session_id
        )
        
        try:
            # Validate inputs
            if not session_id:
                raise ValidationError(
                    "Session ID is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="session_id"
                )
            
            if not template_key:
                raise ValidationError(
                    "Template key is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="template_key"
                )
            
            if not function_name:
                raise ValidationError(
                    "Function name is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="function_name"
                )
            
            # Validate token counts are non-negative
            if sent_tokens < 0:
                logger.warning(f"Negative sent_tokens: {sent_tokens}, setting to 0")
                sent_tokens = 0
            
            if received_tokens < 0:
                logger.warning(f"Negative received_tokens: {received_tokens}, setting to 0")
                received_tokens = 0
            
            total_tokens = sent_tokens + received_tokens
            
            # Use retry transaction for reliability
            with retry_transaction(db, trace_id=trace_id, max_retries=2) as tx:
                from db.models.session_token_usage import SessionTokenUsageModel
                
                # Create usage record
                usage_record = SessionTokenUsageModel(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    template_key=template_key,
                    function_name=function_name,
                    planned_tokens=planned_tokens,
                    sent_tokens=sent_tokens,
                    received_tokens=received_tokens,
                    total_tokens=total_tokens,
                    timestamp=get_current_datetime(),
                    created_at=get_current_datetime()
                )
                
                tx.add(usage_record)
                tx.flush()
                
                logger.info(
                    f"Saved usage: template={template_key}, "
                    f"planned={planned_tokens}, actual={total_tokens}"
                )
                
                return True
                
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            error_msg = f"Database error saving token usage: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="save_usage"
            )
        except Exception as e:
            error_msg = f"Unexpected error saving token usage: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="save_usage"
            )
    
    def get_session_usage(
        self,
        db: Session,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> List[Any]:
        """
        Get all token usage records for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            trace_id: Trace ID for logging (optional)
            
        Returns:
            List of SessionTokenUsageModel instances
            
        Raises:
            ValidationError: If session_id is invalid
            DatabaseError: If database operation fails
        """
        logger = get_context_logger(
            "token_tracker",
            trace_id=trace_id,
            session_id=session_id
        )
        
        try:
            # Validate input
            if not session_id:
                raise ValidationError(
                    "Session ID is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="session_id"
                )
            
            from db.models.session_token_usage import SessionTokenUsageModel
            
            # Query all usage records for session
            records = db.query(SessionTokenUsageModel).filter(
                SessionTokenUsageModel.session_id == session_id
            ).order_by(SessionTokenUsageModel.timestamp.asc()).all()
            
            logger.info(f"Retrieved {len(records)} usage records for session")
            return records
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving session usage: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="get_session_usage"
            )
        except Exception as e:
            error_msg = f"Unexpected error retrieving session usage: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="get_session_usage"
            )
    
    def get_template_usage(
        self,
        db: Session,
        session_id: str,
        template_key: str,
        trace_id: Optional[str] = None
    ) -> List[Any]:
        """
        Get token usage records for a specific template in a session.
        
        Args:
            db: Database session
            session_id: Session ID
            template_key: Template key
            trace_id: Trace ID for logging (optional)
            
        Returns:
            List of SessionTokenUsageModel instances
            
        Raises:
            ValidationError: If inputs are invalid
            DatabaseError: If database operation fails
        """
        logger = get_context_logger(
            "token_tracker",
            trace_id=trace_id,
            session_id=session_id,
            template_key=template_key
        )
        
        try:
            # Validate inputs
            if not session_id:
                raise ValidationError(
                    "Session ID is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="session_id"
                )
            
            if not template_key:
                raise ValidationError(
                    "Template key is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="template_key"
                )
            
            from db.models.session_token_usage import SessionTokenUsageModel
            
            # Query usage records for specific template
            records = db.query(SessionTokenUsageModel).filter(
                SessionTokenUsageModel.session_id == session_id,
                SessionTokenUsageModel.template_key == template_key
            ).order_by(SessionTokenUsageModel.timestamp.asc()).all()
            
            logger.info(f"Retrieved {len(records)} usage records for template {template_key}")
            return records
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving template usage: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="get_template_usage"
            )
        except Exception as e:
            error_msg = f"Unexpected error retrieving template usage: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="get_template_usage"
            )


# ============================================================================
# TOKEN MANAGER
# ============================================================================

class TokenManager:
    """
    Token Manager for session-based token budget management.
    
    Handles initialization of token plans and tracking of token usage
    for language model interactions.
    """
    
    def __init__(self):
        """Initialize TokenManager with calculator and tracker."""
        self.calculator = TokenCalculator()
        self.tracker = TokenTracker()
    
    def initialize_session(
        self,
        db: Session,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Initialize token budget plan for a session.
        
        This method:
        1. Loads instance → instance_config → template_set
        2. For each function in template_set.functions, loads the template
        3. Calculates budgets from template.sections
        4. Saves the plan to sessions.token_plan_json
        
        Args:
            db: Database session
            session_id: Session ID
            trace_id: Trace ID for logging (optional)
            
        Returns:
            Token plan dict if successful, None otherwise
            
        Raises:
            ValidationError: If session_id is invalid
            ResourceNotFoundError: If session or required data not found
            DatabaseError: If database operation fails
        """
        logger = get_context_logger(
            "token_manager",
            trace_id=trace_id,
            session_id=session_id
        )
        
        try:
            # Validate input
            if not session_id:
                raise ValidationError(
                    "Session ID is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="session_id"
                )
            
            logger.info("Initializing token budget plan")
            
            # Use retry transaction for reliability
            with retry_transaction(db, trace_id=trace_id, max_retries=2) as tx:
                # Import models here to avoid circular imports
                from db.models.sessions import SessionModel
                from db.models.instances import InstanceModel
                from db.models.instance_configs import InstanceConfigModel
                from db.models.template_sets import TemplateSetModel
                from db.models.templates import TemplateModel
                
                # 1. Load session
                session = tx.query(SessionModel).filter(
                    SessionModel.id == session_id
                ).first()
                
                if not session:
                    logger.error(f"Session not found: {session_id}")
                    raise ResourceNotFoundError(
                        f"Session not found: {session_id}",
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        resource_type="session",
                        resource_id=session_id
                    )
                
                logger.debug(f"✓ Found session: {session_id}")
                
                # 2. Load instance
                instance_id = session.instance_id
                if not instance_id:
                    logger.error(f"Session {session_id} has no instance_id")
                    raise ResourceNotFoundError(
                        f"Session has no instance_id",
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        resource_type="instance",
                        session_id=session_id
                    )
                
                instance = tx.query(InstanceModel).filter(
                    InstanceModel.id == instance_id,
                    InstanceModel.is_active == True
                ).first()
                
                if not instance:
                    logger.error(f"Instance not found or inactive: {instance_id}")
                    raise ResourceNotFoundError(
                        f"Instance not found or inactive: {instance_id}",
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        resource_type="instance",
                        resource_id=instance_id
                    )
                
                logger.debug(f"✓ Found active instance: {instance_id}")

                # 3. Load instance config
                instance_config = tx.query(InstanceConfigModel).filter(
                    InstanceConfigModel.instance_id == instance_id,
                    InstanceConfigModel.is_active == True
                ).first()
                
                if not instance_config:
                    logger.error(f"No active config for instance: {instance_id}")
                    raise ResourceNotFoundError(
                        f"No active config for instance: {instance_id}",
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        resource_type="instance_config",
                        resource_id=instance_id
                    )
                
                logger.debug(f"✓ Found instance_config: {instance_config.id}")
                
                # 4. Load template_set
                template_set_id = instance_config.template_set_id
                if not template_set_id:
                    logger.error(f"Config {instance_config.id} has no template_set_id")
                    raise ResourceNotFoundError(
                        f"Config has no template_set_id",
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        resource_type="template_set",
                        config_id=str(instance_config.id)
                    )
                
                template_set = tx.query(TemplateSetModel).filter(
                    TemplateSetModel.id == template_set_id
                ).first()
                
                if not template_set:
                    logger.error(f"Template set not found: {template_set_id}")
                    raise ResourceNotFoundError(
                        f"Template set not found: {template_set_id}",
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        resource_type="template_set",
                        resource_id=template_set_id
                    )
                
                logger.debug(f"✓ Found template_set: {template_set_id}")
                
                # 5. Get functions mapping from template_set
                functions = template_set.functions if hasattr(template_set, 'functions') else {}
                if not functions or not isinstance(functions, dict):
                    logger.warning(f"Template set {template_set_id} has no functions mapping")
                    functions = {}
                
                logger.info(f"Found {len(functions)} functions in template_set")
                logger.debug(f"Functions: {list(functions.keys())}")
                
                # 6. Build token plan using calculator
                token_plan = self.calculator.build_session_plan(
                    tx,
                    functions,
                    trace_id=trace_id
                )
                
                if not token_plan or not token_plan.get("templates"):
                    logger.warning("Token plan is empty - no templates processed")
                    return None
                
                # 7. Save plan to session
                session.token_plan_json = token_plan
                session.updated_at = get_current_datetime()
                tx.flush()
                
                logger.info(f"✓ Initialized token plan with {len(token_plan.get('templates', {}))} templates")
                
                return token_plan
                
        except ValidationError:
            raise
        except ResourceNotFoundError:
            raise
        except SQLAlchemyError as e:
            error_msg = f"Database error initializing token plan: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="initialize_session"
            )
        except Exception as e:
            error_msg = f"Unexpected error initializing token plan: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="initialize_session"
            )
    
    def get_token_plan(
        self,
        db: Session,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the token plan for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            trace_id: Trace ID for logging (optional)
            
        Returns:
            Token plan dictionary or None if not found
            
        Raises:
            ValidationError: If session_id is invalid
            DatabaseError: If database operation fails
        """
        logger = get_context_logger(
            "token_manager",
            trace_id=trace_id,
            session_id=session_id
        )
        
        try:
            # Validate input
            if not session_id:
                raise ValidationError(
                    "Session ID is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="session_id"
                )
            
            from db.models.sessions import SessionModel
            
            session = db.query(SessionModel).filter(
                SessionModel.id == session_id
            ).first()
            
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None
            
            token_plan = session.token_plan_json if hasattr(session, 'token_plan_json') else None
            
            if not token_plan:
                logger.warning(f"No token plan for session: {session_id}")
                return None
            
            return token_plan
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving token plan: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="get_token_plan"
            )
        except Exception as e:
            error_msg = f"Unexpected error retrieving token plan: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="get_token_plan"
            )
    
    def record_usage(
        self,
        db: Session,
        session_id: str,
        template_key: str,
        function_name: str,
        sent_tokens: int,
        received_tokens: int,
        llm_model_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """Record token usage with cost calculation"""
        
        logger = get_context_logger("token_tracker", trace_id=trace_id, session_id=session_id)
        
        try:
            # Validate inputs
            if not session_id:
                raise ValidationError(
                    "Session ID is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="session_id"
                )
            
            if not template_key:
                raise ValidationError(
                    "Template key is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="template_key"
                )
            
            if not function_name:
                raise ValidationError(
                    "Function name is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="function_name"
                )
            
            # Validate token counts
            if sent_tokens < 0:
                logger.warning(f"Negative sent_tokens: {sent_tokens}, setting to 0")
                sent_tokens = 0
            
            if received_tokens < 0:
                logger.warning(f"Negative received_tokens: {received_tokens}, setting to 0")
                received_tokens = 0
            
            total_tokens = sent_tokens + received_tokens
            
            # Get planned budget
            token_plan = self.get_token_plan(db, session_id, trace_id)
            planned_tokens = 0
            
            if token_plan and 'templates' in token_plan:
                template_info = token_plan['templates'].get(template_key, {})
                planned_tokens = template_info.get('total_budget', 0)
            
            # Calculate cost if model provided
            input_price_per_1k = None
            output_price_per_1k = None
            cost_usd = None
            
            if llm_model_id:
                from db.models.llm_models import LLMModel
                
                llm_model = db.query(LLMModel).filter(
                    LLMModel.id == llm_model_id
                ).first()
                
                if llm_model and llm_model.input_price_per_1k and llm_model.output_price_per_1k:
                    input_price_per_1k = llm_model.input_price_per_1k
                    output_price_per_1k = llm_model.output_price_per_1k
                    
                    # Calculate cost
                    input_cost = (sent_tokens / 1000.0) * float(input_price_per_1k)
                    output_cost = (received_tokens / 1000.0) * float(output_price_per_1k)
                    cost_usd = input_cost + output_cost
                    
                    logger.debug(
                        f"Cost: {sent_tokens} input @ ${input_price_per_1k}/1K + "
                        f"{received_tokens} output @ ${output_price_per_1k}/1K = ${cost_usd:.6f}"
                    )
            
            # Use retry transaction
            with retry_transaction(db, trace_id=trace_id, max_retries=2) as tx:
                from db.models.session_token_usage import SessionTokenUsageModel
                
                usage_record = SessionTokenUsageModel(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    template_key=template_key,
                    function_name=function_name,
                    planned_tokens=planned_tokens,
                    sent_tokens=sent_tokens,
                    received_tokens=received_tokens,
                    total_tokens=total_tokens,
                    llm_model_id=llm_model_id,
                    input_price_per_1k=input_price_per_1k,
                    output_price_per_1k=output_price_per_1k,
                    cost_usd=cost_usd,
                    
                    timestamp=get_current_datetime(),
                    created_at=get_current_datetime()
                )
                
                tx.add(usage_record)
                tx.flush()
                
                log_msg = f"Recorded usage: template={template_key}, tokens={total_tokens}"
                if cost_usd:
                    log_msg += f", cost=${cost_usd:.6f}"
                logger.info(log_msg)
                
                return True
                
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            error_msg = f"Database error saving token usage: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="save_usage"
            )
        except Exception as e:
            error_msg = f"Unexpected error saving token usage: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="save_usage"
            )
            
    def get_usage_stats(
        self,
        db: Session,
        session_id: str,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get token usage statistics for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            trace_id: Trace ID for logging (optional)
            
        Returns:
            Dictionary with usage statistics
            
        Raises:
            ValidationError: If session_id is invalid
            DatabaseError: If database operation fails
        """
        logger = get_context_logger(
            "token_manager",
            trace_id=trace_id,
            session_id=session_id
        )
        
        try:
            # Validate input
            if not session_id:
                raise ValidationError(
                    "Session ID is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="session_id"
                )
            
            # Get all usage for session
            usage_records = self.tracker.get_session_usage(db, session_id, trace_id)
            
            # Get token plan
            token_plan = self.get_token_plan(db, session_id, trace_id)
            
            # Build statistics
            stats = {
                "session_id": session_id,
                "total_records": len(usage_records),
                "total_planned": 0,
                "total_sent": 0,
                "total_received": 0,
                "total_actual": 0,
                "by_template": {}
            }
            
            # Calculate totals
            for record in usage_records:
                stats["total_planned"] += record.planned_tokens
                stats["total_sent"] += record.sent_tokens
                stats["total_received"] += record.received_tokens
                stats["total_actual"] += record.total_tokens
                
                # Group by template
                template_key = record.template_key
                if template_key not in stats["by_template"]:
                    stats["by_template"][template_key] = {
                        "planned": 0,
                        "sent": 0,
                        "received": 0,
                        "total": 0,
                        "count": 0
                    }
                
                stats["by_template"][template_key]["planned"] += record.planned_tokens
                stats["by_template"][template_key]["sent"] += record.sent_tokens
                stats["by_template"][template_key]["received"] += record.received_tokens
                stats["by_template"][template_key]["total"] += record.total_tokens
                stats["by_template"][template_key]["count"] += 1
            
            # Add plan info if available
            if token_plan:
                stats["plan"] = token_plan
            
            logger.info(f"Retrieved usage stats: {stats['total_records']} records")
            return stats
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            error_msg = f"Database error retrieving usage stats: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="get_usage_stats"
            )
        except Exception as e:
            error_msg = f"Unexpected error retrieving usage stats: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="get_usage_stats"
            )