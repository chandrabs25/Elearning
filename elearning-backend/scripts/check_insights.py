import asyncio
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph.client import neo4j_client

async def check_insights():
    print("🔍 Checking insights for prerequisite 7.2...\n")
    
    # Verify connection first
    await neo4j_client.verify_connectivity()
    
    # Query 1: Check all insights in the database
    print("=== All Insights in Database ===")
    all_insights_query = """
    MATCH (u:User)-[:HAS_INSIGHT]->(i:Insight)-[:ABOUT]->(c:Concept)
    WHERE i.superseded_by IS NULL
    RETURN u.id as user_id, i.type as type, i.content as content, 
           c.id as concept_id, i.source_type as source_type
    ORDER BY c.id
    """
    results = await neo4j_client.execute_read(all_insights_query)
    if results:
        for r in results:
            print(f"  User: {r['user_id']}, Concept: {r['concept_id']}, Type: {r['type']}")
            print(f"    Content: {r['content'][:100] if r['content'] else 'None'}...")
            print(f"    Source: {r['source_type']}")
            print()
    else:
        print("  No insights found!")
    
    # Query 2: Check prerequisite insights for 7.9 specifically
    print("\n=== Prerequisites for 7.9 ===")
    prereq_query = """
    MATCH (c:Concept {id: "7.9"})-[:REQUIRES]->(prereq:Concept)
    RETURN prereq.id as id, prereq.title as title
    """
    prereqs = await neo4j_client.execute_read(prereq_query)
    for p in prereqs:
        print(f"  Prereq: {p['id']} - {p['title']}")
    
    # Query 3: Check insights ABOUT 7.2 or 7.2.* subconcepts
    print("\n=== Insights about 7.2 or subconcepts ===")
    insight_query = """
    MATCH (u:User)-[:HAS_INSIGHT]->(i:Insight)-[:ABOUT]->(c:Concept)
    WHERE i.superseded_by IS NULL
      AND (c.id = "7.2" OR c.id STARTS WITH "7.2.")
    RETURN u.id as user_id, i.type as type, i.content as content, 
           c.id as concept_id, i.source_type as source_type
    """
    results = await neo4j_client.execute_read(insight_query)
    if results:
        for r in results:
            print(f"  User: {r['user_id']}, Concept: {r['concept_id']}, Type: {r['type']}")
            print(f"    Content: {r['content'][:100] if r['content'] else 'None'}...")
    else:
        print("  No insights found for 7.2 or subconcepts!")
    
    await neo4j_client.close()

if __name__ == "__main__":
    asyncio.run(check_insights())
