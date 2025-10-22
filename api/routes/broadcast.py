"""Broadcast message routes."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.models.requests import BroadcastRequest
from api.models.responses import APIResponse
from db.db import get_db
from message_handler.handler import broadcast_message

router = APIRouter(prefix="/api", tags=["broadcast"])


@router.post("/broadcast")
def handle_broadcast(request: Request, msg_request: BroadcastRequest, db: Session = Depends(get_db)):
    """
    Send a broadcast message to multiple users.
    
    No try/except - exceptions bubble to centralized handler.
    """
    # Extract request_id from middleware-set state (fallback to body)
    request_id = getattr(request.state, "request_id", None) or msg_request.request_id
    
    results = broadcast_message(
        db=db,
        content=msg_request.content,
        instance_id=msg_request.instance_id,
        user_ids=msg_request.user_ids,
        request_id=request_id,
        trace_id=msg_request.trace_id
    )
    
    return APIResponse.success(
        data=results,
        message=f"Broadcast sent to {results['summary']['total']} recipients"
    )