"""
Vercel Serverless Function Entry Point for FastAPI Backend
"""
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_path = Path(__file__).parent.parent / "elearning-backend"
sys.path.insert(0, str(backend_path))

# Import the FastAPI app - Vercel auto-detects 'app' variable
from app.main import app

# Handler for Vercel (required for some configurations)
handler = app
