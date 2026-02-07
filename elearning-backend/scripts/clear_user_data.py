import asyncio
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph.client import neo4j_client

async def clear_user_data():
    print("🧹 Cleaning up user data...")
    
    # Verify connection first
    await neo4j_client.verify_connectivity()
    
    queries = [
        # Clear all user nodes and their relationships
        "MATCH (n:User) DETACH DELETE n",
        "MATCH (n:ChatMessage) DETACH DELETE n",
        "MATCH (n:Insight) DETACH DELETE n",
        "MATCH (n:QuizAttempt) DETACH DELETE n", 
        "MATCH (n:Interaction) DETACH DELETE n",
        # Clear any TAUGHT relationships on SubConcept nodes
        "MATCH ()-[r:TAUGHT]->() DELETE r",
        # Clear any VERIFIED relationships
        "MATCH ()-[r:VERIFIED]->() DELETE r",
        # Clear any HAS_MISCONCEPTION relationships
        "MATCH ()-[r:HAS_MISCONCEPTION]->() DELETE r",
        # Clear any user learning progress relationships
        "MATCH ()-[r:LEARNED]->() DELETE r",
        "MATCH ()-[r:STRUGGLED_WITH]->() DELETE r",
        # Clear LangGraph session/memory states (if stored in Neo4j)
        "MATCH (n:MemoryCheckpoint) DETACH DELETE n",
        "MATCH (n:SessionState) DETACH DELETE n",
    ]
    
    try:
        for q in queries:
            print(f"Executing: {q}")
            await neo4j_client.execute_write(q)
        print("✅ User data cleared successfully.")
    except Exception as e:
        print(f"❌ Error clearing data: {e}")
    finally:
        await neo4j_client.close()

if __name__ == "__main__":
    asyncio.run(clear_user_data())
