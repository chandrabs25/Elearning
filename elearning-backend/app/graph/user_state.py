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
    MATCH (u:User {id: $user_id})
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
    """Get the learning status for all concepts in a section.
    
    Args:
        user_id: The user's ID
        section_id: The section ID (e.g., "7.3")
        
    Returns:
        {
            "section_id": "7.3",
            "concepts": [
                {"id": "7.3.1", "title": "...", "explained": true, "verified": false},
                ...
            ],
            "all_explained": bool,
            "all_verified": bool,
            "explained_count": int,
            "verified_count": int,
            "total_count": int
        }
    """
    # Get all concepts in the section and their TAUGHT insights for this user
    query = """
    MATCH (c:Concept)
    WHERE c.id STARTS WITH $section_prefix
    OPTIONAL MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c)
    WHERE i.superseded_by IS NULL
    RETURN c.id as id, 
           c.title as title,
           CASE WHEN i IS NOT NULL THEN true ELSE false END as explained,
           COALESCE(i.verified, false) as verified
    ORDER BY c.id
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        section_prefix=section_id + "."
    )
    
    # Also check if the section itself (e.g., "7.3") is a concept
    section_query = """
    MATCH (c:Concept {id: $section_id})
    OPTIONAL MATCH (u:User {id: $user_id})-[:HAS_INSIGHT]->(i:Insight {type: "TAUGHT"})-[:ABOUT]->(c)
    WHERE i.superseded_by IS NULL
    RETURN c.id as id,
           c.title as title,
           CASE WHEN i IS NOT NULL THEN true ELSE false END as explained,
           COALESCE(i.verified, false) as verified
    """
    
    section_result = await neo4j_client.execute_read(
        section_query,
        user_id=user_id,
        section_id=section_id
    )
    
    concepts = []
    
    # Add section itself if it exists as a concept
    if section_result:
        concepts.append({
            "id": section_result[0]["id"],
            "title": section_result[0]["title"] or section_id,
            "explained": section_result[0]["explained"],
            "verified": section_result[0]["verified"]
        })
    
    # Add sub-concepts
    if results:
        for r in results:
            concepts.append({
                "id": r["id"],
                "title": r["title"] or r["id"],
                "explained": r["explained"],
                "verified": r["verified"]
            })
    
    explained_count = sum(1 for c in concepts if c["explained"])
    verified_count = sum(1 for c in concepts if c["verified"])
    total_count = len(concepts)
    
    return {
        "section_id": section_id,
        "concepts": concepts,
        "all_explained": explained_count == total_count and total_count > 0,
        "all_verified": verified_count == total_count and total_count > 0,
        "explained_count": explained_count,
        "verified_count": verified_count,
        "total_count": total_count
    }


async def mark_concept_verified(user_id: str, concept_id: str, is_verified: bool = True) -> dict:
    """Mark a concept as verified (student demonstrated understanding).
    
    Updates the TAUGHT insight's verified field.
    Also creates a COMPETENCY insight if verified=True.
    
    Args:
        user_id: The user's ID
        concept_id: The concept to mark as verified
        is_verified: Whether the student passed verification
        
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
        await create_insight(
            user_id=user_id,
            insight_type="COMPETENCY",
            content=f"Demonstrated understanding of '{concept_title}' through verification",
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
