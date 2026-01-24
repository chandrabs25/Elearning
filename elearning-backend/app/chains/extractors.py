"""Message data extraction utilities.
Extract specific data from user messages (component names, section IDs, flags).
For intent classification, see app/agents/intent_classifier.py
"""
import re


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
    
    # ExercisePanel
    if any(word in msg for word in ["exercise", "exercises", "practice"]):
        return "ExercisePanel"
    
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
