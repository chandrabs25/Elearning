from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
from app.graph.client import neo4j_client

router = APIRouter()

class NextStepRequest(BaseModel):
    user_id: str
    concept_id: str | None = None

class Component(BaseModel):
    type: str
    props: dict = {}

class UIResponse(BaseModel):
    schema_version: str = "1.0"
    components: list[Component]

GRAVITY_JSON_PATH = "../elearning-platform/src/data/chapters/gravity.json"

def get_gravity_content():
    try:
        with open(GRAVITY_JSON_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback for dev environment if paths differ
        if os.path.exists("gravity.json"):
             with open("gravity.json", "r") as f:
                return json.load(f)
        raise HTTPException(status_code=500, detail="Content file not found")

@router.post("/tutor/next", response_model=UIResponse)
async def next_step(req: NextStepRequest):
    # 1. Get Concept Metadata from Graph
    # If concept_id is provided, use it. Otherwise find the first one or user's current one.
    query = ""
    params = {}
    
    if req.concept_id:
        query = """
        MATCH (c:Concept {id: $id})
        RETURN c
        """
        params = {"id": req.concept_id}
    else:
        # Default to first concept in Chapter 7
        query = """
        MATCH (c:Concept {id: "7.1"})
        RETURN c
        """
    
    results = await neo4j_client.execute_read(query, **params)
    if not results:
         raise HTTPException(status_code=404, detail="Concept not found")
    
    concept = results[0]["c"]
    section_id = concept.get("sectionId", "7.1")
    
    # 2. Get Content from JSON
    data = get_gravity_content()
    sections = data.get("sections", [])
    
    target_section = next((s for s in sections if s["section_id"] == section_id), None)
    
    if not target_section:
        # Fallback if section not found in JSON (e.g. exercises)
        return UIResponse(components=[
            Component(type="h1", props={"children": concept.get("title")}),
            Component(type="p", props={"children": "Content coming soon..."})
        ])

    # 3. Transform Content to UI Schema
    components = []
    
    # Title
    components.append(Component(type="h1", props={"children": target_section.get("section_title")}))
    
    # Body Content
    for item in target_section.get("content", []):
        if item["type"] == "text":
            components.append(Component(type="p", props={"children": item["body"]}))
        elif item["type"] == "list_item":
             components.append(Component(type="li", props={"children": f"{item.get('label', '')} {item.get('body', '')}"}))
        elif item["type"] == "diagram":
             components.append(Component(type="diagram", props={
                 "figure": item.get("figure_number"),
                 "caption": item.get("meta")
             }))
        elif item["type"] == "derivation":
             components.append(Component(type="latex", props={"content": item.get("latex")}))
    
    return UIResponse(components=components)
