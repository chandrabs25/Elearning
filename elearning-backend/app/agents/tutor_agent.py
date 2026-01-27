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
    current_concept_id: str | None
    current_concept_title: str | None
    concept_content: str | None  # Retrieved content from gravity.json
    prerequisites: list[dict]    # Prerequisite concepts from Neo4j
    
    # Socratic flow state
    mode: str  # "normal", "asking_prereq", "evaluating_answer", "explaining_connection", "exercise"
    current_prereq_id: str | None  # The prerequisite we're currently testing
    current_prereq_title: str | None
    prereq_question: str | None   # The question we asked about the prerequisite
    prerequisite_chain: list[str]  # Stack of prerequisites traversed
    prereq_answer_correct: bool   # Whether student answered prereq question correctly
    max_depth: int  # Maximum prerequisite depth (prevent infinite loops)
    
    # Exercise evaluation state
    exercise_label: str | None    # Exercise being evaluated (e.g., "7.1")
    exercise_question: str | None
    exercise_solution: str | None
    exercise_student_answer: str | None
    exercise_evaluation: dict | None  # {is_correct, score, feedback, comparison}


# === Neo4j Tools ===
async def get_concept_with_content(concept_id: str) -> dict:
    """Fetch concept details and content from Neo4j + gravity.json."""
    from app.graph.client import neo4j_client
    from app.chains.content import get_section_by_id, format_content_for_ui, extract_section_text
    
    # Get concept metadata and prerequisites from Neo4j
    query = """
    MATCH (c:Concept {id: $concept_id})
    OPTIONAL MATCH (c)-[:REQUIRES]->(prereq:Concept)
    RETURN c, collect({
        id: prereq.id, 
        title: prereq.title, 
        description: prereq.description,
        isPrerequisite: prereq.isPrerequisite
    }) as prerequisites
    """
    result = await neo4j_client.execute_read_single(query, concept_id=concept_id)
    
    # Get content from gravity.json
    section = get_section_by_id(concept_id)
    content = format_content_for_ui(section) if section else []
    
    # Use shared helper for text extraction
    content_text = extract_section_text(section)
    
    return {
        "concept": result["c"] if result else None,
        "prerequisites": [p for p in (result["prerequisites"] if result else []) if p.get("id")],
        "content": content,
        "content_text": content_text,
        "section_title": section.get("section_title") if section else None
    }


async def get_prerequisite_chain(concept_id: str, depth: int = 3) -> list[dict]:
    """Get chain of prerequisites for a concept (up to N levels deep)."""
    from app.graph.client import neo4j_client
    
    query = """
    MATCH path = (c:Concept {id: $concept_id})-[:REQUIRES*1..3]->(prereq:Concept)
    RETURN prereq.id as id, 
           prereq.title as title, 
           prereq.description as description,
           prereq.isPrerequisite as isPrerequisite,
           length(path) as level
    ORDER BY level
    """
    results = await neo4j_client.execute_read(query, concept_id=concept_id)
    return results if results else []


# === Agent Nodes ===
async def retrieve_context(state: TutorState) -> TutorState:
    """Retrieve concept content and prerequisites from Neo4j.
    
    If concept_content is already set (from RAG search), skip retrieval.
    """
    # Skip retrieval if content already provided (from RAG search)
    if state.get("concept_content"):
        # Initialize mode if not set
        if not state.get("mode"):
            state["mode"] = "normal"
        if state.get("max_depth") is None:
            state["max_depth"] = 3
        return state
    
    concept_id = state.get("current_concept_id") or "7.3"
    
    try:
        data = await get_concept_with_content(concept_id)
        state["concept_content"] = data["content_text"]
        state["prerequisites"] = data["prerequisites"]
        state["current_concept_title"] = data["section_title"] or f"Section {concept_id}"
    except Exception as e:
        print(f"Error retrieving context: {e}")
        state["concept_content"] = ""
        state["prerequisites"] = []
    
    # Initialize mode if not set
    if not state.get("mode"):
        state["mode"] = "normal"
    if state.get("max_depth") is None:
        state["max_depth"] = 3
    
    return state


async def understand_question(state: TutorState) -> TutorState:
    """Analyze user's message - is it a question needing help, or an answer to our prereq question?"""
    # LLM initialization removed (was unused)
    # llm = ChatGroq(...)
    
    last_message = state["messages"][-1].content if state["messages"] else ""
    
    # If we were waiting for an answer to a prerequisite question
    if state.get("mode") == "asking_prereq" and state.get("prereq_question"):
        state["mode"] = "evaluating_answer"
        return state
    
    # Check for confusion indicators (student needs help)
    confusion_keywords = ["don't understand", "confused", "what is", "what's", 
                          "explain", "how does", "why", "unclear", "lost", "help"]
    needs_help = any(kw in last_message.lower() for kw in confusion_keywords)
    
    if needs_help and state.get("prerequisites") and len(state.get("prerequisite_chain", [])) < state.get("max_depth", 3):
        state["mode"] = "needs_prereq_check"
    else:
        state["mode"] = "normal"
    
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
    
    # Find a prerequisite we haven't tested yet
    prereq = None
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
    
    # Get more content for the prerequisite if available
    prereq_content = ""
    if prereq_id.startswith("7.") or prereq_id.startswith("prereq-"):
        try:
            prereq_data = await get_concept_with_content(prereq_id)
            prereq_content = prereq_data.get("content_text", "")[:500]
        except:
            pass
    
    # Generate a conceptual question about the prerequisite
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
    
    state["prereq_answer_correct"] = "CORRECT" in response.content.upper()
    
    # Add to prerequisite chain (we've now tested this one)
    if prereq_id and prereq_id not in state.get("prerequisite_chain", []):
        state["prerequisite_chain"] = state.get("prerequisite_chain", []) + [prereq_id]
    
    return state


async def explain_connection(state: TutorState) -> TutorState:
    """Student answered correctly - explain how prerequisite connects to current topic."""
    from app.config import settings
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    prompt = f"""You are a physics tutor. The student just correctly explained their understanding of "{state.get('current_prereq_title', 'the prerequisite')}".

Now, connect this prerequisite to the main topic they're learning: "{state.get('current_concept_title', 'the topic')}"

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


async def answer_question(state: TutorState) -> TutorState:
    """Generate answer using concept content as context (normal mode)."""
    from app.config import settings
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    prereq_context = ""
    if state.get("prerequisite_chain"):
        prereq_context = f"\n\nNote: You've covered these prerequisites with the student: {', '.join(state['prerequisite_chain'])}"
    
    system_prompt = f"""You are an AI physics tutor helping a student learn about:
**{state.get('current_concept_title', 'Gravitation')}**

Textbook content:
---
{state.get('concept_content', '')[:2500]}
---
{prereq_context}

Guidelines:
- Be clear, concise, and educational
- Use LaTeX for equations ($$...$$)
- Connect to concepts they already know
- Be encouraging and supportive
- End with a follow-up question or suggestion"""

    messages_for_llm = [SystemMessage(content=system_prompt)]
    for msg in state.get("messages", [])[-5:]:
        if hasattr(msg, 'content'):
            if isinstance(msg, HumanMessage):
                messages_for_llm.append(HumanMessage(content=msg.content))
            elif isinstance(msg, AIMessage):
                messages_for_llm.append(AIMessage(content=msg.content))
    
    response = await llm.ainvoke(messages_for_llm)
    state["messages"] = state.get("messages", []) + [AIMessage(content=response.content)]
    
    return state


async def evaluate_exercise(state: TutorState) -> TutorState:
    """Evaluate student's answer to an exercise using LLM."""
    from app.config import settings
    import json
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=settings.groq_api_key
    )
    
    exercise_question = state.get("exercise_question", "")
    exercise_solution = state.get("exercise_solution", "")
    student_answer = state.get("exercise_student_answer", "")
    
    if not exercise_solution:
        # No solution available - can't evaluate properly
        state["exercise_evaluation"] = {
            "is_correct": False,
            "score": 0,
            "feedback": "Unable to evaluate - solution not available.",
            "comparison": ""
        }
        return state
    
    prompt = f"""You are evaluating a physics exercise answer for a student studying gravitation.

**Question:** {exercise_question}

**Correct Solution:**
{exercise_solution}

**Student's Answer:**
{student_answer}

Evaluate the student's answer and respond in JSON format:
{{
    "is_correct": true/false,  // Is the answer substantially correct?
    "score": 0-100,            // Numerical accuracy score
    "feedback": "...",         // Constructive feedback (1-2 sentences)
    "comparison": "..."        // Key differences or missing concepts
}}

Be fair but rigorous. Accept equivalent phrasings."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Parse JSON from response
        response_text = response.content
        # Try to extract JSON from the response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        result = json.loads(response_text.strip())
        
        state["exercise_evaluation"] = {
            "is_correct": result.get("is_correct", False),
            "score": max(0, min(100, result.get("score", 0))),
            "feedback": result.get("feedback", ""),
            "comparison": result.get("comparison", "")
        }
    except Exception as e:
        print(f"Exercise evaluation error: {e}")
        # Fallback evaluation
        state["exercise_evaluation"] = {
            "is_correct": False,
            "score": 0,
            "feedback": f"Unable to fully evaluate. Please review your answer.",
            "comparison": ""
        }
    
    return state


async def respond_to_exercise(state: TutorState) -> TutorState:
    """Generate response based on exercise evaluation."""
    from app.config import settings
    from app.graph.user_state import record_exercise_attempt
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.5,
        api_key=settings.groq_api_key
    )
    
    evaluation = state.get("exercise_evaluation", {})
    is_correct = evaluation.get("is_correct", False)
    score = evaluation.get("score", 0)
    feedback = evaluation.get("feedback", "")
    comparison = evaluation.get("comparison", "")
    exercise_solution = state.get("exercise_solution", "")
    
    # Record attempt in Neo4j
    try:
        result = await record_exercise_attempt(
            user_id=state.get("user_id", "unknown"),
            exercise_label=state.get("exercise_label", "unknown"),
            section_id="EXERCISES",
            is_correct=is_correct,
            is_bonus=True
        )
        mastery_change = result.get("mastery_change", 0)
        new_mastery = result.get("new_level", 0)
    except Exception as e:
        print(f"Error recording exercise attempt: {e}")
        mastery_change = 0
        new_mastery = 0
    
    # Build response message
    if is_correct:
        emoji = "✅"
        opening = "Excellent work!"
    elif score >= 50:
        emoji = "🔶"
        opening = "Good attempt, but there are some issues."
    else:
        emoji = "❌"
        opening = "Not quite right. Let me help you understand."
    
    response_text = f"""{emoji} **Score: {score}/100**

{opening}

**Feedback:** {feedback}

{f'**What was missing:** {comparison}' if comparison and not is_correct else ''}

---

**Correct Solution:**
{exercise_solution}

---

{'🎯 Great job! Would you like to try another exercise or continue learning?' if is_correct else 'Would you like me to explain the solution step by step, or would you like to try another exercise?'}"""

    state["messages"] = state.get("messages", []) + [AIMessage(content=response_text)]
    state["mode"] = "normal"  # Reset mode after exercise
    
    return state


# === Routing Logic ===
def route_after_understand(state: TutorState) -> Literal["ask_prereq_question", "evaluate_prereq_answer", "evaluate_exercise", "answer"]:
    """Route based on current mode."""
    mode = state.get("mode", "normal")
    
    if mode == "needs_prereq_check":
        return "ask_prereq_question"
    elif mode == "evaluating_answer":
        return "evaluate_prereq_answer"
    elif mode == "exercise":
        return "evaluate_exercise"
    else:
        return "answer"


def route_after_evaluation(state: TutorState) -> Literal["explain_connection", "go_deeper"]:
    """Route based on whether student answered prereq correctly."""
    if state.get("prereq_answer_correct", False):
        return "explain_connection"
    else:
        return "go_deeper"


# === Build Graph ===
def build_tutor_graph() -> StateGraph:
    """Construct the LangGraph tutor agent with Socratic prerequisite flow and exercise evaluation."""
    graph = StateGraph(TutorState)
    
    # Add nodes
    graph.add_node("retrieve", retrieve_context)
    graph.add_node("understand", understand_question)
    graph.add_node("ask_prereq_question", ask_prereq_question)
    graph.add_node("evaluate_prereq_answer", evaluate_prereq_answer)
    graph.add_node("explain_connection", explain_connection)
    graph.add_node("go_deeper", go_deeper_prereq)
    graph.add_node("answer", answer_question)
    graph.add_node("evaluate_exercise", evaluate_exercise)
    graph.add_node("respond_to_exercise", respond_to_exercise)
    
    # Set entry point
    graph.set_entry_point("retrieve")
    
    # Add edges
    graph.add_edge("retrieve", "understand")
    
    # After understanding, route to appropriate next step
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {
            "ask_prereq_question": "ask_prereq_question",
            "evaluate_prereq_answer": "evaluate_prereq_answer",
            "evaluate_exercise": "evaluate_exercise",
            "answer": "answer"
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
    
    # After going deeper, either ask another prereq question or answer
    graph.add_conditional_edges(
        "go_deeper",
        lambda s: "ask_prereq_question" if s.get("mode") == "needs_prereq_check" else "answer",
        {
            "ask_prereq_question": "ask_prereq_question",
            "answer": "answer"
        }
    )
    
    # Exercise evaluation flow
    graph.add_edge("evaluate_exercise", "respond_to_exercise")
    graph.add_edge("respond_to_exercise", END)
    
    graph.add_edge("answer", END)
    
    return graph.compile(checkpointer=memory)


# Singleton checkpointer for state persistence
memory = MemorySaver()

# Singleton compiled graph with checkpointer
tutor_agent = build_tutor_graph()


# === Convenience function for exercise evaluation ===
async def evaluate_exercise_with_agent(
    user_id: str,
    exercise_label: str,
    student_answer: str
) -> dict:
    """
    Convenience function to evaluate an exercise using the agent.
    Returns the evaluation result for the API.
    """
    from app.chains.content import get_exercise_with_solution
    
    # Get exercise with solution
    exercise = get_exercise_with_solution(exercise_label)
    if not exercise:
        return {
            "is_correct": False,
            "score": 0,
            "feedback": f"Exercise {exercise_label} not found.",
            "correct_solution": "",
            "comparison": "",
            "mastery_change": 0,
            "new_mastery": 0
        }
    
    # Build initial state for exercise evaluation
    initial_state: TutorState = {
        "messages": [HumanMessage(content=student_answer)],
        "user_id": user_id,
        "current_concept_id": None,
        "current_concept_title": None,
        "concept_content": None,
        "prerequisites": [],
        "mode": "exercise",
        "current_prereq_id": None,
        "current_prereq_title": None,
        "prereq_question": None,
        "prerequisite_chain": [],
        "prereq_answer_correct": False,
        "max_depth": 3,
        "exercise_label": exercise_label,
        "exercise_question": exercise.get("question", ""),
        "exercise_solution": exercise.get("solution", ""),
        "exercise_student_answer": student_answer,
        "exercise_evaluation": None
    }
    
    # Run the agent with required config for checkpointer
    config = {"configurable": {"thread_id": f"exercise-{user_id}-{exercise_label}"}}
    final_state = await tutor_agent.ainvoke(initial_state, config)
    
    evaluation = final_state.get("exercise_evaluation", {})
    
    return {
        "is_correct": evaluation.get("is_correct", False),
        "score": evaluation.get("score", 0),
        "feedback": evaluation.get("feedback", ""),
        "correct_solution": exercise.get("solution", ""),
        "comparison": evaluation.get("comparison", ""),
        "mastery_change": 0,
        "new_mastery": 0
    }


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
