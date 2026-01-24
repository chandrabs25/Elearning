#!/usr/bin/env python3
"""
Generate embeddings for all sections in gravity.json and store in Neo4j.
Uses HuggingFace Inference API with BAAI/bge-base-en-v1.5 model.

Run this once to set up the vector index for RAG search.

Usage:
    python scripts/generate_embeddings.py

Requires:
    - HUGGINGFACE_API_KEY in .env
    - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env
"""

import os
import sys
import json
import httpx
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# HuggingFace model for embeddings
# BAAI/bge-base-en-v1.5: 768 dimensions, excellent quality
HF_MODEL = "BAAI/bge-base-en-v1.5"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"
EMBEDDING_DIMENSIONS = 768


def get_embedding(text: str) -> list[float]:
    """Get embedding from HuggingFace Inference API."""
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise ValueError("HUGGINGFACE_API_KEY not set in .env")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # BGE models work best with instruction prefix for queries
    # For documents, we use the text as-is
    response = httpx.post(
        HF_API_URL,
        headers=headers,
        json={"inputs": text, "options": {"wait_for_model": True}},
        timeout=60.0
    )
    
    if response.status_code != 200:
        raise Exception(f"HuggingFace API error: {response.status_code} - {response.text}")
    
    embedding = response.json()
    
    # The API returns a nested list for single input
    if isinstance(embedding[0], list):
        embedding = embedding[0]
    
    return embedding


def load_sections_from_json() -> list[dict]:
    """Load all sections from gravity.json with their content."""
    paths = [
        Path(__file__).parent.parent / "data" / "gravity.json",
        Path(__file__).parent.parent.parent / "elearning-platform" / "src" / "data" / "chapters" / "gravity.json",
    ]
    
    for path in paths:
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
            break
    else:
        raise FileNotFoundError("gravity.json not found")
    
    sections = []
    for section in data.get("sections", []):
        section_id = section.get("section_id")
        title = section.get("section_title", "")
        
        # Skip non-content sections
        if section_id in ["SUMMARY", "POINTS_TO_PONDER", "PHYSICAL_QUANTITIES_TABLE", "EXERCISES"]:
            continue
        
        # Extract text content
        content_parts = []
        for item in section.get("content", []):
            item_type = item.get("type")
            if item_type == "text":
                content_parts.append(item.get("body", ""))
            elif item_type == "list_item":
                content_parts.append(f"- {item.get('label', '')}: {item.get('body', '')}")
            elif item_type == "derivation":
                content_parts.append(f"Formula: {item.get('latex', '')}")
            elif item_type == "example_box":
                content_parts.append(f"Example: {item.get('question', '')}")
        
        content_text = "\n".join(content_parts)
        
        if content_text.strip():
            sections.append({
                "id": section_id,
                "title": title,
                "content_text": content_text[:3000]  # Limit for embedding
            })
    
    return sections


def generate_embeddings(sections: list[dict]) -> list[dict]:
    """Generate embeddings for each section using HuggingFace API."""
    print(f"Using model: {HF_MODEL}")
    print(f"Embedding dimensions: {EMBEDDING_DIMENSIONS}")
    
    for i, section in enumerate(sections):
        # Combine title and content for better semantic matching
        text = f"{section['title']}\n\n{section['content_text']}"
        
        print(f"  [{i+1}/{len(sections)}] {section['id']}: {section['title'][:50]}...", end=" ", flush=True)
        embedding = get_embedding(text)
        section["embedding"] = embedding
        print(f"✓ ({len(embedding)} dims)")
    
    return sections


def store_embeddings_in_neo4j(sections: list[dict]):
    """Store embeddings in Neo4j and create vector index."""
    from neo4j import GraphDatabase
    
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    
    if not all([uri, user, password]):
        raise ValueError("NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set")
    
    print(f"Connecting to Neo4j at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    with driver.session() as session:
        print("Creating/updating Section nodes with embeddings...")
        for section in sections:
            session.run("""
                MERGE (s:Section {id: $id})
                SET s.title = $title,
                    s.content_summary = $content_summary,
                    s.embedding = $embedding
            """, 
                id=section["id"],
                title=section["title"],
                content_summary=section["content_text"][:2000],
                embedding=section["embedding"]
            )
            print(f"  ✓ {section['id']}: {section['title'][:40]}")
        
        # Create vector index with correct dimensions for bge-base-en-v1.5
        print(f"\nCreating vector index (dimensions: {EMBEDDING_DIMENSIONS})...")
        try:
            # Drop existing index if dimensions changed
            session.run("DROP INDEX section_embeddings IF EXISTS")
            session.run(f"""
                CREATE VECTOR INDEX section_embeddings IF NOT EXISTS
                FOR (s:Section)
                ON (s.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {EMBEDDING_DIMENSIONS},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
            """)
            print("  ✓ Vector index created")
        except Exception as e:
            print(f"  ⚠ Index note: {e}")
    
    driver.close()
    print("\n✓ Done! Embeddings stored in Neo4j.")


def test_vector_search():
    """Quick test of the vector search."""
    from neo4j import GraphDatabase
    
    print("\n--- Testing Vector Search ---")
    
    test_query = "Why does gravity decrease with height?"
    print(f"Getting embedding for: '{test_query}'")
    
    # For queries, BGE recommends prefixing with instruction
    query_text = f"Represent this sentence for searching relevant passages: {test_query}"
    query_embedding = get_embedding(query_text)
    
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    
    with driver.session() as session:
        result = session.run("""
            CALL db.index.vector.queryNodes(
                'section_embeddings',
                3,
                $query_embedding
            ) YIELD node, score
            RETURN node.id AS section_id,
                   node.title AS title,
                   score
            ORDER BY score DESC
        """, query_embedding=query_embedding)
        
        print(f"\nQuery: '{test_query}'")
        print("Top matches:")
        for record in result:
            print(f"  {record['score']:.3f} | {record['section_id']}: {record['title']}")
    
    driver.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Section Embedding Generator for RAG Search")
    print(f"Model: {HF_MODEL}")
    print("=" * 60)
    
    # Check API key
    if not os.getenv("HUGGINGFACE_API_KEY"):
        print("\n❌ Error: HUGGINGFACE_API_KEY not found in .env")
        print("Get your free API key at: https://huggingface.co/settings/tokens")
        sys.exit(1)
    
    # Step 1: Load sections
    print("\n[1/4] Loading sections from gravity.json...")
    sections = load_sections_from_json()
    print(f"    Found {len(sections)} content sections")
    
    # Step 2: Generate embeddings
    print("\n[2/4] Generating embeddings via HuggingFace API...")
    sections = generate_embeddings(sections)
    
    # Step 3: Store in Neo4j
    print("\n[3/4] Storing embeddings in Neo4j...")
    store_embeddings_in_neo4j(sections)
    
    # Step 4: Test search
    print("\n[4/4] Testing vector search...")
    try:
        test_vector_search()
    except Exception as e:
        print(f"  ⚠ Test skipped: {e}")
    
    print("\n" + "=" * 60)
    print("Setup complete! RAG search is ready.")
    print("=" * 60)
