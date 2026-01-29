"""Chat history persistence for Neo4j.

Stores chat messages per user per section, enabling conversation continuity
when users return to the same section.
"""
from app.graph.client import neo4j_client
from app.cache import cache_get, cache_set, cache_delete
from datetime import datetime
from typing import Optional


async def save_chat_message(
    user_id: str,
    section_id: str,
    role: str,
    content: str | list
) -> dict:
    """
    Save a chat message to Neo4j.
    
    Args:
        user_id: The user's ID
        section_id: The section/concept ID (e.g., "7.2")
        role: "user" or "assistant"
        content: Message content (string or list of content items)
    
    Returns:
        The saved message with its generated ID
    """
    # Serialize content if it's a list
    import json
    content_str = json.dumps(content) if isinstance(content, list) else content
    
    query = """
    MATCH (u:User {id: $user_id})
    MERGE (s:Concept {id: $section_id})
    CREATE (m:ChatMessage {
        id: randomUUID(),
        role: $role,
        content: $content,
        timestamp: datetime(),
        section_id: $section_id,
        user_id: $user_id
    })
    CREATE (u)-[:SENT]->(m)
    CREATE (m)-[:IN_SECTION]->(s)
    RETURN m.id as id, m.role as role, m.content as content, m.timestamp as timestamp
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        section_id=section_id,
        role=role,
        content=content_str
    )
    
    # Invalidate cache for this section's chat history
    await cache_delete(f"chat_history:{user_id}:{section_id}")
    
    if results:
        row = results[0]
        return {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "timestamp": str(row["timestamp"]) if row["timestamp"] else None
        }
    return None


async def get_chat_history(
    user_id: str,
    section_id: str,
    limit: int = 20
) -> list[dict]:
    """
    Get chat history for a user in a specific section.
    
    Args:
        user_id: The user's ID
        section_id: The section/concept ID
        limit: Maximum number of messages to return (most recent)
    
    Returns:
        List of messages ordered by timestamp (oldest first)
    """
    cache_key = f"chat_history:{user_id}:{section_id}"
    
    # Try cache first
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    query = """
    MATCH (u:User {id: $user_id})-[:SENT]->(m:ChatMessage)-[:IN_SECTION]->(s:Concept {id: $section_id})
    RETURN m.id as id, m.role as role, m.content as content, m.timestamp as timestamp
    ORDER BY m.timestamp DESC
    LIMIT $limit
    """
    
    results = await neo4j_client.execute_read(
        query,
        user_id=user_id,
        section_id=section_id,
        limit=limit
    )
    
    import json
    messages = []
    for row in reversed(results):  # Reverse to get oldest first
        content = row["content"]
        # Try to parse JSON content (for list-based content)
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass
        
        messages.append({
            "id": row["id"],
            "role": row["role"],
            "content": content,
            "timestamp": str(row["timestamp"]) if row["timestamp"] else None
        })
    
    # Cache for 5 minutes
    await cache_set(cache_key, messages, ttl=300)
    
    return messages


async def clear_chat_history(user_id: str, section_id: str) -> bool:
    """
    Clear all chat history for a user in a specific section.
    
    Args:
        user_id: The user's ID
        section_id: The section/concept ID
    
    Returns:
        True if successful
    """
    query = """
    MATCH (u:User {id: $user_id})-[:SENT]->(m:ChatMessage)-[:IN_SECTION]->(s:Concept {id: $section_id})
    DETACH DELETE m
    RETURN count(*) as deleted
    """
    
    await neo4j_client.execute_read(
        query,
        user_id=user_id,
        section_id=section_id
    )
    
    # Invalidate cache
    await cache_delete(f"chat_history:{user_id}:{section_id}")
    
    return True


async def get_all_section_chat_counts(user_id: str) -> dict[str, int]:
    """
    Get message counts for all sections a user has chatted in.
    Useful for showing which sections have chat history.
    
    Args:
        user_id: The user's ID
    
    Returns:
        Dict mapping section_id to message count
    """
    query = """
    MATCH (u:User {id: $user_id})-[:SENT]->(m:ChatMessage)-[:IN_SECTION]->(s:Concept)
    RETURN s.id as section_id, count(m) as message_count
    """
    
    results = await neo4j_client.execute_read(query, user_id=user_id)
    
    return {row["section_id"]: row["message_count"] for row in results}
