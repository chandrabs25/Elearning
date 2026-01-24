"""
RAG-style content search using Neo4j vector embeddings.
Searches all chapter sections to find relevant content for user questions.

Uses HuggingFace Inference API with BAAI/bge-base-en-v1.5 model.
"""

import httpx
from app.graph.client import get_driver
from app.config import settings


# HuggingFace model for embeddings
HF_MODEL = "BAAI/bge-base-en-v1.5"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"


async def get_query_embedding(query: str) -> list[float]:
    """
    Generate embedding for a search query using HuggingFace API.
    
    For BGE models, queries should be prefixed with instruction for best results.
    """
    api_key = getattr(settings, 'huggingface_api_key', None)
    if not api_key:
        raise ValueError("HUGGINGFACE_API_KEY not configured")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # BGE models work best with instruction prefix for queries
    query_text = f"Represent this sentence for searching relevant passages: {query}"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            HF_API_URL,
            headers=headers,
            json={"inputs": query_text, "options": {"wait_for_model": True}},
            timeout=30.0
        )
    
    if response.status_code != 200:
        raise Exception(f"HuggingFace API error: {response.status_code} - {response.text}")
    
    embedding = response.json()
    
    # The API returns a nested list for single input
    if isinstance(embedding[0], list):
        embedding = embedding[0]
    
    return embedding


async def search_relevant_sections(
    query: str, 
    top_k: int = 3,
    min_score: float = 0.3
) -> list[dict]:
    """
    Search for sections most relevant to the user's query using vector similarity.
    
    Args:
        query: The user's question or doubt
        top_k: Maximum number of sections to return
        min_score: Minimum similarity score threshold (0-1)
    
    Returns:
        List of dicts with section_id, title, content, and relevance_score
    """
    try:
        # Generate embedding for the query
        query_embedding = await get_query_embedding(query)
    except Exception as e:
        print(f"Embedding generation error: {e}")
        return []
    
    # Query Neo4j vector index
    driver = get_driver()
    
    try:
        with driver.session() as session:
            result = session.run("""
                CALL db.index.vector.queryNodes(
                    'section_embeddings',
                    $top_k,
                    $query_embedding
                ) YIELD node, score
                WHERE score >= $min_score
                RETURN node.id AS section_id,
                       node.title AS title,
                       node.content_summary AS content,
                       score
                ORDER BY score DESC
            """, top_k=top_k, query_embedding=query_embedding, min_score=min_score)
            
            sections = [
                {
                    "section_id": record["section_id"],
                    "title": record["title"],
                    "content": record["content"],
                    "relevance_score": record["score"]
                }
                for record in result
            ]
            
            return sections
    except Exception as e:
        print(f"Vector search error: {e}")
        return []


def format_retrieved_content(sections: list[dict]) -> str:
    """
    Format retrieved sections into a single context string for the LLM.
    
    Args:
        sections: List of section dicts from search_relevant_sections
    
    Returns:
        Formatted string with all relevant content
    """
    if not sections:
        return ""
    
    parts = []
    for section in sections:
        parts.append(f"## {section['title']} (Section {section['section_id']})\n\n{section['content']}")
    
    return "\n\n---\n\n".join(parts)


def get_section_suggestions(sections: list[dict]) -> list[dict]:
    """
    Generate suggested actions for the chat response.
    
    Args:
        sections: List of section dicts from search_relevant_sections
    
    Returns:
        List of suggested action dicts for the UI
    """
    return [
        {
            "label": f"📖 Read: {s['title'][:40]}{'...' if len(s['title']) > 40 else ''}",
            "action": f"start:{s['section_id']}",
            "primary": i == 0
        }
        for i, s in enumerate(sections[:2])  # Max 2 suggestions
    ]
