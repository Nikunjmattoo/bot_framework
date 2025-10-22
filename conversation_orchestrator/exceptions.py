"""
Orchestrator exceptions.

All custom exceptions for conversation orchestrator module.
"""


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class IntentDetectionError(OrchestratorError):
    """Intent detection failed."""
    pass


class BrainProcessingError(OrchestratorError):
    """Brain processing failed."""
    pass


class ResponseGenerationError(OrchestratorError):
    """Response generation failed."""
    pass


class TemplateError(OrchestratorError):
    """Template filling or validation failed."""
    pass


class LLMError(OrchestratorError):
    """LLM call failed."""
    pass


class DatabaseError(OrchestratorError):
    """Database operation failed."""
    pass


class ValidationError(OrchestratorError):
    """Input validation failed."""
    pass