"""
Actions model - Instance-specific actions that can be triggered by intents.
"""
from sqlalchemy import Column, UUID, ForeignKey, String, Text, Integer, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship

from db.models.base import Base


class ActionModel(Base):
    """
    Actions - Instance-specific actions that can be triggered.
    
    Each instance defines its own actions (e.g., upload_resume, create_profile).
    Actions map to API endpoints or workflows with comprehensive configuration.
    """
    __tablename__ = 'actions'
    
    # === IDENTIFICATION (7 columns) ===
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    instance_id = Column(
        UUID,
        ForeignKey('instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    canonical_name = Column(String(100), nullable=False, comment="LLM-detected action name")
    display_name = Column(String(200), nullable=False, comment="Human-readable name")
    description = Column(Text, nullable=True)
    action_type = Column(
        String(50),
        nullable=False,
        comment="SYSTEM_API, EXTERNAL_API, WORKFLOW, REDIRECT"
    )
    category = Column(String(100), nullable=True, comment="e.g., onboarding, financial")
    
    # === AUTHORIZATION (4 columns) ===
    requires_auth = Column(Boolean, nullable=False, server_default='true')
    min_trust_score = Column(Float, nullable=False, server_default='0.0')
    allowed_user_tiers = Column(ARRAY(String), nullable=True)
    blocked_user_tiers = Column(ARRAY(String), nullable=True)
    
    # === CONFLICTS (1 column) ===
    opposite_action = Column(
        String(100),
        nullable=True,
        comment="Single opposite action for user confirmation"
    )
    
    # === EXECUTION (4 columns) ===
    api_endpoint = Column(String(500), nullable=True)
    http_method = Column(String(10), nullable=True, comment="GET, POST, PUT, DELETE")
    timeout_ms = Column(Integer, nullable=False, server_default='30000')
    execution_type = Column(
        String(50),
        nullable=True,
        comment="api_call, workflow, redirect"
    )
    
    # === UNDO (3 columns) ===
    is_undoable = Column(
        Boolean,
        nullable=False,
        server_default='false',
        comment="Can action be undone? Used for bot confirmation messaging"
    )
    undo_action = Column(String(100), nullable=True)
    undo_window_seconds = Column(Integer, nullable=True, server_default='300')
    
    # === REPEATABILITY (4 columns) ===
    is_repeatable = Column(Boolean, nullable=False, server_default='true')
    max_executions_per_session = Column(
        Integer,
        nullable=True,
        comment="Prevent session abuse (e.g., uploading resume 50 times)"
    )
    max_executions_per_day = Column(
        Integer,
        nullable=True,
        comment="Cross-session abuse prevention"
    )
    min_repeat_interval_seconds = Column(
        Integer,
        nullable=True,
        comment="Prevent rapid-fire abuse"
    )
    
    # === WORKFLOW (4 columns) ===
    workflow_id = Column(
        UUID,
        ForeignKey('workflows.id', ondelete='SET NULL'),
        nullable=True
    )
    sequence_number = Column(Integer, nullable=True, comment="Order in workflow")
    is_optional_step = Column(Boolean, nullable=False, server_default='false')
    parallel_group = Column(
        Integer,
        nullable=True,
        comment="Actions with same # run in parallel"
    )
    
    # === CONFIG JSONB (everything else) ===
    config = Column(
        JSONB,
        nullable=False,
        server_default='{}',
        comment="""
        Contains: prerequisites, params, retry_policy, confirmation, success_status_code
        Structure:
        {
            "prerequisites": {
                "depends_on_actions": ["create_profile"],
                "depends_on_schemas": [{"schema_key": "user_profile", "required_fields": ["email"]}],
                "blocked_if_actions": ["profile_deleted"],
                "blocked_if_schemas": ["profile_exists"],
                "blockers": ["email_in_use"]
            },
            "params_required": ["email", "phone"],
            "params_optional": ["bio"],
            "param_validation": {"email": {"type": "email", "regex": "...", "error_message": "..."}},
            "retry_policy": {
                "max_retries": 3,
                "backoff_strategy": "exponential",
                "initial_delay_seconds": 2,
                "max_delay_seconds": 60,
                "retry_on_status": [500, 502, 503],
                "retry_on_errors": ["timeout", "api_error"],
                "no_retry_on_errors": ["validation_error"]
            },
            "confirmation": {"required": true, "prompt": "Are you sure?"},
            "success_status_code": 200
        }
        """
    )
    
    # === METADATA (3 columns) ===
    is_active = Column(Boolean, nullable=False, server_default='true')
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # === RELATIONSHIPS ===
    instance = relationship("InstanceModel", back_populates="actions")
    workflow = relationship("WorkflowModel", back_populates="actions")
    
    # === TABLE CONSTRAINTS ===
    __table_args__ = (
        # Unique constraint: one canonical_name per instance
        # Index is automatically created by SQLAlchemy for unique constraints
    )
    
    def __repr__(self):
        return (
            f"<Action(id='{self.id}', canonical_name='{self.canonical_name}', "
            f"action_type='{self.action_type}')>"
        )
    
    # === HELPER METHODS ===
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'instance_id': str(self.instance_id),
            'canonical_name': self.canonical_name,
            'display_name': self.display_name,
            'description': self.description,
            'action_type': self.action_type,
            'category': self.category,
            'requires_auth': self.requires_auth,
            'is_undoable': self.is_undoable,
            'is_repeatable': self.is_repeatable,
            'config': self.config,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_prerequisites(self):
        """Get prerequisite configuration."""
        return self.config.get('prerequisites', {})
    
    def get_params_required(self):
        """Get required parameters."""
        return self.config.get('params_required', [])
    
    def get_params_optional(self):
        """Get optional parameters."""
        return self.config.get('params_optional', [])
    
    def get_retry_policy(self):
        """Get retry policy configuration."""
        return self.config.get('retry_policy', {})
    
    def needs_confirmation(self):
        """Check if action requires user confirmation."""
        return self.config.get('confirmation', {}).get('required', False)
    
    def get_confirmation_prompt(self):
        """Get confirmation prompt for user."""
        return self.config.get('confirmation', {}).get('prompt', 'Are you sure?')