from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
from app.graph.client import neo4j_client

router = APIRouter()

class NextStepRequest(BaseModel):
    user_id: str
    concept_id: str | None = None

class Component(BaseModel):
    type: str
    props: dict = {}

class UIResponse(BaseModel):
    schema_version: str = "1.0"
    components: list[Component]

GRAVITY_JSON_PATH = "../elearning-platform/src/data/chapters/gravity.json"

def get_gravity_content():
    try:
        with open(GRAVITY_JSON_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback for dev environment if paths differ
        if os.path.exists("gravity.json"):
             with open("gravity.json", "r") as f:
                return json.load(f)
        raise HTTPException(status_code=500, detail="Content file not found")

@router.post("/tutor/next", response_model=UIResponse)
async def next_step(req: NextStepRequest):
    # 1. Get Concept Metadata from Graph
    # If concept_id is provided, use it. Otherwise find the first one or user's current one.
    query = ""
    params = {}
    
    if req.concept_id:
        query = """
        MATCH (c:Concept {id: $id})
        RETURN c
        """
        params = {"id": req.concept_id}
    else:
        # Default to first concept in Chapter 7
        query = """
        MATCH (c:Concept {id: "7.1"})
        RETURN c
        """
    
    results = await neo4j_client.execute_read(query, **params)
    if not results:
         raise HTTPException(status_code=404, detail="Concept not found")
    
    concept = results[0]["c"]
    section_id = concept.get("sectionId", "7.1")
    
    # 2. Get Content from JSON
    data = get_gravity_content()
    sections = data.get("sections", [])
    
    target_section = next((s for s in sections if s["section_id"] == section_id), None)
    
    if not target_section:
        # Fallback if section not found in JSON (e.g. exercises)
        return UIResponse(components=[
            Component(type="h1", props={"children": concept.get("title")}),
            Component(type="p", props={"children": "Content coming soon..."})
        ])

    # 3. Transform Content to UI Schema
    components = []
    
    # Title
    components.append(Component(type="h1", props={"children": target_section.get("section_title")}))
    
    # Body Content
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
    
    return UIResponse(components=components)


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


async def evaluate_exercise_answer(
    question: str,
    sub_questions: list,
    correct_solution: str,
    student_answer: str
) -> dict:
    """Use LLM to evaluate student answer against correct solution."""
    from groq import Groq
    from app.config import settings
    
    # Format sub-questions if present
    sub_q_text = ""
    if sub_questions:
        sub_q_text = "\n".join([f"  {sq.get('label', '')} {sq.get('body', '')}" for sq in sub_questions])
        sub_q_text = f"\nSub-questions:\n{sub_q_text}"
    
    prompt = f"""You are evaluating a physics exercise answer for a student studying gravitation.

**Question:** {question}{sub_q_text}

**Correct Solution:**
{correct_solution}

**Student's Answer:**
{student_answer}

Evaluate the student's answer and respond in JSON format:
{{
    "is_correct": true/false,  // Is the answer substantially correct (covers main concepts)?
    "score": 0-100,            // Numerical accuracy score
    "feedback": "...",         // Constructive feedback for the student (1-2 sentences)
    "comparison": "..."        // Key differences or missing concepts (1 sentence, or empty if correct)
}}

Evaluation guidelines:
- Be fair but rigorous. Physics answers must be conceptually correct.
- Accept equivalent phrasings and different notation styles.
- Award partial credit for partially correct answers.
- Focus on understanding, not exact wording match."""

    try:
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "is_correct": result.get("is_correct", False),
            "score": max(0, min(100, result.get("score", 0))),
            "feedback": result.get("feedback", "Unable to evaluate."),
            "comparison": result.get("comparison", "")
        }
    except Exception as e:
        print(f"LLM evaluation error: {e}")
        # Fallback: simple keyword matching
        solution_lower = correct_solution.lower()
        answer_lower = student_answer.lower()
        words_matched = sum(1 for word in answer_lower.split() if word in solution_lower)
        score = min(100, int(words_matched * 10))
        is_correct = score >= 50
        return {
            "is_correct": is_correct,
            "score": score,
            "feedback": "Partial match based on keywords." if is_correct else "Your answer differs significantly from the expected solution.",
            "comparison": "Please review the correct solution for details."
        }


@router.post("/tutor/evaluate-exercise", response_model=ExerciseEvaluationResponse)
async def evaluate_exercise(request: ExerciseEvaluationRequest):
    """Evaluate student answer against exercise solution using LLM."""
    from app.chains.content import get_exercise_with_solution
    from app.graph.user_state import record_exercise_attempt
    
    # 1. Get exercise with solution
    exercise = get_exercise_with_solution(request.exercise_label)
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Exercise {request.exercise_label} not found")
    
    if not exercise.get("solution"):
        raise HTTPException(status_code=404, detail=f"Solution not available for exercise {request.exercise_label}")
    
    # 2. Call LLM to evaluate
    evaluation = await evaluate_exercise_answer(
        question=exercise["question"],
        sub_questions=exercise.get("sub_questions", []),
        correct_solution=exercise["solution"],
        student_answer=request.student_answer
    )
    
    # 3. Record attempt in Neo4j
    result = await record_exercise_attempt(
        user_id=request.user_id,
        exercise_label=request.exercise_label,
        section_id="EXERCISES",
        is_correct=evaluation["is_correct"],
        is_bonus=request.is_bonus
    )
    
    # 4. Return evaluation with solution revealed
    return ExerciseEvaluationResponse(
        is_correct=evaluation["is_correct"],
        score=evaluation["score"],
        feedback=evaluation["feedback"],
        correct_solution=exercise["solution"],
        comparison=evaluation["comparison"],
        mastery_change=result.get("mastery_change", 0),
        new_mastery=result.get("new_level", 0)
    )

