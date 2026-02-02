#!/usr/bin/env python3
"""
Generate subconcepts for each section in gravity.json using Google Gemini.
Store subconcepts in Neo4j as Concept nodes with hierarchical IDs (e.g., 7.2.1, 7.2.2).
"""

import json
import os
import asyncio
import time
import google.generativeai as genai
from neo4j import AsyncGraphDatabase

# Configuration - load from environment or use defaults
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://1f4cce0a.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Path to gravity.json
GRAVITY_JSON_PATH = os.path.join(os.path.dirname(__file__), "gravity.json")


def generate_subconcepts_for_section(model, section: dict) -> list[dict]:
    """Use Gemini to identify subconcepts within a section."""
    
    section_id = section.get("section_id", "")
    title = section.get("section_title", "")
    
    # Extract text from content array
    content_items = section.get("content", [])
    text_parts = []
    for item in content_items:
        if item.get("type") == "text" and item.get("body"):
            text_parts.append(item["body"])
    text = "\n\n".join(text_parts)[:4000]  # Limit for prompt size
    
    # Skip non-chapter sections
    if not section_id.startswith("7.") or section_id in ["Summary", "Points to ponder", "Exercises"]:
        print(f"  Skipping non-chapter section: {section_id}")
        return []
    
    prompt = f"""Analyze this physics section and identify 2-5 distinct key concepts that should be taught separately.

Section: {title} (ID: {section_id})
Content:
{text}

For each concept, provide:
1. A short, clear title (max 10 words)
2. A one-sentence description of what it covers

Return ONLY a valid JSON array in this exact format (no markdown, no explanation):
[
  {{"title": "Concept Title", "description": "What this concept covers"}},
  {{"title": "Another Concept", "description": "What this covers"}}
]

Important:
- Extract 2-5 concepts from the actual content provided
- Make titles concise and specific
- Ensure descriptions are one sentence each
- Return ONLY the JSON array, nothing else"""

    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        
        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        subconcepts = json.loads(content)
        
        # Add IDs
        for i, sc in enumerate(subconcepts):
            sc["id"] = f"{section_id}.{i + 1}"
            sc["parent_section_id"] = section_id
        
        return subconcepts
        
    except json.JSONDecodeError as e:
        print(f"  JSON parse error for {section_id}: {e}")
        print(f"  Raw response: {content[:200]}...")
        return []
    except Exception as e:
        print(f"  Error generating subconcepts for {section_id}: {e}")
        return []


async def store_subconcepts_in_neo4j(driver, subconcepts: list[dict]):
    """Store subconcepts in Neo4j as Concept nodes."""
    
    async with driver.session() as session:
        for sc in subconcepts:
            query = """
            MERGE (c:Concept {id: $id})
            SET c.title = $title,
                c.description = $description,
                c.type = 'subconcept',
                c.parent_section_id = $parent_section_id,
                c.created_at = datetime()
            
            WITH c
            MATCH (parent:Concept {id: $parent_section_id})
            MERGE (parent)-[:HAS_SUBCONCEPT]->(c)
            
            RETURN c.id as id
            """
            
            try:
                result = await session.run(
                    query,
                    id=sc["id"],
                    title=sc["title"],
                    description=sc.get("description", ""),
                    parent_section_id=sc["parent_section_id"]
                )
                await result.consume()
                print(f"    ✓ Stored: {sc['id']} - {sc['title']}")
            except Exception as e:
                print(f"    ✗ Error storing {sc['id']}: {e}")


async def main():
    print("=" * 60)
    print("Subconcept Generation Script (using Google Gemini)")
    print("=" * 60)
    
    # Validate environment
    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_API_KEY not set. Please set it in environment.")
        return
    
    if not NEO4J_PASSWORD:
        print("ERROR: NEO4J_PASSWORD not set. Please set it in environment.")
        return
    
    # Configure Gemini
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Load gravity.json
    print(f"\n📖 Loading sections from: {GRAVITY_JSON_PATH}")
    with open(GRAVITY_JSON_PATH, "r") as f:
        data = json.load(f)
    
    sections = data.get("sections", [])
    print(f"   Found {len(sections)} sections")
    
    # Initialize Neo4j
    print("\n🔌 Connecting to Neo4j...")
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    all_subconcepts = []
    
    # Process each section
    print("\n🧠 Generating subconcepts with Gemini...")
    for section in sections:
        section_id = section.get("section_id", "")
        title = section.get("section_title", "")
        
        # Skip non-numeric sections
        if not section_id or not section_id[0].isdigit():
            continue
            
        print(f"\n[{section_id}] {title}")
        subconcepts = generate_subconcepts_for_section(model, section)
        
        if subconcepts:
            print(f"   Generated {len(subconcepts)} subconcepts:")
            for sc in subconcepts:
                print(f"   - {sc['id']}: {sc['title']}")
            all_subconcepts.extend(subconcepts)
        
        # Wait 5 seconds before next API call to avoid rate limits
        print("   Waiting 5 seconds before next request...")
        time.sleep(5)
    
    # Store in Neo4j
    print("\n\n💾 Storing subconcepts in Neo4j...")
    await store_subconcepts_in_neo4j(driver, all_subconcepts)
    
    # Save to JSON for reference
    output_path = os.path.join(os.path.dirname(__file__), "subconcepts.json")
    with open(output_path, "w") as f:
        json.dump(all_subconcepts, f, indent=2)
    print(f"\n📄 Also saved to: {output_path}")
    
    # Cleanup
    await driver.close()
    
    print("\n" + "=" * 60)
    print(f"✅ Done! Generated {len(all_subconcepts)} subconcepts total.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
