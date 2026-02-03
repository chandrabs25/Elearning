"""LangGraph-based Tutor Agent with Socratic prerequisite questioning."""
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# === State Schema ===
class TutorState(TypedDict):
    """State maintained across the conversation."""
    messages: Annotated[list, add_messages]  # Conversation history
    user_id: str
    current_concept_id: str | None  # Section ID (e.g., "7.3")
    current_concept_title: str | None
    concept_content: str | None  # Retrieved content from gravity.json
    prerequisites: list[dict]    # Prerequisite concepts from Neo4j
    insights: list[dict]         # User insights for current concept (from graph)
    
    # Sub-concept progressive teaching
    current_subconcept_id: str | None  # Current sub-concept (e.g., "7.3.1")
    current_subconcept_title: str | None
    total_subconcepts: int  # Total sub-concepts in current section
    explained_subconcept_count: int  # Count of explained sub-concepts
    
    # Context-aware teaching state (populated by analyze_student_context)
    active_misconceptions: list[dict]  # Insights where type == MISCONCEPTION
    active_competencies: list[dict]    # Insights where type == COMPETENCY
    risk_concepts: list[str]           # Concept IDs where student has struggled before
    
    # Socratic flow state
    mode: str  # "normal", "asking_prereq", "evaluating_answer", "explaining_connection", "off_topic", "waiting_to_resume", "awaiting_subsection_verification"
    current_prereq_id: str | None  # The prerequisite we're currently testing
    current_prereq_title: str | None
    prereq_question: str | None   # The question we asked about the prerequisite
    prerequisite_chain: list[str]  # Stack of prerequisites traversed
    prereq_answer_correct: bool   # Whether student answered prereq question correctly
    max_depth: int  # Maximum prerequisite depth (prevent infinite loops)
    
    # Original topic tracking (preserved when going deeper into prereqs)
    main_concept_id: str | None  # Original topic the student asked about
    main_concept_title: str | None
    
    # Off-topic handling
    off_topic_question: str | None  # The off-topic question to answer
    
    # Per-subsection verification
    pending_verification_concept: str | None  # Subsection ID awaiting verification
    pending_verification_title: str | None    # Title of subsection being verified
    verification_question: str | None         # The question asked for verification



# === Neo4j Tools ===
async def get_concept_with_content(concept_id: str) -> dict:
    """Fetch concept details and content from Neo4j + gravity.json.
    
    For subconcepts (e.g., 7.3.1), prerequisites are inherited from the parent section (7.3).
    """
    from app.graph.client import neo4j_client
    from app.chains.content import get_section_by_id, format_content_for_ui, extract_section_text
    
    # Get concept metadata and prerequisites from Neo4j
    # For subconcepts, also look up parent's prerequisites via PART_OF relationship
    query = """
    MATCH (c:Concept {id: $concept_id})
    
    // Direct prerequisites of this concept
    OPTIONAL MATCH (c)-[:REQUIRES]->(direct_prereq:Concept)
    
    // Parent's prerequisites (for subconcepts like 7.3.1 -> 7.3)
    OPTIONAL MATCH (c)-[:PART_OF]->(parent:Concept)-[:REQUIRES]->(parent_prereq:Concept)
    
    WITH c, 
         collect(DISTINCT {
             id: direct_prereq.id, 
             title: direct_prereq.title, 
             description: direct_prereq.description,
             isPrerequisite: direct_prereq.isPrerequisite
         }) as direct_prereqs,
         collect(DISTINCT {
             id: parent_prereq.id, 
             title: parent_prereq.title, 
             description: parent_prereq.description,
             isPrerequisite: parent_prereq.isPrerequisite
         }) as parent_prereqs
    
    RETURN c, direct_prereqs + parent_prereqs as prerequisites
    """
    result = await neo4j_client.execute_read_single(query, concept_id=concept_id)
    
    # Determine section ID for content lookup
    # For subconcept 7.3.1, get content from parent section 7.3
    section_id = concept_id
    if concept_id.count('.') >= 2:
        # This is a subconcept (e.g., 7.3.2) - get parent section (7.3)
        section_id = '.'.join(concept_id.split('.')[:2])
    
    # Get content from gravity.json
    section = get_section_by_id(section_id)
    content = format_content_for_ui(section) if section else []
    
    # Use shared helper for text extraction
    content_text = extract_section_text(section)
    
    # Filter out empty prerequisites and deduplicate by id
    prereqs = []
    seen_ids = set()
    for p in (result["prerequisites"] if result else []):
        pid = p.get("id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            prereqs.append(p)
    
    return {
        "concept": result["c"] if result else None,
        "prerequisites": prereqs,
        "content": content,
        "content_text": content_text,
        "section_title": section.get("section_title") if section else None
    }



# === Agent Nodes ===
async def retrieve_context(state: TutorState) -> TutorState:
    """Retrieve concept content, prerequisites, and user insights from Neo4j.
    
    Always fetches prerequisites and insights to enable personalized Socratic flow.
    Only skips content retrieval if already provided.
    """
    from app.graph.user_state import get_insights_for_concept
    
    concept_id = state.get("current_concept_id") or "7.3"
    user_id = state.get("user_id")
    
    # Always fetch prerequisites for Socratic flow
    try:
        data = await get_concept_with_content(concept_id)
        
        # Only update content if not already provided (from RAG)
        if not state.get("concept_content"):
            state["concept_content"] = data["content_text"]
            state["current_concept_title"] = data["section_title"] or f"Section {concept_id}"
        
        # Always update prerequisites from Neo4j
        state["prerequisites"] = data["prerequisites"]
        
        # Fetch user insights for this concept
        if user_id:
            insights = await get_insights_for_concept(user_id, concept_id)
            state["insights"] = insights
            print(f"[Insights] Found {len(insights)} insights for user {user_id} on {concept_id}")
        else:
            state["insights"] = []
        
        # Debug: Log what we found
        prereq_count = len(state["prerequisites"])
        print(f"[Socratic] Found {prereq_count} prerequisites for {concept_id}: {[p.get('title') for p in state['prerequisites']]}")
        
    except Exception as e:
        print(f"Error retrieving context: {e}")
        if not state.get("concept_content"):
            state["concept_content"] = ""
        state["prerequisites"] = []
        state["insights"] = []
    
    # Initialize mode if not set
    if not state.get("mode"):
        state["mode"] = "normal"
    if state.get("max_depth") is None:
        state["max_depth"] = 3
    
    return state


async def analyze_student_context(state: TutorState) -> TutorState:
    """Analyze student insights to set teaching strategy for this turn.
    
    This node runs after retrieve_context and before understand_question.
    It categorizes insights and identifies concepts where the student has struggled,
    enabling proactive teaching adjustments.
    """
    insights = state.get("insights", [])
    
    # Categorize insights by type
    misconceptions = [i for i in insights if i.get("type") == "MISCONCEPTION"]
    competencies = [i for i in insights if i.get("type") == "COMPETENCY"]
    
    state["active_misconceptions"] = misconceptions
    state["active_competencies"] = competencies
    
    # Identify risk concepts - concepts where student has struggled before
    # These are extracted from misconception insights' concept_ids
    risk_concepts = set()
    for m in misconceptions:
        # Get concept_ids from the insight if available
        concept_ids = m.get("concept_ids", [])
        if concept_ids:
            risk_concepts.update(concept_ids)
    
    state["risk_concepts"] = list(risk_concepts)
    
    # Log context analysis results
    if misconceptions:
        print(f"[Context] Found {len(misconceptions)} misconceptions, {len(risk_concepts)} risk concepts")
    if competencies:
        print(f"[Context] Found {len(competencies)} competencies")
    
    return state


async def understand_question(state: TutorState) -> TutorState:
    """Analyze user's message using LLM to detect confusion or need for prerequisite help."""
    from app.config import settings
    
    last_message = state["messages"][-1].content if state["messages"] else ""
    
    # If we asked if they want to resume after off-topic
    if state.get("mode") == "waiting_to_resume":
        try:
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                api_key=settings.groq_api_key
            )
            
            concept_title = state.get("current_concept_title", "the topic")
            
            classify_prompt = f"""The tutor asked if the student wants to continue learning about "{concept_title}".

Student's response: "{last_message}"

Is the student:
- YES_CONTINUE: Saying yes, agreeing, or ready to continue learning
- NO_CONTINUE: Saying no, wants to do something else, or has another question
- UNCLEAR: Response is unclear or doesn't address the question

Respond with ONLY one word: YES_CONTINUE, NO_CONTINUE, or UNCLEAR."""

            response = await llm.ainvoke([HumanMessage(content=classify_prompt)])
            classification = response.content.strip().upper()
            
            print(f"[Off-Topic] Resume response: {classification}")
            
            if "YES_CONTINUE" in classification:
                state["mode"] = "ready_to_continue"
                return state
            else:
                # Student doesn't want to continue - treat as new question
                state["mode"] = "normal"
                # Fall through to normal processing
                
        except Exception as e:
            print(f"[Off-Topic] Resume classification error: {e}")
            state["mode"] = "normal"
    
    # If we were waiting for an answer to a prerequisite question
    if state.get("mode") == "asking_prereq" and state.get("prereq_question"):
        # Check if the response is actually an attempt to answer, or something unrelated
        try:
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                api_key=settings.groq_api_key
            )
            
            prereq_title = state.get("current_prereq_title", "the concept")
            prereq_question = state.get("prereq_question", "")
            
            classify_prompt = f"""The tutor asked this question about "{prereq_title}":
"{prereq_question}"

Student's response: "{last_message}"

Is the student:
- ANSWERING: Attempting to answer the question (even if wrong or partial)
- CONFUSED: Expressing they don't understand or need help
- OFF_TOPIC: Ignoring the question, asking something unrelated, or changing the subject

Respond with ONLY one word: ANSWERING, CONFUSED, or OFF_TOPIC."""

            response = await llm.ainvoke([HumanMessage(content=classify_prompt)])
            classification = response.content.strip().upper()
            
            print(f"[Socratic] Prereq response classification: {classification}")
            
            if "OFF_TOPIC" in classification:
                # Student is ignoring the prereq question - answer their question instead
                print(f"[Socratic] Off-topic response detected, routing to off_topic handler")
                state["mode"] = "off_topic"
                state["off_topic_question"] = last_message
                state["prereq_question"] = None  # Clear the pending question
                return state  # Route to answer_off_topic node
            elif "CONFUSED" in classification:
                # Student needs help with the prereq itself - go deeper
                state["prereq_answer_correct"] = False
                state["mode"] = "evaluating_answer"
                return state
            else:
                # Student is attempting to answer - evaluate it
                state["mode"] = "evaluating_answer"
                return state
                
        except Exception as e:
            print(f"[Socratic] Response classification error: {e}, defaulting to evaluation")
            state["mode"] = "evaluating_answer"
            return state
    
    # If we are checking if user is familiar with prerequisites
    if state.get("mode") == "checking_prereq_familiarity":
        try:
             # Use LLM to classify response
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                api_key=settings.groq_api_key
            )
            
            prompt = f"""The tutor asked the student if they are familiar with these prerequisites: {', '.join([p['title'] for p in state.get('prerequisites', [])])}.

Student response: "{last_message}"

Classify the student's response:
- KNOWS_PREREQS: Student says "yes", "I know them", "I'm familiar", or explains them correctly.
- NEEDS_EXPLANATION: Student says "no", "explain them", "I don't know", "what are they?".
- OTHER: Student ignores the question or asks something unrelated.

Respond with ONLY one word: KNOWS_PREREQS, NEEDS_EXPLANATION, or OTHER."""

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            classification = response.content.strip().upper()
            
            print(f"[Socratic] Prereq familiarity check: {classification}")
            
            if "KNOWS_PREREQS" in classification:
                state["mode"] = "ready_to_continue"
                return state
            elif "NEEDS_EXPLANATION" in classification:
                state["mode"] = "explain_prereqs"
                return state
            else:
                # Fallback to normal flow if response is unrelated
                state["mode"] = "normal"
                
        except Exception as e:
            print(f"[Socratic] Familiarity check error: {e}")
            state["mode"] = "normal"

    try:
        # Use LLM to detect if student is confused or needs help
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            api_key=settings.groq_api_key
        )
        
        concept_title = state.get("current_concept_title", "the topic")
        
        prompt = f"""Analyze this student message in the context of learning about "{concept_title}":

Student message: "{last_message}"

Is the student expressing VALID CONFUSION about the content, or just asking an initial question?

Signs of valid confusion (NEEDS PREREQ HELP):
- "I don't understand that explanation"
- "But why is...?" (challenging the explanation)
- "I'm lost", "This doesn't make sense"
- "What do you mean by [previous concept]?"

Signs of NORMAL LEARNING (DO NOT TRIGGER PREREQ CHECK):
- "Can you explain {concept_title}?" (Initial request)
- "What is gravity?"
- "Teach me about this."
- "Give me an example."

Respond with ONLY one word:
- CONFUSED: if they are struggling with an explanation you already gave.
- CLEAR: for initial questions, requests for explanation, or simple facts."""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        needs_help = "CONFUSED" in response.content.upper()
        print(f"[Socratic] Confusion detection (LLM): {needs_help} for '{last_message[:50]}...'")
            
    except Exception as e:
        print(f"[Socratic] Confusion detection error: {e}, falling back to keyword match")
        # Fallback to keyword detection - be more conservative
        confusion_keywords = ["don't understand", "im lost", "i'm lost", "confusing", "doesn't make sense"]
        needs_help = any(kw in last_message.lower() for kw in confusion_keywords)
    
    # Route to prereq check if confused and we have prerequisites to check
    has_prereqs = bool(state.get("prerequisites"))
    under_depth_limit = len(state.get("prerequisite_chain", [])) < state.get("max_depth", 3)
    
    if needs_help and has_prereqs and under_depth_limit:
        state["mode"] = "needs_prereq_check"
        print(f"[Socratic] Triggering prereq check - has {len(state['prerequisites'])} prerequisites")
    else:
        state["mode"] = "normal"
        if needs_help and not has_prereqs:
            print(f"[Socratic] Student confused but no prerequisites available")
    
    return state


async def ask_prereq_question(state: TutorState) -> TutorState:
    """Ask the student a question about the prerequisite to assess their understanding."""
    from app.config import settings
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    # Get the next prerequisite to test
    prereqs = state.get("prerequisites", [])
    already_tested = state.get("prerequisite_chain", [])
    risk_concepts = set(state.get("risk_concepts", []))
    
    # Prioritize risky prereqs first, then others
    prereq = None
    for p in prereqs:
        pid = p.get("id")
        if pid and pid not in already_tested:
            if pid in risk_concepts:
                prereq = p  # Found a risky prereq - test this first
                break
    
    # If no risky prereqs found, test any untested prereq
    if not prereq:
        for p in prereqs:
            if p.get("id") and p.get("id") not in already_tested:
                prereq = p
                break
    
    if not prereq:
        # No more prerequisites to test, just answer
        state["mode"] = "normal"
        return state
    
    prereq_id = prereq.get("id", "")
    prereq_title = prereq.get("title", "this concept")
    prereq_desc = prereq.get("description", "")
    is_risky = prereq_id in risk_concepts
    
    # Get more content for the prerequisite if available
    prereq_content = ""
    if prereq_id:
        try:
            prereq_data = await get_concept_with_content(prereq_id)
            prereq_content = prereq_data.get("content_text", "")[:500]
        except:
            pass
    
    # Context-aware prompt: gentler approach if student has prior struggle
    if is_risky:
        prompt = f"""You are a caring physics tutor. The student is learning "{state.get('current_concept_title', 'the topic')}".

Based on past interactions, this student has struggled with a related concept: "{prereq_title}".

You want to gently check their current understanding WITHOUT making them feel bad about past struggles.

Prerequisite: {prereq_title}
Description: {prereq_desc}
{f'Key content: {prereq_content}' if prereq_content else ''}

Generate a supportive, non-judgmental question to check if they now understand this concept.
Frame it as a quick refresher, not a test.

Format: "Let's do a quick warm-up before we tackle {state.get('current_concept_title', 'this topic')}: [YOUR QUESTION HERE]"

Be extra warm and encouraging since this was tricky for them before."""
    else:
        prompt = f"""You are a physics tutor using the Socratic method. The student is struggling with "{state.get('current_concept_title', 'the topic')}".

Before explaining, you need to check if they understand a prerequisite concept.

Prerequisite: {prereq_title}
Description: {prereq_desc}
{f'Key content: {prereq_content}' if prereq_content else ''}

Generate a simple, conceptual question (NOT a calculation) to check if the student understands this prerequisite.
The question should be answerable in 1-2 sentences.

Format your response as:
"Before we dive into {state.get('current_concept_title', 'this topic')}, let me check something: [YOUR QUESTION HERE]"

Be friendly and encouraging."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    # Update state
    state["current_prereq_id"] = prereq_id
    state["current_prereq_title"] = prereq_title
    state["prereq_question"] = response.content
    state["mode"] = "asking_prereq"
    state["messages"] = state.get("messages", []) + [AIMessage(content=response.content)]
    
    return state



async def evaluate_prereq_answer(state: TutorState) -> TutorState:
    """Evaluate if the student's answer to the prerequisite question is correct."""
    from app.config import settings
    from app.graph.user_state import create_insight
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.2,
        api_key=settings.groq_api_key
    )
    
    # Get the student's answer (last human message)
    student_answer = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            student_answer = msg.content
            break
    
    prereq_title = state.get("current_prereq_title", "the concept")
    prereq_id = state.get("current_prereq_id", "")
    main_concept_id = state.get("current_concept_id", "")
    main_concept_title = state.get("current_concept_title", "the topic")
    user_id = state.get("user_id")
    
    # Get prerequisite content for evaluation
    prereq_content = ""
    if prereq_id:
        try:
            prereq_data = await get_concept_with_content(prereq_id)
            prereq_content = prereq_data.get("content_text", "")[:1000]
        except:
            pass
    
    evaluation_prompt = f"""You are evaluating a student's understanding of "{prereq_title}".

The question asked: {state.get('prereq_question', '')}

Student's answer: "{student_answer}"

Correct concept information: {prereq_content if prereq_content else 'General physics knowledge of ' + prereq_title}

Does the student demonstrate adequate understanding of the prerequisite concept?
Consider: They don't need to be perfect, just show they grasp the basic idea.

Respond with ONLY one word:
- "CORRECT" if they show adequate understanding
- "INCORRECT" if they don't understand or are significantly wrong"""

    response = await llm.ainvoke([HumanMessage(content=evaluation_prompt)])
    
    is_correct = "CORRECT" in response.content.upper()
    state["prereq_answer_correct"] = is_correct
    
    # Generate insight based on the evaluation
    if user_id and prereq_id:
        try:
            concept_ids = [prereq_id]
            if main_concept_id and main_concept_id != prereq_id:
                concept_ids.append(main_concept_id)
            
            if not is_correct:
                # Create MISCONCEPTION insight
                await create_insight(
                    user_id=user_id,
                    insight_type="MISCONCEPTION",
                    content=f"Struggled with '{prereq_title}' when learning '{main_concept_title}'",
                    concept_ids=concept_ids,
                    confidence=0.8
                )
                print(f"[Insight] Created MISCONCEPTION for {prereq_title}")
        except Exception as e:
            print(f"[Insight] Error creating insight: {e}")
    
    # Add to prerequisite chain (we've now tested this one)
    if prereq_id and prereq_id not in state.get("prerequisite_chain", []):
        state["prerequisite_chain"] = state.get("prerequisite_chain", []) + [prereq_id]
    
    return state


async def explain_connection(state: TutorState) -> TutorState:
    """Student answered correctly - explain how prerequisite connects to current topic."""
    from app.config import settings
    from app.graph.user_state import create_insight, supersede_insight
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    prereq_id = state.get("current_prereq_id", "")
    prereq_title = state.get("current_prereq_title", "the prerequisite")
    main_concept_id = state.get("current_concept_id", "")
    main_concept_title = state.get("current_concept_title", "the topic")
    user_id = state.get("user_id")
    
    # Create COMPETENCY insight for understanding the link
    new_insight_id = None
    if user_id and prereq_id:
        try:
            concept_ids = [prereq_id]
            if main_concept_id and main_concept_id != prereq_id:
                concept_ids.append(main_concept_id)
            
            new_insight = await create_insight(
                user_id=user_id,
                insight_type="COMPETENCY",
                content=f"Understood link between '{prereq_title}' and '{main_concept_title}'",
                concept_ids=concept_ids,
                confidence=0.9
            )
            new_insight_id = new_insight.get("id")
            print(f"[Insight] Created COMPETENCY for {prereq_title} -> {main_concept_title}")
            
            # Supersede any existing MISCONCEPTION insights for this prereq
            # This marks the student's progress from "struggling" to "understanding"
            existing_misconceptions = [
                i for i in state.get("active_misconceptions", [])
                if prereq_id in i.get("concept_ids", [])
            ]
            
            for old_insight in existing_misconceptions:
                old_id = old_insight.get("id")
                if old_id and new_insight_id:
                    await supersede_insight(old_id, new_insight_id)
                    print(f"[Insight] Superseded misconception: {old_insight.get('content', old_id)}")
                    
        except Exception as e:
            print(f"[Insight] Error creating/superseding insight: {e}")
    
    prompt = f"""You are a physics tutor. The student just correctly explained their understanding of "{prereq_title}".

Now, connect this prerequisite to the main topic they're learning: "{main_concept_title}"

Main topic content:
{state.get('concept_content', '')[:2000]}

Your response should:
1. Briefly acknowledge their correct understanding (1 sentence)
2. Explain how the prerequisite connects to and enables understanding of the current topic (2-3 paragraphs)
3. Use LaTeX for equations ($$...$$)
4. Now explain the current topic clearly

Be encouraging!"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    state["mode"] = "normal"
    state["messages"] = state.get("messages", []) + [AIMessage(content=response.content)]
    
    return state


async def go_deeper_prereq(state: TutorState) -> TutorState:
    """Student didn't understand prereq - go to the prerequisite's prerequisites."""
    from app.config import settings
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    current_prereq_id = state.get("current_prereq_id", "")
    current_prereq_title = state.get("current_prereq_title", "that concept")
    
    # Get the prerequisites OF the current prerequisite
    deeper_prereqs = []
    if current_prereq_id:
        try:
            prereq_data = await get_concept_with_content(current_prereq_id)
            deeper_prereqs = prereq_data.get("prerequisites", [])
        except:
            pass
    
    if deeper_prereqs and len(state.get("prerequisite_chain", [])) < state.get("max_depth", 3):
        # There are deeper prerequisites - update state to test those
        # Preserve original topic before going deeper
        if not state.get("main_concept_id"):
            state["main_concept_id"] = state.get("current_concept_id")
            state["main_concept_title"] = state.get("current_concept_title")
        
        state["prerequisites"] = deeper_prereqs
        state["current_concept_id"] = current_prereq_id
        state["current_concept_title"] = current_prereq_title
        
        # Generate encouraging response about going deeper
        response_text = f"""No worries! It seems like we need to revisit some foundational concepts first. 
Let me help you understand {current_prereq_title} step by step.

Let me ask you about something even more fundamental..."""
        
        state["mode"] = "needs_prereq_check"
        state["messages"] = state.get("messages", []) + [AIMessage(content=response_text)]
    else:
        # No deeper prerequisites or max depth reached - just explain
        prompt = f"""You are a physics tutor. The student is struggling with "{current_prereq_title}".

Explain this prerequisite concept from the ground up, assuming minimal prior knowledge.
Be very clear and use simple analogies where possible.
Use LaTeX for equations ($$...$$).

After explaining, ask if they now understand better."""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        state["mode"] = "asking_prereq"  # Will check understanding again
        state["prereq_question"] = "Do you understand this now? Can you explain it in your own words?"
        state["messages"] = state.get("messages", []) + [AIMessage(content=response.content)]
    
    return state


async def get_mastery_suggestion(user_id: str, concept_id: str) -> str:
    """Check mastery and generate suggestion if threshold met."""
    from app.graph.user_state import get_section_mastery
    
    if not concept_id or not user_id:
        return ""
        
    try:
        mastery = await get_section_mastery(user_id, concept_id)
        level = mastery.get("level", 0)
        
        if level >= 70:
            return "\n\n(Tip: Validated mastery level is high. Suggest taking a Quiz or Challenge for this topic!)"
        elif level >= 30:
            return "\n\n(Tip: Validated mastery level is moderate. Suggest trying some Practice Exercises!)"
        return ""
    except:
        return ""


async def answer_question(state: TutorState) -> TutorState:
    """Generate answer using progressive sub-concept teaching.
    
    Teaches one sub-concept at a time, marks each as explained,
    and advances to the next sub-concept after each explanation.
    """
    from app.config import settings
    from app.graph.user_state import (
        mark_concept_explained, 
        get_section_learning_status,
        get_first_unexplained_subconcept,
        get_next_subconcept,
        get_subconcepts_for_section
    )
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    user_id = state.get("user_id")
    section_id = state.get("current_concept_id")  # e.g., "7.3"
    section_title = state.get("current_concept_title")
    
    # Check if we have prerequisites to introduce first
    prereqs = state.get("prerequisites", [])
    prereq_list = ", ".join([p["title"] for p in prereqs]) if prereqs else ""
    
    if prereq_list and state.get("mode") != "checking_prereq_familiarity":
        # Introduce prerequisites first
        system_prompt = f"""You are an AI physics tutor helping a student learn about:
**{section_title}**

Textbook content:
---
{state.get('concept_content', '')[:2500]}
---

Prerequisites for this topic: {prereq_list}

Guidelines:
1. Briefly introduce the topic based on the student's question.
2. Explicitly list the prerequisite concepts ({prereq_list}).
3. Explain that understanding these is key to mastering the current topic.
4. Ask the student: "Are you familiar with these concepts and how they relate to {section_title}?"
5. Do NOT explain the prerequisites in detail yet - wait for their answer.
"""
        state["mode"] = "checking_prereq_familiarity"
    else:
        # Progressive sub-concept teaching mode
        current_subconcept_id = state.get("current_subconcept_id")
        
        # If no current sub-concept, find the first unexplained one
        if not current_subconcept_id and user_id and section_id:
            try:
                unexplained = await get_first_unexplained_subconcept(user_id, section_id)
                if unexplained:
                    current_subconcept_id = unexplained["id"]
                    state["current_subconcept_id"] = current_subconcept_id
                    state["current_subconcept_title"] = unexplained["title"]
                    state["current_subconcept_description"] = unexplained.get("description", "")
            except Exception as e:
                print(f"[SubConcept] Error getting first unexplained: {e}")
        
        # Get all subconcepts for progress display
        all_subconcepts = []
        if section_id:
            try:
                all_subconcepts = await get_subconcepts_for_section(section_id)
                state["total_subconcepts"] = len(all_subconcepts)
            except Exception as e:
                print(f"[SubConcept] Error getting subconcepts: {e}")
        
        # Build subconcept-focused content if we have a current subconcept
        subconcept_content = state.get('concept_content', '')[:2500]
        subconcept_title = state.get("current_subconcept_title", "")
        progress_info = ""
        
        if current_subconcept_id and all_subconcepts:
            # Find current index
            current_idx = next((i for i, sc in enumerate(all_subconcepts) if sc["id"] == current_subconcept_id), 0)
            progress_info = f"\n\n📍 **Currently Teaching:** {subconcept_title} ({current_idx + 1}/{len(all_subconcepts)})"
        
        # Build insight context
        insights = state.get("insights", [])
        insight_context = ""
        if insights:
            insight_lines = []
            for i in insights:
                insight_type = i.get("type", "")
                content = i.get("content", "")
                if insight_type == "MISCONCEPTION":
                    insight_lines.append(f"- ⚠️ Previous struggle: {content}")
                elif insight_type == "COMPETENCY":
                    insight_lines.append(f"- ✅ Demonstrated understanding: {content}")
                elif insight_type == "PREFERENCE":
                    insight_lines.append(f"- 💡 Preference: {content}")
            if insight_lines:
                insight_context = "\n\n**Student History (use this to personalize your response):**\n" + "\n".join(insight_lines)
        
        # Get mastery-based suggestion
        suggestion = await get_mastery_suggestion(user_id, section_id)
        
        # Get subconcept description for focused teaching
        subconcept_description = state.get("current_subconcept_description", "")
        
        # Build system prompt for current sub-concept
        subconcept_focus = ""
        if subconcept_title:
            subconcept_focus = f"""
=== TEACHING TARGET (MUST TEACH ONLY THIS) ===
Subconcept: {subconcept_title}
{f"What this covers: {subconcept_description}" if subconcept_description else ""}
==============================================
"""
        
        # Truncate section content to reduce distraction
        section_context = subconcept_content[:1500] if subconcept_content else ""
        
        system_prompt = f"""You are an AI physics tutor. You MUST follow these rules strictly:

**Section:** {section_title}
{progress_info}

{subconcept_focus}

**Reference Material (do NOT explain everything here - ONLY use to find content about the current subconcept):**
---
{section_context}
---
{insight_context}

=== CRITICAL RULES ===
1. ONLY teach the subconcept "{subconcept_title}" - DO NOT explain other concepts from this section
2. Keep your explanation CONCISE (2-3 paragraphs maximum)
3. Use LaTeX for equations: $$equation$$
4. DO NOT give multiple choice options or ask what topic they want next
5. End by saying you'll now check their understanding

=== RESPONSE FORMAT ===
1. Brief greeting/acknowledgment (1 sentence)
2. Clear explanation of ONLY "{subconcept_title}" (2-3 paragraphs)
3. End with: "Let me check your understanding of this concept..."{suggestion}"""
    
    # Build messages for LLM
    messages_for_llm = [SystemMessage(content=system_prompt)]
    for msg in state.get("messages", [])[-5:]:
        if hasattr(msg, 'content'):
            if isinstance(msg, HumanMessage):
                messages_for_llm.append(HumanMessage(content=msg.content))
            elif isinstance(msg, AIMessage):
                messages_for_llm.append(AIMessage(content=msg.content))
    
    response = await llm.ainvoke(messages_for_llm)
    response_text = response.content
    
    # Mark current concept/subconcept as explained
    # IMPORTANT: Only mark as explained when we're actually TEACHING, not when asking about prerequisites
    current_mode = state.get("mode", "normal")
    should_mark_explained = current_mode not in ["checking_prereq_familiarity", "asking_prereq", "evaluating_answer"]
    
    if user_id and should_mark_explained:
        try:
            # Determine what to mark as explained
            concept_to_mark = state.get("current_subconcept_id") or section_id
            
            if concept_to_mark:
                await mark_concept_explained(user_id, concept_to_mark)
                
                # Also mark parent section to ensure section-level tracking works
                if state.get("current_subconcept_id") and section_id:
                    await mark_concept_explained(user_id, section_id)
                
                # Get updated section status
                section_status = await get_section_learning_status(user_id, section_id)
                explained_count = section_status.get("explained_count", 0)
                total_count = section_status.get("total_count", 0)
                
                state["explained_subconcept_count"] = explained_count
                
                # Add progress indicator to response
                if total_count > 0:
                    progress_text = f"\n\n📊 **Progress:** {explained_count}/{total_count} concepts covered"
                    
                    if section_status.get("all_explained"):
                        if not section_status.get("all_verified"):
                            response_text += f"\n\n🎉 **You've covered all {total_count} concepts in this section!** Click 'Check Understanding' when you're ready to verify your knowledge."
                        else:
                            response_text += f"\n\n✅ **Section complete!** You've mastered all concepts. Ready for the next section?"
                    else:
                        # Not all concepts explained yet - show progress and remind about button
                        response_text += progress_text
                        # Remind user about the verification button
                        unverified_count = explained_count - section_status.get("verified_count", 0)
                        if unverified_count > 0:
                            response_text += f"\n\n💡 *When you're ready, click the 'Check Understanding' button to verify!*"

        except Exception as e:
            print(f"[Tracking] Error marking concept explained: {e}")
    
    state["messages"] = state.get("messages", []) + [AIMessage(content=response_text)]
    
    return state



async def continue_topic(state: TutorState) -> TutorState:
    """User knows prerequisites - teach the CURRENT SUBCONCEPT only.
    
    This function:
    1. Teaches ONE subconcept using a strict prompt
    2. Marks the subconcept as explained
    3. Returns with mode = 'normal'
    
    Verification is triggered by the UI's 'Check Understanding' button,
    not by the agent. See /api/tutor/check-understanding and /api/tutor/verify-understanding.
    """
    from app.config import settings
    from app.graph.user_state import (
        mark_concept_explained, 
        get_section_learning_status, 
        get_next_subconcept,
        get_subconcepts_for_section
    )
    
    user_id = state.get("user_id")
    section_id = state.get("current_concept_id")
    section_title = state.get("current_concept_title", "this section")
    current_sc = state.get("current_subconcept_id")
    current_sc_title = state.get("current_subconcept_title", "the first concept")
    current_sc_desc = state.get("current_subconcept_description", "")
    
    # If no subconcept set, get the first one
    if not current_sc and section_id:
        try:
            all_subconcepts = await get_subconcepts_for_section(section_id)
            if all_subconcepts:
                current_sc = all_subconcepts[0]["id"]
                current_sc_title = all_subconcepts[0]["title"]
                current_sc_desc = all_subconcepts[0].get("description", "")
                state["current_subconcept_id"] = current_sc
                state["current_subconcept_title"] = current_sc_title
                state["current_subconcept_description"] = current_sc_desc
        except Exception as e:
            print(f"[continue_topic] Error getting subconcepts: {e}")
    
    # Truncate content to reduce noise
    section_content = state.get('concept_content', '')[:1500]
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    # STRICT subconcept-focused prompt
    system_prompt = f"""You are an AI physics tutor. The student confirmed they understand prerequisites.

═══════════════════════════════════════════════════════════════
TEACHING TARGET: "{current_sc_title}" (Sub-concept {current_sc})
═══════════════════════════════════════════════════════════════

**SECTION:** {section_title}
**SUBCONCEPT:** {current_sc_title}
{f"**DESCRIPTION:** {current_sc_desc}" if current_sc_desc else ""}

Reference material (for context ONLY):
---
{section_content}
---

═══════════ CRITICAL RULES ═══════════
1. ONLY explain "{current_sc_title}" - nothing else
2. Keep explanation to 2-3 short paragraphs maximum
3. Start with: "Great! Let's begin with **{current_sc_title}**."
4. Use LaTeX for equations: $$equation$$
5. Do NOT explain other topics or laws
6. Do NOT ask follow-up questions - just explain the concept
7. End your explanation naturally (I will add a verification question)

FORBIDDEN: Do not teach the entire section. Focus ONLY on this single sub-concept.
"""
    
    messages_for_llm = [SystemMessage(content=system_prompt)]
    # Add minimal context
    for msg in state.get("messages", [])[-2:]:
        if isinstance(msg, HumanMessage):
            messages_for_llm.append(msg)
    
    response = await llm.ainvoke(messages_for_llm)
    response_text = response.content
    
    # Mark subconcept as explained
    if user_id and current_sc:
        try:
            await mark_concept_explained(user_id, current_sc)
            print(f"[continue_topic] Marked {current_sc} as explained for {user_id}")
            
            # Also mark parent section
            if section_id and section_id != current_sc:
                await mark_concept_explained(user_id, section_id)
        except Exception as e:
            print(f"[continue_topic] Error marking explained: {e}")
    
    # Get progress info and add helpful message about verification button
    progress_text = ""
    if user_id and section_id:
        try:
            section_status = await get_section_learning_status(user_id, section_id)
            explained_count = section_status.get("explained_count", 0)
            total_count = section_status.get("total_count", 0)
            if total_count > 0:
                progress_text = f"\n\n📊 **Progress:** {explained_count}/{total_count} concepts covered"
                # Remind about the verification button
                if explained_count > 0 and not section_status.get("all_verified"):
                    progress_text += "\n\n💡 *When you're ready, click the 'Check Understanding' button to verify!*"
        except Exception as e:
            print(f"[continue_topic] Error getting status: {e}")
    
    # Append progress to response
    response_text += progress_text
    
    # Set mode to normal - verification happens via UI button, not inline
    state["mode"] = "normal"
    
    state["messages"] = state.get("messages", []) + [AIMessage(content=response_text)]
    return state





async def explain_prereqs(state: TutorState) -> TutorState:
    """User doesn't know prerequisites - explain them."""
    from app.config import settings
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    prereqs = state.get("prerequisites", [])
    prereq_titles = ", ".join([p["title"] for p in prereqs])
    
    system_prompt = f"""You are an AI physics tutor. The student needs help understanding prerequisites for **{state.get('current_concept_title')}**.

Prerequisites to explain: {prereq_titles}

Guidelines:
1. Explain these prerequisite concepts clearly and simply.
2. Use analogies if helpful.
3. Relate them back to why they feature in {state.get('current_concept_title')}.
4. After explaining, ask: "Does that make sense? Are you ready to continue with {state.get('current_concept_title')}?"
"""

    response = await llm.ainvoke([SystemMessage(content=system_prompt)])
    
    # After explaining, we set mode to check familiarity again (or just normal to let them respond)
    # Let's set to normal but with context that we just explained
    state["mode"] = "checking_prereq_familiarity" 
    state["messages"] = state.get("messages", []) + [AIMessage(content=response.content)]
    return state


async def answer_off_topic(state: TutorState) -> TutorState:
    """Answer an off-topic question and redirect back to the current topic."""
    from app.config import settings
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.6,
        api_key=settings.groq_api_key
    )
    
    off_topic_question = state.get("off_topic_question", "")
    current_topic = state.get("current_concept_title", "the topic we were discussing")
    
    prompt = f"""You are a friendly AI physics tutor. The student has asked an off-topic question while you were teaching about "{current_topic}".

Off-topic question: "{off_topic_question}"

Your response should:
1. Briefly and helpfully answer their question (keep it concise - just 1-2 sentences)
2. Then naturally transition back to the learning topic
3. End by asking if they'd like to continue learning about "{current_topic}"

Be warm and don't make the student feel bad for asking. Something like:
"[Brief answer]. By the way, we were learning about {current_topic}. Would you like to continue where we left off?"

Keep your total response under 100 words."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    # Set mode to waiting for resume confirmation
    state["mode"] = "waiting_to_resume"
    state["off_topic_question"] = None  # Clear the question
    state["messages"] = state.get("messages", []) + [AIMessage(content=response.content)]
    
    return state


# === Routing Logic ===
def route_after_understand(state: TutorState) -> Literal["ask_prereq_question", "evaluate_prereq_answer", "answer", "continue_topic", "explain_prereqs", "answer_off_topic"]:
    """Route based on current mode and context-aware analysis.
    
    If prerequisites overlap with risk_concepts (where student has struggled before),
    proactively ask about them even in normal mode.
    """
    mode = state.get("mode", "normal")
    
    if mode == "needs_prereq_check":
        return "ask_prereq_question"
    elif mode == "evaluating_answer" or mode == "asking_prereq":
        # When in asking_prereq mode, the next user message is their answer
        return "evaluate_prereq_answer"
    elif mode == "ready_to_continue":
        return "continue_topic"
    elif mode == "explain_prereqs":
        return "explain_prereqs"
    elif mode == "off_topic":
        return "answer_off_topic"
    else:
        # Context-aware routing: check if any prerequisite is risky
        risk_concepts = set(state.get("risk_concepts", []))
        prereqs = state.get("prerequisites", [])
        prereq_ids = {p.get("id") for p in prereqs if p.get("id")}
        already_tested = set(state.get("prerequisite_chain", []))
        
        # Also consider prereqs where user already has COMPETENCY insight
        # This prevents re-testing prereqs across different sessions
        competency_concept_ids = set()
        for comp in state.get("active_competencies", []):
            for cid in comp.get("concept_ids", []):
                competency_concept_ids.add(cid)
        
        # Combine session-tested and competency-proven prereqs
        already_proven = already_tested | competency_concept_ids
        
        # Find risky prereqs that haven't been tested yet
        risky_untested = (prereq_ids & risk_concepts) - already_proven
        
        if risky_untested:
            print(f"[Context] Proactive prereq check: {risky_untested} are risky and untested")
            state["mode"] = "needs_prereq_check"
            return "ask_prereq_question"
        
        return "answer"


def route_after_evaluation(state: TutorState) -> Literal["explain_connection", "go_deeper"]:
    """Route based on whether student answered prereq correctly."""
    if state.get("prereq_answer_correct", False):
        return "explain_connection"
    else:
        return "go_deeper"


def route_after_go_deeper(state: TutorState) -> str:
    """Route after go_deeper based on mode.
    
    - needs_prereq_check: Ask another prereq question
    - asking_prereq: Wait for user response (END)
    - otherwise: Answer the question
    """
    mode = state.get("mode")
    if mode == "needs_prereq_check":
        return "ask_prereq_question"
    elif mode == "asking_prereq":
        return "__end__"  # Wait for user response after explaining
    return "answer"

# === Build Graph ===
def build_tutor_graph() -> StateGraph:
    """Construct the LangGraph tutor agent with Socratic prerequisite flow and exercise evaluation."""
    graph = StateGraph(TutorState)
    
    # Add nodes
    graph.add_node("retrieve", retrieve_context)
    graph.add_node("analyze_context", analyze_student_context)  # Context analysis
    graph.add_node("understand", understand_question)
    graph.add_node("ask_prereq_question", ask_prereq_question)
    graph.add_node("evaluate_prereq_answer", evaluate_prereq_answer)
    graph.add_node("explain_connection", explain_connection)
    graph.add_node("go_deeper", go_deeper_prereq)
    graph.add_node("answer", answer_question)
    
    # New nodes for redesigned flow
    graph.add_node("continue_topic", continue_topic)
    graph.add_node("explain_prereqs", explain_prereqs)
    graph.add_node("answer_off_topic", answer_off_topic)  # Off-topic question handling
    
    # Set entry point
    graph.set_entry_point("retrieve")
    
    # Add edges - now with analyze_context in the chain
    graph.add_edge("retrieve", "analyze_context")
    graph.add_edge("analyze_context", "understand")
    
    # After understanding, route to appropriate next step
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {
            "ask_prereq_question": "ask_prereq_question",
            "evaluate_prereq_answer": "evaluate_prereq_answer",
            "answer": "answer",
            "continue_topic": "continue_topic",
            "explain_prereqs": "explain_prereqs",
            "answer_off_topic": "answer_off_topic"
        }
    )
    
    # After asking prereq question, end (wait for user response)
    graph.add_edge("ask_prereq_question", END)
    
    # After evaluating prereq, route based on correctness
    graph.add_conditional_edges(
        "evaluate_prereq_answer",
        route_after_evaluation,
        {
            "explain_connection": "explain_connection",
            "go_deeper": "go_deeper"
        }
    )
    
    # After explaining connection, answer the original question
    graph.add_edge("explain_connection", "answer")
    
    # After going deeper, route based on mode
    graph.add_conditional_edges(
        "go_deeper",
        route_after_go_deeper,
        {
            "ask_prereq_question": "ask_prereq_question",
            "answer": "answer",
            "__end__": END
        }
    )
    

    # Normal answer flow
    graph.add_edge("answer", END)
    graph.add_edge("continue_topic", END)
    
    # Explanation flow - waits for user feedback
    graph.add_edge("explain_prereqs", END)
    
    # Off-topic flow - waits for resume confirmation
    graph.add_edge("answer_off_topic", END)
    
    return graph.compile(checkpointer=memory)


# Singleton checkpointer for state persistence
memory = MemorySaver()

# Singleton compiled graph with checkpointer
tutor_agent = build_tutor_graph()


async def evaluate_quiz_answer(
    question: str,
    solution: str,
    student_answer: str
) -> dict:
    """
    Evaluate a quiz/open-ended answer using LLM.
    Returns: {is_correct, is_partial, feedback}
    """
    from app.config import settings
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=settings.groq_api_key
    )
    
    prompt = f"""You are a physics tutor evaluating a student's answer.

Question: {question}
Correct Solution Logic: {solution}

Student Answer: {student_answer}

Evaluate the student's answer.
- If they described the correct process/logic (even without exact math), mark it CORRECT.
- If they have the right idea but missing key parts, mark it PARTIAL.
- If they are fundamentally wrong, mark it WRONG.
- Be encouraging but strict on physics principles.

Response format (exactly as shown):
Status: [CORRECT / PARTIAL / WRONG]
Feedback: [Your constructive feedback here]"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        eval_text = response.content
        
        is_correct = "Status: CORRECT" in eval_text.upper() or "STATUS:CORRECT" in eval_text.upper().replace(" ", "")
        is_partial = "PARTIAL" in eval_text.upper()
        
        # Extract feedback
        feedback = eval_text
        if "Feedback:" in eval_text:
            feedback = eval_text.split("Feedback:")[-1].strip()
        feedback = feedback.replace("Status: CORRECT", "").replace("Status: PARTIAL", "").replace("Status: WRONG", "").strip()
        
        return {
            "is_correct": is_correct,
            "is_partial": is_partial,
            "feedback": feedback
        }
    except Exception as e:
        print(f"Quiz evaluation error: {e}")
        return {
            "is_correct": False,
            "is_partial": False,
            "feedback": "Unable to evaluate your answer. Please try again."
        }
