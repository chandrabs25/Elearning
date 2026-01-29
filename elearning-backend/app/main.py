"""E-Learning Backend - Minimal Reset"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.graph.client import neo4j_client

# Initialize LangSmith tracing IMMEDIATELY (before importing agents)
from app.langsmith_config import init_langsmith
init_langsmith()

from app.api import chat
from app.api import converse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    yield

    # Shutdown logic
    await neo4j_client.close()

app = FastAPI(title="E-Learning Backend", lifespan=lifespan)

import os


cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    settings.frontend_url,
]

if os.getenv("VERCEL_URL"):
    cors_origins.append(f"https://{os.getenv('VERCEL_URL')}")
if os.getenv("ALLOWED_ORIGINS"):
    cors_origins.extend(os.getenv("ALLOWED_ORIGINS").split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat.router, prefix="/api")
app.include_router(converse.router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "alive"}
