from pydantic import BaseModel
from typing import Optional, List, Any

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[dict] = {}

class ChatResponse(BaseModel):
    message: str
    data: Optional[Any] = None
