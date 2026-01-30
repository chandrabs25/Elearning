"""Agent router for stateful tutor agent invocation.

Routes user messages through the LangGraph tutor agent with state persistence.
Thread ID is based on user_id to maintain conversation state per user.
"""
from langchain_core.messages import HumanMessage, AIMessage


async def invoke_tutor_agent(
    user_id: str,
    message: str,
    context: dict
) -> dict:
    """Route message through stateful tutor agent.
    
    Args:
        user_id: Unique user identifier
        message: User's message text
        context: Conversation context from frontend
        
    Returns:
        dict with 'messages', 'mode', and other state fields
    """
    from app.agents.tutor_agent import tutor_agent, TutorState
    
    # Thread ID = user_id (persists state per user)
    thread_id = f"tutor-{user_id}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Build initial state from context
    initial_state: TutorState = {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "current_concept_id": context.get("current_section") or context.get("current_concept_id"),
        "current_concept_title": context.get("section_title"),
        "concept_content": context.get("section_content"),  # Pre-loaded content if available
        "prerequisites": [],
        "insights": [],  # Will be populated by retrieve_context
        "active_misconceptions": [],  # Will be populated by analyze_student_context
        "active_competencies": [],
        "risk_concepts": [],
        "mode": context.get("agent_mode", "normal"),
        "current_prereq_id": context.get("current_prereq_id"),
        "current_prereq_title": context.get("current_prereq_title"),
        "prereq_question": context.get("prereq_question"),
        "prerequisite_chain": context.get("prerequisite_chain", []),
        "prereq_answer_correct": False,
        "max_depth": 3,
        "main_concept_id": None,  # Preserved when going deeper into prereqs
        "main_concept_title": None
    }
    
    # Invoke agent with persistence
    try:
        result = await tutor_agent.ainvoke(initial_state, config=config)
        return {
            "success": True,
            "messages": result.get("messages", []),
            "mode": result.get("mode", "normal"),
            "current_prereq_id": result.get("current_prereq_id"),
            "current_prereq_title": result.get("current_prereq_title"),
            "prereq_question": result.get("prereq_question"),
            "prerequisite_chain": result.get("prerequisite_chain", []),
            "response": _extract_last_ai_message(result.get("messages", []))
        }
    except Exception as e:
        print(f"Agent invocation error: {e}")
        return {
            "success": False,
            "messages": [],
            "mode": "normal",
            "response": "I'm having trouble processing your request. Please try again.",
            "error": str(e)
        }


def _extract_last_ai_message(messages: list) -> str:
    """Extract the last AI response from messages."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg.content
    return ""


async def reset_agent_state(user_id: str) -> bool:
    """Reset the agent state for a user (start fresh conversation).
    
    Note: With MemorySaver, this creates a new thread effectively.
    For persistent checkpointers, you'd delete the checkpoint.
    """
    # Simply use a new thread_id with timestamp to reset
    # Or implement checkpoint deletion for persistent stores
    return True
