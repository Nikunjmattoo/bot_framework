"""
Conversation Orchestrator Module

Orchestrates multi-stage conversation processing:
- Intent detection
- Brain processing (user data, intent ledger, conversation director)
- Response generation
- Post-processing
"""

__version__ = "0.1.0"

from conversation_orchestrator.brain.brain import process_brain

__all__ = ["process_brain"]