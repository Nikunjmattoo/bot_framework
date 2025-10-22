"""WhatsApp-specific routes."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.models.requests import WhatsAppMessageRequest
from api.models.responses import APIResponse
from db.db import get_db
from message_handler.handler import process_whatsapp_message

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.post("/messages")
def handle_whatsapp_message(request: Request, msg_request: WhatsAppMessageRequest, db: Session = Depends(get_db)):
    """
    Process a WhatsApp message.
    
    No try/except - exceptions bubble to centralized handler.
    """
    # Extract request_id from middleware-set state (fallback to body)
    request_id = getattr(request.state, "request_id", None) or msg_request.request_id
    
    result = process_whatsapp_message(
        db=db,
        whatsapp_message=msg_request.message,
        metadata=msg_request.metadata,
        instance_id=msg_request.instance_id,
        request_id=request_id,
        trace_id=msg_request.trace_id
    )
    
    return APIResponse.success(
        data=result,
        message="WhatsApp message processed successfully"
    )