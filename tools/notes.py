import json
import os
from pathlib import Path
from datetime import datetime

_NOTES_PATH = Path(os.environ.get("JARVIS_DATA_DIR", ".")) / "data" / "notes.json"


def _load():
    if not _NOTES_PATH.exists():
        return []
    with open(_NOTES_PATH) as f:
        return json.load(f)


def _save(notes):
    _NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_NOTES_PATH, "w") as f:
        json.dump(notes, f, indent=2)


def save_note(content, category="general"):
    notes = _load()
    note = {
        "id": len(notes) + 1,
        "content": content,
        "category": category,
        "created": datetime.now().isoformat(),
    }
    notes.append(note)
    _save(notes)
    return f"Saved [{category}]: {content}"


def get_notes(category=None, limit=10):
    notes = _load()
    if category:
        notes = [n for n in notes if n.get("category") == category]
    notes = notes[-limit:]
    if not notes:
        return "No notes found."
    lines = []
    for n in notes:
        date = n["created"][:10]
        lines.append(f"[{n['id']}] ({date}) [{n['category']}] {n['content']}")
    return "\n".join(lines)


def register_notes_tools(registry):
    registry.register(
        name="save_note",
        description=(
            "Save a note, reminder, idea, or piece of information for later retrieval. "
            "Use this when the user wants to remember something, capture an idea, log a task, "
            "or set a reminder. Categories: 'general', 'ifa', 'business', 'personal', 'reminder'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The note content to save."},
                "category": {
                    "type": "string",
                    "enum": ["general", "ifa", "business", "personal", "reminder"],
                    "description": "Category for the note. Default: 'general'.",
                },
            },
            "required": ["content"],
        },
        fn=save_note,
    )

    registry.register(
        name="get_notes",
        description=(
            "Retrieve saved notes and reminders. Use when the user asks what they've noted, "
            "wants to review ideas or tasks, or asks about saved reminders. "
            "Can filter by category. Returns the most recent entries first."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["general", "ifa", "business", "personal", "reminder"],
                    "description": "Filter by category. Omit to get all notes.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max notes to return. Default: 10.",
                },
            },
            "required": [],
        },
        fn=get_notes,
    )
