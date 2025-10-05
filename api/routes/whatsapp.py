"""WhatsApp-specific routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.models.requests import WhatsAppMessageRequest
from api.models.responses import APIResponse
from db.db import get_db
from message_handler.handler import process_whatsapp_message

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.post("/messages")
def handle_whatsapp_message(request: WhatsAppMessageRequest, db: Session = Depends(get_db)):
    """
    Process a WhatsApp message.
    
    No try/except - exceptions bubble to centralized handler.
    """
    result = process_whatsapp_message(
        db=db,
        whatsapp_message=request.message,
        metadata=request.metadata,
        instance_id=request.instance_id,
        trace_id=request.trace_id
    )
    
    return APIResponse.success(
        data=result,
        message="WhatsApp message processed successfully"
    )