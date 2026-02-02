"""LangSmith initialization for LLM tracing."""
import os
from app.config import settings


def init_langsmith():
    """Initialize LangSmith tracing if API key is configured.
    
    LangChain-based LLM calls (ChatGroq) are automatically traced.
    Direct SDK calls need @traceable decorator.
    
    Supports both:
    - LANGSMITH_API_KEY (via settings)
    - LANGCHAIN_API_KEY (standard LangSmith env variable)
    """
    # Check for API key from either settings or direct env variable
    api_key = settings.langsmith_api_key or os.environ.get("LANGCHAIN_API_KEY")
    
    if api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        print(f"[LangSmith] ✅ Tracing ENABLED for project: {settings.langchain_project}")
        print(f"[LangSmith]    API Key: {api_key[:8]}...{api_key[-4:]}")
    else:
        # Check if tracing is already enabled via env
        if os.environ.get("LANGCHAIN_TRACING_V2") == "true":
            print(f"[LangSmith] ✅ Tracing already enabled via environment")
        else:
            print("[LangSmith] ⚠️ Tracing DISABLED (no LANGCHAIN_API_KEY or LANGSMITH_API_KEY found)")

