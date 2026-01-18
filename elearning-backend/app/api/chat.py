from fastapi import APIRouter
from app.schemas.base import ChatRequest, ChatResponse
from app.config import settings
from langchain_groq import ChatGroq

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Bare minimum chat endpoint."""
    
    # 1. Connect to LLM (Proof of Connection)
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key
    )
    
    # 2. Simple Invoke
    response = await llm.ainvoke(request.message)
    
    return ChatResponse(message=response.content)
