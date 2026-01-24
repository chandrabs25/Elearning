"""UI Schema generator for dynamic frontend rendering."""
from typing import Literal
from pydantic import BaseModel


LayoutMode = Literal["focus", "split", "compare", "stack", "dynamic"]
PanelRole = Literal["primary", "secondary", "auxiliary"]
PanelWidth = Literal["auto", "narrow", "wide", "25%", "33%", "50%", "75%"]


class PanelContent(BaseModel):
    """Content for a single panel."""
    type: str  # Component type: WelcomeCard, ExplanationPanel, etc.
    props: dict = {}
    pinned: bool = False
    animation: str = "fadeIn"  # Animation preset
    role: PanelRole = "primary"  # Determines width allocation
    width: PanelWidth | None = None  # Explicit width override


class ProgressData(BaseModel):
    """Progress data for header display."""
    lifetime_mastery: float = 0
    current_section_id: str | None = None
    current_section_mastery: float = 0
    sections_progress: list[dict] = []


class CelebrationData(BaseModel):
    """Data for celebration modal."""
    show: bool = False
    section_title: str = ""
    mastery_percent: float = 0
    next_section_id: str | None = None
    next_section_title: str | None = None


class UISchema(BaseModel):
    """Complete UI schema for frontend rendering."""
    layout: LayoutMode
    panels: list[PanelContent]
    input_placeholder: str = "Talk to me..."
    next_prompt: str | None = None  # Suggested follow-up text
    progress: ProgressData | None = None  # Progress bar data
    celebration: CelebrationData | None = None  # Celebration modal data
    suggested_actions: list[dict] = []  # Action buttons: [{"label": "Quiz Me", "action": "quiz", "primary": True}]


def welcome_schema(user_name: str = None, last_section: dict = None) -> UISchema:
    """Generate welcome screen schema."""
    props = {
        "title": "Gravitation",
        "subtitle": "Class 11 NCERT Physics — Chapter 7",
        "topics": [
            {"id": "7.1", "title": "Introduction"},
            {"id": "7.2", "title": "Kepler's Laws"},
            {"id": "7.3", "title": "Universal Law of Gravitation"}
        ]
    }
    
    # Add last section if user has history
    if last_section:
        props["lastSection"] = last_section
    
    return UISchema(
        layout="focus",
        panels=[
            PanelContent(
                type="WelcomeCard",
                props=props,
                animation="fadeIn"
            )
        ],
        input_placeholder="Enter a command or select a topic to begin..."
    )


def explanation_schema(
    title: str,
    content: list[dict],
    related_sections: list[dict] = None,
    all_sections: list[dict] = None,
    current_section_id: str = None,
    show_related: bool = True,
    progress: ProgressData = None
) -> UISchema:
    """Generate teaching/explanation schema."""
    panels = [
        PanelContent(
            type="ExplanationPanel",
            props={
                "title": title,
                "content": content,
                "animated": True
            },
            animation="slideInLeft",
            role="primary"  # Takes remaining space (75% when with auxiliary)
        )
    ]
    
    # Use all_sections if provided, otherwise fall back to related_sections
    nav_sections = all_sections if all_sections else related_sections
    
    if show_related and nav_sections:
        # Mark related sections
        if related_sections and all_sections:
            related_ids = {s["id"]: s.get("relation") for s in related_sections}
            for section in nav_sections:
                if section["id"] in related_ids:
                    section["relation"] = related_ids[section["id"]]
        
        panels.append(
            PanelContent(
                type="NavigationMap",
                props={
                    "sections": nav_sections,
                    "title": "Chapter Sections",
                    "currentSectionId": current_section_id
                },
                animation="slideInRight",
                role="auxiliary",  # Fixed 25% width
                width="25%"
            )
        )
        return UISchema(layout="dynamic", panels=panels, progress=progress)
    
    return UISchema(layout="focus", panels=panels, progress=progress)


def explanation_with_exercises_schema(
    title: str,
    content: list[dict],
    section_id: str,
    exercises: list[dict],
    related_sections: list[dict] = None,
    completed_exercises: list[str] = None,
    progress: ProgressData = None
) -> UISchema:
    """Generate explanation schema with exercises panel."""
    panels = [
        PanelContent(
            type="ExplanationPanel",
            props={
                "title": title,
                "content": content,
                "animated": True
            },
            animation="slideInLeft",
            role="primary"
        ),
        PanelContent(
            type="ExercisePanel",
            props={
                "title": "Practice Exercises",
                "sectionId": section_id,
                "sectionTitle": title,
                "exercises": exercises,
                "completedExercises": completed_exercises or [],
                "bonusAvailable": True
            },
            animation="slideInRight",
            role="primary"
        )
    ]
    
    if related_sections:
        panels.append(
            PanelContent(
                type="NavigationMap",
                props={
                    "sections": related_sections,
                    "title": "Related Topics"
                },
                animation="slideInRight",
                role="auxiliary",
                width="20%"
            )
        )
    
    return UISchema(
        layout="dynamic", 
        panels=panels, 
        progress=progress,
        input_placeholder="Solve exercises or ask questions..."
    )


def celebration_schema(
    section_title: str,
    mastery_percent: float,
    next_section_id: str = None,
    next_section_title: str = None,
    progress: ProgressData = None
) -> CelebrationData:
    """Generate celebration modal data."""
    return CelebrationData(
        show=True,
        section_title=section_title,
        mastery_percent=mastery_percent,
        next_section_id=next_section_id,
        next_section_title=next_section_title
    )


def quiz_schema(question: str, concept_id: str, question_type: str = "open") -> UISchema:
    """Generate quiz/assessment schema."""
    return UISchema(
        layout="focus",
        panels=[
            PanelContent(
                type="QuizCard",
                props={
                    "question": question,
                    "concept_id": concept_id,
                    "type": question_type,
                    "glow": True
                },
                animation="pulseIn"
            )
        ],
        input_placeholder="Type your answer...",
        next_prompt="Take your time. Think through the problem."
    )


def mcq_schema(question: str, options: list[str], concept_id: str) -> UISchema:
    """Generate MCQ/Multiple Choice schema."""
    return UISchema(
        layout="focus",
        panels=[
            PanelContent(
                type="MCQCard",
                props={
                    "question": question,
                    "options": options,
                    "concept_id": concept_id,
                    "glow": True
                },
                animation="slideInUp"
            )
        ],
        input_placeholder="Select the correct option...",
        next_prompt="Choose the best answer."
    )


def feedback_schema(
    message: str,
    status: str,  # "success", "error", "warning", "info"
    mastery_change: int = None,
    new_mastery: int = None,
    actions: list[dict] = None
) -> UISchema:
    """Generate feedback card schema after answer evaluation."""
    props = {
        "message": message,
        "status": status
    }
    
    if mastery_change is not None:
        props["masteryChange"] = mastery_change
    if new_mastery is not None:
        props["newMastery"] = new_mastery
    if actions:
        props["actions"] = actions
    
    return UISchema(
        layout="focus",
        panels=[
            PanelContent(
                type="FeedbackCard",
                props=props,
                animation="popIn" if status == "success" else "fadeIn"
            )
        ]
    )


def split_with_derivation(
    main_content: dict,
    derivation: dict,
    main_pinned: bool = False
) -> UISchema:
    """Generate split view with derivation panel."""
    return UISchema(
        layout="split",
        panels=[
            PanelContent(
                type="ExplanationPanel",
                props=main_content,
                pinned=main_pinned,
                animation="slideInLeft" if not main_pinned else "none"
            ),
            PanelContent(
                type="DerivationBlock",
                props=derivation,
                animation="slideInRight"
            )
        ]
    )


def compare_schema(original: dict, new_content: dict) -> UISchema:
    """Generate comparison view (e.g., for prerequisite doubt)."""
    return UISchema(
        layout="compare",
        panels=[
            PanelContent(
                type="PinnedPreview",
                props={**original, "minimized": True},
                pinned=True,
                animation="shrinkLeft"
            ),
            PanelContent(
                type="ExplanationPanel",
                props=new_content,
                animation="expandRight"
            )
        ]
    )


def summary_schema(mastery_data: list, weak_areas: list) -> UISchema:
    """Generate progress summary schema."""
    return UISchema(
        layout="focus",
        panels=[
            PanelContent(
                type="SummaryCard",
                props={
                    "mastery": mastery_data,
                    "weak_areas": weak_areas,
                    "title": "Your Progress"
                },
                animation="fadeIn"
            )
        ]
    )


def multi_panel_schema(
    existing_panels: list[dict],
    new_content: dict,
    new_title: str,
    related_sections: list[dict] = None
) -> UISchema:
    """
    Generate a multi-panel layout by adding new content to existing panels.
    All primary panels share remaining space after auxiliary panels (25% each).
    """
    panels = []
    
    # Rebuild existing panels as primary
    for ep in existing_panels:
        panels.append(
            PanelContent(
                type=ep.get("type", "ExplanationPanel"),
                props=ep.get("props", {}),
                pinned=ep.get("pinned", False),
                animation="shrinkLeft",  # Shrink to make room
                role="primary"
            )
        )
    
    # Add new content panel as primary
    panels.append(
        PanelContent(
            type="ExplanationPanel",
            props={
                "title": new_title,
                "content": new_content,
                "animated": True
            },
            animation="expandRight",
            role="primary"
        )
    )
    
    # Add related topics if provided (as auxiliary - 25%)
    if related_sections:
        panels.append(
            PanelContent(
                type="NavigationMap",
                props={
                    "sections": related_sections,
                    "title": "Related Topics"
                },
                animation="slideInRight",
                role="auxiliary",
                width="25%"
            )
        )
    
    return UISchema(
        layout="dynamic",
        panels=panels,
        input_placeholder="Ask more or say 'focus on' to go back to single view...",
        next_prompt="You can add more content or 'focus' to return to single view"
    )


def chat_panel_schema(
    existing_panels: list[PanelContent],
    current_context: dict = None,
    initial_message: str = None
) -> UISchema:
    """
    Generate a layout with ChatPanel added to existing content.
    ChatPanel allows contextual Q&A while keeping the main content visible.
    """
    panels = list(existing_panels)  # Copy existing panels
    
    # Add chat panel as primary (shares space with other primary panels)
    chat_props = {
        "context": current_context or {},
        "messages": [],
        "placeholder": "Ask me anything..."
    }
    
    if initial_message:
        chat_props["messages"] = [{
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": f"I'm here to help! You asked: \"{initial_message}\". What would you like to know?"
            }]
        }]
    
    panels.append(
        PanelContent(
            type="ChatPanel",
            props=chat_props,
            animation="slideInRight",
            role="primary"
        )
    )
    
    return UISchema(
        layout="dynamic",
        panels=panels,
        input_placeholder="Ask your question... (Tab to switch focus)",
        next_prompt="Chat panel open. Press Tab to switch between panels."
    )


def exercise_only_schema(
    section_id: str,
    section_title: str,
    exercises: list[dict],
    completed_exercises: list[str] = None,
    progress: ProgressData = None
) -> UISchema:
    """Generate exercise-only view for practice."""
    return UISchema(
        layout="focus",
        panels=[
            PanelContent(
                type="ExercisePanel",
                props={
                    "title": f"Exercises: {section_title}",
                    "sectionId": section_id,
                    "sectionTitle": section_title,
                    "exercises": exercises,
                    "completedExercises": completed_exercises or [],
                    "bonusAvailable": True
                },
                animation="fadeIn",
                role="primary"
            )
        ],
        progress=progress,
        input_placeholder="Describe your approach to solving the problem..."
    )
