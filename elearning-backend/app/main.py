"""E-Learning Backend - Minimal Reset"""
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.graph.client import neo4j_client
from app.api import chat
from app.api import tutor
from app.api import converse

# Background task to keep the service alive on Render free tier
async def keep_alive_task():
    """Ping self every 12 minutes to prevent Render free tier from sleeping"""
    import os
    
    # Get the service URL from environment (Render sets RENDER_EXTERNAL_URL)
    service_url = os.getenv("RENDER_EXTERNAL_URL", "")
    
    if not service_url:
        print("⚠ RENDER_EXTERNAL_URL not set, keep-alive disabled")
        return
    
    print(f"✓ Keep-alive task started, pinging {service_url}/health every 12 minutes")
    
    while True:
        await asyncio.sleep(12 * 60)  # 12 minutes
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{service_url}/health", timeout=10)
                print(f"✓ Keep-alive ping: {response.status_code}")
        except Exception as e:
            print(f"⚠ Keep-alive ping failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB Connections on Start
    await neo4j_client.verify_connectivity()
    print("✓ Neo4j Connected")
    
    # Start keep-alive background task
    keep_alive = asyncio.create_task(keep_alive_task())
    
    yield
    
    # Cleanup
    keep_alive.cancel()
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
