"""Broadcast message routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.models.requests import BroadcastRequest
from api.models.responses import APIResponse
from db.db import get_db
from message_handler.handler import broadcast_message

router = APIRouter(prefix="/api", tags=["broadcast"])


@router.post("/broadcast")
def handle_broadcast(request: BroadcastRequest, db: Session = Depends(get_db)):
    """
    Send a broadcast message to multiple users.
    
    No try/except - exceptions bubble to centralized handler.
    """
    results = broadcast_message(
        db=db,
        content=request.content,
        instance_id=request.instance_id,
        user_ids=request.user_ids,
        trace_id=request.trace_id
    )
    
    return APIResponse.success(
        data={"results": results},
        message=f"Broadcast sent to {len(results)} recipients"
    )