# AI Tutor Platform

An intelligent, interactive learning platform for NCERT Physics (Class 11 - Gravitation), powered by LLMs and a dynamic, component-based UI.

---

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                   │
│                         (Next.js / Vercel)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │  TutorPage   │───►│ DynamicPanel │───►│ Component Registry       │  │
│  │  (Orchestr.) │    │  (Renderer)  │    │ (WelcomeCard, QuizCard,  │  │
│  └──────────────┘    └──────────────┘    │  ExplanationPanel, etc.) │  │
│         │                                 └──────────────────────────┘  │
│         │ SSE / REST                                                    │
└─────────┼───────────────────────────────────────────────────────────────┘
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                    │
│                          (FastAPI / Fly.io)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    /api/tutor/converse                             │ │
│  │  ┌──────────────┐    ┌──────────────┐    ┌────────────────────┐   │ │
│  │  │ Intent       │───►│ Handler      │───►│ UI Schema          │   │ │
│  │  │ Classifier   │    │ Router       │    │ Generator          │   │ │
│  │  │ (LLM/Cache)  │    │ (Determin.)  │    │ (Pydantic Models)  │   │ │
│  │  └──────────────┘    └──────────────┘    └────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│         │                      │                                        │
│         ▼                      ▼                                        │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐  │
│  │ TutorAgent   │    │                DATA LAYER                    │  │
│  │ (LangGraph)  │    │  ┌────────────┐  ┌────────────┐  ┌────────┐ │  │
│  │              │    │  │ Neo4j      │  │ Redis      │  │ JSON   │ │  │
│  │ - Socratic   │    │  │ (Users,    │  │ (Cache,    │  │ (NCERT │ │  │
│  │   Flow       │    │  │  Concepts, │  │  Sessions, │  │  Text) │ │  │
│  │ - Exercise   │    │  │  Progress) │  │  TTS)      │  │        │ │  │
│  │   Evaluation │    │  └────────────┘  └────────────┘  └────────┘ │  │
│  └──────────────┘    └──────────────────────────────────────────────┘  │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        LLM PROVIDERS                              │  │
│  │              Groq (Llama 3.3 70B + Orpheus TTS)                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### Frontend (`elearning-platform/`)
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **Animations**: Framer Motion
- **Deployment**: Vercel

| Component | Purpose |
|-----------|---------|
| `TutorPage` | Main orchestrator - handles API calls, state, animations |
| `DynamicPanel` | Renders any panel type from backend UISchema |
| `ExplanationPanel` | Displays NCERT content with LaTeX rendering |
| `NavigationMap` | Chapter navigation with mastery indicators |
| `QuizCard` / `MCQCard` | Interactive assessment components |
| `ChatPanel` | Contextual Q&A with the AI tutor |

### Backend (`elearning-backend/`)
- **Framework**: FastAPI
- **Agent**: LangGraph (stateful Socratic tutor)
- **LLM**: Groq (Llama 3.3 70B)
- **Deployment**: Fly.io

| Module | Purpose |
|--------|---------|
| `converse.py` | Main API router - intent classification, UI generation |
| `tutor_agent.py` | LangGraph agent for Socratic teaching & exercise evaluation |
| `ui_generator.py` | Pydantic models for dynamic UI schemas |
| `user_state.py` | Neo4j user progress tracking |
| `redis_client.py` | Caching layer (intents, TTS, sessions) |

---

## Data Flow

1. **User Input** → Frontend sends message/action to `/api/tutor/converse`
2. **Intent Classification** → Deterministic (button) or LLM-based (free text)
3. **Handler Execution** → Appropriate handler fetches content, runs agent, etc.
4. **UI Schema Generation** → Returns `UISchema` with layout + panels
5. **Frontend Rendering** → `DynamicPanel` renders the response

---

## Key Features

- **Dynamic UI**: Server-driven UI composition - backend controls layout
- **Socratic Teaching**: Agent probes prerequisite understanding before explaining
- **Streaming**: SSE-based content streaming with skeleton loaders
- **Caching**: Redis caching for intents, user state, and TTS audio
- **Voice**: Text-to-speech via Groq Orpheus model

---

 