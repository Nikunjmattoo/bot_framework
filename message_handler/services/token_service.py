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
        functions: Dict[str, str],
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build complete token plan for a session from functions mapping.
        
        Args:
            db: Database session
            functions: Dict mapping function_name -> template_key
            trace_id: Trace ID for logging (optional)
            
        Returns:
            Token plan dictionary with structure:
            {
                "templates": {
                    "template_key": {
                        "function": "function_name",
                        "modules": {...},
                        "total_budget": 1000
                    }
                },
                "created_at": "2025-10-06T..."
            }
            
        Raises:
            DatabaseError: If database operation fails
        """
        logger = get_context_logger("token_calculator", trace_id=trace_id)
        
        try:
            from db.models.templates import TemplateModel
            
            plan = {
                "templates": {},
                "created_at": get_current_datetime().isoformat()
            }
            
            # Process each function -> template mapping
            for function_name, template_key in functions.items():
                logger.debug(f"Processing function={function_name}, template={template_key}")
                
                # Load template
                template = db.query(TemplateModel).filter(
                    TemplateModel.template_key == template_key,
                    TemplateModel.is_active == True
                ).first()
                
                if not template:
                    logger.warning(f"Template not found: {template_key}, skipping")
                    continue
                
                # Calculate budget for this template
                template_budget = self.calculate_template_budget(
                    template,
                    trace_id=trace_id
                )
                
                # Add to plan
                plan["templates"][template_key] = {
                    "function": function_name,
                    "modules": template_budget["modules"],
                    "total_budget": template_budget["total_budget"]
                }
                
                logger.debug(
                    f"Added template {template_key}: "
                    f"{len(template_budget['modules'])} modules, "
                    f"total={template_budget['total_budget']} tokens"
                )
            
            logger.info(f"Built token plan with {len(plan['templates'])} templates")
            return plan
            
        except SQLAlchemyError as e:
            error_msg = f"Database error building session plan: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.DATABASE_ERROR,
                original_exception=e,
                operation="build_session_plan"
            )
        except Exception as e:
            error_msg = f"Unexpected error building session plan: {str(e)}"
            logger.exception(error_msg)
            raise DatabaseError(
                error_msg,
                error_code=ErrorCode.INTERNAL_ERROR,
                original_exception=e,
                operation="build_session_plan"
            )
    
    def calculate_template_budget(
        self,
        template: Any,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate token budget for a template from its modules.
        
        Args:
            template: TemplateModel instance
            trace_id: Trace ID for logging (optional)
            
        Returns:
            Dictionary with structure:
            {
                "modules": {
                    "module_name": {
                        "budget_tokens": 500,
                        "type": "static",
                        "sequence": 1
                    }
                },
                "total_budget": 1500
            }
        """
        logger = get_context_logger("token_calculator", trace_id=trace_id)
        
        result = {
            "modules": {},
            "total_budget": 0
        }
        
        # Extract modules from template
        modules = template.modules if hasattr(template, 'modules') else {}
        
        if not modules or not isinstance(modules, dict):
            logger.warning(f"Template {template.template_key} has no modules")
            return result
        
        # Process each module
        for module_name, module_config in modules.items():
            if not isinstance(module_config, dict):
                logger.warning(f"Invalid module config for {module_name}, skipping")
                continue
            
            # Extract budget
            budget_tokens = module_config.get("budget_tokens", 0)
            module_type = module_config.get("type", "static")
            sequence = module_config.get("sequence", 0)
            
            # Validate budget is a number
            if not isinstance(budget_tokens, (int, float)):
                logger.warning(f"Invalid budget for module {module_name}: {budget_tokens}")
                budget_tokens = 0
            
            budget_tokens = int(budget_tokens)
            
            # Add to result
            result["modules"][module_name] = {
                "budget_tokens": budget_tokens,
                "type": module_type,
                "sequence": sequence
            }
            
            # Add to total
            result["total_budget"] += budget_tokens
        
        logger.debug(
            f"Calculated budget for template {template.template_key}: "
            f"{len(result['modules'])} modules, total={result['total_budget']} tokens"
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
    ) -> bool:
        """
        Initialize token budget plan for a session.
        
        This method:
        1. Loads instance → instance_config → template_set
        2. For each function in template_set.functions, loads the template
        3. Calculates budgets from template.modules
        4. Saves the plan to sessions.token_plan_json
        
        Args:
            db: Database session
            session_id: Session ID
            trace_id: Trace ID for logging (optional)
            
        Returns:
            True if successful, False otherwise
            
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
                    InstanceModel.id == instance_id
                ).first()
                
                if not instance:
                    logger.error(f"Instance not found: {instance_id}")
                    raise ResourceNotFoundError(
                        f"Instance not found: {instance_id}",
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        resource_type="instance",
                        resource_id=instance_id
                    )
                
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
                
                # 5. Get functions mapping from template_set
                functions = template_set.functions if hasattr(template_set, 'functions') else {}
                if not functions or not isinstance(functions, dict):
                    logger.warning(f"Template set {template_set_id} has no functions mapping")
                    functions = {}
                
                logger.info(f"Found {len(functions)} functions in template_set")
                
                # 6. Build token plan using calculator
                token_plan = self.calculator.build_session_plan(
                    tx,
                    functions,
                    trace_id=trace_id
                )
                
                # 7. Save plan to session
                session.token_plan_json = token_plan
                session.updated_at = get_current_datetime()
                tx.flush()
                
                logger.info(f"Initialized token plan with {len(token_plan.get('templates', {}))} templates")
                return True
                
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
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Record actual token usage for a template.
        
        Args:
            db: Database session
            session_id: Session ID
            template_key: Template key (e.g., "intent_detection_v1")
            function_name: Function name (e.g., "intent_detection")
            sent_tokens: Number of tokens sent (prompt)
            received_tokens: Number of tokens received (completion)
            trace_id: Trace ID for logging (optional)
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ValidationError: If inputs are invalid
            DatabaseError: If database operation fails
        """
        logger = get_context_logger(
            "token_manager",
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
            
            if not function_name:
                raise ValidationError(
                    "Function name is required",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="function_name"
                )
            
            # Get the planned budget for this template
            token_plan = self.get_token_plan(db, session_id, trace_id)
            planned_tokens = 0
            
            if token_plan and 'templates' in token_plan:
                template_info = token_plan['templates'].get(template_key, {})
                planned_tokens = template_info.get('total_budget', 0)
            
            # Record usage using tracker
            success = self.tracker.save_usage(
                db,
                session_id=session_id,
                template_key=template_key,
                function_name=function_name,
                planned_tokens=planned_tokens,
                sent_tokens=sent_tokens,
                received_tokens=received_tokens,
                trace_id=trace_id
            )
            
            if success:
                logger.info(
                    f"Recorded usage: sent={sent_tokens}, received={received_tokens}, "
                    f"total={sent_tokens + received_tokens}, planned={planned_tokens}"
                )
            
            return success
            
        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"Error recording token usage: {str(e)}"
            logger.error(error_msg)
            return False
    
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