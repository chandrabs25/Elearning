"""LLM-based intent classification for tutor conversations."""
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage


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


async def classify_intent_llm(message: str, context: dict = None) -> str:
    """
    LLM-based intent classification.
    Returns intent string matching TutorIntent values.
    """
    from app.config import settings
    
    context = context or {}
    
    # Check context-based intents first (no LLM needed)
    if context.get("expecting_answer"):
        return "answer_question"
    if context.get("expecting_exercise_answer"):
        return "answer_exercise"
    
    # Use LLM for everything else
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        api_key=settings.groq_api_key
    )
    
    prompt = f"""You are an intent classifier for an AI physics tutor. Classify the user's message into exactly ONE intent.

User message: "{message}"

Available intents:
- CONTINUE: User wants to continue, agrees, says yes/ok/sure
- NAVIGATE: User wants to go to next/previous section, go to a specific section
- TOPIC: User wants to START LEARNING a topic from the beginning. Examples: "teach me gravity", "explain Newton's laws", "what is escape velocity", "show me section 7.1"
- DOUBT: User has a SPECIFIC QUESTION that needs to be ANSWERED using the textbook. Examples: "why does the moon not fall?", "how do I calculate orbital velocity?", "I don't understand this formula", "what's the difference between weight and mass?"
- QUIZ: User wants a quiz, says "quiz me", "test me", "give me a problem"
- MCQ: User specifically wants multiple choice questions
- EXERCISES: User wants practice exercises from the chapter
- DERIVATION: User wants to see a formula, equation, or derivation step-by-step
- SUMMARY: User asks about their progress, "how am I doing"
- ADD_CONTENT: User wants to add content to current view, "also show", "beside this"
- REMOVE: User wants to hide/remove a panel
- CHAT: User wants to open chat, says "help me", "ask AI"

Reply with ONLY the intent name (e.g., "QUIZ" or "DOUBT"), nothing else.

CRITICAL INSTRUCTION FOR "TOPIC" vs "DOUBT":
- If the user asks for a DEFINITION or EXPLANATION of a main concept (e.g., "what is gravity", "explain escape velocity", "teach me potential energy"), classify as **TOPIC**. We want to show them the full lesson content, not just a chat answer.
- Only use **DOUBT** if the user asks a specific "WHY" or "HOW" question, a comparison, or a niche question that isn't a requesting a full topic.
- Bias: When in doubt, prefer TOPIC (showing content) over DOUBT (chat)."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        intent_raw = response.content.strip().upper()
        
        # Clean up response (in case LLM adds extra text)
        for intent in INTENT_MAP.keys():
            if intent in intent_raw:
                return INTENT_MAP[intent]
        
        # Default fallback
        return "start_topic"
    except Exception as e:
        print(f"Intent classification error: {e}")
        # Fallback to simple keyword matching
        return _fallback_classify(message, context)


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
    if any(w in msg for w in ["help", "doubt", "ask ai"]):
        return "open_chat"
    if "?" in msg:
        return "ask_doubt"
    
    return "start_topic"
