"""User state management for Neo4j with Redis caching."""
from app.graph.client import neo4j_client
from app.cache import cache_get, cache_set, cache_delete
from datetime import datetime


async def get_or_create_user(user_id: str) -> dict:
    """Get user or create new one."""
    query = """
    MERGE (u:User {id: $user_id})
    ON CREATE SET u.created_at = datetime(), u.session_count = 0, u.lifetime_mastery = 0
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
