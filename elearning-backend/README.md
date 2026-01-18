# E-Learning Backend

Python FastAPI backend for the E-Learning Platform using LangChain, LangGraph, and Neo4j.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Copy environment variables
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

## Run

```bash
# Development server with auto-reload
uvicorn app.main:app --reload --port 8000

# Or with specific host
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Evaluation
- `POST /api/evaluate` - Evaluate student explanation

### Hints
- `POST /api/hint` - Generate progressive hint

### Approach
- `POST /api/approach` - Evaluate problem-solving approach

### Graph (Neo4j)
- `GET /api/graph/concept/{id}` - Get concept
- `GET /api/graph/concept/{id}/full` - Get concept with prerequisites
- `GET /api/graph/concept/{id}/next` - Get next concept
- `GET /api/graph/concept/{id}/previous` - Get previous concept
- `GET /api/graph/concept/{id}/prerequisites` - Get all prerequisites
- `GET /api/graph/concept/{id}/exercises` - Get exercises for concept
- `GET /api/graph/learning-path` - Get learning path

### Health
- `GET /health` - Health check

## OpenAPI Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
