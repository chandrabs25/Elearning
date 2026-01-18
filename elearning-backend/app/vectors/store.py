"""Vector store for semantic search over knowledge graph nodes."""
import os
import json
from pathlib import Path
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from app.config import settings

VECTOR_STORE_PATH = Path(__file__).parent / "faiss_index"


def get_embeddings():
    """Get HuggingFace embeddings model (free, local)."""
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",  # BGE-M3 model, already cached
        model_kwargs={"device": "cpu"},
    )


async def build_vector_store(nodes: list[dict]) -> FAISS:
    """Build FAISS vector store from knowledge graph nodes.
    
    Args:
        nodes: List of dicts with 'id', 'title', 'description', 'type' keys
    
    Returns:
        FAISS vector store
    """
    documents = []
    for node in nodes:
        # Combine title and description for better semantic matching
        content = f"{node['title']}: {node.get('description', '')}"
        doc = Document(
            page_content=content,
            metadata={
                "id": node["id"],
                "title": node["title"],
                "type": node.get("type", "concept"),
                "description": node.get("description", ""),
            }
        )
        documents.append(doc)
    
    embeddings = get_embeddings()
    vector_store = FAISS.from_documents(documents, embeddings)
    
    # Save locally
    vector_store.save_local(str(VECTOR_STORE_PATH))
    print(f"✓ Vector store saved with {len(documents)} documents")
    
    return vector_store


def load_vector_store() -> FAISS | None:
    """Load existing FAISS vector store."""
    if not VECTOR_STORE_PATH.exists():
        return None
    
    embeddings = get_embeddings()
    return FAISS.load_local(
        str(VECTOR_STORE_PATH),
        embeddings,
        allow_dangerous_deserialization=True
    )


async def search_similar(query: str, k: int = 5) -> list[dict]:
    """Search for similar nodes by query.
    
    Args:
        query: Natural language search query
        k: Number of results to return
    
    Returns:
        List of matching nodes with scores
    """
    vector_store = load_vector_store()
    if not vector_store:
        return []
    
    results = vector_store.similarity_search_with_score(query, k=k)
    
    return [
        {
            "id": doc.metadata["id"],
            "title": doc.metadata["title"],
            "type": doc.metadata["type"],
            "description": doc.metadata["description"],
            "score": round(1 - score, 2),  # Convert distance to similarity
        }
        for doc, score in results
    ]
