"""Main conversation endpoint for AI Tutor V2."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal
import json
import asyncio

from app.graph.user_state import (
    get_or_create_user,
    get_user_state,
    update_current_concept,
    get_last_session,
    get_weak_concepts,
    update_mastery,
    get_section_mastery,
    get_lifetime_progress,
    record_exercise_attempt,
    get_completed_exercises,
    record_chat_interaction
)
from app.graph.chat_history import (
    save_chat_message,
    get_chat_history,
    clear_chat_history
)
from app.chains.extractors import extract_topic_from_add_request, extract_component_to_remove, is_open_book_request, extract_highlight_terms
from app.chains.content import (
    get_section_by_id,
    get_related_sections,
    format_content_for_ui,
    search_sections_by_topic,
    get_table_of_contents,
    get_exercises_for_section,
    get_chapter_exercises,
    get_related_exercises,
    get_example_with_solution,
    get_next_section_id,
    get_section_title
)
from app.chains.ui_generator import (
    UISchema,
    PanelContent,
    ProgressData,
    CelebrationData,
    welcome_schema,
    explanation_schema,
    explanation_with_exercises_schema,
    quiz_schema,

    multi_panel_schema,
    chat_panel_schema,
    mcq_schema,
    feedback_schema,
    exercise_only_schema,
    celebration_schema
)


router = APIRouter()

# Mastery threshold for section completion
MASTERY_THRESHOLD = 70

# Default section ID for fallbacks (first section in gravity chapter)
DEFAULT_SECTION_ID = "7.1"


def get_current_section_id(user_state: dict, fallback: str = None) -> str:
    """Extract current section ID from user state with fallback."""
    if fallback is None:
        fallback = DEFAULT_SECTION_ID
    current = user_state.get("current_concept") if user_state else None
    return current.get("sectionId", current.get("id")) if current else fallback


def extract_mcq_option(answer: str) -> str:
    """Extract MCQ option letter (A, B, C, D) from various input formats.
    
    Handles: 'A', 'a', 'Option A', 'The answer is B', 'B)', 'b.', etc.
    """
    answer = answer.strip().upper()
    # Check for letter patterns
    for letter in ['A', 'B', 'C', 'D']:
        # Match standalone letter or "OPTION X" pattern
        if answer == letter or answer.startswith(f"OPTION {letter}") or answer.startswith(f"{letter}.") or answer.startswith(f"{letter})"):
            return letter
        # Match "THE ANSWER IS X" or similar
        if f" {letter}" in answer or answer.endswith(letter):
            return letter
    # Fallback: first character if it's a letter
    if answer and answer[0] in 'ABCD':
        return answer[0]
    return answer


from langsmith import traceable


@traceable(name="evaluate_mcq_answer")
async def evaluate_mcq_answer(
    question: str,
    options: list[str],
    correct_option: str,
    student_answer: str
) -> dict:
    """Use LLM to evaluate MCQ answer - judges both choice and reasoning.
    
    Returns:
        {
            "is_correct": bool,      # True if correct option chosen or reasoning is valid
            "is_partial": bool,      # True if reasoning shows understanding but wrong option
            "chosen_option": str,    # The option letter the student chose (A/B/C/D or None)
            "feedback": str          # LLM-generated feedback
        }
    """
    from groq import AsyncGroq
    from app.config import settings
    import json
    
    # Normalize correct option to letter
    correct_letter = extract_mcq_option(correct_option)
    
    # Format options for prompt
    options_text = "\n".join([f"{chr(65+i)}. {opt}" for i, opt in enumerate(options)]) if options else ""
    
    prompt = f"""You are evaluating a student's answer to a multiple-choice physics question.

QUESTION: {question}

OPTIONS:
{options_text}

CORRECT ANSWER: {correct_letter}

STUDENT'S RESPONSE: "{student_answer}"

Analyze the student's response and determine:
1. Did they explicitly or implicitly choose the correct option ({correct_letter})?
2. Even if they chose wrong, does their reasoning show correct understanding?

Return a JSON object:
{{
    "chosen_option": "A/B/C/D or null if unclear",
    "is_correct": true/false (true if correct option OR correct reasoning),
    "is_partial": true/false (true if wrong option but good reasoning),
    "feedback": "brief feedback explaining if correct/incorrect and why"
}}

Be generous with partial credit if the student shows understanding but picked wrong letter.
Return ONLY the JSON, no markdown."""
    
    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        # Clean JSON if wrapped in markdown
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        result = json.loads(content)
        return {
            "is_correct": result.get("is_correct", False),
            "is_partial": result.get("is_partial", False),
            "chosen_option": result.get("chosen_option"),
            "feedback": result.get("feedback", "Answer evaluated.")
        }
    except Exception as e:
        print(f"MCQ evaluation error: {e}")
        # Fallback to pattern matching
        user_letter = extract_mcq_option(student_answer)
        is_correct = user_letter == correct_letter
        return {
            "is_correct": is_correct,
            "is_partial": False,
            "chosen_option": user_letter,
            "feedback": f"{'Correct!' if is_correct else f'The correct answer was {correct_letter}.'}"
        }


def _maybe_create_celebration(concept_id: str, result: dict):
    """Create celebration schema if section was just mastered.
    
    Returns CelebrationData or None.
    """
    if result.get("completed") and result.get("new_level", 0) >= MASTERY_THRESHOLD:
        next_id = get_next_section_id(concept_id)
        next_title = get_section_title(next_id) if next_id else None
        section_title = get_section_title(concept_id) or concept_id
        return celebration_schema(
            section_title=section_title,
            mastery_percent=result["new_level"],
            next_section_id=next_id,
            next_section_title=next_title
        )
    return None


def _get_feedback_prompt(result: dict, is_correct: bool, is_partial: bool = False, question_type: str = "quiz") -> str:
    """Generate guided prompt based on answer result.
    
    Returns appropriate next_prompt string.
    """
    mastery = result.get("new_level", 0)
    
    if mastery >= MASTERY_THRESHOLD:
        return "🎉 Section mastered! Type 'next' to continue."
    
    if is_correct:
        return f"Excellent! {mastery}% mastery. Try 'quiz me' for more!"
    elif is_partial:
        return f"Almost there! {mastery}% mastery. Try again or ask for help."
    else:
        return f"Keep trying! {mastery}% mastery. Type 'explain' for help."


class ConversationRequest(BaseModel):
    user_id: str
    message: str = ""  # Free-form text (uses LLM)
    action: str | None = None  # Deterministic action from button click (skips LLM)
    pinned_left: str | None = None
    pinned_right: str | None = None
    context: dict = {}


# Map action strings to intent values
# Format: "action" -> "intent" for simple mappings
# Prefix-based actions (e.g., "start:7.3") are handled in action_check below
ACTION_TO_INTENT = {
    "next": "navigate",
    "previous": "navigate",
    "quiz": "take_quiz",
    "quiz me": "take_quiz",
    "take_quiz": "take_quiz",  # Frontend sends intent as action
    "open book quiz": "take_quiz_open",
    "mcq": "generate_mcq",
    "give me MCQs": "generate_mcq",
    "generate_mcq": "generate_mcq",  # Backend sends intent as action
    "open book MCQs": "generate_mcq_open",
    "exercises": "show_exercises",
    "show exercises": "show_exercises",
    "show_exercises": "show_exercises",  # Backend sends intent as action
    "continue": "continue_learning",
    "continue_learning": "continue_learning",  # Backend sends intent as action
    "summary": "show_summary",
    "chat": "open_chat",
    "open chat": "open_chat",
    "explain this": "explain_content",
    "show derivation": "show_derivation",
    "help me": "open_chat",
    "show my progress": "show_progress",
    "progress summary": "show_progress",
    "my progress": "show_progress",
    "progress": "show_progress",
    "remove chapter sections": "remove_component",
    "close chat": "remove_component",
    "close exercises": "remove_component",
    "close exercise": "remove_component",
    "close panel": "remove_component",
    "remove chat": "remove_component",
    "hide chat": "remove_component",
    "hide exercises": "remove_component",
    "show chapters": "show_chapters",
    "show topics": "show_chapters",
    "topics": "show_chapters",
    "focus": "focus_view",
}


ACTION_PREFIXES = {
    "start:": "start_topic",      # start:<section_id_or_title>
    "teach:": "start_topic",      # teach:<topic>
    "teach me ": "start_topic",   # teach me <section_id> (from NavigationMap/ProgressBar)
    "goto:": "navigate_to",       # goto:<section_id>
}


def parse_action(action_str: str) -> tuple[str | None, str | None]:
    """
    Parse an action string to extract intent and payload.
    Returns (intent, payload) or (None, None) if not a recognized action.
    """
    if not action_str:
        return None, None
    
    # Check exact match first
    if action_str in ACTION_TO_INTENT:
        return ACTION_TO_INTENT[action_str], action_str
    
    # Check prefix-based actions
    for prefix, intent in ACTION_PREFIXES.items():
        if action_str.startswith(prefix):
            payload = action_str[len(prefix):]
            return intent, payload
    
    return None, None


class ConversationResponse(BaseModel):
    ui: UISchema
    conversation_context: dict = {}
    debug: dict = {}


@router.post("/tutor/converse", response_model=ConversationResponse)
async def converse(req: ConversationRequest):
    """
    Main conversation endpoint. Processes user message and returns UI schema.
    Supports two modes:
    - action: Deterministic button click (skips LLM, fast)
    - message: Free-form text (uses LLM classifier)
    """
    # 1. Get or create user
    await get_or_create_user(req.user_id)
    user_state = await get_user_state(req.user_id)
    
    # 2. Determine intent - check action first (skips LLM for button clicks)
    context = {**req.context}
    action_payload = None
    
    # Check if user has a current section
    has_current_section = bool(user_state and user_state.get("current_concept"))
    
    # Helper to check if action looks like an MCQ option
    def is_mcq_option(action: str) -> bool:
        action_lower = action.lower().strip()
        # Match patterns like "Option A", "A", "1", etc.
        if action_lower.startswith("option "):
            return True
        if len(action_lower) == 1 and action_lower in "abcd1234":
            return True
        # Match the actual option text from MCQ (stored in context)
        options = context.get("options", [])
        return action in options
    
    if req.action:
        # First, check if this is a KNOWN deterministic action (navigation, quiz, etc.)
        intent, action_payload = parse_action(req.action)
        if intent:
            # Deterministic action found - use it regardless of quiz state
            message = action_payload if action_payload else req.action
        elif context.get("expecting_answer") and context.get("question_type") == "mcq" and is_mcq_option(req.action):
            # MCQ option click while expecting answer - treat as MCQ answer
            intent = "submit_mcq_answer"
            message = req.action
        else:
            # Unknown action - log warning and return error
            print(f"Warning: Unknown action '{req.action}' - not in ACTION_TO_INTENT")
            return ConversationResponse(
                ui=feedback_schema(
                    message=f"Unknown action: {req.action}",
                    status="info"
                ),
                conversation_context=context
            )
    elif context.get("focused_panel") in ("quiz", "mcq") and context.get("input_mode") == "answer":
        # Quiz/MCQ focused in Answer mode - ALL text is treated as an answer
        # Users should use buttons or toggle to Ask mode if they want to navigate
        intent = "submit_quiz_answer"
        message = req.message
        context["quiz_answer"] = req.message
    elif context.get("focused_panel") == "chat":
        # ChatPanel focused - route text through the Socratic agent
        intent = "chat_message"  # Routes to agent for Socratic teaching
        message = req.message
    else:
        # All other text - use LLM classifier to decide between:
        # - TOPIC: "Teach me gravity" → Show section (no RAG)
        # - DOUBT: "Why does the moon not fall?" → RAG answer
        # - Other intents: QUIZ, NAVIGATE, etc.
        from app.agents.intent_classifier import classify_intent_with_section
        result = await classify_intent_with_section(req.message, context)
        intent = result["intent"]
        # Store resolved section in context for handlers to use
        if result.get("target_section_id"):
            context["resolved_section_id"] = result["target_section_id"]
            context["resolved_section_title"] = result.get("target_section_title")
        message = req.message
        if intent == "ask_doubt":
            context["initial_question"] = message
    
    # 3. Route to handler using registry pattern
    # Define handler registry - maps intent to (handler, args_type)
    # args_type: "full" = (user_id, message, user_state, context)
    #            "no_msg" = (user_id, user_state, context)
    #            "no_state" = (user_id, message, context)
    #            "minimal" = (user_id, user_state)
    
    async def _route_to_handler():
        # Simple handlers with full signature
        if intent == "continue_learning":
            return await handle_continue(req.user_id, user_state, context)
        if intent == "start_topic":
            return await handle_start_topic(req.user_id, message, context)
        if intent == "navigate":
            return await handle_navigate(req.user_id, message, user_state, context)
        if intent == "ask_derivation":
            return await handle_derivation(req.user_id, message, user_state, context)
        if intent == "show_summary":
            return await handle_show_progress(req.user_id, user_state, context)  # Redirect to progress
        if intent == "answer_question":
            return await handle_answer(req.user_id, message, context)
        if intent == "add_content":
            return await handle_add_content(req.user_id, message, user_state, context)
        if intent == "remove_component":
            return await handle_remove_component(req.user_id, message, user_state, context)
        if intent == "add_summary":
            return await handle_add_summary(req.user_id, user_state, context)
        if intent == "open_chat":
            # Button click - just open the chat panel (no agent)
            return await handle_open_chat(req.user_id, user_state, context)
        if intent == "chat_message" or intent == "ask_doubt":
            # Text in chat panel or doubt from main - route through agent
            context["initial_question"] = message
            return await handle_agent_chat(req.user_id, message, user_state, context)
        if intent == "take_quiz":
            return await handle_quiz_request(req.user_id, message, user_state, context)
        if intent == "generate_mcq":
            return await handle_mcq_request(req.user_id, message, user_state, context)
        if intent == "submit_quiz_answer":
            return await handle_quiz_answer(req.user_id, message, context)
        if intent == "submit_mcq_answer":
            return await handle_answer(req.user_id, message, context)
        if intent == "show_exercises":
            return await handle_show_exercises(req.user_id, message, user_state, context)
        if intent == "answer_exercise":
            return await handle_exercise_answer(req.user_id, message, context)
        if intent == "navigate_to":
            return await handle_navigate(req.user_id, f"go to {message}", user_state, context)
        if intent == "explain_content":
            return await handle_answer(req.user_id, "explain the current section in detail", context)
        if intent == "show_derivation":
            return await handle_derivation(req.user_id, "show derivation", user_state, context)
        if intent == "show_progress":
            return await handle_show_progress(req.user_id, user_state, context)
        if intent == "show_chapters":
            return await handle_add_content(req.user_id, "show chapters", user_state, context)
        if intent == "focus_view":
            return await handle_remove_component(req.user_id, "focus", user_state, context)
        if intent == "take_quiz_open":
            context["open_book"] = True
            return await handle_quiz_request(req.user_id, message, user_state, context)
        if intent == "generate_mcq_open":
            context["open_book"] = True
            return await handle_mcq_request(req.user_id, message, user_state, context)
        
        # Default: treat as topic request
        return await handle_start_topic(req.user_id, message, context)
    
    return await _route_to_handler()


@router.post("/tutor/converse/stream")
async def converse_stream(req: ConversationRequest):
    """
    Streaming version of converse endpoint.
    Uses Server-Sent Events (SSE) for progressive UI rendering:
    1. Sends skeleton UI immediately
    2. Streams content chunks progressively
    3. Sends complete signal when done
    """
    from app.chains.skeleton_generator import create_skeleton_ui, chunk_content
    from app.agents.intent_classifier import classify_intent_with_section
    
    async def generate():
        try:
            # 1. Get user state
            await get_or_create_user(req.user_id)
            user_state = await get_user_state(req.user_id)
            context = {**req.context}
            
            # 2. Quick intent classification for skeleton
            intent = "start_topic"  # Default
            section_title = None
            
            if req.action:
                intent, _ = parse_action(req.action)
                intent = intent or "start_topic"
            else:
                result = await classify_intent_with_section(req.message, context)
                intent = result["intent"]
                section_title = result.get("target_section_title")
                if result.get("target_section_id"):
                    context["resolved_section_id"] = result["target_section_id"]
            
            # 3. Send skeleton immediately
            skeleton = create_skeleton_ui(intent, section_title)
            yield f"data: {json.dumps({'type': 'skeleton', 'ui': skeleton})}\n\n"
            
            # Small delay to ensure skeleton renders
            await asyncio.sleep(0.05)
            
            # 4. Process the actual request (reuse existing logic)
            # Create a fake request to call the main handler
            full_response = await converse(req)
            # Use mode='json' to ensure datetimes are serialized to strings
            ui_dict = full_response.ui.model_dump(mode='json')
            
            # 5. Stream content for each panel
            for panel_idx, panel in enumerate(ui_dict.get("panels", [])):
                props = panel.get("props", {})
                content = props.get("content", [])
                
                # Handle LIST content (e.g. ExplanationPanel)
                if content and isinstance(content, list):
                    # Stream content items one by one
                    for chunk_idx, item in enumerate(content):
                        chunk_event = {
                            "type": "content_chunk",
                            "panel_index": panel_idx,
                            "chunk_index": chunk_idx,
                            "chunk": item
                        }
                        yield f"data: {json.dumps(chunk_event)}\n\n"
                        await asyncio.sleep(0.03)  # Smooth animation
                
                # Handle STRING content (e.g. ChatPanel) - optional streaming
                elif content and isinstance(content, str):
                    # For now just send the full string as one chunk? 
                    # Real streaming would require chunk_text helper
                    pass 

            # 6. Send complete signal with final UI
            # Ensure context is also serializable (though mode='json' doesn't help dicts, Pydantic v2 handles it if mapped)
            # But context is a raw dict. Best is to rely on Pydantic or use default=str
            yield f"data: {json.dumps({'type': 'complete', 'ui': ui_dict, 'context': full_response.conversation_context}, default=str)}\n\n"
            
        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/tutor/init/{user_id}")
async def init_session(user_id: str):
    """Initialize a tutor session - returns welcome screen with progress."""
    await get_or_create_user(user_id)
    last_session = await get_last_session(user_id)
    user_state = await get_user_state(user_id)
    
    # Get last section info for continue button
    last_section = None
    if user_state and user_state.get("current_concept"):
        current = user_state.get("current_concept")
        section_id = current.get("sectionId", current.get("id"))
        section = get_section_by_id(section_id) if section_id else None
        if section:
            last_section = {
                "id": section_id,
                "title": section.get("section_title", "Continue Learning")
            }
    
    # DEMO DEFAULT: If no history, default to section 7.3 (user has covered 7.1 and 7.2)
    if last_section is None:
        demo_section = get_section_by_id("7.3")
        if demo_section:
            last_section = {
                "id": "7.3",
                "title": demo_section.get("section_title", "Universal Law of Gravitation")
            }
    
    # Get progress data
    toc = get_table_of_contents()
    section_ids = [item["id"] for item in toc if not item["id"].startswith("SUMMARY") and item["id"] != "Points to ponder" and item["id"] != "Exercises"]
    progress_data = await get_lifetime_progress(user_id, section_ids)
    
    # DEMO DEFAULT: Set demo progress for sections 7.1 and 7.2 if no real progress
    demo_sections_progress = []
    for item in toc:
        if item["id"].startswith("SUMMARY") or item["id"] == "Points to ponder" or item["id"] == "Exercises":
            continue
        
        real_mastery = next((s["mastery"] for s in progress_data.get("sections_progress", []) if s["id"] == item["id"]), 0)
        real_completed = next((s["completed"] for s in progress_data.get("sections_progress", []) if s["id"] == item["id"]), False)
        
        # Demo defaults: 7.1 and 7.2 are completed with high mastery
        if real_mastery == 0 and item["id"] in ["7.1", "7.2"]:
            demo_sections_progress.append({
                "id": item["id"],
                "title": item["title"],
                "mastery": 85 if item["id"] == "7.1" else 78,
                "completed": True
            })
        else:
            demo_sections_progress.append({
                "id": item["id"],
                "title": item["title"],
                "mastery": real_mastery,
                "completed": real_completed
            })
    
    ui = welcome_schema(last_section=last_section)
    
    # Calculate demo lifetime mastery
    total_mastery = sum(s["mastery"] for s in demo_sections_progress)
    num_sections = len(demo_sections_progress)
    demo_lifetime = total_mastery // num_sections if num_sections > 0 else 0
    
    # Add progress to UI
    ui.progress = ProgressData(
        lifetime_mastery=demo_lifetime if progress_data.get("lifetime_mastery", 0) == 0 else progress_data.get("lifetime_mastery", 0),
        sections_progress=demo_sections_progress
    )
    
    return ConversationResponse(
        ui=ui,
        conversation_context={
            "has_history": last_section is not None,
            "current_concept": user_state.get("current_concept") if user_state else None
        }
    )


@router.get("/tutor/progress/{user_id}")
async def get_progress(user_id: str):
    """Get user's lifetime progress including exploration points."""
    from app.graph.user_state import get_exploration_points
    
    toc = get_table_of_contents()
    section_ids = [item["id"] for item in toc if item["id"].startswith("7.")]
    progress_data = await get_lifetime_progress(user_id, section_ids)
    exploration_points = await get_exploration_points(user_id)
    
    return {
        "lifetime_mastery": progress_data.get("lifetime_mastery", 0),
        "exploration_points": exploration_points,
        "sections_progress": [
            {
                "id": item["id"],
                "title": item["title"],
                "mastery": next((s["mastery"] for s in progress_data.get("sections_progress", []) if s["id"] == item["id"]), 0),
                "completed": next((s["completed"] for s in progress_data.get("sections_progress", []) if s["id"] == item["id"]), False)
            }
            for item in toc
            if item["id"].startswith("7.")
        ]
    }




class ChatMessage(BaseModel):
    role: str  
    content: list | str  # Can be string or list of content items


class ChatPanelRequest(BaseModel):
    user_id: str
    message: str
    context: dict = {}
    history: list[ChatMessage] = []


class ChatPanelResponse(BaseModel):
    message: ChatMessage
    suggestions: list[str] = []
    mastery_update: dict | None = None


@router.post("/tutor/chat", response_model=ChatPanelResponse)
async def chat_panel_message(req: ChatPanelRequest):
    """
    Handle messages sent from the ChatPanel using LangGraph agent.
    Uses Neo4j for prerequisite traversal and maintains conversation context.
    """
    from app.agents.tutor_agent import tutor_agent, TutorState
    from langchain_core.messages import HumanMessage, AIMessage
    
    section_id = req.context.get("current_section_id")
    section_title = req.context.get("current_section_title", "Gravitation")
    
    # Record chat interaction for mastery tracking
    mastery_result = None
    if section_id:
        mastery_result = await record_chat_interaction(req.user_id, section_id, "relevant")
    
    # Convert history to LangChain messages
    history_messages = []
    for msg in req.history[-5:]:  # Last 5 messages for context
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if msg.role == "user":
            history_messages.append(HumanMessage(content=content))
        else:
            history_messages.append(AIMessage(content=content))
    
    # Add current message
    history_messages.append(HumanMessage(content=req.message))
    
    # Check if RAG-retrieved sections are available
    retrieved_sections = req.context.get("retrieved_sections", [])
    
    # If we have retrieved sections, format them as context
    if retrieved_sections and isinstance(retrieved_sections[0], dict):
        from app.chains.content_search import format_retrieved_content
        rag_content = format_retrieved_content(retrieved_sections)
        # Use the first matched section as the "current" for tracking
        primary_section = retrieved_sections[0]
        section_id = primary_section.get("section_id", section_id or "7.3")
        section_title = primary_section.get("title", section_title)
    else:
        # Fallback: Load section content from section_id
        rag_content = None
        if section_id:
            section_data = get_section_by_id(section_id)
            if section_data:
                section_title = section_data.get("section_title", section_title)
                content = format_content_for_ui(section_data)
                rag_content = f"Current Section: {section_title}\n\n{content}"
    
    # Build initial state for LangGraph agent
    initial_state: TutorState = {
        "messages": history_messages,
        "user_id": req.user_id,
        "current_concept_id": section_id or "7.3",
        "current_concept_title": section_title,
        "concept_content": rag_content,  # Pre-populated from RAG if available
        "prerequisites": [],
        "needs_prerequisite": False,
        "prerequisite_chain": [],
        "confusion_detected": False
    }
    
    try:
        # Build config with thread_id for checkpointer
        thread_id = f"chat-{req.user_id}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Run the LangGraph agent
        final_state = await tutor_agent.ainvoke(initial_state, config=config)
        
        # Extract the last AI message
        ai_messages = [m for m in final_state.get("messages", []) if isinstance(m, AIMessage)]
        response_text = ai_messages[-1].content if ai_messages else "I'm here to help! What would you like to know?"
        
        # Parse response for rich content
        main_content, suggestions = parse_response_with_suggestions(response_text)
        content_items = parse_response_to_content(main_content)
        
        # Generate contextual suggestions based on state
        if not suggestions or suggestions == ["Can you explain this with an example?", "What's the key formula here?", "Quiz me on this!"]:
            prereq_chain = final_state.get("prerequisite_chain", [])
            if prereq_chain:
                suggestions = [
                    f"Tell me more about {prereq_chain[-1]}",
                    f"How does this connect to {section_title}?",
                    "I understand now, continue with the main topic"
                ]
            else:
                suggestions = [
                    "Can you show me an example?",
                    "What are the key formulas?",
                    "Quiz me on this topic"
                ]
        
        # Save messages to history (persist conversation)
        if section_id:
            # Save user message
            await save_chat_message(
                user_id=req.user_id,
                section_id=section_id,
                role="user",
                content=req.message
            )
            # Save assistant message
            await save_chat_message(
                user_id=req.user_id,
                section_id=section_id,
                role="assistant",
                content=content_items
            )
        
        return ChatPanelResponse(
            message=ChatMessage(
                role="assistant",
                content=content_items
            ),
            suggestions=suggestions[:3],
            mastery_update=mastery_result
        )
    
    except Exception as e:
        print(f"LangGraph agent error: {e}")
        # Fallback to simple response
        return ChatPanelResponse(
            message=ChatMessage(
                role="assistant",
                content=[{"type": "text", "text": f"I encountered an issue processing your question. Could you please rephrase it? (Error: {str(e)})"}]
            ),
            suggestions=["Try asking differently", "Explain the concept", "Show an example"],
            mastery_update=mastery_result
        )


class ChatHistoryResponse(BaseModel):
    """Response model for chat history endpoint."""
    messages: list[dict]
    section_id: str
    count: int


@router.get("/tutor/chat/history/{user_id}/{section_id}", response_model=ChatHistoryResponse)
async def get_section_chat_history(user_id: str, section_id: str, limit: int = 20):
    """
    Get chat history for a specific user and section.
    
    Args:
        user_id: The user's ID
        section_id: The section/concept ID (e.g., "7.2")
        limit: Maximum number of messages to return (default 20)
    
    Returns:
        List of chat messages for the section
    """
    messages = await get_chat_history(user_id, section_id, limit)
    
    return ChatHistoryResponse(
        messages=messages,
        section_id=section_id,
        count=len(messages)
    )


@router.delete("/tutor/chat/history/{user_id}/{section_id}")
async def delete_section_chat_history(user_id: str, section_id: str):
    """
    Clear chat history for a specific user and section.
    
    Args:
        user_id: The user's ID
        section_id: The section/concept ID
    
    Returns:
        Success status
    """
    await clear_chat_history(user_id, section_id)
    return {"success": True, "message": f"Chat history cleared for section {section_id}"}


def parse_response_to_content(text: str) -> list:
    """Parse LLM response into structured content items with LaTeX support."""
    import re
    
    items = []
    
    # Split by block equations ($$...$$)
    parts = re.split(r'(\$\$[^$]+\$\$)', text)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        if part.startswith('$$') and part.endswith('$$'):
            # Block equation
            latex = part[2:-2].strip()
            items.append({
                "type": "latex",
                "content": latex
            })
        else:
            # Check for inline equations and regular text
            # Split paragraphs
            paragraphs = part.split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if para:
                    items.append({
                        "type": "text",
                        "text": para
                    })
    
    return items if items else [{"type": "text", "text": text}]


def parse_response_with_suggestions(text: str) -> tuple[str, list[str]]:
    """
    Parse LLM response to extract main content and suggestions.
    Returns (main_content, suggestions_list).
    """
    import re
    
    # Default suggestions in case parsing fails
    default_suggestions = [
        "Can you explain this with an example?",
        "What's the key formula here?",
        "Quiz me on this!"
    ]
    
    # Try to split on the suggestions marker
    if "---SUGGESTIONS---" in text:
        parts = text.split("---SUGGESTIONS---")
        main_content = parts[0].strip()
        suggestions_text = parts[1].strip() if len(parts) > 1 else ""
        
        # Parse numbered suggestions
        suggestions = []
        lines = suggestions_text.split("\n")
        for line in lines:
            line = line.strip()
            # Match patterns like "1. ", "2. ", "3. " or "1) ", "2) ", etc.
            match = re.match(r'^[\d]+[\.\)]\s*(.+)$', line)
            if match:
                suggestion = match.group(1).strip()
                if suggestion:
                    suggestions.append(suggestion)
        
        return main_content, suggestions[:3] if suggestions else default_suggestions
    
    # Fallback: return full text and default suggestions
    return text, default_suggestions


# === Intent Handlers ===

async def handle_continue(user_id: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'continue learning' intent."""
    current = user_state.get("current_concept") if user_state else None
    
    if current:
        section = get_section_by_id(current.get("sectionId", current.get("id")))
        if section:
            return await _build_explanation_response(
                user_id, section, context, 
                intro_message="Let's continue where we left off. "
            )
    
    # No history - start from beginning
    section = get_section_by_id(DEFAULT_SECTION_ID)
    if section:
        await update_current_concept(user_id, DEFAULT_SECTION_ID)
        return await _build_explanation_response(user_id, section, context)
    
    raise HTTPException(status_code=500, detail="Content not found")


async def handle_start_topic(user_id: str, message: str, context: dict) -> ConversationResponse:
    """Handle topic teaching request."""
    # 1. Check if LLM already resolved the section (from combined classifier)
    if context.get("resolved_section_id"):
        section_id = context["resolved_section_id"]
        section = get_section_by_id(section_id)
        if section:
            await update_current_concept(user_id, section_id)
            return await _build_explanation_response(user_id, section, context)
    
    # 2. Check if message contains a direct section ID (e.g., "7.2", "teach me 7.2")
    #    This MUST come before fuzzy search to handle NavigationMap/ProgressBar clicks
    words = message.split()
    for word in words:
        if word.startswith("7."):
            section = get_section_by_id(word)
            if section:
                await update_current_concept(user_id, word)
                return await _build_explanation_response(user_id, section, context)
    
    # 3. Fallback: Try fuzzy search for topic name (for natural language requests)
    matches = search_sections_by_topic(message)
    
    if matches:
        section_id = matches[0]["id"]
        section = get_section_by_id(section_id)
        
        if section:
            await update_current_concept(user_id, section_id)
            return await _build_explanation_response(user_id, section, context)
    
    # Fallback: show table of contents
    toc = get_table_of_contents()
    return ConversationResponse(
        ui=UISchema(
            layout="focus",
            panels=[{
                "type": "NavigationMap",
                "props": {
                    "title": "I couldn't find that topic. Here's what we can explore:",
                    "sections": toc[:10]
                },
                "animation": "fadeIn"
            }]
        ),
        conversation_context={"last_search": message}
    )



async def handle_navigate(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle navigation requests (next, previous, go to)."""
    msg = message.lower()
    
    current_id = get_current_section_id(user_state, DEFAULT_SECTION_ID)
    
    if "next" in msg:
        # Get next section
        related = get_related_sections(current_id)
        next_section = next((r for r in related if r.get("relation") == "next"), None)
        
        if next_section:
            section = get_section_by_id(next_section["id"])
            if section:
                await update_current_concept(user_id, next_section["id"])
                return await _build_explanation_response(user_id, section, context)
    
    elif "previous" in msg or "back" in msg:
        related = get_related_sections(current_id)
        prev_section = next((r for r in related if r.get("relation") == "previous"), None)
        
        if prev_section:
            section = get_section_by_id(prev_section["id"])
            if section:
                await update_current_concept(user_id, prev_section["id"])
                return await _build_explanation_response(user_id, section, context)
    
    # Check for specific section reference
    return await handle_start_topic(user_id, message, context)


async def handle_derivation(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle derivation/formula requests."""
    current_id = get_current_section_id(user_state, "7.3")  # Default to 7.3 for derivations
    
    section = get_section_by_id(current_id)
    if not section:
        section = get_section_by_id("7.3")  # Fallback to universal law (derivation-heavy)
    
    # Detect step-by-step mode request
    msg_lower = message.lower()
    step_by_step = any(kw in msg_lower for kw in ["step by step", "step-by-step", "one step at a time", "slowly", "one at a time"])
    
    # Extract derivations from section
    derivations = [
        item for item in section.get("content", [])
        if item.get("type") == "derivation"
    ]
    
    if derivations:
        return ConversationResponse(
            ui=UISchema(
                layout="focus",
                panels=[{
                    "type": "DerivationBlock",
                    "props": {
                        "title": f"Derivation from {section['section_title']}",
                        "derivations": [
                            {"latex": d["latex"], "description": d.get("meta", "")}
                            for d in derivations
                        ],
                        "stepByStep": step_by_step  # Enable carousel mode when requested
                    },
                    "animation": "fadeIn"
                }]
            ),
            conversation_context={"showing_derivation": True, "section_id": current_id, "step_by_step": step_by_step}
        )
    
    return await handle_start_topic(user_id, message, context)





async def handle_show_progress(user_id: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle show progress request - displays section mastery overview."""
    # Get progress data
    toc = get_table_of_contents()
    section_ids = [item["id"] for item in toc if not item["id"].startswith("SUMMARY") and item["id"] not in ["Points to ponder", "Exercises", "PHYSICAL_QUANTITIES_TABLE", "POINTS_TO_PONDER"]]
    
    # Build sections progress
    sections_progress = []
    total_mastery = 0
    
    for section_id in section_ids:
        mastery = await get_section_mastery(user_id, section_id)
        title = get_section_title(section_id) or section_id
        sections_progress.append({
            "id": section_id,
            "title": title,
            "mastery": mastery,
            "completed": mastery >= 70
        })
        total_mastery += mastery
    
    avg_mastery = total_mastery / len(section_ids) if section_ids else 0
    
    # Create progress panel
    progress_data = ProgressData(
        lifetime_mastery=avg_mastery,
        current_section_id=context.get("current_section"),
        current_section_mastery=0,
        sections_progress=sections_progress
    )
    
    ui = UISchema(
        layout="focus",
        panels=[
            PanelContent(
                type="ProgressCard",
                props={
                    "title": "Your Progress",
                    "sections": sections_progress,
                    "lifetime_mastery": avg_mastery
                },
                role="primary",
                animation="fadeIn"
            )
        ],
        input_placeholder="What would you like to learn next?",
        progress=progress_data,
        suggested_actions=[
            {"label": "Continue Learning", "action": "continue", "primary": True},
            {"label": "Practice Weak Areas", "action": "exercises"},
        ]
    )
    
    return ConversationResponse(
        ui=ui,
        conversation_context={"showing_progress": True}
    )


async def handle_answer(user_id: str, answer: str, context: dict) -> ConversationResponse:
    """Handle quiz/MCQ answer evaluation."""
    question_type = context.get("question_type", "open")
    concept_id = context.get("current_section", DEFAULT_SECTION_ID)
    
    # 1. Handle MCQ Answer - Use LLM to evaluate choice AND reasoning
    if question_type == "mcq":
        question = context.get("question", "")
        options = context.get("options", [])  # The list of option texts
        correct_option = context.get("correct_option", "")  # e.g., "B" or "Option B"
        
        # Use LLM to evaluate - it can judge reasoning even if letter is wrong
        evaluation = await evaluate_mcq_answer(
            question=question,
            options=options,
            correct_option=correct_option,
            student_answer=answer
        )
        
        is_correct = evaluation["is_correct"]
        is_partial = evaluation["is_partial"]
        feedback = evaluation["feedback"]
        
        # Score based on correctness
        if is_correct:
            delta = 10
            status = "success"
            feedback = f"✅ {feedback}"
        elif is_partial:
            delta = 5  # Partial credit for good reasoning
            status = "warning"
            feedback = f"⚠️ {feedback}"
        else:
            delta = -5
            status = "error"
            feedback = f"❌ {feedback}"
        
        # Update mastery
        result = await update_mastery(user_id, concept_id, delta)
        
        # Use helpers for celebration and prompt
        celebration = _maybe_create_celebration(concept_id, result)
        next_prompt = _get_feedback_prompt(result, is_correct, is_partial)
        
        ui = feedback_schema(
            message=feedback,
            status=status,
            mastery_change=delta,
            new_mastery=result["new_level"],
            actions=[
                {"label": "Next Question", "action": "generate_mcq"},
                {"label": "Back to Learning", "action": "continue"}
            ]
        )
        ui.celebration = celebration
        ui.next_prompt = next_prompt
        ui.input_placeholder = "Type 'quiz me' for another question, or ask for help..."
        
        return ConversationResponse(
            ui=ui,
            conversation_context={
                "answered": True,
                "expecting_answer": False,  # Clear so buttons work normally
                "question_type": None,      # Clear quiz state
                "new_mastery": result["new_level"],
                "section_completed": result["completed"]
            }
        )

    # 2. Handle Open-Ended Problem Solving (Quiz) - Use agent
    else:
        from app.agents.tutor_agent import evaluate_quiz_answer

        solution = context.get("solution_meta") or context.get("solution_latex") or ""
        question = context.get("question", "")
        
        # Use agent to evaluate
        evaluation = await evaluate_quiz_answer(
            question=question,
            solution=solution,
            student_answer=answer
        )
        
        is_correct = evaluation["is_correct"]
        is_partial = evaluation["is_partial"]
        feedback_msg = evaluation["feedback"]
        
        if is_correct:
            delta = 15
            status = "success"
        elif is_partial:
            delta = 5
            status = "warning"
        else:
            delta = -5
            status = "error"
        
        result = await update_mastery(user_id, concept_id, delta)
        
        # Use helpers for celebration and prompt
        celebration = _maybe_create_celebration(concept_id, result)
        next_prompt = _get_feedback_prompt(result, is_correct, is_partial)
        
        ui = feedback_schema(
            message=feedback_msg,
            status=status,
            mastery_change=delta,
            new_mastery=result["new_level"],
            actions=[
                {"label": "Try Another", "action": "take_quiz"},
                {"label": "Back to Topic", "action": "continue"}
            ]
        )
        ui.celebration = celebration
        ui.next_prompt = next_prompt
        ui.input_placeholder = "Type 'quiz me' for another, or ask a question..."
        
        return ConversationResponse(
            ui=ui,
            conversation_context={
                "evaluated": True,
                "new_mastery": result["new_level"],
                "section_completed": result["completed"]
            }
        )


async def handle_quiz_request(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'take quiz' intent - fetch an example problem or fallback to MCQ."""
    # Prioritize section from context (frontend state), fallback to user_state (DB)
    current_id = context.get("current_section") or get_current_section_id(user_state, DEFAULT_SECTION_ID)
    
    exercises = get_exercises_for_section(current_id)
    
    if not exercises:
        # No example problems - guide to MCQ instead
        return await handle_mcq_request(user_id, message, user_state, context)
        
    # Pick one random exercise
    import random
    exercise = random.choice(exercises)
    
    # Reload section to get full details including solution
    section = get_section_by_id(current_id)
    full_ex = next((item for item in section.get("content", []) 
               if item.get("type") == "example_box" and item.get("question") == exercise["question"]), None)
    
    solution_meta = ""
    if full_ex and "solution" in full_ex:
        sol = full_ex["solution"]
        solution_meta = sol.get("meta", "") + " " + sol.get("latex", "")

    # Check if open book mode
    open_book = is_open_book_request(message)
    
    if open_book:
        # Show content alongside quiz
        content = format_content_for_ui(section)
        ui = UISchema(
            layout="dynamic",
            panels=[
                PanelContent(
                    type="ExplanationPanel",
                    props={
                        "title": section["section_title"],
                        "content": content,
                        "animated": False
                    },
                    animation="fadeIn",
                    role="primary"
                ),
                PanelContent(
                    type="QuizCard",
                    props={
                        "question": exercise["question"],
                        "concept_id": current_id,
                        "type": "open",
                        "glow": True
                    },
                    animation="slideInUp",
                    role="primary"
                )
            ],
            input_placeholder="Describe your approach to solving this problem...",
            next_prompt="📖 Open Book Mode: Reference the content while solving the problem."
        )
    else:
        # Closed book - quiz only
        ui = quiz_schema(
            question=exercise["question"], 
            concept_id=current_id,
            question_type="open"
        )
        ui.next_prompt = "📕 Closed Book: Think through the problem, then describe your approach."
        ui.input_placeholder = "Describe your approach to solving this problem..."
    
    return ConversationResponse(
        ui=ui,
        conversation_context={
            "expecting_answer": True,
            "question_type": "open",
            "question": exercise["question"],
            "solution_meta": solution_meta,
            "current_section": current_id,
            "open_book": open_book
        }
    )


async def handle_quiz_answer(user_id: str, answer: str, context: dict) -> ConversationResponse:
    """Handle quiz answer submitted via the input bar in Answer mode."""
    from app.agents.tutor_agent import evaluate_quiz_answer
    
    # Get quiz context from the conversation context
    question = context.get("question", "")
    solution = context.get("solution_meta") or context.get("solution_latex") or ""
    concept_id = context.get("current_section") or DEFAULT_SECTION_ID
    
    if not question:
        # No active quiz question
        return ConversationResponse(
            ui=feedback_schema(
                message="No quiz question found. Try 'quiz me' to get a question first.",
                status="warning",
                actions=[{"label": "Quiz Me", "action": "take_quiz"}]
            ),
            conversation_context=context
        )
    
    # Use agent to evaluate the answer
    evaluation = await evaluate_quiz_answer(
        question=question,
        solution=solution,
        student_answer=answer
    )
    
    is_correct = evaluation["is_correct"]
    is_partial = evaluation["is_partial"]
    feedback_msg = evaluation["feedback"]
    
    # Calculate mastery delta
    if is_correct:
        delta = 15
        status = "success"
    elif is_partial:
        delta = 5
        status = "warning"
    else:
        delta = -5
        status = "error"
    
    result = await update_mastery(user_id, concept_id, delta)
    
    # Use helpers for celebration and prompt
    celebration = _maybe_create_celebration(concept_id, result)
    next_prompt = _get_feedback_prompt(result, is_correct, is_partial)
    
    ui = feedback_schema(
        message=feedback_msg,
        status=status,
        mastery_change=delta,
        new_mastery=result["new_level"],
        actions=[
            {"label": "Try Another", "action": "take_quiz"},
            {"label": "Back to Topic", "action": "continue"}
        ]
    )
    ui.celebration = celebration
    ui.next_prompt = next_prompt
    ui.input_placeholder = "Type 'quiz me' for another, or ask a question..."
    
    return ConversationResponse(
        ui=ui,
        conversation_context={
            **context,
            "evaluated": True,
            "expecting_answer": False,  # Clear so buttons work normally
            "question_type": None,      # Clear quiz state
            "new_mastery": result["new_level"],
            "section_completed": result["completed"]
        }
    )

@traceable(name="handle_mcq_request")
async def handle_mcq_request(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'generate mcq' intent using LLM."""
    from groq import AsyncGroq
    from app.config import settings
    import json
    
    # Prioritize section from context (frontend state), fallback to user_state (DB)
    current_id = context.get("current_section") or get_current_section_id(user_state, DEFAULT_SECTION_ID)
    section = get_section_by_id(current_id)
    
    title = section["section_title"] if section else "Gravitation"
    
    # Check if open book mode
    open_book = is_open_book_request(message)
    
    client = AsyncGroq(api_key=settings.groq_api_key)
    
    prompt = f"""
    Generate a multiple-choice question (MCQ) for a physics student learning about: {title}.
    
    Return ONLY a valid JSON object with this structure:
    {{
        "question": "The question text here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_option": "Option A",
        "explanation": "Why it is correct."
    }}
    Make it challenging but conceptual.
    """
    
    try:
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile"
        )
        content = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        mcq_data = json.loads(content)
        
        if open_book:
            # Show content alongside MCQ
            section_content = format_content_for_ui(section)
            ui = UISchema(
                layout="dynamic",
                panels=[
                    PanelContent(
                        type="ExplanationPanel",
                        props={
                            "title": section["section_title"],
                            "content": section_content,
                            "animated": False
                        },
                        animation="fadeIn",
                        role="primary"
                    ),
                    PanelContent(
                        type="MCQCard",
                        props={
                            "question": mcq_data["question"],
                            "options": mcq_data["options"],
                            "concept_id": current_id,
                            "glow": True
                        },
                        animation="slideInUp",
                        role="primary"
                    )
                ],
                input_placeholder="Select the correct option...",
                next_prompt="📖 Open Book Mode: Reference the content to find the answer."
            )
        else:
            # Closed book - MCQ only
            ui = mcq_schema(
                question=mcq_data["question"],
                options=mcq_data["options"],
                concept_id=current_id
            )
            ui.next_prompt = "📕 Closed Book: Select the best answer from memory."
            ui.input_placeholder = "Type your answer (e.g., 'A' or 'Option A')..."
        
        return ConversationResponse(
            ui=ui,
            conversation_context={
                "expecting_answer": True,
                "question_type": "mcq",
                "correct_option": mcq_data["correct_option"],
                "explanation": mcq_data["explanation"],
                "current_section": current_id,
                "open_book": open_book
            }
        )
    except Exception as e:
        print(f"MCQ Gen Error: {e}")
        return ConversationResponse(
            ui=UISchema(
                layout="focus",
                panels=[{
                    "type": "FeedbackCard",
                    "props": {
                        "message": "I couldn't generate a quiz right now. Let's stick to the text.",
                        "status": "info"
                    },
                    "animation": "fadeIn"
                }]
            )
        )


async def handle_show_exercises(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'show exercises' intent - display chapter exercises related to current section."""
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else None
    
    # Check if user wants all exercises or section-specific
    msg_lower = message.lower()
    
    if "all" in msg_lower or not current_id:
        # Show all chapter exercises
        exercises = get_chapter_exercises()
        title = "Chapter Exercises"
        section_title = "Gravitation"
        section_id = "EXERCISES"
    else:
        # Show exercises related to current section
        exercises = get_related_exercises(current_id)
        if not exercises:
            exercises = get_exercises_for_section(current_id)
        section_title = get_section_title(current_id) or current_id
        title = f"Exercises for {section_title}"
        section_id = current_id
    
    if not exercises:
        return ConversationResponse(
            ui=UISchema(
                layout="focus",
                panels=[{
                    "type": "FeedbackCard",
                    "props": {
                        "message": "No exercises found for this section. Try asking for 'all exercises'.",
                        "status": "info"
                    },
                    "animation": "fadeIn"
                }]
            )
        )
    
    # Get completed exercises
    completed = await get_completed_exercises(user_id, section_id)
    
    # Get progress
    progress = await _get_progress_data(user_id, current_id)
    
    return ConversationResponse(
        ui=exercise_only_schema(
            section_id=section_id,
            section_title=section_title,
            exercises=exercises,
            completed_exercises=completed,
            progress=progress
        ),
        conversation_context={
            "viewing_exercises": True,
            "section_id": section_id,
            "expecting_exercise_answer": True
        }
    )


async def handle_exercise_answer(user_id: str, answer: str, context: dict) -> ConversationResponse:
    """Handle answer to an exercise using agent-based evaluation."""
    from app.agents.tutor_agent import evaluate_quiz_answer
    
    exercise_label = context.get("exercise_label")
    section_id = context.get("section_id", DEFAULT_SECTION_ID)
    exercise_question = context.get("exercise_question", "")
    is_bonus = context.get("is_bonus", True)
    
    try:
        # Use agent to evaluate
        evaluation = await evaluate_quiz_answer(
            question=exercise_question,
            solution="",  # No solution available, evaluate based on physics principles
            student_answer=answer
        )
        
        is_correct = evaluation["is_correct"]
        is_partial = evaluation["is_partial"]
        feedback = evaluation["feedback"]
        
        # Record attempt and update mastery
        result = await record_exercise_attempt(
            user_id=user_id,
            exercise_label=exercise_label,
            section_id=section_id,
            is_correct=is_correct,
            is_bonus=is_bonus
        )
        
        if is_correct:
            status = "success"
            msg_prefix = "✅ Excellent! Your approach is correct. "
        elif is_partial:
            status = "warning"
            msg_prefix = "⚠️ You're on the right track! "
        else:
            status = "error"
            msg_prefix = "❌ Not quite right. "
        
        feedback_msg = msg_prefix + feedback
        
        # Use helpers for celebration and prompt
        celebration = _maybe_create_celebration(section_id, result)
        next_prompt = _get_feedback_prompt(result, is_correct, is_partial)
        
        ui = feedback_schema(
            message=feedback_msg,
            status=status,
            mastery_change=result.get("mastery_change", 0),
            new_mastery=new_mastery,
            actions=[
                {"label": "Try Another Exercise", "action": "show_exercises"},
                {"label": "Back to Content", "action": "continue"}
            ]
        )
        ui.celebration = celebration
        ui.next_prompt = next_prompt
        ui.input_placeholder = "Try 'exercises' for more practice, or 'next' to continue..."
        
        return ConversationResponse(
            ui=ui,
            conversation_context={
                "exercise_answered": True,
                "exercise_label": exercise_label,
                "was_correct": is_correct,
                "new_mastery": new_mastery
            }
        )
        
    except Exception as e:
        print(f"Exercise evaluation error: {e}")
        return ConversationResponse(
            ui=feedback_schema(
                message="I had trouble evaluating your answer. Let's try again.",
                status="info",
                actions=[{"label": "Try Again", "action": "show_exercises"}]
            )
        )



async def handle_toggle_chapters(user_id: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'show chapters' / 'topics' toggle."""
    # Check if NavigationMap is already present in the UI context/panels
    # The frontend sends current panel types in context if we track them, 
    # but we can also infer from user state or just use a simple toggle logic based on last action.
    # However, for a robust toggle, we need to know what's on screen.
    # We'll assume if the user asks to "show topics", they want to see it.
    # If they ask again or "close topics", we remove it.
    
    # Check if we are currently showing navigation
    # This is a bit tricky without full UI state from frontend, but we can check if the LAST valid response had it
    # OR better: The frontend specifically requested "show topics", so we show it.
    # IF the intent was "remove_component" with "NavigationMap", we hide it.
    
    # BUT the user said "if the navigation menu is already on the screen, pressing the topics button should remove it"
    # This implies the button sends the SAME command "show topics". 
    # So we need to know if it's currently visible.
    
    # We can inspect the `context` passed from the frontend.
    # Let's see what's in `context`.
    # It contains `panels` list of IDs often.
    
    # IMPORTANT: The frontend sends the full context. We should update the frontend to send the list of active panel TYPES.
    # But for now, let's look at `handle_remove_component`.
    
    # Logic:
    # 1. Get current section
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else None
    current_section = get_section_by_id(current_id) if current_id else None
    
    toc = get_table_of_contents()
    
    # If we can detect it's already open, close it.
    # Since we can't easily detect UI state from here without frontend change, 
    # and the user said "deterministic button", we will try to infer or fallback.
    
    # Wait, the user prompt implies the frontend button sends "show topics".
    # If we want a toggle, we need state.
    # Let's check `context`.
    
    # HEURISTIC: If the last action was "show topics", then close it? No, unreliable.
    
    # BETTER APPROACH:
    # Inspect `context.get("active_panels", [])` if available?
    # The input context structure in `page.tsx`:
    # `const requestContext = { ...context, focused_panel, input_mode: inputMode };`
    # It doesn't send active panels.
    
    # TO FIX THIS PROPERLY WITHOUT FRONTEND CHANGES (as requested "don't use complex logic" might mean "keep it simple"):
    # We will implement "open" logic here. The frontend might need to send "close" if it's open?
    # User said: "if the navigation menu is already on the screen, pressing the topics button should remove the navigation menu from the screen"
    # This implies the toggling logic should happen.
    
    # Since we cannot know for sure, let's add a `is_navigation_open` flag to the context?
    # Or, we can just return the NavigationMap.
    
    # ACTUALLY, checking the grep results, `handle_remove_component` handles removal.
    # If we want a TOGGLE, the frontend should probably interpret the button press.
    # BUT, the user asked "make it display... if already on screen... remove".
    
    # Let's modify the prompt to `toggle topics`? No, the button sends `show topics`.
    
    # OK, let's assume looking at `context.get('navigation_visible')`.
    # We can update `page.tsx` to send this.
    # But I should try to do it with just backend if possible.
    # The backend maintains `conversation_context`.
    
    visible = context.get("navigation_visible", False)
    
    if visible:
        # Remove it (reuse handle_remove_component logic effectively)
        return await handle_remove_component(user_id, "close navigation", user_state, context)
    else:
        # Show it (Add NavigationMap)
        if current_section:
            # Add to side
            content = format_content_for_ui(current_section)
            related = get_related_sections(current_id)
            
            ui = explanation_schema(
                title=current_section["section_title"],
                content=content,
                related_sections=related,
                all_sections=toc
            )
            # Ensure NavigationMap is in there (explanation_schema adds it if all_sections passed?)
            # Let's check `explanation_schema`. Usually it puts generic layout.
            # We might need `multi_panel_schema` or explicit panel text.
            
            # Explicitly constructing UI with NavigationMap
            # If `explanation_schema` doesn't enforce it, we might need a custom one.
            # But let's look at `handle_add_content` fallback:
            # It returns a `NavigationMap` panel.
            
            # Let's just return a UI with NavigationMap added to the current view.
            # This is hard without knowing current view.
            
            # SIMPLIFICATION:
            # Just return the table of contents as a focus or side panel.
            return ConversationResponse(
                ui=UISchema(
                    layout="focus",
                    panels=[{
                        "type": "NavigationMap",
                        "props": {
                            "title": "Topics",
                            "sections": toc
                        },
                        "animation": "fadeIn"
                    }]
                ),
                conversation_context={"navigation_visible": True}
            )

async def handle_add_content(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'add content' intent - add a new panel without replacing existing content."""
    
    # Specialized handling for "show chapters" / "topics"
    if message.lower() in ["show chapters", "show topics", "topics"]:
        return await handle_toggle_chapters(user_id, user_state, context)

    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else None
    current_section = get_section_by_id(current_id) if current_id else None
    
    new_section = None
    
    # 1. Check if LLM already resolved the section (from combined classifier)
    if context.get("resolved_section_id"):
        resolved_id = context["resolved_section_id"]
        # ... logic continues matched original ...
        if resolved_id != current_id:  # Don't add the same section
            new_section = get_section_by_id(resolved_id)
    
    # 2. Fallback: Use extractors and search (for legacy/direct calls)
    if not new_section:
        topic = extract_topic_from_add_request(message)
        if topic:
            new_section = get_section_by_id(topic)
            if not new_section:
                matches = search_sections_by_topic(topic)
                if matches:
                    new_section = get_section_by_id(matches[0]["id"])
    
    if not new_section:
        matches = search_sections_by_topic(message)
        if matches:
            matches = [m for m in matches if m["id"] != current_id]
            if matches:
                new_section = get_section_by_id(matches[0]["id"])
    
    if new_section and current_section:
        existing_content = format_content_for_ui(current_section)
        new_content = format_content_for_ui(new_section)
        
        current_related = get_related_sections(current_id) if current_id else []
        new_related = get_related_sections(new_section["section_id"])
        
        all_related = {r["id"]: r for r in current_related}
        for r in new_related:
            all_related[r["id"]] = r
        combined_related = list(all_related.values())[:5]
        
        existing_panels = [{
            "type": "ExplanationPanel",
            "props": {
                "title": current_section["section_title"],
                "content": existing_content,
                "animated": False
            }
        }]
        
        ui = multi_panel_schema(
            existing_panels=existing_panels,
            new_content=new_content,
            new_title=new_section["section_title"],
            related_sections=combined_related
        )
        
        return ConversationResponse(
            ui=ui,
            conversation_context={
                "multi_panel": True,
                "panels": [current_id, new_section["section_id"]],
                "current_section": new_section["section_id"],
                "section_title": new_section["section_title"]
            },
            debug={"added_section": new_section["section_id"]}
        )
    
    elif new_section:
        return await _build_explanation_response(user_id, new_section, context)
    
    else:
        # Fallback to search result if nothing found
        return ConversationResponse(
            ui=UISchema(
                layout="focus",
                panels=[{
                    "type": "FeedbackCard",
                    "props": {
                        "message": f"I couldn't find content to add. Try specifying a section like '7.2' or a topic like 'Kepler's laws'.",
                        "status": "info"
                    },
                    "animation": "fadeIn"
                }]
            ),
            conversation_context={"add_failed": True, "query": message}
        )


async def handle_remove_component(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'remove component' intent - remove a panel from the current view."""
    component_to_remove = extract_component_to_remove(message)
    
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else None
    current_section = get_section_by_id(current_id) if current_id else None
    
    if not current_section:
        return ConversationResponse(
            ui=welcome_schema(),
            conversation_context={"removed": False, "reason": "no_current_section"}
        )
    
    # Check if we're in multi-panel comparison mode
    is_multi_panel = context.get("multi_panel", False)
    panel_ids = context.get("panels", [])
    
    removed_name = {
        "NavigationMap": "Chapter Sections panel",
        "SummaryCard": "Summary panel",
        "DerivationBlock": "Derivation block",
        "ExplanationPanel": "Explanation panel",
        "ChatPanel": "Chat panel",
        "ExercisePanel": "Exercises panel"
    }.get(component_to_remove, "component")
    
    # If removing ChatPanel
    if component_to_remove == "ChatPanel":
        # Rebuild current view without chat
        content = format_content_for_ui(current_section)
        toc = get_table_of_contents()
        related = get_related_sections(current_id)
        
        ui = explanation_schema(
            title=current_section["section_title"],
            content=content,
            related_sections=related,
            all_sections=toc
        )
        
        return ConversationResponse(
            ui=ui,
            conversation_context={
                "removed": component_to_remove,
                "current_section": current_id,
                "section_title": current_section["section_title"]
            },
            debug={"removed_component": component_to_remove, "message": f"Removed {removed_name}"}
        )
    
    # If removing NavigationMap (Related Topics)
    if component_to_remove == "NavigationMap":
        if is_multi_panel and len(panel_ids) >= 2:
            # Preserve multi-panel view, just remove the navigation
            panels = []
            for panel_id in panel_ids:
                section = get_section_by_id(panel_id)
                if section:
                    content = format_content_for_ui(section)
                    panels.append(
                        PanelContent(
                            type="ExplanationPanel",
                            props={
                                "title": section["section_title"],
                                "content": content,
                                "animated": False
                            },
                            animation="fadeIn",
                            role="primary"
                        )
                    )
            
            ui = UISchema(
                layout="dynamic",
                panels=panels,
                input_placeholder="Navigation hidden. Type 'show chapters' to restore.",
                next_prompt="Related Topics panel removed. Type 'show chapters' to bring it back."
            )
            
            return ConversationResponse(
                ui=ui,
                conversation_context={
                    "removed": component_to_remove,
                    "multi_panel": True,
                    "panels": panel_ids,
                    "current_section": current_id,
                    "navigation_hidden": True
                },
                debug={"removed_component": component_to_remove, "message": f"Removed {removed_name}", "preserved_panels": panel_ids}
            )
        else:
            # Single panel mode - hide navigation
            content = format_content_for_ui(current_section)
            ui = UISchema(
                layout="focus",
                panels=[
                    PanelContent(
                        type="ExplanationPanel",
                        props={
                            "title": current_section["section_title"],
                            "content": content,
                            "animated": False
                        },
                        animation="fadeIn",
                        role="primary"
                    )
                ],
                input_placeholder="Navigation hidden. Type 'show chapters' to restore.",
                next_prompt="Chapter sections panel removed. Type 'show chapters' to bring it back."
            )
            
            return ConversationResponse(
                ui=ui,
                conversation_context={
                    "removed": component_to_remove,
                    "current_section": current_id,
                    "navigation_hidden": True
                },
                debug={"removed_component": component_to_remove, "message": f"Removed {removed_name}"}
            )
    else:
        # Removing other components - rebuild with navigation
        return await _build_explanation_response(user_id, current_section, context)


async def handle_add_summary(user_id: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'add summary' intent - add summary panel to current view."""
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else None
    current_section = get_section_by_id(current_id) if current_id else None
    
    mastery = user_state.get("mastery", []) if user_state else []
    weak_areas = await get_weak_concepts(user_id)
    
    if current_section:
        existing_content = format_content_for_ui(current_section)
        related = get_related_sections(current_id) if current_id else []
        
        return ConversationResponse(
            ui=UISchema(
                layout="dynamic",
                panels=[
                    PanelContent(
                        type="ExplanationPanel",
                        props={
                            "title": current_section["section_title"],
                            "content": existing_content,
                            "animated": False
                        },
                        animation="fadeIn",
                        role="primary"
                    ),
                    PanelContent(
                        type="SummaryCard",
                        props={
                            "title": "Your Progress",
                            "mastery": mastery,
                            "weak_areas": weak_areas
                        },
                        animation="slideInRight",
                        role="primary"
                    ),
                    PanelContent(
                        type="NavigationMap",
                        props={
                            "sections": related[:5],
                            "title": "Related"
                        },
                        animation="slideInRight",
                        role="auxiliary",
                        width="25%"
                    )
                ],
                input_placeholder="Say 'remove summary' to hide it..."
            ),
            conversation_context={
                "multi_panel": True,
                "showing_summary": True,
                "current_section": current_id
            }
        )
    else:
        # No current section - show progress instead
        return await handle_show_progress(user_id, user_state, context)


# === Helpers ===

async def _get_progress_data(user_id: str, current_section_id: str = None) -> ProgressData:
    """Get progress data for UI."""
    toc = get_table_of_contents()
    section_ids = [item["id"] for item in toc if item["id"].startswith("7.")]
    progress_data = await get_lifetime_progress(user_id, section_ids)
    
    current_mastery = 0
    if current_section_id:
        section_info = await get_section_mastery(user_id, current_section_id)
        current_mastery = section_info.get("level", 0)
    
    return ProgressData(
        lifetime_mastery=progress_data.get("lifetime_mastery", 0),
        current_section_id=current_section_id,
        current_section_mastery=current_mastery,
        sections_progress=[
            {
                "id": item["id"],
                "title": item["title"],
                "mastery": next((s["mastery"] for s in progress_data.get("sections_progress", []) if s["id"] == item["id"]), 0),
                "completed": next((s["completed"] for s in progress_data.get("sections_progress", []) if s["id"] == item["id"]), False)
            }
            for item in toc
            if item["id"].startswith("7.")
        ]
    )


async def _build_explanation_response(
    user_id: str, 
    section: dict, 
    context: dict,
    intro_message: str = "",
    show_exercises: bool = False
) -> ConversationResponse:
    """Build explanation UI response for a section with guided prompts."""
    content = format_content_for_ui(section)
    related = get_related_sections(section["section_id"])
    section_id = section["section_id"]
    section_title = section["section_title"]
    
    # Prepend intro message if provided
    if intro_message and content:
        content[0]["content"] = intro_message + content[0].get("content", "")
    
    # Get progress data
    progress = await _get_progress_data(user_id, section_id)
    
    # Get current mastery for this section
    section_mastery = await get_section_mastery(user_id, section_id)
    current_mastery = section_mastery.get("level", 0)
    
    # Check for exercises and example problems
    exercises = get_related_exercises(section_id)
    example_problems = get_exercises_for_section(section_id)  # Example boxes in section
    completed_exercises = await get_completed_exercises(user_id, section_id)
    
    # Get ALL sections for navigation panel with their mastery
    toc = get_table_of_contents()
    all_sections = []
    for item in toc:
        # Skip non-content sections
        if item["id"] in ["Summary", "Points to ponder", "Exercises", "PHYSICAL_QUANTITIES_TABLE", "POINTS_TO_PONDER", "SUMMARY"]:
            continue
        
        # Get mastery for this section
        item_mastery = next(
            (s["mastery"] for s in progress.sections_progress if s["id"] == item["id"]), 
            0
        ) if progress and progress.sections_progress else 0
        item_completed = next(
            (s["completed"] for s in progress.sections_progress if s["id"] == item["id"]), 
            False
        ) if progress and progress.sections_progress else False
        
        all_sections.append({
            "id": item["id"],
            "title": item["title"],
            "mastery": item_mastery,
            "completed": item_completed,
            "isCurrent": item["id"] == section_id
        })
    
    # Build guided prompt based on context
    has_examples = len(example_problems) > 0 if example_problems else False
    
    # Build suggested actions for guided learning flow
    suggested_actions = []
    next_id = get_next_section_id(section_id)
    
    if current_mastery >= MASTERY_THRESHOLD:
        # Already mastered - suggest next section
        next_prompt = "🎉 Section mastered! Type 'next' to continue or explore more."
        input_placeholder = "Type 'next' to continue, or ask a question..."
        # Removed manual quiz buttons - quizzes will auto-appear during conversation
        suggested_actions = []
    elif current_mastery > 0:
        # In progress - guide via prompts instead of buttons
        next_prompt = f"📊 {current_mastery}% mastery (need 70%). Keep discussing the concepts!"
        input_placeholder = "Ask a question to deepen your understanding..."
        suggested_actions = []
    else:
        # Just started - encourage discussion
        if has_examples:
            next_prompt = "Let's explore this topic. Ask questions or discuss the concepts!"
            input_placeholder = "What would you like to understand better?"
        else:
            next_prompt = "Let's discuss this topic. Ask me anything about the content!"
            input_placeholder = "Ask about the topic or share your thoughts..."
        suggested_actions = []
    
    # Show exercises panel alongside content if requested
    if exercises and show_exercises:
        ui = explanation_with_exercises_schema(
            title=section_title,
            content=content,
            section_id=section_id,
            exercises=exercises,
            related_sections=related,
            completed_exercises=completed_exercises,
            progress=progress
        )
    else:
        ui = explanation_schema(
            title=section_title,
            content=content,
            related_sections=related,
            all_sections=all_sections,
            current_section_id=section_id,
            show_related=True,  # Always show navigation
            progress=progress
        )
    
    # Add guided prompts and actions to UI
    ui.next_prompt = next_prompt
    ui.input_placeholder = input_placeholder
    ui.suggested_actions = suggested_actions
    
    return ConversationResponse(
        ui=ui,
        conversation_context={
            "current_section": section_id,
            "section_title": section_title,
            "has_exercises": len(exercises) > 0 if exercises else False,
            "has_examples": has_examples,
            "current_mastery": current_mastery
        },
        debug={
            "content_items": len(content),
            "related_sections": len(related),
            "all_sections": len(all_sections),
            "exercises_available": len(exercises) if exercises else 0,
            "example_problems": len(example_problems) if example_problems else 0
        }
    )


async def handle_agent_chat(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle chat/doubt through the stateful tutor agent.
    
    Routes message through LangGraph agent which maintains conversation state
    and can perform multi-turn Socratic teaching.
    """
    from app.agents.agent_router import invoke_tutor_agent
    from app.chains.content import extract_section_text
    
    current = user_state.get("current_concept") if user_state else None
    current_id = get_current_section_id(user_state, DEFAULT_SECTION_ID)
    current_section = get_section_by_id(current_id)
    
    # Get section content for agent context
    section_content = None
    if current_section:
        section_content = format_content_for_ui(current_section)
        # Use shared helper for text extraction
        context["section_content"] = extract_section_text(current_section)
        context["section_title"] = current_section.get("section_title")
    
    # Invoke the stateful agent
    agent_result = await invoke_tutor_agent(user_id, message, context)
    
    if not agent_result.get("success"):
        # Fallback to simple response on error
        return ConversationResponse(
            ui=chat_panel_schema(
                existing_panels=[],
                current_context={"error": True},
                initial_message=agent_result.get("response", "Something went wrong.")
            ),
            conversation_context=context
        )
    
    # Build UI with agent response
    ai_response = agent_result.get("response", "")
    agent_mode = agent_result.get("mode", "normal")
    
    # Build existing panels with current section
    existing_panels = []
    if current_section:
        existing_panels.append(
            PanelContent(
                type="ExplanationPanel",
                props={
                    "title": current_section["section_title"],
                    "content": section_content,
                    "animated": False,
                    "section_id": current_id
                },
                role="primary"
            )
        )
    
    chat_context = {
        "current_section_id": current_id,
        "current_section_title": current_section["section_title"] if current_section else None,
        "user_id": user_id,
        "agent_mode": agent_mode
    }
    
    ui = chat_panel_schema(
        existing_panels=existing_panels,
        current_context=chat_context,
        initial_message=ai_response
    )
    
    # Extract key terms from user's message for dynamic highlighting
    highlight_terms = extract_highlight_terms(message)
    if highlight_terms:
        ui.highlight_terms = highlight_terms
    
    # Check mastery and show "Ready for Quiz" button if threshold crossed
    try:
        from app.graph.user_state import get_user_state
        user_mastery_state = await get_user_state(user_id)
        current_mastery = 0
        if user_mastery_state and user_mastery_state.get("mastery"):
            # mastery is a list of dicts: [{concept: id, level: N, ...}, ...]
            for m in user_mastery_state["mastery"]:
                if m.get("concept") == current_id:
                    current_mastery = m.get("level", 0)
                    break
        
        if current_mastery >= MASTERY_THRESHOLD:
            ui.suggested_actions = [
                {
                    "label": "🎯 Ready for Quiz!",
                    "action": "generate_mcq",
                    "primary": True,
                    "tooltip": f"Mastery: {current_mastery}% — Test your knowledge!"
                },
                {
                    "label": "📝 Try Exercises",
                    "action": "show_exercises",
                    "primary": False
                }
            ]
    except Exception as e:
        print(f"Mastery check error: {e}")
    
    # Update context with agent state for persistence
    new_context = {
        **context,
        "chat_open": True,
        "current_section": current_id,
        "focused_panel": "chat",
        "agent_mode": agent_mode,
        "current_prereq_id": agent_result.get("current_prereq_id"),
        "current_prereq_title": agent_result.get("current_prereq_title"),
        "prereq_question": agent_result.get("prereq_question"),
        "prerequisite_chain": agent_result.get("prerequisite_chain", [])
    }
    
    return ConversationResponse(
        ui=ui,
        conversation_context=new_context,
        debug={
            "agent_mode": agent_mode,
            "success": True
        }
    )


async def handle_open_chat(user_id: str, user_state: dict, context: dict) -> ConversationResponse:
    """Open chat panel alongside existing content (no agent invocation).
    
    This just adds the ChatPanel to the current UI - it doesn't run the agent.
    The agent is only invoked when user actually sends a chat message.
    """
    current_id = get_current_section_id(user_state, DEFAULT_SECTION_ID)
    current_section = get_section_by_id(current_id)
    
    # Build existing panels with current section
    existing_panels = []
    section_content = None
    if current_section:
        section_content = format_content_for_ui(current_section)
        existing_panels.append(
            PanelContent(
                type="ExplanationPanel",
                props={
                    "title": current_section["section_title"],
                    "content": section_content,
                    "animated": False,
                    "section_id": current_id
                },
                role="primary"
            )
        )
    
    chat_context = {
        "current_section_id": current_id,
        "current_section_title": current_section["section_title"] if current_section else None,
        "user_id": user_id
    }
    
    # Use chat_panel_schema which adds ChatPanel to existing panels
    ui = chat_panel_schema(
        existing_panels=existing_panels,
        current_context=chat_context,
        initial_message=None  # No initial message - just open the panel
    )
    
    return ConversationResponse(
        ui=ui,
        conversation_context=context
    )


# ==================== Text-to-Speech Endpoint ====================




# === Tutor Navigation & Evaluation Endpoints (moved from tutor.py) ===

import json
import os

GRAVITY_JSON_PATH = "../elearning-platform/src/data/chapters/gravity.json"

def get_gravity_content():
    """Load gravity.json content."""
    try:
        with open(GRAVITY_JSON_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        if os.path.exists("gravity.json"):
            with open("gravity.json", "r") as f:
                return json.load(f)
        raise HTTPException(status_code=500, detail="Content file not found")


class NextStepRequest(BaseModel):
    user_id: str
    concept_id: str | None = None


class Component(BaseModel):
    type: str
    props: dict = {}


class UINextResponse(BaseModel):
    schema_version: str = "1.0"
    components: list[Component]


@router.post("/tutor/next", response_model=UINextResponse)
async def next_step(req: NextStepRequest):
    """Get next section content based on concept ID."""
    from app.graph.client import neo4j_client
    
    query = ""
    params = {}
    
    if req.concept_id:
        query = """
        MATCH (c:Concept {id: $id})
        RETURN c
        """
        params = {"id": req.concept_id}
    else:
        query = """
        MATCH (c:Concept {id: "7.1"})
        RETURN c
        """
    
    results = await neo4j_client.execute_read(query, **params)
    if not results:
        raise HTTPException(status_code=404, detail="Concept not found")
    
    concept = results[0]["c"]
    section_id = concept.get("sectionId", "7.1")
    
    data = get_gravity_content()
    sections = data.get("sections", [])
    
    target_section = next((s for s in sections if s["section_id"] == section_id), None)
    
    if not target_section:
        return UINextResponse(components=[
            Component(type="h1", props={"children": concept.get("title")}),
            Component(type="p", props={"children": "Content coming soon..."})
        ])

    components = []
    components.append(Component(type="h1", props={"children": target_section.get("section_title")}))
    
    for item in target_section.get("content", []):
        if item["type"] == "text":
            components.append(Component(type="p", props={"children": item["body"]}))
        elif item["type"] == "list_item":
            components.append(Component(type="li", props={"children": f"{item.get('label', '')} {item.get('body', '')}"}))
        elif item["type"] == "diagram":
            components.append(Component(type="diagram", props={
                "figure": item.get("figure_number"),
                "caption": item.get("meta")
            }))
        elif item["type"] == "derivation":
            components.append(Component(type="latex", props={"content": item.get("latex")}))
    
    return UINextResponse(components=components)


class ExerciseEvaluationRequest(BaseModel):
    user_id: str
    exercise_label: str
    student_answer: str
    is_bonus: bool = True


class ExerciseEvaluationResponse(BaseModel):
    is_correct: bool
    score: int
    feedback: str
    correct_solution: str
    comparison: str
    mastery_change: int
    new_mastery: int


@router.post("/tutor/evaluate-exercise", response_model=ExerciseEvaluationResponse)
async def evaluate_exercise(request: ExerciseEvaluationRequest):
    """Evaluate student answer against exercise solution using LangGraph agent."""
    from app.agents.tutor_agent import evaluate_exercise_with_agent
    from app.chains.content import get_exercise_with_solution
    
    exercise = get_exercise_with_solution(request.exercise_label)
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Exercise {request.exercise_label} not found")
    
    if not exercise.get("solution"):
        raise HTTPException(status_code=404, detail=f"Solution not available for exercise {request.exercise_label}")
    
    result = await evaluate_exercise_with_agent(
        user_id=request.user_id,
        exercise_label=request.exercise_label,
        student_answer=request.student_answer
    )
    
    try:
        mastery_result = await record_exercise_attempt(
            user_id=request.user_id,
            exercise_label=request.exercise_label,
            section_id="EXERCISES",
            is_correct=result["is_correct"],
            is_bonus=request.is_bonus
        )
        mastery_change = mastery_result.get("mastery_change", 0)
        new_mastery = mastery_result.get("new_level", 0)
    except Exception as e:
        print(f"Error recording exercise: {e}")
        mastery_change = 0
        new_mastery = 0
    
    return ExerciseEvaluationResponse(
        is_correct=result["is_correct"],
        score=result["score"],
        feedback=result["feedback"],
        correct_solution=exercise["solution"],
        comparison=result["comparison"],
        mastery_change=mastery_change,
        new_mastery=new_mastery
    )

