"""Message handling routes."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.models.requests import MessageRequest
from api.models.responses import APIResponse
from db.db import get_db
from message_handler.handler import process_message

# API router with /api prefix
api_router = APIRouter(prefix="/api", tags=["messages"])

# Web router with /web prefix
web_router = APIRouter(prefix="/web", tags=["web"])

# App router with /app prefix
app_router = APIRouter(prefix="/app", tags=["app"])


@api_router.post("/messages")
def handle_api_message(request: Request, msg_request: MessageRequest, db: Session = Depends(get_db)):
    """Process a message through the API channel."""
    request_id = getattr(request.state, "request_id", None) or msg_request.request_id

    result = process_message(
        db=db,
        content=msg_request.content,
        instance_id=msg_request.instance_id,
        user_details=msg_request.user_details.model_dump() if msg_request.user_details else None,
        request_id=request_id,
        trace_id=msg_request.trace_id,
        channel="api"
    )

    return APIResponse.success(
        data=result,
        message="Message processed successfully"
    )


@web_router.post("/messages")
def handle_web_message(request: Request, msg_request: MessageRequest, db: Session = Depends(get_db)):
    """Process a message through the web channel."""
    request_id = getattr(request.state, "request_id", None) or msg_request.request_id

    result = process_message(
        db=db,
        content=msg_request.content,
        instance_id=msg_request.instance_id,
        user_details=msg_request.user_details.model_dump() if msg_request.user_details else None,
        request_id=request_id,
        trace_id=msg_request.trace_id,
        channel="web"
    )

    return APIResponse.success(
        data=result,
        message="Web message processed successfully"
    )


@app_router.post("/messages")
def handle_app_message(request: Request, msg_request: MessageRequest, db: Session = Depends(get_db)):
    """Process a message through the mobile app channel."""
    request_id = getattr(request.state, "request_id", None) or msg_request.request_id

    result = process_message(
        db=db,
        content=msg_request.content,
        instance_id=msg_request.instance_id,
        user_details=msg_request.user_details.model_dump() if msg_request.user_details else None,
        request_id=request_id,
        trace_id=msg_request.trace_id,
        channel="app"
    )

    return APIResponse.success(
        data=result,
        message="App message processed successfully"
    )