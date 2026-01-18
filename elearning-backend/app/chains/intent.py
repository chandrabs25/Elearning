"""Intent classification for tutor conversations."""
# Updated: Added more quiz keywords
from enum import Enum


class TutorIntent(str, Enum):
    """Possible intents from user messages."""
    CONTINUE_LEARNING = "continue_learning"  # "Yes, let's continue"
    START_TOPIC = "start_topic"              # "Teach me escape velocity"
    ASK_DOUBT = "ask_doubt"                  # "What's potential energy?"
    ASK_DERIVATION = "ask_derivation"        # "Show me the formula"
    ANSWER_QUESTION = "answer_question"      # User answering a quiz
    PIN_CONTENT = "pin_content"              # "Pin this on the left"
    NAVIGATE = "navigate"                    # "Go to next section"
    SHOW_SUMMARY = "show_summary"            # "Show my progress"
    ADD_CONTENT = "add_content"              # "Also show", "compare with", "beside this"
    REMOVE_COMPONENT = "remove_component"    # "Remove related topics", "hide sidebar"
    ADD_SUMMARY = "add_summary"              # "Add summary to screen", "show my progress here"
    OPEN_CHAT = "open_chat"                  # "Ask AI", "I have a doubt", "help me"
    TAKE_QUIZ = "take_quiz"                  # "Quiz me", "give me a problem"
    GENERATE_MCQ = "generate_mcq"            # "Give me some MCQs", "test me"
    SHOW_EXERCISES = "show_exercises"        # "Show exercises", "practice problems"
    ANSWER_EXERCISE = "answer_exercise"      # User answering an exercise
    UNKNOWN = "unknown"


def classify_intent(message: str, context: dict = None) -> TutorIntent:
    """
    Simple keyword-based intent classification.
    In production, replace with LLM-based classification.
    """
    msg = message.lower().strip()
    
    # Check for "show chapters/navigation" to restore panel (before remove check)
    show_nav_keywords = ["show chapter", "show navigation", "show sections", "show sidebar", 
                         "bring back chapter", "restore chapter", "restore navigation"]
    if any(word in msg for word in show_nav_keywords):
        return TutorIntent.CONTINUE_LEARNING  # Will rebuild with navigation
    
    # Check for remove component intent
    remove_keywords = ["remove", "hide", "close", "get rid of", "don't show", 
                       "less clutter", "dismiss", "take away"]
    # More specific component keywords to avoid false positives
    component_keywords = ["chapter section", "chapter panel", "sidebar", "navigation panel", 
                          "topics panel", "sections panel", "summary panel", "right panel", 
                          "left panel", "related topics", "chatbox", "chat box", "chat panel", 
                          "chat", "ai chat"]
    if any(r in msg for r in remove_keywords) and any(c in msg for c in component_keywords):
        return TutorIntent.REMOVE_COMPONENT
    
    # Check for add summary to current view (different from show_summary which replaces view)
    add_summary_keywords = ["add summary", "put summary", "summary here", "summary on screen",
                           "summary beside", "summary panel", "my progress here"]
    if any(word in msg for word in add_summary_keywords):
        return TutorIntent.ADD_SUMMARY
    
    # Check for exercise/practice intent
    exercise_keywords = ["exercises", "exercise", "practice problem", "chapter exercise", 
                         "related exercises", "show exercises", "practice"]
    if any(word in msg for word in exercise_keywords):
        return TutorIntent.SHOW_EXERCISES
    
    # Check if user is answering an exercise
    if context and context.get("expecting_exercise_answer"):
        return TutorIntent.ANSWER_EXERCISE
    
    # Check for quiz/problem solving (example problems from sections)
    # Check this BEFORE add_content to handle "open book quiz" correctly
    quiz_keywords = ["quiz me", "quiz", "give me a problem", "solve a problem", 
                     "test me", "challenge me", "example problem", "open book quiz",
                     "closed book quiz", "take a quiz", "start quiz"]
    mcq_keywords = ["mcq", "multiple choice", "give me mcq", "open book mcq", 
                    "closed book mcq", "multiple choice question"]
    
    # Check MCQ first (more specific)
    if any(word in msg for word in mcq_keywords):
        return TutorIntent.GENERATE_MCQ
    
    # Then check general quiz
    if any(word in msg for word in quiz_keywords):
        return TutorIntent.TAKE_QUIZ
    
    # Check for open chat intent (explicit request for chat panel only)
    open_chat_keywords = ["open chat", "add chat", "new chat", "chat panel",
                          "open ai chat", "add ai panel", "new panel"]
    if any(word in msg for word in open_chat_keywords):
        return TutorIntent.OPEN_CHAT
    
    # Check for add content (multi-panel) intent
    add_keywords = ["also", "beside", "alongside", "compare", "side by side", 
                    "on the side", "in another panel", "keep this", "at the same time",
                    "while keeping", "don't replace", "additionally"]
    if any(word in msg for word in add_keywords):
        return TutorIntent.ADD_CONTENT
    
    # Check for continuation
    if msg in ["yes", "yeah", "continue", "let's go", "sure", "ok"]:
        return TutorIntent.CONTINUE_LEARNING
    
    # Check for navigation
    if any(word in msg for word in ["next", "previous", "go to", "move to"]):
        return TutorIntent.NAVIGATE
    
    # Check for pinning
    if "pin" in msg:
        return TutorIntent.PIN_CONTENT
    
    # Check for derivation/formula requests
    if any(word in msg for word in ["derive", "formula", "equation", "show me how"]):
        return TutorIntent.ASK_DERIVATION
    
    # Check for summary (full view replacement)
    if any(word in msg for word in ["progress", "summary", "how am i doing"]):
        return TutorIntent.SHOW_SUMMARY
    
    # Check for topic teaching
    if any(word in msg for word in ["teach", "explain", "what is", "what's", "tell me about"]):
        return TutorIntent.START_TOPIC
    
    # Check if context expects an answer
    if context and context.get("expecting_answer"):
        return TutorIntent.ANSWER_QUESTION
    
    # Default to doubt/question
    if "?" in msg:
        return TutorIntent.ASK_DOUBT
    
    return TutorIntent.START_TOPIC  # Default: treat as topic request


def extract_component_to_remove(message: str) -> str | None:
    """Extract which component the user wants to remove."""
    msg = message.lower()
    
    # ChatPanel (chatbox, ai chat)
    if any(word in msg for word in ["chatbox", "chat box", "chat panel", "ai chat"]):
        return "ChatPanel"
    # Simple "chat" check - but be careful not to match "chapter"
    if "chat" in msg and "chapter" not in msg:
        return "ChatPanel"
    
    # NavigationMap (chapter sections panel on the right)
    if any(word in msg for word in ["chapter section", "chapter panel", "navigation", "sidebar", "topics panel", "sections panel", "right panel"]):
        return "NavigationMap"
    # Also check for "related topics" (old name)
    if "related" in msg and "topics" in msg:
        return "NavigationMap"
    
    if any(word in msg for word in ["summary", "progress"]):
        return "SummaryCard"
    if any(word in msg for word in ["derivation", "formula", "equation"]):
        return "DerivationBlock"
    if any(word in msg for word in ["explanation", "content", "main"]):
        return "ExplanationPanel"
    
    return None


def is_open_book_request(message: str) -> bool:
    """Check if user wants open book mode (content visible during quiz)."""
    msg = message.lower()
    open_book_keywords = ["open book", "openbook", "with content", "alongside", 
                          "keep content", "keep the content", "with the content",
                          "side by side", "while showing"]
    return any(word in msg for word in open_book_keywords)


def extract_topic_from_add_request(message: str) -> str | None:
    """Extract the topic/section ID from an add content request."""
    msg = message.lower()
    
    # Try to find section numbers like 7.1, 7.2, etc.
    import re
    section_match = re.search(r'(\d+\.?\d*)', msg)
    if section_match:
        return section_match.group(1)
    
    # Look for common topic keywords after add-intent keywords
    topic_keywords = ["derivation", "formula", "equation", "law", "theorem", 
                      "kepler", "newton", "gravitation", "escape velocity"]
    for keyword in topic_keywords:
        if keyword in msg:
            return keyword
    
    return None
