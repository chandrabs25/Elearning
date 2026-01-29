"""E-Learning Backend Configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    
    
    google_api_key: str = ""
    groq_api_key: str = ""
    huggingface_api_key: str = "" 
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS
    frontend_url: str = "http://localhost:3000"
    
    # LangSmith (optional - for LLM tracing)
    langsmith_api_key: str | None = None
    langchain_project: str = "elearning-tutor"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
