from fastapi import APIRouter
from groq import AsyncGroq
from app.schemas.base import ChatRequest, ChatResponse
from app.config import settings

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Bare minimum chat endpoint."""
    
    # 1. Connect to LLM (Proof of Connection)
    client = AsyncGroq(api_key=settings.groq_api_key)
    
    # 2. Simple Invoke
    chat_completion = await client.chat.completions.create(
        messages=[{"role": "user", "content": request.message}],
        model="moonshotai/kimi-k2-instruct-0905",
    )
    
    return ChatResponse(message=chat_completion.choices[0].message.content)
