"""
Database service for fetching enrichment data.

Fetches session_summary, previous_messages, active_task, next_narrative from DB.
"""

import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from db.db import get_db
from db.models.messages import MessageModel
from db.models.sessions import SessionModel
from conversation_orchestrator.schemas import Message, ActiveTask
from conversation_orchestrator.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def fetch_session_summary(session_id: str) -> Optional[str]:
    """
    Fetch session summary from database.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Session summary string (100-150 tokens) or None if not found
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        db: Session = next(get_db())
        
        try:
            # Fetch session
            session = db.query(SessionModel).filter(
                SessionModel.id == session_id
            ).first()
            
            if not session:
                logger.warning(
                    "db_service:session_not_found",
                    extra={"session_id": session_id}
                )
                return None
            
            # Get session_summary from session model
            # TODO: Adjust based on your actual schema
            summary = getattr(session, 'session_summary', None)
            
            if summary:
                logger.debug(
                    "db_service:session_summary_found",
                    extra={"session_id": session_id, "summary_length": len(summary)}
                )
            else:
                logger.debug(
                    "db_service:session_summary_not_found",
                    extra={"session_id": session_id}
                )
            
            return summary
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(
            "db_service:fetch_session_summary_error",
            extra={"session_id": session_id, "error": str(e)}
        )
        raise DatabaseError(
            message=f"Failed to fetch session summary: {str(e)}",
            error_code="DB_FETCH_ERROR",
            details={"session_id": session_id}
        ) from e


def fetch_previous_messages(session_id: str, limit: int = 4) -> List[Message]:
    """
    Fetch previous messages from database.
    
    Returns last N messages (default: 4 = 2 turns).
    
    Args:
        session_id: Session identifier
        limit: Number of messages to fetch (default: 4)
    
    Returns:
        List of Message objects (ordered chronologically, oldest first)
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        db: Session = next(get_db())
        
        try:
            # Fetch last N messages, ordered by created_at desc
            messages_query = db.query(MessageModel).filter(
                MessageModel.session_id == session_id
            ).order_by(desc(MessageModel.created_at)).limit(limit)
            
            messages = messages_query.all()
            
            if not messages:
                logger.debug(
                    "db_service:no_previous_messages",
                    extra={"session_id": session_id}
                )
                return []
            
            # Convert to Message objects and reverse to chronological order
            message_list = [
                Message(
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.created_at
                )
                for msg in reversed(messages)
            ]
            
            logger.debug(
                "db_service:previous_messages_found",
                extra={"session_id": session_id, "count": len(message_list)}
            )
            
            return message_list
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(
            "db_service:fetch_previous_messages_error",
            extra={"session_id": session_id, "error": str(e)}
        )
        raise DatabaseError(
            message=f"Failed to fetch previous messages: {str(e)}",
            error_code="DB_FETCH_ERROR",
            details={"session_id": session_id}
        ) from e


def fetch_active_task(session_id: str) -> Optional[ActiveTask]:
    """
    Fetch active task from database.
    
    Args:
        session_id: Session identifier
    
    Returns:
        ActiveTask object or None if no active task
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        db: Session = next(get_db())
        
        try:
            # Fetch session
            session = db.query(SessionModel).filter(
                SessionModel.id == session_id
            ).first()
            
            if not session:
                logger.warning(
                    "db_service:session_not_found",
                    extra={"session_id": session_id}
                )
                return None
            
            # Get active_task from session
            # TODO: Adjust based on your actual schema
            # This might be a JSON field or a separate table
            task_name = getattr(session, 'active_task_name', None)
            task_status = getattr(session, 'active_task_status', None)
            task_started = getattr(session, 'active_task_started_at', None)
            
            if task_name:
                active_task = ActiveTask(
                    name=task_name,
                    status=task_status,
                    started_at=task_started
                )
                
                logger.debug(
                    "db_service:active_task_found",
                    extra={"session_id": session_id, "task_name": task_name}
                )
                
                return active_task
            else:
                logger.debug(
                    "db_service:no_active_task",
                    extra={"session_id": session_id}
                )
                return None
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(
            "db_service:fetch_active_task_error",
            extra={"session_id": session_id, "error": str(e)}
        )
        raise DatabaseError(
            message=f"Failed to fetch active task: {str(e)}",
            error_code="DB_FETCH_ERROR",
            details={"session_id": session_id}
        ) from e

def fetch_template_string(template_key: str) -> str:
    """
    Fetch and build template string from database.
    
    Concatenates all section contents in sequence order.
    
    Args:
        template_key: Template key (e.g., "intent_v1")
    
    Returns:
        Complete template string with all sections combined
    
    Raises:
        DatabaseError: If template not found or fetch fails
    """
    try:
        db: Session = next(get_db())
        
        try:
            from db.models.templates import TemplateModel
            
            # Fetch template
            template = db.query(TemplateModel).filter(
                TemplateModel.template_key == template_key,
                TemplateModel.is_active == True
            ).first()
            
            if not template:
                raise DatabaseError(
                    message=f"Template not found: {template_key}",
                    error_code="TEMPLATE_NOT_FOUND",
                    details={"template_key": template_key}
                )
            
            # Get sections
            sections = template.sections if hasattr(template, 'sections') else []
            
            if not sections:
                raise DatabaseError(
                    message=f"Template has no sections: {template_key}",
                    error_code="TEMPLATE_EMPTY",
                    details={"template_key": template_key}
                )
            
            # Sort by sequence
            sorted_sections = sorted(sections, key=lambda s: s.get('sequence', 0))
            
            # Concatenate content
            template_parts = []
            for section in sorted_sections:
                content = section.get('content', '')
                if content:
                    template_parts.append(content)
            
            final_template = '\n\n'.join(template_parts)
            
            logger.debug(
                "db_service:template_built",
                extra={
                    "template_key": template_key,
                    "sections_count": len(sorted_sections),
                    "template_length": len(final_template)
                }
            )
            
            return final_template
        
        finally:
            db.close()
    
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(
            "db_service:fetch_template_error",
            extra={"template_key": template_key, "error": str(e)}
        )
        raise DatabaseError(
            message=f"Failed to fetch template: {str(e)}",
            error_code="DB_FETCH_ERROR",
            details={"template_key": template_key}
        ) from e
    
def fetch_next_narrative(session_id: str) -> Optional[str]:
    """
    Fetch next narrative guidance from previous turn.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Next narrative string or None if not found
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        db: Session = next(get_db())
        
        try:
            # Fetch session
            session = db.query(SessionModel).filter(
                SessionModel.id == session_id
            ).first()
            
            if not session:
                logger.warning(
                    "db_service:session_not_found",
                    extra={"session_id": session_id}
                )
                return None
            
            # Get next_narrative from session
            # TODO: Adjust based on your actual schema
            # This might be stored in a separate table or as a JSON field
            next_narrative = getattr(session, 'next_narrative', None)
            
            if next_narrative:
                logger.debug(
                    "db_service:next_narrative_found",
                    extra={"session_id": session_id, "narrative_length": len(next_narrative)}
                )
            else:
                logger.debug(
                    "db_service:next_narrative_not_found",
                    extra={"session_id": session_id}
                )
            
            return next_narrative
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(
            "db_service:fetch_next_narrative_error",
            extra={"session_id": session_id, "error": str(e)}
        )
        raise DatabaseError(
            message=f"Failed to fetch next narrative: {str(e)}",
            error_code="DB_FETCH_ERROR",
            details={"session_id": session_id}
        ) from e