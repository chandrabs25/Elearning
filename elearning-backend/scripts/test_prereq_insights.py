import asyncio
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph.client import neo4j_client
from app.graph.user_state import get_prerequisite_insights

async def test_prereq_insights():
    print("🔍 Testing get_prerequisite_insights for 7.9...\n")
    
    # Verify connection first
    await neo4j_client.verify_connectivity()
    
    # Test the actual function
    result = await get_prerequisite_insights("demo-user", "7.9")
    
    print(f"Found {len(result)} prerequisites:\n")
    for prereq in result:
        print(f"Prereq: {prereq['id']} - {prereq['title']}")
        print(f"  is_taught: {prereq['is_taught']}")
        print(f"  is_verified: {prereq['is_verified']}")
        print(f"  insights: {len(prereq['insights'])} insights")
        for i in prereq['insights'][:5]:
            print(f"    - [{i['type']}] {i.get('content', 'No content')[:80]}...")
            print(f"      concept_id: {i.get('concept_id')}")
        print()
    
    await neo4j_client.close()

if __name__ == "__main__":
    asyncio.run(test_prereq_insights())
