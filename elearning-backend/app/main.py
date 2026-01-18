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
    # Verify DB Connections on Start
    await neo4j_client.verify_connectivity()
    print("✓ Neo4j Connected")
    yield
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
