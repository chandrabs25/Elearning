"""LangSmith initialization for LLM tracing."""
import os
from app.config import settings


def init_langsmith():
    """Initialize LangSmith tracing if API key is configured.
    
    LangChain-based LLM calls (ChatGroq) are automatically traced.
    Direct SDK calls need @traceable decorator.
    """
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        print(f"[LangSmith] Tracing enabled for project: {settings.langchain_project}")
    else:
        print("[LangSmith] Tracing disabled (no API key)")
