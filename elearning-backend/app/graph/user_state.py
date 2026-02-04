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
    """Persist tutor session state (mode, prereq info) to Neo4j User node."""
    import json
    query = """
    MATCH (u:User {id: $user_id})
    SET u.tutor_mode = $mode,
        u.tutor_prereq_id = $prereq_id,
        u.tutor_prereq_title = $prereq_title,
        u.tutor_prereq_question = $prereq_question,
        u.tutor_prereq_chain = $prereq_chain,
        u.tutor_pending_verification = $pending_verification
    """
    await neo4j_client.execute_write(
        query,
        user_id=user_id,
        mode=tutor_state.get("mode", "normal"),
        prereq_id=tutor_state.get("current_prereq_id"),
        prereq_title=tutor_state.get("current_prereq_title"),
        prereq_question=tutor_state.get("prereq_question"),
        prereq_chain=json.dumps(tutor_state.get("prerequisite_chain", [])),
        pending_verification=tutor_state.get("pending_verification_concept")
    )
    
    # Invalidate cache
    await cache_delete(f"tutor_state:{user_id}")


async def get_tutor_state(user_id: str) -> dict:
    """Retrieve persisted tutor session state from Neo4j User node."""
    import json
    cache_key = f"tutor_state:{user_id}"
    
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    query = """
    MATCH (u:User {id: $user_id})
    RETURN u.tutor_mode as mode,
           u.tutor_prereq_id as prereq_id,
           u.tutor_prereq_title as prereq_title,
           u.tutor_prereq_question as prereq_question,
           u.tutor_prereq_chain as prereq_chain,
           u.tutor_pending_verification as pending_verification
    """
    results = await neo4j_client.execute_read(query, user_id=user_id)
    if not results or not results[0]:
        return {}
    
    row = results[0]
    state = {
        "mode": row.get("mode") or "normal",
        "current_prereq_id": row.get("prereq_id"),
        "current_prereq_title": row.get("prereq_title"),
        "prereq_question": row.get("prereq_question"),
        "prerequisite_chain": json.loads(row.get("prereq_chain") or "[]"),
        "pending_verification_concept": row.get("pending_verification")
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
    """Get user's most recent session summary."""
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session)
    RETURN s.summary as summary, s.created_at as created_at
    ORDER BY s.created_at DESC
    LIMIT 1
    """
    results = await neo4j_client.execute_read(query, user_id=user_id)
    return results[0] if results else None


# === Insight Management Functions ===

async def create_insight(
    user_id: str,
    insight_type: str,  # COMPETENCY, MISCONCEPTION, PREFERENCE
    content: str,
    concept_ids: list[str],
    confidence: float = 1.0
) -> dict:
    """Create a new Insight node and link it to the user and concepts.
    
    Args:
        user_id: The user's ID
        insight_type: Type of insight (COMPETENCY, MISCONCEPTION, PREFERENCE)
        content: Description of the insight
        concept_ids: List of concept IDs this insight is about
        confidence: How certain the agent is about this insight (0.0-1.0)
    
    Returns:
        The created insight with its ID
    """
    import uuid
    
    insight_id = f"insight-{uuid.uuid4().hex[:12]}"
    
    # Create insight node and link to user
    query = """
    MATCH (u:User {id: $user_id})
    CREATE (i:Insight {
        id: $insight_id,
        type: $insight_type,
        content: $content,
        confidence: $confidence,
        created_at: datetime()
    })
    MERGE (u)-[:HAS_INSIGHT]->(i)
    WITH i
    UNWIND $concept_ids AS concept_id
    MATCH (c:Concept {id: concept_id})
    MERGE (i)-[:ABOUT]->(c)
    RETURN i.id as id, i.type as type, i.content as content, i.created_at as created_at
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        insight_id=insight_id,
        insight_type=insight_type,
        content=content,
        confidence=confidence,
        concept_ids=concept_ids
    )
    
    # Invalidate user state cache
    await cache_delete(f"user_state:{user_id}")
    
    if results:
        return {
            "id": results[0]["id"],
            "type": results[0]["type"],
            "content": results[0]["content"],
            "created_at": str(results[0]["created_at"]) if results[0]["created_at"] else None
        }
    return {"id": insight_id, "type": insight_type, "content": content}


async def get_insights_for_concept(user_id: str, concept_id: str) -> list[dict]:
    """Get all active insights for a user related to a specific concept.
    
    Returns insights that are:
    1. Linked to the user
    2. About the specified concept
    3. Not superseded by a newer insight
    
    Args:
        user_id: The user's ID
        concept_id: The concept to get insights for
    
    Returns:
        List of insight dictionaries
    """
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight)-[:ABOUT]->(c:Concept {id: $concept_id})
    WHERE i.superseded_by IS NULL
    RETURN i.id as id, 
           i.type as type, 
           i.content as content, 
           i.confidence as confidence,
           i.created_at as created_at
    ORDER BY i.created_at DESC
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        concept_id=concept_id
    )
    
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "content": r["content"],
            "confidence": r["confidence"],
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


async def create_insight_with_supersede(
    user_id: str,
    insight_type: str,  # COMPETENCY or MISCONCEPTION
    content: str,
    concept_ids: list[str],
    confidence: float = 1.0
) -> dict:
    """Create a new insight AND automatically supersede contradicting insights.
    
    Supersede logic:
    - If creating COMPETENCY → supersede existing MISCONCEPTIONs for same concepts
    - If creating MISCONCEPTION → supersede existing COMPETENCYs for same concepts
    
    Args:
        user_id: The user's ID
        insight_type: Type of insight (COMPETENCY or MISCONCEPTION)
        content: Description of the insight
        concept_ids: List of concept IDs this insight is about
        confidence: How certain the agent is about this insight (0.0-1.0)
    
    Returns:
        The created insight with its ID and count of superseded insights
    """
    # Determine which type to supersede
    opposite_type = "MISCONCEPTION" if insight_type == "COMPETENCY" else "COMPETENCY"
    
    # First, find existing contradicting insights for the same concepts
    find_query = """
    MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: $opposite_type})-[:ABOUT]->(c:Concept)
    WHERE c.id IN $concept_ids AND i.superseded_by IS NULL
    RETURN i.id as id, i.content as content, collect(c.id) as concept_ids
    """
    
    contradicting = await neo4j_client.execute_read(
        find_query,
        user_id=user_id,
        opposite_type=opposite_type,
        concept_ids=concept_ids
    )
    
    # Create the new insight
    new_insight = await create_insight(
        user_id=user_id,
        insight_type=insight_type,
        content=content,
        concept_ids=concept_ids,
        confidence=confidence
    )
    
    new_insight_id = new_insight.get("id")
    superseded_count = 0
    
    # Supersede all contradicting insights
    if new_insight_id and contradicting:
        for old in contradicting:
            old_id = old.get("id")
            if old_id:
                success = await supersede_insight(old_id, new_insight_id)
                if success:
                    superseded_count += 1
                    print(f"[Insight] Superseded {opposite_type}: {old.get('content', old_id)[:50]}...")
    
    new_insight["superseded_count"] = superseded_count
    
    if superseded_count > 0:
        print(f"[Insight] Created {insight_type} and superseded {superseded_count} {opposite_type}(s)")
    
    return new_insight


async def get_prerequisite_insights(user_id: str, concept_id: str) -> list[dict]:
    """Get learning status and insights for all prerequisites of a concept.
    
    This provides the tutor with context about the student's understanding of
    prerequisite concepts, including:
    - Whether each prerequisite has been taught
    - Whether each prerequisite has been verified
    - Any competency or misconception insights
    
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
    // Get prerequisites for the concept (or its parent section)
    MATCH (c:Concept {id: $section_id})-[:REQUIRES]->(prereq:Concept)
    
    // Check if this prerequisite has a TAUGHT insight for this user
    OPTIONAL MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(taught:Insight {type: "TAUGHT"})-[:ABOUT]->(prereq)
    WHERE taught.superseded_by IS NULL
    
    // Get all active insights for this prerequisite
    OPTIONAL MATCH (u)-[:HAS_INSIGHT]->(insight:Insight)-[:ABOUT]->(prereq)
    WHERE insight.superseded_by IS NULL AND insight.id <> taught.id
    
    WITH prereq, taught, 
         collect(DISTINCT {
             type: insight.type, 
             content: insight.content,
             confidence: insight.confidence
         }) as insights
    
    RETURN prereq.id as id,
           prereq.title as title,
           prereq.description as description,
           CASE WHEN taught IS NOT NULL THEN true ELSE false END as is_taught,
           COALESCE(taught.verified, false) as is_verified,
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
    RETURN c.id as id, 
           c.title as title,
           CASE WHEN i IS NOT NULL THEN true ELSE false END as explained,
           COALESCE(i.verified, false) as verified,
           COALESCE(i.needs_retry, false) as needs_retry,
           COALESCE(i.retry_count, 0) as retry_count
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

