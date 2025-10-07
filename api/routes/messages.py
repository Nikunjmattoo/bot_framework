"""Message handling routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.models.requests import MessageRequest
from api.models.responses import APIResponse
from db.db import get_db
from message_handler.handler import process_message

router = APIRouter(prefix="/api", tags=["messages"])


@router.post("/messages")
def handle_api_message(request: MessageRequest, db: Session = Depends(get_db)):
    """
    Process a message through the API channel.
    
    No try/except - exceptions bubble to centralized handler.
    """
    result = process_message(
        db=db,
        content=request.content,
        instance_id=request.instance_id,
        user_details=request.user.dict() if request.user else None,
        idempotency_key=request.idempotency_key,
        trace_id=request.trace_id,
        channel="api"
    )
    
    return APIResponse.success(
        data=result,
        message="Message processed successfully"
    )


@router.post("/web/messages")
def handle_web_message(request: MessageRequest, db: Session = Depends(get_db)):
    """
    Process a message through the web channel.
    
    No try/except - exceptions bubble to centralized handler.
    """
    result = process_message(
        db=db,
        content=request.content,
        instance_id=request.instance_id,
        user_details=request.user.dict() if request.user else None,
        idempotency_key=request.idempotency_key,
        trace_id=request.trace_id,
        channel="web"
    )
    
    return APIResponse.success(
        data=result,
        message="Web message processed successfully"
    )


@router.post("/app/messages")
def handle_app_message(request: MessageRequest, db: Session = Depends(get_db)):
    """
    Process a message through the mobile app channel.
    
    No try/except - exceptions bubble to centralized handler.
    """
    result = process_message(
        db=db,
        content=request.content,
        instance_id=request.instance_id,
        user_details=request.user.dict() if request.user else None,
        idempotency_key=request.idempotency_key,
        trace_id=request.trace_id,
        channel="app"
    )
    
    return APIResponse.success(
        data=result,
        message="App message processed successfully"
    )