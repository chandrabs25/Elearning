"""E-Learning Backend - Minimal Reset"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.graph.client import neo4j_client
from app.api import chat
from app.api import tutor
from app.api import converse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Note: Neo4j connection is lazy - connects on first query
    # This is necessary for Vercel serverless which doesn't support startup events well
    yield
    # Cleanup on shutdown (if applicable)
    await neo4j_client.close()

app = FastAPI(title="E-Learning Backend", lifespan=lifespan)

import os

# CORS origins - allow localhost for dev and production frontend
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    settings.frontend_url,
]
# In production, also allow the Vercel deployment URLs
if os.getenv("VERCEL_URL"):
    cors_origins.append(f"https://{os.getenv('VERCEL_URL')}")
if os.getenv("ALLOWED_ORIGINS"):
    cors_origins.extend(os.getenv("ALLOWED_ORIGINS").split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat.router, prefix="/api")
app.include_router(tutor.router, prefix="/api")
app.include_router(converse.router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "alive"}
