"""Content loader for retrieving rich media from gravity.json."""
import json
import os
from pathlib import Path
from functools import lru_cache

# Path to gravity.json (assuming it's in the project root or accessible)
# Converting relative path to absolute for stability
GRAVITY_JSON_PATH = Path(os.getcwd()).parent / "gravity.json"

class ContentLoader:
    def __init__(self):
        self._data = None
        self._section_map = {}
        self._load_data()

    def _load_data(self):
        """Load and index gravity.json."""
        try:
            # Fallback paths if not found
            if not GRAVITY_JSON_PATH.exists():
                print(f"Warning: gravity.json not found at {GRAVITY_JSON_PATH}")
                return

            with open(GRAVITY_JSON_PATH, "r") as f:
                self._data = json.load(f)

            # Index sections by ID for O(1) lookup
            for section in self._data.get("sections", []):
                self._section_map[section["section_id"]] = section

        except Exception as e:
            print(f"Error loading gravity.json: {e}")

    def get_section_content(self, section_id: str) -> dict | None:
        """Get full content for a section."""
        return self._section_map.get(section_id)

    def get_toc(self) -> list[dict]:
        """Get the table of contents."""
        return self._data.get("table_of_contents", []) if self._data else []

    def get_visuals(self, section_id: str) -> list[dict]:
        """Get visual elements, or fallback to text content if none exist."""
        section = self.get_section_content(section_id)
        if not section:
            return []

        visuals = []
        # First pass: Look for rich visuals
        for item in section.get("content", []):
            if item["type"] in ["diagram", "table", "derivation"]:
                 visuals.append(item)
        
        # Fallback: If no visuals, return text blocks as "text_content"
        # This allows the UI to fill the space dynamically instead of showing "No visuals"
        if not visuals:
            for item in section.get("content", []):
                if item["type"] in ["text", "list_item"]:
                    visuals.append({
                        "type": "text_block",
                        "body": item["body"],
                        "label": item.get("label") # for list items
                    })
        
        # Always add the section title as the first element
        visuals.insert(0, {
            "type": "section_header",
            "title": section.get("section_title", "").title() # Convert "INTRODUCTION" to "Introduction"
        })
        
        return visuals

# Global instance
content_loader = ContentLoader()

def get_content_loader():
    return content_loader
