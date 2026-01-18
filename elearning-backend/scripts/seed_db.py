import os
import re
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Neo4j Configuration
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

CYPHER_FILE_PATH = "../elearning-platform/src/data/graph/seed-data.cypher"

def read_cypher_file(file_path):
    """Reads the Cypher file and splits it into individual statements."""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            
        # Split by double newlines to separate blocks (simple heuristic for this specific file)
        # Filter out empty strings and comment-only blocks
        statements = [
            s.strip() for s in content.split('\n\n') 
            if s.strip() and not s.strip().startswith('//')
        ]
        return statements
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        exit(1)

def seed_database():
    print(f"Connecting to Neo4j at {URI}...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    
    try:
        # Verify connection
        driver.verify_connectivity()
        print("Connected successfully.")
        
        # Read Cypher file
        with open(CYPHER_FILE_PATH, 'r') as f:
            cypher_query = f.read()

        print(f"Read {len(cypher_query)} bytes from Cypher file.")

        with driver.session() as session:
            # Clear existing data
            print("Cleaning database...")
            session.run("MATCH (n) DETACH DELETE n")
            
            # Execute the entire script as one transaction
            # We wrap it in a write transaction ensures atomic execution
            print("Executing Cypher script...")
            
            def execute_cypher(tx, query):
                tx.run(query)

            session.execute_write(execute_cypher, cypher_query)
            
        print("✅ Database seeded successfully!")
        
        # Verify counts
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN labels(n) as label, count(n) as count ORDER BY count DESC")
            print("Node counts:")
            for record in result:
                print(f"{record['label']}: {record['count']}")

    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        
    finally:
        driver.close()

if __name__ == "__main__":
    seed_database()
