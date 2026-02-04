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
    
    # Extract ALL content types from content array
    content_items = section.get("content", [])
    text_parts = []
    for item in content_items:
        item_type = item.get("type", "")
        
        if item_type == "text" and item.get("body"):
            text_parts.append(item["body"])
        
        elif item_type == "list_item":
            # IMPORTANT: This captures laws like "1. Law of orbits"
            label = item.get("label", "")
            body = item.get("body", "")
            text_parts.append(f"**{label}**: {body}")
        
        elif item_type == "derivation" and item.get("meta"):
            text_parts.append(f"[Derivation: {item['meta']}]")
        
        elif item_type == "example_box":
            label = item.get("label", "")
            question = item.get("question", "")
            text_parts.append(f"[{label}: {question[:200]}]")
    
    # Increased limit to capture more content
    text = "\n\n".join(text_parts)[:8000]
    
    # Skip non-chapter sections
    if not section_id.startswith("7.") or section_id in ["Summary", "Points to ponder", "Exercises"]:
        print(f"  Skipping non-chapter section: {section_id}")
        return []
    
    prompt = f"""Analyze this physics section and identify the KEY LAWS, PRINCIPLES, or CONCEPTS that should be taught as separate units.

Section: {title} (ID: {section_id})

Full Content:
{text}

CRITICAL INSTRUCTIONS:
1. If the section contains NAMED LAWS (e.g., "Law of orbits", "First Law", "Second Law"), EACH LAW must be a separate subconcept
2. If there are numbered principles or rules, extract each one individually
3. Focus on the PRIMARY educational content, not supporting explanations or illustrations
4. Titles should be concise and reflect the actual law/concept name from the content
5. Extract 2-6 subconcepts based on the actual structure of the content

Return ONLY a valid JSON array (no markdown):
[
  {{"title": "Concise Title", "description": "One-sentence explanation of what this covers"}},
  ...
]"""

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
        
        # Add IDs and parent reference
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
    """Store subconcepts in Neo4j as Concept nodes with sequential relationships."""
    
    async with driver.session() as session:
        # First, create all subconcept nodes
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
        
        # Group subconcepts by parent section and create NEXT_SUBCONCEPT relationships
        print("\n🔗 Creating NEXT_SUBCONCEPT relationships...")
        sections = {}
        for sc in subconcepts:
            parent = sc["parent_section_id"]
            if parent not in sections:
                sections[parent] = []
            sections[parent].append(sc)
        
        for section_id, section_subconcepts in sections.items():
            # Sort by ID to ensure correct order
            section_subconcepts.sort(key=lambda x: x["id"])
            
            for i in range(len(section_subconcepts) - 1):
                from_id = section_subconcepts[i]["id"]
                to_id = section_subconcepts[i + 1]["id"]
                
                try:
                    await session.run("""
                        MATCH (a:Concept {id: $from_id})
                        MATCH (b:Concept {id: $to_id})
                        MERGE (a)-[:NEXT_SUBCONCEPT]->(b)
                    """, from_id=from_id, to_id=to_id)
                    print(f"    ✓ {from_id} -> {to_id}")
                except Exception as e:
                    print(f"    ✗ Error linking {from_id} -> {to_id}: {e}")




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
