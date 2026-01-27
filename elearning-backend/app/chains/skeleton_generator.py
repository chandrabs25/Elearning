"""Skeleton UI generator for instant loading feedback."""
import json


def create_skeleton_ui(intent: str, section_title: str = None) -> dict:
    """Create a skeleton UI structure based on intent for instant feedback.
    
    This returns a minimal UI with loading states that can be rendered
    immediately while actual content is being fetched/generated.
    """
    
    # Base skeleton props
    loading_explanation = {
        "type": "ExplanationPanel",
        "props": {
            "loading": True,
            "title": section_title or "Loading...",
            "content": []
        }
    }
    
    loading_derivation = {
        "type": "DerivationBlock",
        "props": {
            "loading": True,
            "title": "Loading derivation...",
            "steps": []
        }
    }
    
    loading_quiz = {
        "type": "QuizCard",
        "props": {
            "loading": True,
            "question": "",
            "options": []
        }
    }
    
    loading_chat = {
        "type": "ChatPanel",
        "props": {
            "loading": True,
            "messages": []
        }
    }
    
    # Map intents to skeleton layouts
    skeletons = {
        "start_topic": {
            "layout": "focus",
            "panels": [loading_explanation],
            "loading": True
        },
        "add_content": {
            "layout": "split",
            "panels": [loading_explanation, loading_explanation],
            "loading": True
        },
        "derivation": {
            "layout": "focus",
            "panels": [loading_derivation],
            "loading": True
        },
        "quiz": {
            "layout": "focus",
            "panels": [loading_quiz],
            "loading": True
        },
        "open_chat": {
            "layout": "dynamic",
            "panels": [loading_explanation, loading_chat],
            "loading": True
        },
        "ask_doubt": {
            "layout": "dynamic",
            "panels": [loading_explanation, loading_chat],
            "loading": True
        }
    }
    
    # Return skeleton or default
    return skeletons.get(intent, {
        "layout": "focus",
        "panels": [loading_explanation],
        "loading": True
    })


def chunk_content(content: list, chunk_size: int = 1) -> list:
    """Split content items into chunks for progressive streaming.
    
    Args:
        content: List of content items (paragraphs, latex, etc.)
        chunk_size: Number of items per chunk
        
    Yields:
        Content item chunks
    """
    for i in range(0, len(content), chunk_size):
        yield content[i:i + chunk_size]


def chunk_text(text: str, words_per_chunk: int = 5) -> list:
    """Split text into word chunks for streaming effect.
    
    Args:
        text: Full text string
        words_per_chunk: Number of words per chunk
        
    Yields:
        Text chunks
    """
    words = text.split()
    for i in range(0, len(words), words_per_chunk):
        yield ' '.join(words[i:i + words_per_chunk])
