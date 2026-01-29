"""LLM-based intent classification for tutor conversations."""
import json
import hashlib
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from app.cache import cache_get, cache_set


# Intent constants - matching the original TutorIntent enum
class Intent:
    CONTINUE_LEARNING = "CONTINUE"
    START_TOPIC = "TOPIC"
    ASK_DOUBT = "DOUBT"
    ASK_DERIVATION = "DERIVATION"
    ANSWER_QUESTION = "ANSWER"
    NAVIGATE = "NAVIGATE"
    SHOW_SUMMARY = "SUMMARY"
    ADD_CONTENT = "ADD_CONTENT"
    REMOVE_COMPONENT = "REMOVE"
    ADD_SUMMARY = "ADD_SUMMARY"
    OPEN_CHAT = "CHAT"
    TAKE_QUIZ = "QUIZ"
    GENERATE_MCQ = "MCQ"
    SHOW_EXERCISES = "EXERCISES"
    ANSWER_EXERCISE = "ANSWER_EXERCISE"
    UNKNOWN = "UNKNOWN"


# Map LLM response to TutorIntent
INTENT_MAP = {
    "CONTINUE": "continue_learning",
    "TOPIC": "start_topic",
    "DOUBT": "ask_doubt",
    "DERIVATION": "ask_derivation",
    "ANSWER": "answer_question",
    "NAVIGATE": "navigate",
    "SUMMARY": "show_summary",
    "ADD_CONTENT": "add_content",
    "REMOVE": "remove_component",
    "ADD_SUMMARY": "add_summary",
    "CHAT": "open_chat",
    "QUIZ": "take_quiz",
    "MCQ": "generate_mcq",
    "EXERCISES": "show_exercises",
    "ANSWER_EXERCISE": "answer_exercise",
    "UNKNOWN": "start_topic"  # Default fallback
}


async def classify_intent_with_section(message: str, context: dict = None) -> dict:
    """
    Combined LLM-based intent classification AND section resolution.
    Returns dict with:
        - intent: str (e.g., "start_topic", "add_content")
        - target_section_id: str | None (e.g., "7.2")
        - target_section_title: str | None
    """
    from app.config import settings
    from app.chains.content import get_table_of_contents
    
    context = context or {}
    
    # Check context-based intents first (no LLM needed)
    # Only shortcut to answer if actually in Answer mode (not Ask mode)
    if context.get("expecting_answer") and context.get("input_mode") != "ask":
        return {"intent": "answer_question", "target_section_id": None, "target_section_title": None}
    if context.get("expecting_exercise_answer") and context.get("input_mode") != "ask":
        return {"intent": "answer_exercise", "target_section_id": None, "target_section_title": None}
    
    # Try cache first (normalize message for better hit rate)
    # Include input_mode in cache key so Ask vs Answer modes don't conflict
    normalized_msg = message.lower().strip()
    input_mode = context.get("input_mode", "default")
    cache_key = f"intent:{input_mode}:{hashlib.md5(normalized_msg.encode()).hexdigest()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Get available sections for the LLM to choose from
    toc = get_table_of_contents()
    section_list = "\n".join([f"  - {s['id']}: {s['title']}" for s in toc[:15]])  # Limit to 15
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        api_key=settings.groq_api_key
    )
    
    prompt = f"""You are an intent classifier for an AI physics tutor. Analyze the user's message and return a JSON object.

User message: "{message}"

Available sections in the textbook:
{section_list}

Available intents:
- CONTINUE: User wants to continue, agrees, says yes/ok/sure
- NAVIGATE: User wants to go to next/previous section
- TOPIC: User wants to learn a topic (show lesson content)
- DOUBT: User has a specific question to be answered
- QUIZ: User wants a quiz
- MCQ: User wants multiple choice questions
- EXERCISES: User wants practice exercises
- DERIVATION: User wants formulas/derivations
- SUMMARY: User asks about their progress
- ADD_CONTENT: User wants to ADD content beside current view ("also show", "compare with")
- REMOVE: User wants to hide/remove a panel ("close", "hide")
- CHAT: User wants to open chat

Reply with ONLY valid JSON (no markdown, no explanation):
{{"intent": "INTENT_NAME", "section_id": "X.X or null", "section_title": "Title or null"}}

Rules:
1. If intent is TOPIC, ADD_CONTENT, or NAVIGATE, pick the BEST matching section from the list.
2. For TOPIC: Pick the section that best matches what user wants to learn.
3. For ADD_CONTENT: Pick the section user wants to ADD (not the current one).
4. For intents like QUIZ, DOUBT, CHAT: section_id can be null.
5. Prefer exact title matches. "Kepler's laws" → "7.2" not "7.1".
6. If user says "next" or "previous", set intent to NAVIGATE and section_id to null."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Try to parse JSON
        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        result = json.loads(content)
        intent_raw = result.get("intent", "UNKNOWN").upper()
        
        result_dict = {
            "intent": INTENT_MAP.get(intent_raw, "start_topic"),
            "target_section_id": result.get("section_id"),
            "target_section_title": result.get("section_title")
        }
        
        # Cache permanently (LRU eviction only)
        await cache_set(cache_key, result_dict)
        return result_dict
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}, content: {content}")
        # Fallback: try to extract intent from text
        return {"intent": _fallback_classify(message, context), "target_section_id": None, "target_section_title": None}
    except Exception as e:
        print(f"Intent classification error: {e}")
        return {"intent": _fallback_classify(message, context), "target_section_id": None, "target_section_title": None}


# Backward compatibility wrapper
async def classify_intent_llm(message: str, context: dict = None) -> str:
    """Legacy wrapper - returns just the intent string."""
    result = await classify_intent_with_section(message, context)
    return result["intent"]


def _fallback_classify(message: str, context: dict) -> str:
    """Simple keyword fallback if LLM fails."""
    msg = message.lower().strip()
    
    if msg in ["yes", "yeah", "continue", "ok", "sure"]:
        return "continue_learning"
    if any(w in msg for w in ["next", "previous", "go to"]):
        return "navigate"
    if any(w in msg for w in ["quiz me", "test me"]):
        return "take_quiz"
    if any(w in msg for w in ["mcq", "multiple choice"]):
        return "generate_mcq"
    if any(w in msg for w in ["exercise", "practice"]):
        return "show_exercises"
    if any(w in msg for w in ["formula", "derive", "equation"]):
        return "ask_derivation"
    if any(w in msg for w in ["progress", "summary", "how am i"]):
        return "show_summary"
    if any(w in msg for w in ["also", "add", "beside", "compare"]):
        return "add_content"
    if any(w in msg for w in ["close", "hide", "remove"]):
        return "remove_component"
    if any(w in msg for w in ["help", "doubt", "ask ai"]):
        return "open_chat"
    if "?" in msg:
        return "ask_doubt"
    
    return "start_topic"
