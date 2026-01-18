"""
Vercel Serverless Function Entry Point for FastAPI Backend

This file serves as the entry point for Vercel's Python runtime.
It imports and exposes the FastAPI app from the elearning-backend.
"""
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_path = Path(__file__).parent.parent / "elearning-backend"
sys.path.insert(0, str(backend_path))

# Import the FastAPI app
from app.main import app

# Vercel will automatically detect this as an ASGI app
# The app variable is what Vercel looks for
