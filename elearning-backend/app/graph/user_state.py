"""User state management for Neo4j with Redis caching."""
from app.graph.client import neo4j_client
from app.cache import cache_get, cache_set, cache_delete
from datetime import datetime


async def get_or_create_user(user_id: str) -> dict:
    """Get user or create new one."""
    query = """
    MERGE (u:User {id: $user_id})
    ON CREATE SET u.created_at = datetime(), u.session_count = 0, u.lifetime_mastery = 0, u.exploration_points = 0
    ON MATCH SET u.last_active = datetime()
    RETURN u
    """
    results = await neo4j_client.execute_read(query, user_id=user_id)
    return results[0]["u"] if results else None


async def get_user_state(user_id: str) -> dict:
    """Get user's current learning state (with Redis caching)."""
    cache_key = f"user_state:{user_id}"
    
    # Try cache first
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Fetch from Neo4j
    query = """
    MATCH (u:User {id: $user_id})
    OPTIONAL MATCH (u)-[:STUDYING]->(current:Concept)
    OPTIONAL MATCH (u)-[m:MASTERY]->(c:Concept)
    RETURN u, current, 
           collect({concept: c.id, level: m.level, title: c.title, completed: m.completed}) as mastery
    """
    results = await neo4j_client.execute_read(query, user_id=user_id)
    if not results:
        return None
    
    row = results[0]
    state = {
        "user": dict(row["u"]) if row["u"] else None,
        "current_concept": dict(row["current"]) if row["current"] else None,
        "mastery": row["mastery"] if row["mastery"] else []
    }
    
    # Cache permanently (invalidated on state changes)
    await cache_set(cache_key, state)
    return state


async def save_tutor_state(user_id: str, tutor_state: dict) -> None:
    """Persist tutor session state (mode, prereq info) to Neo4j User node.
    
    State is stored per-section to prevent bleed across different topics.
    """
    import json
    
    section_id = tutor_state.get("current_concept_id")
    if not section_id:
        return  # Cannot save without section context
    
    # Store state in a JSON map keyed by section_id
    state_data = {
        "mode": tutor_state.get("mode", "normal"),
        "section_id": section_id,
        "prereq_id": tutor_state.get("current_prereq_id"),
        "prereq_title": tutor_state.get("current_prereq_title"),
        "prereq_question": tutor_state.get("prereq_question"),
        "prereq_chain": tutor_state.get("prerequisite_chain", []),
        "pending_verification": tutor_state.get("pending_verification_concept")
    }
    
    query = """
    MATCH (u:User {id: $user_id})
    // Get existing tutor_states map or create empty one
    WITH u, COALESCE(u.tutor_states, "{}") as states_json
    // Parse JSON, update for this section using apoc.map.setKey, serialize back
    WITH u, apoc.convert.fromJsonMap(states_json) as states_map
    SET u.tutor_states = apoc.convert.toJson(
        apoc.map.setKey(states_map, $section_id, $state_data)
    )
    """
    
    await neo4j_client.execute_write(
        query,
        user_id=user_id,
        section_id=section_id,
        state_data=state_data
    )
    
    # Invalidate cache for this section
    await cache_delete(f"tutor_state:{user_id}:{section_id}")


async def get_tutor_state(user_id: str, section_id: str = None) -> dict:
    """Retrieve persisted tutor session state from Neo4j User node.
    
    Args:
        user_id: The user ID
        section_id: The section ID to get state for. If None, returns empty/default state.
    
    Returns:
        Dictionary with mode, prereq info, etc. for this specific section.
    """
    import json
    
    if not section_id:
        # Without section context, return empty state
        return {"mode": "normal", "prerequisite_chain": []}
    
    cache_key = f"tutor_state:{user_id}:{section_id}"
    
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    query = """
    MATCH (u:User {id: $user_id})
    WITH u, COALESCE(u.tutor_states, "{}") as states_json
    WITH apoc.convert.fromJsonMap(states_json) as states_map
    RETURN states_map[$section_id] as state_data
    """
    results = await neo4j_client.execute_read(query, user_id=user_id, section_id=section_id)
    if not results or not results[0]:
        return {"mode": "normal", "prerequisite_chain": []}
    
    state_data = results[0].get("state_data")
    if not state_data:
        return {"mode": "normal", "prerequisite_chain": []}
    # state_data is already a dict from the JSON map
    state = {
        "mode": state_data.get("mode", "normal"),
        "current_section_id": state_data.get("section_id"),
        "current_prereq_id": state_data.get("prereq_id"),
        "current_prereq_title": state_data.get("prereq_title"),
        "prereq_question": state_data.get("prereq_question"),
        "prerequisite_chain": state_data.get("prereq_chain", []),
        "pending_verification_concept": state_data.get("pending_verification")
    }
    
    await cache_set(cache_key, state)
    return state


async def update_current_concept(user_id: str, concept_id: str) -> None:
    """Update user's current studying concept."""
    query = """
    MATCH (u:User {id: $user_id})
    MATCH (c:Concept {id: $concept_id})
    OPTIONAL MATCH (u)-[r:STUDYING]->()
    DELETE r
    MERGE (u)-[:STUDYING]->(c)
    """
    await neo4j_client.execute_read(query, user_id=user_id, concept_id=concept_id)
    # Invalidate cache after state change
    await cache_delete(f"user_state:{user_id}")


async def update_mastery(user_id: str, concept_id: str, delta: int) -> dict:
    """
    Update mastery level for a concept. Returns new level and completion status.
    Mastery can now decrease if delta is negative (wrong answers).
    """
    query = """
    MATCH (u:User {id: $user_id})
    MERGE (c:Concept {id: $concept_id})
    MERGE (u)-[m:MASTERY]->(c)
    ON CREATE SET m.level = CASE 
        WHEN $delta > 100 THEN 100 
        WHEN $delta < 0 THEN 0 
        ELSE $delta 
    END, m.last_tested = datetime(), m.completed = false
    ON MATCH SET m.level = CASE 
        WHEN m.level + $delta > 100 THEN 100 
        WHEN m.level + $delta < 0 THEN 0 
        ELSE m.level + $delta 
    END, m.last_tested = datetime()
    WITH u, m, c
    SET m.completed = CASE WHEN m.level >= 70 THEN true ELSE false END
    WITH u, m, c
    // Update lifetime mastery average
    OPTIONAL MATCH (u)-[all_m:MASTERY]->()
    WITH u, m, c, avg(all_m.level) as avg_mastery
    SET u.lifetime_mastery = avg_mastery
    RETURN m.level as new_level, m.completed as completed, u.lifetime_mastery as lifetime_mastery
    """
    results = await neo4j_client.execute_read(
        query, user_id=user_id, concept_id=concept_id, delta=delta
    )
    # Invalidate cache after mastery change
    await cache_delete(f"user_state:{user_id}")
    
    if results:
        return {
            "new_level": results[0]["new_level"],
            "completed": results[0]["completed"],
            "lifetime_mastery": results[0]["lifetime_mastery"]
        }
    return {"new_level": 0, "completed": False, "lifetime_mastery": 0}


async def get_section_mastery(user_id: str, concept_id: str) -> dict:
    """Get mastery for a specific section."""
    query = """
    MATCH (u:User {id: $user_id})-[m:MASTERY]->(c:Concept {id: $concept_id})
    RETURN m.level as level, m.completed as completed
    """
    results = await neo4j_client.execute_read(query, user_id=user_id, concept_id=concept_id)
    if results:
        return {
            "level": results[0]["level"],
            "completed": results[0]["completed"]
        }
    return {"level": 0, "completed": False}


async def get_lifetime_progress(user_id: str, section_ids: list[str]) -> dict:
    """Get lifetime progress for all sections."""
    query = """
    MATCH (u:User {id: $user_id})
    OPTIONAL MATCH (u)-[m:MASTERY]->(c:Concept)
    WHERE c.id IN $section_ids
    WITH u, c, m
    ORDER BY c.id
    RETURN u.lifetime_mastery as lifetime_mastery,
           collect({
               id: c.id, 
               mastery: COALESCE(m.level, 0), 
               completed: COALESCE(m.completed, false)
           }) as sections_progress
    """
    results = await neo4j_client.execute_read(
        query, user_id=user_id, section_ids=section_ids
    )
    
    if results and results[0]:
        return {
            "lifetime_mastery": results[0]["lifetime_mastery"] or 0,
            "sections_progress": results[0]["sections_progress"] or []
        }
    return {"lifetime_mastery": 0, "sections_progress": []}


async def mark_section_completed(user_id: str, concept_id: str) -> dict:
    """Mark a section as completed and return next section info."""
    query = """
    MATCH (u:User {id: $user_id})
    MERGE (c:Concept {id: $concept_id})
    MERGE (u)-[m:MASTERY]->(c)
    SET m.completed = true
    RETURN m.level as level
    """
    results = await neo4j_client.execute_read(
        query, user_id=user_id, concept_id=concept_id
    )
    return {"level": results[0]["level"] if results else 0}


async def get_weak_concepts(user_id: str, threshold: int = 50) -> list:
    """Get concepts where user has low mastery."""
    query = """
    MATCH (u:User {id: $user_id})-[m:MASTERY]->(c:Concept)
    WHERE m.level < $threshold
    RETURN c.id as id, c.title as title, m.level as level
    ORDER BY m.level ASC
    LIMIT 3
    """
    results = await neo4j_client.execute_read(
        query, user_id=user_id, threshold=threshold
    )
    return results


async def record_exercise_attempt(
    user_id: str, 
    exercise_label: str, 
    section_id: str, 
    is_correct: bool,
    is_bonus: bool = False
) -> dict:
    """Record an exercise attempt and update mastery."""
    # Base mastery change
    if is_correct:
        delta = 10 if is_bonus else 5
    else:
        delta = -3  # Decrease mastery for wrong answers
    
    # Update mastery
    result = await update_mastery(user_id, section_id, delta)
    
    # Record the attempt
    query = """
    MATCH (u:User {id: $user_id})
    MERGE (e:Exercise {label: $exercise_label, section_id: $section_id})
    MERGE (u)-[a:ATTEMPTED]->(e)
    SET a.is_correct = $is_correct,
        a.timestamp = datetime(),
        a.is_bonus = $is_bonus
    RETURN a
    """
    await neo4j_client.execute_read(
        query, 
        user_id=user_id, 
        exercise_label=exercise_label, 
        section_id=section_id,
        is_correct=is_correct,
        is_bonus=is_bonus
    )
    
    return {
        **result,
        "mastery_change": delta
    }


async def get_completed_exercises(user_id: str, section_id: str) -> list[str]:
    """Get list of completed exercises for a section."""
    query = """
    MATCH (u:User {id: $user_id})-[a:ATTEMPTED]->(e:Exercise {section_id: $section_id})
    WHERE a.is_correct = true
    RETURN e.label as label
    """
    results = await neo4j_client.execute_read(
        query, user_id=user_id, section_id=section_id
    )
    return [r["label"] for r in results] if results else []


async def record_chat_interaction(
    user_id: str, 
    section_id: str, 
    relevance: str = "relevant"  # "relevant", "related", "irrelevant"
) -> dict:
    """
    Record a chat interaction with relevance-based mastery.
    - relevant: Directly about current section → +2 mastery (max 6 from chat)
    - related: About related concept → +1 exploration, no mastery
    - irrelevant: Off-topic → no change
    """
    if relevance == "relevant":
        # Direct relevance: boost mastery (max 3 interactions = 6 points)
        query = """
        MATCH (u:User {id: $user_id})
        MERGE (c:Concept {id: $section_id})
        MERGE (u)-[m:MASTERY]->(c)
        ON CREATE SET m.level = 2, m.chat_interactions = 1, m.completed = false
        ON MATCH SET 
            m.chat_interactions = COALESCE(m.chat_interactions, 0) + 1,
            m.level = CASE 
                WHEN COALESCE(m.chat_interactions, 0) < 3 THEN m.level + 2
                ELSE m.level
            END
        RETURN m.level as new_level, m.chat_interactions as interactions, 0 as exploration_added
        """
    elif relevance == "related":
        # Related topic: add exploration points, no mastery change
        query = """
        MATCH (u:User {id: $user_id})
        SET u.exploration_points = COALESCE(u.exploration_points, 0) + 1
        WITH u
        OPTIONAL MATCH (u)-[m:MASTERY]->(c:Concept {id: $section_id})
        RETURN COALESCE(m.level, 0) as new_level, 
               COALESCE(m.chat_interactions, 0) as interactions,
               1 as exploration_added
        """
    else:
        # Irrelevant: no change
        query = """
        MATCH (u:User {id: $user_id})
        OPTIONAL MATCH (u)-[m:MASTERY]->(c:Concept {id: $section_id})
        RETURN COALESCE(m.level, 0) as new_level, 
               COALESCE(m.chat_interactions, 0) as interactions,
               0 as exploration_added
        """
    
    results = await neo4j_client.execute_read(
        query, user_id=user_id, section_id=section_id
    )
    if results:
        return {
            "new_level": results[0]["new_level"],
            "interactions": results[0]["interactions"],
            "exploration_added": results[0]["exploration_added"],
            "relevance": relevance
        }
    return {"new_level": 0, "interactions": 0, "exploration_added": 0, "relevance": relevance}


async def get_exploration_points(user_id: str) -> int:
    """Get user's exploration points."""
    query = """
    MATCH (u:User {id: $user_id})
    RETURN COALESCE(u.exploration_points, 0) as points
    """
    results = await neo4j_client.execute_read(query, user_id=user_id)
    return results[0]["points"] if results else 0


async def save_session_summary(user_id: str, summary: str) -> None:
    """Save a session summary for the user."""
    query = """
    MATCH (u:User {id: $user_id})
    CREATE (s:Session {
        summary: $summary,
        created_at: datetime()
    })
    MERGE (u)-[:HAS_SESSION]->(s)
    SET u.session_count = u.session_count + 1
    """
    await neo4j_client.execute_read(query, user_id=user_id, summary=summary)


async def get_last_session(user_id: str) -> dict | None:
    """Get user's most recent session summary.
    
    NOTE: Session tracking is not currently implemented (Session nodes aren't created).
    Returning None to avoid Neo4j warnings about missing labels/relationships.
    """
    # Session nodes aren't being created yet - skip query to avoid warnings
    return None
    
    # When Session tracking is implemented, uncomment this:
    # query = """
    # MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session)
    # RETURN s.summary as summary, s.created_at as created_at
    # ORDER BY s.created_at DESC
    # LIMIT 1
    # """
    # results = await neo4j_client.execute_read(query, user_id=user_id)
    # return results[0] if results else None


# === Insight Management Functions ===

async def create_insight(
    user_id: str,
    insight_type: str,  # COMPETENCY, MISCONCEPTION, PREFERENCE
    content: str,
    concept_ids: list[str],
    confidence: float = 1.0,
    source_type: str | None = None,  # NEW: "exercise", "quiz", "mcq", "verification"
    source_id: str | None = None  # NEW: Specific question/exercise ID
) -> dict:
    """Create a new Insight node and link it to the user and concepts.
    
    Args:
        user_id: The user's ID
        insight_type: Type of insight (COMPETENCY, MISCONCEPTION, PREFERENCE)
        content: Description of the insight
        concept_ids: List of concept IDs this insight is about
        confidence: How certain the agent is about this insight (0.0-1.0)
        source_type: Optional source type (exercise, quiz, mcq, verification)
        source_id: Optional specific ID of the source object
    
    Returns:
        The created insight with its ID
    """
    import uuid
    
    insight_id = f"insight-{uuid.uuid4().hex[:12]}"
    
    # Create insight node and link to user
    # Include source_type and source_id if provided
    query = """
    MATCH (u:User {id: $user_id})
    CREATE (i:Insight {
        id: $insight_id,
        type: $insight_type,
        content: $content,
        confidence: $confidence,
        source_type: $source_type,
        source_id: $source_id,
        created_at: datetime()
    })
    MERGE (u)-[:HAS_INSIGHT]->(i)
    WITH i
    UNWIND $concept_ids AS concept_id
    MATCH (c:Concept {id: concept_id})
    MERGE (i)-[:ABOUT]->(c)
    RETURN i.id as id, i.type as type, i.content as content, 
           i.source_type as source_type, i.source_id as source_id,
           i.created_at as created_at
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        insight_id=insight_id,
        insight_type=insight_type,
        content=content,
        confidence=confidence,
        concept_ids=concept_ids,
        source_type=source_type,
        source_id=source_id
    )
    
    # Invalidate user state cache
    await cache_delete(f"user_state:{user_id}")
    
    if results:
        return {
            "id": results[0]["id"],
            "type": results[0]["type"],
            "content": results[0]["content"],
            "source_type": results[0]["source_type"],
            "source_id": results[0]["source_id"],
            "created_at": str(results[0]["created_at"]) if results[0]["created_at"] else None
        }
    return {"id": insight_id, "type": insight_type, "content": content, "source_type": source_type, "source_id": source_id}




async def get_insights_for_concept(user_id: str, concept_id: str, include_subconcepts: bool = True) -> list[dict]:
    """Get all active insights for a user related to a specific concept.
    
    Returns insights that are:
    1. Linked to the user
    2. About the specified concept OR its subconcepts (if include_subconcepts=True)
    3. Not superseded by a newer insight
    
    Also includes object-level insights (exercises, MCQs, quizzes) that are linked
    to the section via their source_id matching the section prefix.
    
    Args:
        user_id: The user's ID
        concept_id: The concept to get insights for (e.g., "7.2")
        include_subconcepts: Whether to include insights from subconcepts like 7.2.1, 7.2.2
    
    Returns:
        List of insight dictionaries with source info
    """
    # Build section prefix for subconcept matching
    section_prefix = concept_id + "."
    
    query = """
    // Get insights directly about this concept or its subconcepts.
    // Aggregate concept IDs per insight so callers can use concept_ids reliably.
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight)-[:ABOUT]->(c:Concept)
    WHERE i.superseded_by IS NULL
      AND (c.id = $concept_id OR ($include_sub AND c.id STARTS WITH $section_prefix))
    WITH i, collect(DISTINCT c.id) as concept_ids
    RETURN i.id as id,
           i.type as type,
           i.content as content,
           i.confidence as confidence,
           i.source_type as source_type,
           i.source_id as source_id,
           concept_ids,
           concept_ids[0] as concept_id,
           i.created_at as created_at
    ORDER BY i.created_at DESC
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        concept_id=concept_id,
        section_prefix=section_prefix,
        include_sub=include_subconcepts
    )
    
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "content": r["content"],
            "confidence": r["confidence"],
            "source_type": r["source_type"],
            "source_id": r["source_id"],
            "concept_ids": r["concept_ids"] or [],
            "concept_id": r["concept_id"],
            "created_at": str(r["created_at"]) if r["created_at"] else None
        }
        for r in results
    ] if results else []


async def get_insights_by_source(
    user_id: str, 
    source_type: str, 
    source_id: str
) -> list[dict]:
    """Get all active insights for a user linked to a specific source object.
    
    This enables object-level insight lookup (e.g., all insights from exercise 7.5).
    
    Args:
        user_id: The user's ID
        source_type: The source type (exercise, quiz, mcq, verification)
        source_id: The specific source ID
    
    Returns:
        List of insight dictionaries matching the source
    """
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight)
    WHERE i.superseded_by IS NULL
      AND i.source_type = $source_type
      AND i.source_id = $source_id
    RETURN i.id as id, 
           i.type as type, 
           i.content as content, 
           i.confidence as confidence,
           i.source_type as source_type,
           i.source_id as source_id,
           i.created_at as created_at
    ORDER BY i.created_at DESC
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        source_type=source_type,
        source_id=source_id
    )
    
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "content": r["content"],
            "confidence": r["confidence"],
            "source_type": r["source_type"],
            "source_id": r["source_id"],
            "created_at": str(r["created_at"]) if r["created_at"] else None
        }
        for r in results
    ] if results else []


async def get_all_user_insights(user_id: str, limit: int = 20) -> list[dict]:
    """Get all active insights for a user across all concepts.
    
    Args:
        user_id: The user's ID
        limit: Maximum number of insights to return
    
    Returns:
        List of insight dictionaries with associated concept IDs
    """
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight)-[:ABOUT]->(c:Concept)
    WHERE i.superseded_by IS NULL
    WITH i, collect(c.id) as concept_ids
    RETURN i.id as id,
           i.type as type,
           i.content as content,
           i.confidence as confidence,
           i.created_at as created_at,
           concept_ids
    ORDER BY i.created_at DESC
    LIMIT $limit
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        limit=limit
    )
    
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "content": r["content"],
            "confidence": r["confidence"],
            "created_at": str(r["created_at"]) if r["created_at"] else None,
            "concept_ids": r["concept_ids"]
        }
        for r in results
    ] if results else []


async def supersede_insight(old_insight_id: str, new_insight_id: str) -> bool:
    """Mark an old insight as superseded by a new one.
    
    This is used when new information contradicts or updates previous insights.
    
    Args:
        old_insight_id: ID of the insight to supersede
        new_insight_id: ID of the new insight that replaces it
    
    Returns:
        True if successful, False otherwise
    """
    query = """
    MATCH (old:Insight {id: $old_insight_id})
    MATCH (new:Insight {id: $new_insight_id})
    SET old.superseded_by = $new_insight_id
    MERGE (new)-[:SUPERSEDES]->(old)
    RETURN old.id as id
    """
    
    results = await neo4j_client.execute_read(
        query,
        old_insight_id=old_insight_id,
        new_insight_id=new_insight_id
    )
    
    return bool(results)


# NOTE: create_insight_with_supersede was removed - replaced by reconcile_insights
# which uses LLM to intelligently decide ADDS/PARTIAL_SUPERSEDE/FULL_SUPERSEDE/REDUNDANT



async def reconcile_insights(
    user_id: str,
    new_content: str,
    insight_type: str,
    concept_ids: list[str],
    source_type: str | None = None,
    source_id: str | None = None,
    confidence: float = 1.0
) -> dict:
    """Use LLM to intelligently reconcile new insight with existing insights.
    
    OPTIMIZATION: Only calls LLM if there's an existing insight for the SAME source object.
    If no existing insight for this source_id, directly creates without LLM reconciliation.
    
    Args:
        user_id: The user's ID
        new_content: The content of the new insight
        insight_type: COMPETENCY or MISCONCEPTION
        concept_ids: Concept IDs this insight is about
        source_type: Optional source type (exercise, quiz, mcq, verification)
        source_id: Optional specific ID of the source object
        confidence: Confidence level of the insight
    
    Returns:
        Dict with action taken and resulting insight(s)
    """
    from app.config import settings
    from groq import AsyncGroq
    import json
    
    # OPTIMIZATION: First check for existing insights on the SAME source object
    # This is the primary criterion - only reconcile with same-object insights
    existing_insights = []
    
    if source_type and source_id:
        # Check for insights from the exact same source object
        existing_insights = await get_insights_by_source(user_id, source_type, source_id)
        
        if not existing_insights:
            # No prior insight for this specific object - create directly, no LLM needed
            print(f"[Insight] No existing insight for {source_type}:{source_id} - creating directly")
            new_insight = await create_insight(
                user_id=user_id,
                insight_type=insight_type,
                content=new_content,
                concept_ids=concept_ids,
                confidence=confidence,
                source_type=source_type,
                source_id=source_id
            )
            return {"action": "CREATE_NEW", "insight": new_insight}
    else:
        # No source_id provided - fall back to concept-level lookup
        for concept_id in concept_ids:
            insights = await get_insights_for_concept(user_id, concept_id)
            for ins in insights:
                if ins not in existing_insights:
                    existing_insights.append(ins)
        
        # If no existing insights at all, create directly
        if not existing_insights:
            new_insight = await create_insight(
                user_id=user_id,
                insight_type=insight_type,
                content=new_content,
                concept_ids=concept_ids,
                confidence=confidence,
                source_type=source_type,
                source_id=source_id
            )
            return {"action": "CREATE_NEW", "insight": new_insight}
    
    # At this point, we have existing insights to reconcile against
    print(f"[Insight] Found {len(existing_insights)} existing insights for {source_type or 'concept'}:{source_id or concept_ids[0]} - using LLM reconciliation")

    
    # Format existing insights for LLM
    existing_formatted = "\n".join([
        f"- [{i['type']}] (ID: {i['id']}): {i['content']}"
        for i in existing_insights
    ])
    
    # LLM determines the relationship
    client = AsyncGroq(api_key=settings.groq_api_key)
    
    prompt = f"""You are analyzing student learning insights to determine how new information relates to existing knowledge.

EXISTING INSIGHTS for this student on these concepts:
{existing_formatted}

NEW OBSERVATION:
Type: {insight_type}
Content: {new_content}

Determine the relationship between the new observation and existing insights:

1. **ADDS** - The new observation provides NEW information about a DIFFERENT aspect. Both insights should coexist.
   Example: Existing says "understands static friction", new says "confused about rolling friction" → Both are valid, different topics.

2. **PARTIAL_SUPERSEDE** - The new observation PARTIALLY contradicts or updates an existing insight. Merge them.
   Example: Existing says "confused about all friction types", new says "now understands static but still confused about kinetic"
   → Supersede old, create merged insight.

3. **FULL_SUPERSEDE** - The new observation COMPLETELY contradicts an existing insight. Replace it.
   Example: Existing says "confused about Newton's 3rd law", new says "correctly explained action-reaction pairs"
   → Supersede old, create new.

4. **REDUNDANT** - The new observation is already captured by an existing insight. Skip.
   Example: Existing says "understands free body diagrams", new says "correctly drew force arrows" → Skip.

Respond with ONLY valid JSON (no markdown):
{{
    "action": "ADDS" | "PARTIAL_SUPERSEDE" | "FULL_SUPERSEDE" | "REDUNDANT",
    "affected_insight_ids": ["id1", "id2"],
    "merged_content": "combined insight text if PARTIAL_SUPERSEDE, else null",
    "reason": "brief explanation"
}}"""

    try:
        response = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        # Clean up potential markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        decision = json.loads(response_text)
        action = decision.get("action", "ADDS")
        affected_ids = decision.get("affected_insight_ids", [])
        merged_content = decision.get("merged_content")
        reason = decision.get("reason", "")
        
        print(f"[Insight Reconcile] Action: {action}, Reason: {reason}")
        
        if action == "REDUNDANT":
            return {"action": "REDUNDANT", "reason": reason, "insight": None}
        
        if action == "ADDS":
            # Create new insight alongside existing
            new_insight = await create_insight(
                user_id=user_id,
                insight_type=insight_type,
                content=new_content,
                concept_ids=concept_ids,
                confidence=confidence,
                source_type=source_type,
                source_id=source_id
            )
            return {"action": "ADDS", "insight": new_insight}
        
        if action == "PARTIAL_SUPERSEDE":
            # Create merged insight and supersede affected
            final_content = merged_content if merged_content else new_content
            new_insight = await create_insight(
                user_id=user_id,
                insight_type=insight_type,
                content=final_content,
                concept_ids=concept_ids,
                confidence=confidence,
                source_type=source_type,
                source_id=source_id
            )
            
            # Supersede affected insights
            for old_id in affected_ids:
                await supersede_insight(old_id, new_insight["id"])
            
            return {"action": "PARTIAL_SUPERSEDE", "insight": new_insight, "superseded": affected_ids}
        
        if action == "FULL_SUPERSEDE":
            # Create new insight and supersede all affected
            new_insight = await create_insight(
                user_id=user_id,
                insight_type=insight_type,
                content=new_content,
                concept_ids=concept_ids,
                confidence=confidence,
                source_type=source_type,
                source_id=source_id
            )
            
            for old_id in affected_ids:
                await supersede_insight(old_id, new_insight["id"])
            
            return {"action": "FULL_SUPERSEDE", "insight": new_insight, "superseded": affected_ids}
        
    except Exception as e:
        print(f"[Insight Reconcile] Error: {e}, falling back to simple creation")
        # Fallback to simple creation on error
        new_insight = await create_insight(
            user_id=user_id,
            insight_type=insight_type,
            content=new_content,
            concept_ids=concept_ids,
            confidence=confidence,
            source_type=source_type,
            source_id=source_id
        )
        return {"action": "CREATE_NEW_FALLBACK", "insight": new_insight}
    
    # Default fallback
    new_insight = await create_insight(
        user_id=user_id,
        insight_type=insight_type,
        content=new_content,
        concept_ids=concept_ids,
        confidence=confidence,
        source_type=source_type,
        source_id=source_id
    )
    return {"action": "CREATE_NEW", "insight": new_insight}



async def get_prerequisite_insights(user_id: str, concept_id: str) -> list[dict]:
    """Get learning status and insights for all prerequisites of a concept.
    
    This provides the tutor with context about the student's understanding of
    prerequisite concepts, including:
    - Whether each prerequisite has been taught
    - Whether each prerequisite has been verified
    - Any competency or misconception insights (including from subconcepts)
    - Object-level insights (exercises, MCQs, quizzes)
    
    Args:
        user_id: The user's ID
        concept_id: The concept whose prerequisites to check
    
    Returns:
        List of prerequisite status dicts with id, title, is_taught, is_verified, insights
    """
    # For subconcepts (e.g., 7.3.1), check parent section's prerequisites (7.3)
    section_id = concept_id
    if concept_id.count('.') >= 2:
        section_id = '.'.join(concept_id.split('.')[:2])
    
    query = """
    // Bind user once so prerequisite-insight fetch does not depend on TAUGHT existing.
    MATCH (u:User {id: $user_id})
    MATCH (c:Concept {id: $section_id})-[:REQUIRES]->(prereq:Concept)

    // TAUGHT status for prerequisite section node
    OPTIONAL MATCH (u)-[:HAS_INSIGHT]->(taught:Insight {type: "TAUGHT"})-[:ABOUT]->(prereq)
    WHERE taught.superseded_by IS NULL
    WITH u, prereq, collect(DISTINCT taught) as taught_insights

    // All active insights for prerequisite and its subsections (object-level included)
    OPTIONAL MATCH (u)-[:HAS_INSIGHT]->(insight:Insight)-[:ABOUT]->(related:Concept)
    WHERE insight.superseded_by IS NULL
      AND (related.id = prereq.id OR related.id STARTS WITH prereq.id + ".")
      AND NONE(t IN taught_insights WHERE t IS NOT NULL AND insight.id = t.id)
    WITH prereq, taught_insights,
         collect(DISTINCT {
             type: insight.type,
             content: insight.content,
             confidence: insight.confidence,
             source_type: insight.source_type,
             source_id: insight.source_id,
             concept_id: related.id
         }) as insights

    RETURN prereq.id as id,
           prereq.title as title,
           prereq.description as description,
           size(taught_insights) > 0 as is_taught,
           any(t IN taught_insights WHERE COALESCE(t.verified, false)) as is_verified,
           insights
    ORDER BY prereq.id
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        section_id=section_id
    )
    
    # Filter out empty insights and format response
    formatted = []
    for r in results:
        insights = [i for i in r["insights"] if i.get("type")]  # Filter empty
        formatted.append({
            "id": r["id"],
            "title": r["title"] or r["id"],
            "description": r["description"] or "",
            "is_taught": r["is_taught"],
            "is_verified": r["is_verified"],
            "insights": insights
        })
    
    return formatted


# === Concept Explanation Tracking Functions ===

async def mark_concept_explained(user_id: str, concept_id: str) -> dict:
    """Mark a concept as explained/taught to the user.
    
    Creates a TAUGHT insight if one doesn't already exist for this concept.
    Idempotent - calling multiple times won't create duplicates.
    
    Args:
        user_id: The user's ID
        concept_id: The concept that was explained
        
    Returns:
        The insight (new or existing)
    """
    # First check if TAUGHT insight already exists for this concept
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c:Concept {id: $concept_id})
    WHERE i.superseded_by IS NULL
    RETURN i.id as id, i.verified as verified, i.created_at as created_at
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        concept_id=concept_id
    )
    
    if results:
        # Already explained, return existing
        return {
            "id": results[0]["id"],
            "type": "TAUGHT",
            "verified": results[0]["verified"] or False,
            "created_at": str(results[0]["created_at"]) if results[0]["created_at"] else None,
            "already_existed": True
        }
    
    # Create new TAUGHT insight
    import uuid
    insight_id = f"insight-{uuid.uuid4().hex[:12]}"
    
    create_query = """
    MERGE (u:User {id: $user_id})
    WITH u
    MATCH (c:Concept {id: $concept_id})
    CREATE (i:Insight {
        id: $insight_id,
        type: "TAUGHT",
        content: "Concept explained to student",
        confidence: 1.0,
        verified: false,
        created_at: datetime()
    })
    MERGE (u)-[:HAS_INSIGHT]->(i)
    MERGE (i)-[:ABOUT]->(c)
    RETURN i.id as id, i.created_at as created_at
    """
    
    results = await neo4j_client.execute_write(
        create_query,
        user_id=user_id,
        concept_id=concept_id,
        insight_id=insight_id
    )
    
    # Invalidate cache
    await cache_delete(f"user_state:{user_id}")
    
    return {
        "id": insight_id,
        "type": "TAUGHT",
        "verified": False,
        "created_at": str(results[0]["created_at"]) if results else None,
        "already_existed": False
    }


async def get_section_learning_status(user_id: str, section_id: str) -> dict:
    """Get the learning status for all sub-concepts in a section.
    
    Note: Only counts sub-concepts (e.g., 7.3.1, 7.3.2) for progress tracking,
    not the parent section itself (7.3).
    
    Concepts needing retry are sorted to the END of the verification queue.
    
    Args:
        user_id: The user's ID
        section_id: The section ID (e.g., "7.3")
        
    Returns:
        {
            "section_id": "7.3",
            "concepts": [
                {"id": "7.3.1", "title": "...", "explained": true, "verified": false, "needs_retry": false},
                ...
            ],
            "all_explained": bool,
            "all_verified": bool,
            "explained_count": int,
            "verified_count": int,
            "total_count": int
        }
    """
    # Get all SUB-CONCEPTS in the section (excludes section itself)
    # Include retry fields for queue ordering
    query = """
    MATCH (c:Concept)
    WHERE c.id STARTS WITH $section_prefix
    OPTIONAL MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c)
    WHERE i.superseded_by IS NULL
    WITH c, collect(DISTINCT i) as taught_insights
    RETURN c.id as id,
           c.title as title,
           size(taught_insights) > 0 as explained,
           any(t in taught_insights WHERE COALESCE(t.verified, false)) as verified,
           any(t in taught_insights WHERE COALESCE(t.needs_retry, false)) as needs_retry,
           reduce(mx = 0, t in taught_insights |
               CASE WHEN COALESCE(t.retry_count, 0) > mx THEN COALESCE(t.retry_count, 0) ELSE mx END
           ) as retry_count
    ORDER BY c.id
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        section_prefix=section_id + "."
    )
    
    # Build concepts list (sub-concepts only)
    concepts = []
    if results:
        for r in results:
            concepts.append({
                "id": r["id"],
                "title": r["title"] or r["id"],
                "explained": r["explained"],
                "verified": r["verified"],
                "needs_retry": r["needs_retry"],
                "retry_count": r["retry_count"]
            })
    
    # Sort: concepts needing retry go to the END of the queue
    # First: explained but not verified, not needing retry (fresh verifications)
    # Then: needing retry (sorted by retry_count for fairness)
    concepts_to_verify = [c for c in concepts if c["explained"] and not c["verified"]]
    fresh = [c for c in concepts_to_verify if not c["needs_retry"]]
    retries = sorted([c for c in concepts_to_verify if c["needs_retry"]], key=lambda x: x["retry_count"])
    
    # Rebuild concepts list maintaining original order for explained/verified
    # but with to_verify order updated
    explained_count = sum(1 for c in concepts if c["explained"])
    verified_count = sum(1 for c in concepts if c["verified"])
    total_count = len(concepts)
    
    return {
        "section_id": section_id,
        "concepts": concepts,
        "to_verify_ordered": fresh + retries,  # NEW: ordered queue for verification
        "all_explained": explained_count == total_count and total_count > 0,
        "all_verified": verified_count == total_count and total_count > 0,
        "explained_count": explained_count,
        "verified_count": verified_count,
        "total_count": total_count
    }



async def mark_concept_verified(user_id: str, concept_id: str, is_verified: bool = True, insight_content: str | None = None) -> dict:
    """Mark a concept as verified (student demonstrated understanding).
    
    Updates the TAUGHT insight's verified field.
    Also creates a COMPETENCY insight if verified=True.
    
    Args:
        user_id: The user's ID
        concept_id: The concept to mark as verified
        is_verified: Whether the student passed verification
        insight_content: Optional LLM-generated insight content (uses default if not provided)
        
    Returns:
        Updated status
    """
    # Update the TAUGHT insight
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c:Concept {id: $concept_id})
    WHERE i.superseded_by IS NULL
    SET i.verified = $is_verified,
        i.verified_at = datetime()
    RETURN i.id as id, c.title as concept_title
    """
    
    results = await neo4j_client.execute_write(
        query,
        user_id=user_id,
        concept_id=concept_id,
        is_verified=is_verified
    )
    
    concept_title = results[0]["concept_title"] if results else concept_id
    
    # If verified, also create a COMPETENCY insight
    if is_verified and results:
        # Use provided LLM content or fallback to default
        content = insight_content or f"Demonstrated understanding of '{concept_title}' through verification"
        await create_insight(
            user_id=user_id,
            insight_type="COMPETENCY",
            content=content,
            concept_ids=[concept_id],
            confidence=0.9
        )
    
    # Invalidate cache
    await cache_delete(f"user_state:{user_id}")
    
    return {
        "concept_id": concept_id,
        "verified": is_verified,
        "insight_updated": bool(results)
    }


async def schedule_retry_verification(user_id: str, concept_id: str) -> dict:
    """Schedule a failed verification for retry at the end of the queue.
    
    This is called when a student fails verification. The concept is pushed to
    the back of the verification queue by setting retry_at timestamp.
    
    Args:
        user_id: The user's ID
        concept_id: The concept that needs retry
        
    Returns:
        Updated retry state
    """
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c:Concept {id: $concept_id})
    WHERE i.superseded_by IS NULL
    SET i.retry_count = COALESCE(i.retry_count, 0) + 1,
        i.retry_at = datetime(),
        i.needs_retry = true
    RETURN i.id as id, i.retry_count as retry_count, c.id as concept_id
    """
    
    results = await neo4j_client.execute_write(
        query,
        user_id=user_id,
        concept_id=concept_id
    )
    
    # Invalidate cache
    await cache_delete(f"user_state:{user_id}")
    
    if results:
        return {
            "concept_id": concept_id,
            "retry_count": results[0]["retry_count"],
            "scheduled": True
        }
    return {"concept_id": concept_id, "scheduled": False}


async def clear_retry_flag(user_id: str, concept_id: str) -> bool:
    """Clear retry flag when verification passes on retry."""
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c:Concept {id: $concept_id})
    WHERE i.superseded_by IS NULL
    SET i.needs_retry = false
    RETURN i.id as id
    """
    
    results = await neo4j_client.execute_write(
        query,
        user_id=user_id,
        concept_id=concept_id
    )
    
    await cache_delete(f"user_state:{user_id}")
    return bool(results)


# === Sub-Concept Navigation Functions ===

async def get_subconcepts_for_section(section_id: str) -> list[dict]:
    """Get all sub-concepts for a section, ordered by ID.
    
    Args:
        section_id: The section ID (e.g., "7.3")
        
    Returns:
        List of sub-concept dicts with id, title, description, type
    """
    query = """
    MATCH (c:Concept)
    WHERE c.id STARTS WITH $section_prefix
    RETURN c.id as id, c.title as title, c.description as description, c.type as type
    ORDER BY c.id
    """
    
    results = await neo4j_client.execute_read(
        query,
        section_prefix=section_id + "."
    )
    
    return [
        {
            "id": r["id"],
            "title": r["title"] or r["id"],
            "description": r["description"] or "",
            "type": r["type"] or "concept"
        }
        for r in results
    ] if results else []


async def get_first_unexplained_subconcept(user_id: str, section_id: str) -> dict | None:
    """Get the first sub-concept in a section that hasn't been explained to the user.
    
    Args:
        user_id: The user's ID
        section_id: The section ID (e.g., "7.3")
        
    Returns:
        First unexplained sub-concept with id, title, description, type or None if all explained
    """
    query = """
    MATCH (c:Concept)
    WHERE c.id STARTS WITH $section_prefix
    OPTIONAL MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c)
    WHERE i.superseded_by IS NULL
    WITH c, i
    WHERE i IS NULL
    RETURN c.id as id, c.title as title, c.description as description, c.type as type
    ORDER BY c.id
    LIMIT 1
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        section_prefix=section_id + "."
    )
    
    if results:
        return {
            "id": results[0]["id"],
            "title": results[0]["title"] or results[0]["id"],
            "description": results[0]["description"] or "",
            "type": results[0]["type"] or "concept"
        }
    return None


async def get_next_subconcept(user_id: str, section_id: str, current_subconcept_id: str) -> dict | None:
    """Get the next sub-concept after the current one.
    
    Args:
        user_id: The user's ID
        section_id: The section ID
        current_subconcept_id: The current sub-concept ID (e.g., "7.3.1")
        
    Returns:
        Next sub-concept or None if at the end
    """
    # Get all subconcepts
    all_subconcepts = await get_subconcepts_for_section(section_id)
    
    # Find current index
    current_index = -1
    for i, sc in enumerate(all_subconcepts):
        if sc["id"] == current_subconcept_id:
            current_index = i
            break
    
    # Return next if exists
    if current_index >= 0 and current_index < len(all_subconcepts) - 1:
        return all_subconcepts[current_index + 1]
    
    return None
