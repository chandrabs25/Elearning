"""Main conversation endpoint for AI Tutor V2."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

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
from app.chains.intent import classify_intent, TutorIntent, extract_topic_from_add_request, extract_component_to_remove, is_open_book_request
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
    summary_schema,
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


class ConversationRequest(BaseModel):
    user_id: str
    message: str
    pinned_left: str | None = None
    pinned_right: str | None = None
    context: dict = {}


class ConversationResponse(BaseModel):
    ui: UISchema
    conversation_context: dict = {}
    debug: dict = {}


@router.post("/tutor/converse", response_model=ConversationResponse)
async def converse(req: ConversationRequest):
    """
    Main conversation endpoint. Processes user message and returns UI schema.
    """
    # 1. Get or create user
    await get_or_create_user(req.user_id)
    user_state = await get_user_state(req.user_id)
    
    # 2. Classify intent
    context = {**req.context}
    intent = classify_intent(req.message, context)
    
    # 3. Route to handler based on intent
    if intent == TutorIntent.CONTINUE_LEARNING:
        return await handle_continue(req.user_id, user_state, context)
    
    elif intent == TutorIntent.START_TOPIC:
        return await handle_start_topic(req.user_id, req.message, context)
    
    elif intent == TutorIntent.NAVIGATE:
        return await handle_navigate(req.user_id, req.message, user_state, context)
    
    elif intent == TutorIntent.ASK_DERIVATION:
        return await handle_derivation(req.user_id, req.message, user_state, context)
    
    elif intent == TutorIntent.SHOW_SUMMARY:
        return await handle_summary(req.user_id, user_state)
    
    elif intent == TutorIntent.ANSWER_QUESTION:
        return await handle_answer(req.user_id, req.message, context)
    
    elif intent == TutorIntent.ADD_CONTENT:
        return await handle_add_content(req.user_id, req.message, user_state, context)
    
    elif intent == TutorIntent.REMOVE_COMPONENT:
        return await handle_remove_component(req.user_id, req.message, user_state, context)
    
    elif intent == TutorIntent.ADD_SUMMARY:
        return await handle_add_summary(req.user_id, user_state, context)
    
    elif intent == TutorIntent.OPEN_CHAT:
        return await handle_open_chat(req.user_id, req.message, user_state, context)

    elif intent == TutorIntent.TAKE_QUIZ:
        return await handle_quiz_request(req.user_id, req.message, user_state, context)

    elif intent == TutorIntent.GENERATE_MCQ:
        return await handle_mcq_request(req.user_id, req.message, user_state, context)
    
    elif intent == TutorIntent.SHOW_EXERCISES:
        return await handle_show_exercises(req.user_id, req.message, user_state, context)
    
    elif intent == TutorIntent.ANSWER_EXERCISE:
        return await handle_exercise_answer(req.user_id, req.message, context)
    
    else:
        # Default: treat as topic request
        return await handle_start_topic(req.user_id, req.message, context)


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


# === Chat Panel Models and Endpoint ===

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
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
    Handle messages sent from the ChatPanel.
    Returns responses with rich content (math, diagrams, etc.).
    Updates mastery only for relevant chat interactions.
    """
    from langchain_groq import ChatGroq
    from app.config import settings
    
    section_id = req.context.get("current_section_id")
    section_title = req.context.get("current_section_title", "Gravitation")
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key
    )
    
    # Step 1: Check relevance of the user's question
    relevance = "relevant"  # default
    if section_id:
        relevance_prompt = f"""You are evaluating if a student's question is relevant to their current study topic.

Current Section: {section_title} (Section {section_id})
Chapter: Gravitation (covers: Kepler's laws, universal gravitation, gravitational constant, acceleration due to gravity, gravitational potential energy, escape speed, earth satellites, orbital energy)

Student's Question: "{req.message}"

Classify this question as ONE of:
- "relevant": Directly about the current section topic ({section_title})
- "related": About gravitation/physics but a different section (e.g., asking about escape velocity while studying Kepler's laws)
- "irrelevant": Not about physics or gravitation at all (e.g., "what's the weather?", "tell me a joke")

Reply with ONLY one word: relevant, related, or irrelevant"""

        try:
            relevance_response = await llm.ainvoke(relevance_prompt)
            relevance_text = relevance_response.content.strip().lower()
            if "irrelevant" in relevance_text:
                relevance = "irrelevant"
            elif "related" in relevance_text:
                relevance = "related"
            else:
                relevance = "relevant"
        except:
            relevance = "relevant"  # Default to relevant on error
    
    # Step 2: Record chat interaction with relevance
    mastery_result = None
    if section_id:
        mastery_result = await record_chat_interaction(req.user_id, section_id, relevance)
    
    # Step 3: Build the response prompt
    context_str = f"The user is currently studying: {section_title}. " if section_title else ""
    
    # Add relevance-aware instruction
    relevance_instruction = ""
    if relevance == "related":
        relevance_instruction = "\nNote: The student is asking about a related but different topic. Answer helpfully, but gently guide them back to the current section if appropriate."
    elif relevance == "irrelevant":
        relevance_instruction = "\nNote: This question seems off-topic. Answer briefly if possible, then redirect: 'That's interesting! But let's focus on gravitation. Do you have questions about the current topic?'"
    
    system_prompt = f"""You are an AI tutor helping a student learn physics (specifically gravitation).
{context_str}{relevance_instruction}
When answering:
- Be clear and educational
- Use LaTeX for math equations (wrap with $$ for block equations)
- Refer to relevant concepts from the textbook when applicable
- Keep responses focused and digestible

Format your response as educational content. If there are equations, include them.
"""
    
    # Prepare conversation history for LLM
    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history[-5:]:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        messages.append({"role": msg.role, "content": content})
    messages.append({"role": "user", "content": req.message})
    
    # Call LLM for response
    response = await llm.ainvoke(messages)
    response_text = response.content
    
    # Parse response for rich content
    content_items = parse_response_to_content(response_text)
    
    # Generate follow-up suggestions based on relevance
    suggestions = generate_suggestions(req.message, req.context, relevance)
    
    return ChatPanelResponse(
        message=ChatMessage(
            role="assistant",
            content=content_items
        ),
        suggestions=suggestions,
        mastery_update=mastery_result
    )


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


def generate_suggestions(message: str, context: dict, relevance: str = "relevant") -> list[str]:
    """Generate follow-up question suggestions based on context and relevance."""
    suggestions = []
    
    msg_lower = message.lower()
    section_title = context.get("current_section_title", "").lower()
    
    # If irrelevant, guide back to topic
    if relevance == "irrelevant":
        return [
            f"Tell me more about {context.get('current_section_title', 'this topic')}",
            "Can you explain the main formula?",
            "Quiz me on this section"
        ]
    
    # If related (different section), suggest exploring or returning
    if relevance == "related":
        return [
            "How does this connect to what I'm studying?",
            f"Let's go back to {context.get('current_section_title', 'the current topic')}",
            "Show me related sections"
        ]
    
    # Relevant questions - physics-specific suggestions
    if "escape" in msg_lower or "velocity" in msg_lower:
        suggestions.append("How is escape velocity related to orbital velocity?")
        suggestions.append("What's Earth's escape velocity?")
    elif "kepler" in msg_lower:
        suggestions.append("Can you show me the derivation?")
        suggestions.append("What are some real-world applications?")
    elif "gravity" in msg_lower or "gravitation" in msg_lower:
        suggestions.append("How does gravity work on other planets?")
        suggestions.append("What's the gravitational constant?")
    elif "satellite" in msg_lower or "orbit" in msg_lower:
        suggestions.append("How do geostationary satellites work?")
        suggestions.append("What determines orbital period?")
    elif "potential" in msg_lower or "energy" in msg_lower:
        suggestions.append("How is potential energy related to escape velocity?")
    
    # Default suggestions encourage practice
    if not suggestions:
        suggestions = [
            "Can you explain this with an example?",
            "What's the key formula here?",
            "Quiz me on this!"
        ]
    
    return suggestions[:3]


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
    section = get_section_by_id("7.1")
    if section:
        await update_current_concept(user_id, "7.1")
        return await _build_explanation_response(user_id, section, context)
    
    raise HTTPException(status_code=500, detail="Content not found")


async def handle_start_topic(user_id: str, message: str, context: dict) -> ConversationResponse:
    """Handle topic teaching request."""
    # Try to find the topic in content
    matches = search_sections_by_topic(message)
    
    if matches:
        section_id = matches[0]["id"]
        section = get_section_by_id(section_id)
        
        if section:
            await update_current_concept(user_id, section_id)
            return await _build_explanation_response(user_id, section, context)
    
    # Check if message contains a section ID directly
    words = message.split()
    for word in words:
        if word.startswith("7."):
            section = get_section_by_id(word)
            if section:
                await update_current_concept(user_id, word)
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
    
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else "7.1"
    
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
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else "7.3"
    
    section = get_section_by_id(current_id)
    if not section:
        section = get_section_by_id("7.3")  # Fallback to universal law
    
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
                        ]
                    },
                    "animation": "fadeIn"
                }]
            ),
            conversation_context={"showing_derivation": True, "section_id": current_id}
        )
    
    return await handle_start_topic(user_id, message, context)


async def handle_summary(user_id: str, user_state: dict) -> ConversationResponse:
    """Handle progress summary request."""
    mastery = user_state.get("mastery", []) if user_state else []
    weak = await get_weak_concepts(user_id)
    
    return ConversationResponse(
        ui=summary_schema(mastery, weak),
        conversation_context={"showing_summary": True}
    )


async def handle_answer(user_id: str, answer: str, context: dict) -> ConversationResponse:
    """Handle quiz/MCQ answer evaluation."""
    question_type = context.get("question_type", "open")
    concept_id = context.get("current_section", "7.1")
    
    # 1. Handle MCQ Answer
    if question_type == "mcq":
        correct_option = context.get("correct_option")  # e.g., "B"
        user_selection = answer.strip().split()[0].upper()
        
        is_correct = False
        if correct_option and (user_selection == correct_option or answer == correct_option):
            is_correct = True
        
        # Update mastery (dynamic - can decrease)
        delta = 10 if is_correct else -5
        result = await update_mastery(user_id, concept_id, delta)
        
        if is_correct:
            feedback = f"✅ Correct! The answer is indeed {correct_option}."
            status = "success"
        else:
            feedback = f"❌ Not quite. The correct answer was {correct_option}."
            status = "error"
        
        # Check if section is now complete
        celebration = None
        if result["completed"] and result["new_level"] >= MASTERY_THRESHOLD:
            next_id = get_next_section_id(concept_id)
            next_title = get_section_title(next_id) if next_id else None
            section_title = get_section_title(concept_id) or concept_id
            celebration = celebration_schema(
                section_title=section_title,
                mastery_percent=result["new_level"],
                next_section_id=next_id,
                next_section_title=next_title
            )
        
        # Build guided prompt based on result
        if result["new_level"] >= MASTERY_THRESHOLD:
            next_prompt = "🎉 Section mastered! Type 'next' to continue."
        elif is_correct:
            next_prompt = f"Great! {result['new_level']}% mastery. Keep going with 'quiz me'!"
        else:
            next_prompt = f"Don't give up! {result['new_level']}% mastery. Try 'quiz me' again or ask for help."
        
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
                "new_mastery": result["new_level"],
                "section_completed": result["completed"]
            }
        )

    # 2. Handle Open-Ended Problem Solving (Quiz)
    else:
        from langchain_groq import ChatGroq
        from app.config import settings

        solution = context.get("solution_meta") or context.get("solution_latex")
        
        llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.groq_api_key)
        
        prompt = f"""
        You are a physics tutor evaluating a student's answer.
        
        Question: {context.get('question')}
        Correct Solution Logic: {solution}
        
        Student Answer: {answer}
        
        Evaluate the student's answer. 
        - If they described the correct process/logic (even without math), mark it CORRECT.
        - If they are wrong, explain why.
        - Be encouraging but strict on physics principles.
        
        Response format: 
        Status: [CORRECT / PARTIAL / WRONG]
        Feedback: [Your feedback here]
        """
        
        evaluation = await llm.ainvoke(prompt)
        eval_text = evaluation.content
        
        is_correct = "Status: CORRECT" in eval_text
        is_partial = "PARTIAL" in eval_text
        
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
        
        feedback_msg = eval_text.replace("Status: CORRECT", "").replace("Status: WRONG", "").replace("Status: PARTIAL", "").strip()
        
        # Check for section completion
        celebration = None
        if result["completed"] and result["new_level"] >= MASTERY_THRESHOLD:
            next_id = get_next_section_id(concept_id)
            next_title = get_section_title(next_id) if next_id else None
            section_title = get_section_title(concept_id) or concept_id
            celebration = celebration_schema(
                section_title=section_title,
                mastery_percent=result["new_level"],
                next_section_id=next_id,
                next_section_title=next_title
            )
        
        # Build guided prompt based on result
        if result["new_level"] >= MASTERY_THRESHOLD:
            next_prompt = "🎉 Section mastered! Type 'next' to continue."
        elif is_correct:
            next_prompt = f"Excellent! {result['new_level']}% mastery. Try 'quiz me' for more!"
        elif is_partial:
            next_prompt = f"Almost there! {result['new_level']}% mastery. Try again or ask for help."
        else:
            next_prompt = f"Keep trying! {result['new_level']}% mastery. Type 'explain' for help."
        
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
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else "7.2"
    
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


async def handle_mcq_request(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'generate mcq' intent using LLM."""
    from langchain_groq import ChatGroq
    from app.config import settings
    import json
    
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else "7.1"
    section = get_section_by_id(current_id)
    
    title = section["section_title"] if section else "Gravitation"
    
    # Check if open book mode
    open_book = is_open_book_request(message)
    
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.groq_api_key)
    
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
        response = await llm.ainvoke(prompt)
        content = response.content.replace("```json", "").replace("```", "").strip()
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
    """Handle answer to an exercise."""
    from langchain_groq import ChatGroq
    from app.config import settings
    
    exercise_label = context.get("exercise_label")
    section_id = context.get("section_id", "7.1")
    exercise_question = context.get("exercise_question", "")
    is_bonus = context.get("is_bonus", True)
    
    # Use LLM to evaluate the answer
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.groq_api_key)
    
    prompt = f"""
    You are a physics tutor evaluating a student's approach to solving a problem.
    
    Exercise: {exercise_label}
    Question: {exercise_question}
    
    Student's Approach: {answer}
    
    Evaluate if the student's approach/reasoning is correct.
    - Focus on whether they understand the physics concepts
    - Check if their approach would lead to the correct answer
    - Be encouraging but accurate
    
    Response format:
    Status: [CORRECT / PARTIAL / WRONG]
    Feedback: [Your detailed feedback]
    """
    
    try:
        evaluation = await llm.ainvoke(prompt)
        eval_text = evaluation.content
        
        is_correct = "Status: CORRECT" in eval_text
        is_partial = "PARTIAL" in eval_text
        
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
        
        feedback_msg = msg_prefix + eval_text.replace("Status: CORRECT", "").replace("Status: WRONG", "").replace("Status: PARTIAL", "").replace("Feedback:", "").strip()
        
        # Check for celebration
        celebration = None
        if result.get("completed") and result.get("new_level", 0) >= MASTERY_THRESHOLD:
            next_id = get_next_section_id(section_id)
            next_title = get_section_title(next_id) if next_id else None
            section_title = get_section_title(section_id) or section_id
            celebration = celebration_schema(
                section_title=section_title,
                mastery_percent=result["new_level"],
                next_section_id=next_id,
                next_section_title=next_title
            )
        
        # Build guided prompt
        new_mastery = result.get("new_level", 0)
        if new_mastery >= MASTERY_THRESHOLD:
            next_prompt = "🎉 Section mastered! Type 'next' to continue."
        elif is_correct:
            next_prompt = f"Well done! {new_mastery}% mastery. Try more exercises or 'next' section."
        else:
            next_prompt = f"Keep practicing! {new_mastery}% mastery. Try another exercise."
        
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


async def handle_add_content(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'add content' intent - add a new panel without replacing existing content."""
    topic = extract_topic_from_add_request(message)
    
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else None
    current_section = get_section_by_id(current_id) if current_id else None
    
    new_section = None
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
        "ChatPanel": "Chat panel"
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
            toc=toc
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
        return await handle_summary(user_id, user_state)


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
    
    if current_mastery >= MASTERY_THRESHOLD:
        # Already mastered
        next_prompt = "🎉 Section mastered! Type 'next' to continue or explore more."
        input_placeholder = "Type 'next' to continue, or ask a question..."
    elif current_mastery > 0:
        # In progress
        next_prompt = f"📊 {current_mastery}% mastery (need 70%). Type 'quiz me' to practice!"
        input_placeholder = "Type 'quiz me' to test yourself, or ask a question..."
    else:
        # Just started
        if has_examples:
            next_prompt = "Ready to test your understanding? Type 'quiz me' or ask a question."
            input_placeholder = "Type 'quiz me' to practice, or ask about the topic..."
        else:
            next_prompt = "Test yourself! Type 'mcq' for a question, or ask me anything."
            input_placeholder = "Type 'mcq' to test yourself, or ask a question..."
    
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
    
    # Add guided prompts to UI
    ui.next_prompt = next_prompt
    ui.input_placeholder = input_placeholder
    
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


async def handle_open_chat(user_id: str, message: str, user_state: dict, context: dict) -> ConversationResponse:
    """Handle 'open chat' intent - add ChatPanel alongside current content."""
    current = user_state.get("current_concept") if user_state else None
    current_id = current.get("sectionId", current.get("id")) if current else None
    current_section = get_section_by_id(current_id) if current_id else None
    
    existing_panels = []
    
    if current_section:
        content = format_content_for_ui(current_section)
        existing_panels.append(
            PanelContent(
                type="ExplanationPanel",
                props={
                    "title": current_section["section_title"],
                    "content": content,
                    "animated": False
                },
                role="primary"
            )
        )
    else:
        existing_panels.append(
            PanelContent(
                type="WelcomeCard",
                props={
                    "title": "AI Chat",
                    "subtitle": "Ask me anything about Gravitation!",
                    "glow": False
                },
                role="primary"
            )
        )
    
    chat_context = {
        "current_section_id": current_id,
        "current_section_title": current_section["section_title"] if current_section else None,
        "user_id": user_id
    }
    
    ui = chat_panel_schema(
        existing_panels=existing_panels,
        current_context=chat_context,
        initial_message=message if message and "?" in message else None
    )
    
    return ConversationResponse(
        ui=ui,
        conversation_context={
            **context,
            "chat_open": True,
            "current_section": current_id,
            "focused_panel": "chat"
        },
        debug={
            "has_current_content": current_section is not None
        }
    )


# ==================== Text-to-Speech Endpoint ====================

class TTSRequest(BaseModel):
    text: str


@router.post("/tutor/speak")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using Groq's Orpheus TTS model.
    
    Model: canopylabs/orpheus-v1-english (Expressive English TTS)
    Voices: Kore, Charon, Fenrir, Aoede, Puck, Ballad, Verse
    Docs: https://console.groq.com/docs/text-to-speech
    """
    import httpx
    from app.config import settings
    from fastapi.responses import Response
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "canopylabs/orpheus-v1-english",
                    "input": request.text,
                    "voice": "austin",  # Valid voices: autumn, diana, hannah, austin, daniel, troy
                    "speed": 1.5,  # Faster speed (1.0 is normal)
                    "response_format": "wav"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    media_type="audio/wav",
                    headers={"Content-Disposition": "inline; filename=speech.wav"}
                )
            else:
                print(f"TTS Error: {response.status_code} - {response.text}")
                # Return 204 No Content to avoid blocking UI
                return Response(content=b"", status_code=204)
                
    except Exception as e:
        print(f"TTS Exception: {e}")
        # Return 204 No Content to avoid blocking UI
        return Response(content=b"", status_code=204)
