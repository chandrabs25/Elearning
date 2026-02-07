import asyncio
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph.client import neo4j_client

async def check_data():
    print("🔍 Checking database state...")
    
    # Verify connection first
    await neo4j_client.verify_connectivity()
    
    queries = {
        "Users": "MATCH (n:User) RETURN count(n) as count",
        "Insights (Misconceptions etc)": "MATCH (n:Insight) RETURN count(n) as count",
        "Chat Messages": "MATCH (n:ChatMessage) RETURN count(n) as count",
        "Taught Concepts (explained=true)": "MATCH ()-[r:MASTERY {completed: true}]->() RETURN count(r) as count", # Mastery completed is closest to 'verified'
        "Explained Concepts (via user state)": "MATCH (u:User) RETURN size(keys(u.tutor_states)) as count" # State tracking
    }
    
    # Also check specifically for Misconception type insights
    queries["Misconception Insights"] = "MATCH (n:Insight {type: 'MISCONCEPTION'}) RETURN count(n) as count"
    
    try:
        results = {}
        for label, q in queries.items():
            res = await neo4j_client.execute_read(q)
            count = res[0]["count"] if res else 0
            results[label] = count
            print(f"{label}: {count}")
            
        print("\n✅ Check complete.")
        
    except Exception as e:
        print(f"❌ Error checking data: {e}")
    finally:
        await neo4j_client.close()

if __name__ == "__main__":
    asyncio.run(check_data())
