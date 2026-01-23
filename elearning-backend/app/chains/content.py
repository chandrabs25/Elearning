"""Content retrieval from gravity.json and Neo4j."""
import json
import os
from functools import lru_cache


GRAVITY_JSON_PATH = "../elearning-platform/src/data/chapters/gravity.json"


@lru_cache(maxsize=1)
def load_gravity_content() -> dict:
    """Load and cache the gravity chapter content."""
    paths_to_try = [
        GRAVITY_JSON_PATH,
        "gravity.json",
        os.path.join(os.path.dirname(__file__), "../../data/gravity.json")
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    
    raise FileNotFoundError("gravity.json not found")


def get_section_by_id(section_id: str) -> dict | None:
    """Get a specific section by its ID."""
    data = load_gravity_content()
    for section in data.get("sections", []):
        if section.get("section_id") == section_id:
            return section
    return None


def get_table_of_contents() -> list:
    """Get the table of contents."""
    data = load_gravity_content()
    return data.get("table_of_contents", [])


def get_related_sections(section_id: str) -> list:
    """Get sections related to the given section (neighbors in TOC)."""
    toc = get_table_of_contents()
    current_idx = None
    
    for i, item in enumerate(toc):
        if item["id"] == section_id:
            current_idx = i
            break
    
    if current_idx is None:
        return []
    
    related = []
    # Previous section
    if current_idx > 0:
        related.append({**toc[current_idx - 1], "relation": "previous"})
    # Next section
    if current_idx < len(toc) - 1:
        related.append({**toc[current_idx + 1], "relation": "next"})
    
    return related


def search_sections_by_topic(query: str) -> list:
    """Search sections by keyword in title or content."""
    data = load_gravity_content()
    query_lower = query.lower()
    matches = []
    
    for section in data.get("sections", []):
        title = section.get("section_title", "").lower()
        if query_lower in title:
            matches.append({
                "id": section["section_id"],
                "title": section["section_title"],
                "match_type": "title"
            })
            continue
        
        # Search in content
        for item in section.get("content", []):
            if item.get("type") == "text" and query_lower in item.get("body", "").lower():
                matches.append({
                    "id": section["section_id"],
                    "title": section["section_title"],
                    "match_type": "content"
                })
                break
    
    return matches


def format_content_for_ui(section: dict) -> list:
    """Format section content for UI rendering."""
    formatted = []
    
    for item in section.get("content", []):
        item_type = item.get("type")
        
        if item_type == "text":
            formatted.append({
                "type": "paragraph",
                "content": item["body"]
            })
        elif item_type == "list_item":
            formatted.append({
                "type": "listItem",
                "label": item.get("label", ""),
                "content": item.get("body", "")
            })
        elif item_type == "derivation":
            formatted.append({
                "type": "latex",
                "content": item.get("latex", ""),
                "description": item.get("meta", "")
            })
        elif item_type == "diagram":
            formatted.append({
                "type": "diagram",
                "figure": item.get("figure_number", ""),
                "caption": item.get("meta", "")
            })
        elif item_type == "table":
            formatted.append({
                "type": "table",
                "title": item.get("title", ""),
                "headers": item.get("headers", []),
                "rows": item.get("rows", [])
            })
        elif item_type == "example_box":
            formatted.append({
                "type": "example",
                "label": item.get("label", ""),
                "question": item.get("question", ""),
                "solution": item.get("solution", {})
            })
    
    return formatted


def get_exercises_for_section(section_id: str) -> list:
    """Get exercises related to a section from Neo4j mapping."""
    # This would ideally query Neo4j for exercises linked to the concept
    # For now, return a sample based on section
    data = load_gravity_content()
    
    for section in data.get("sections", []):
        if section.get("section_id") == section_id:
            # Look for example_box items
            examples = []
            for item in section.get("content", []):
                if item.get("type") == "example_box":
                    examples.append({
                        "label": item.get("label"),
                        "question": item.get("question")
                    })
            return examples
    
    return []


def get_chapter_exercises() -> list:
    """Get all exercises from the Exercises section."""
    data = load_gravity_content()
    
    for section in data.get("sections", []):
        if section.get("section_id") == "EXERCISES":
            exercises = []
            for item in section.get("content", []):
                if item.get("type") == "exercise_item":
                    exercise = {
                        "label": item.get("label"),
                        "question": item.get("question"),
                        "body": item.get("body"),
                        "sub_questions": item.get("sub_questions", [])
                    }
                    exercises.append(exercise)
            return exercises
    return []


def get_exercises_by_section_mapping() -> dict:
    """
    Map chapter exercises to their related sections.
    Returns a dict where keys are section IDs and values are lists of exercises.
    """
    # Mapping of exercise numbers to related section IDs
    # Based on the content of the exercises
    exercise_section_map = {
        "7.1": ["7.1", "7.2", "7.3"],  # General questions about shielding, astronaut
        "7.2": ["7.5", "7.6"],          # Altitude and depth effects on g
        "7.3": ["7.2"],                  # Kepler's law - orbital size
        "7.4": ["7.2", "7.9"],           # Kepler's law - Jupiter's moons
        "7.5": ["7.2"],                  # Milky Way revolution
        "7.6": ["7.10"],                 # Satellite energy
        "7.7": ["7.8"],                  # Escape speed
        "7.8": ["7.10"],                 # Comet energy
        "7.9": ["7.9"],                  # Astronaut in space
        "7.10": ["7.3"],                 # Gravitational intensity
        "7.11": ["7.3"],                 # Gravitational intensity
        "7.12": ["7.3"],                 # Neutral point
        "7.13": ["7.4", "7.9"],          # Weighing the sun
        "7.14": ["7.2"],                 # Saturn orbital distance
        "7.15": ["7.6"],                 # Weight at height
        "7.16": ["7.6"],                 # Weight at depth
        "7.17": ["7.8"],                 # Rocket escape
        "7.18": ["7.8"],                 # Escape speed
        "7.19": ["7.9", "7.10"],         # Satellite energy
        "7.20": ["7.7", "7.8"],          # Two stars collision
        "7.21": ["7.3", "7.7"]           # Gravitational force and potential
    }
    
    # Invert the mapping: section_id -> [exercise_labels]
    section_exercises = {}
    for ex_label, sections in exercise_section_map.items():
        for section_id in sections:
            if section_id not in section_exercises:
                section_exercises[section_id] = []
            section_exercises[section_id].append(ex_label)
    
    return section_exercises


def get_related_exercises(section_id: str) -> list:
    """Get chapter exercises related to a specific section."""
    mapping = get_exercises_by_section_mapping()
    exercise_labels = mapping.get(section_id, [])
    
    if not exercise_labels:
        return []
    
    all_exercises = get_chapter_exercises()
    related = [ex for ex in all_exercises if ex["label"] in exercise_labels]
    return related


def get_example_with_solution(section_id: str, example_label: str) -> dict | None:
    """Get a specific example problem with its full solution."""
    section = get_section_by_id(section_id)
    if not section:
        return None
    
    for item in section.get("content", []):
        if item.get("type") == "example_box" and item.get("label") == example_label:
            return {
                "label": item.get("label"),
                "question": item.get("question"),
                "solution": item.get("solution")
            }
    return None


def get_exercise_with_solution(exercise_label: str) -> dict | None:
    """Get exercise item from EXERCISES section with its full solution."""
    data = load_gravity_content()
    
    for section in data.get("sections", []):
        if section.get("section_id") == "EXERCISES":
            for item in section.get("content", []):
                if item.get("type") == "exercise_item" and item.get("label") == exercise_label:
                    return {
                        "label": item.get("label"),
                        "question": item.get("question"),
                        "sub_questions": item.get("sub_questions", []),
                        "body": item.get("body"),
                        "solution": item.get("solution", "")
                    }
    return None


def get_next_section_id(current_section_id: str) -> str | None:
    """Get the next section ID in the table of contents."""
    toc = get_table_of_contents()
    
    for i, item in enumerate(toc):
        if item["id"] == current_section_id:
            if i + 1 < len(toc):
                next_item = toc[i + 1]
                # Skip non-learning sections
                if next_item["id"] not in ["Summary", "Points to ponder", "Exercises", "PHYSICAL_QUANTITIES_TABLE", "POINTS_TO_PONDER", "SUMMARY"]:
                    return next_item["id"]
                # Try to get the one after
                if i + 2 < len(toc):
                    return toc[i + 2]["id"]
            return None
    return None


def get_section_title(section_id: str) -> str | None:
    """Get the title of a section by ID."""
    toc = get_table_of_contents()
    for item in toc:
        if item["id"] == section_id:
            return item["title"]
    return None
