"""Obsidian vault integration.

Jarvis writes every note as a Markdown file inside your Obsidian vault, sorted
into folders by category, and can search everything already in the vault
(including the Claude docs export). Set OBSIDIAN_VAULT_PATH in .env to turn it on.

    python -m tools.obsidian --import    # copy old data/notes.json notes into the vault
    python -m tools.obsidian --index     # rebuild the "Jarvis Home" index note
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

CATEGORY_FOLDERS = {
    "general": "Inbox",
    "ifa": "IFA",
    "business": "Business",
    "personal": "Personal",
    "reminder": "Reminders",
    "streaming": "Streaming",
}
SKIP_DIRS = {".obsidian", ".git", ".trash"}


def vault_root():
    path = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    return Path(path).expanduser() if path else None


def jarvis_dir():
    root = vault_root()
    if root is None:
        return None
    return root / os.environ.get("OBSIDIAN_JARVIS_FOLDER", "Jarvis")


def enabled():
    root = vault_root()
    return root is not None and root.is_dir()


def _slug(text, limit=60):
    first_line = text.strip().splitlines()[0] if text.strip() else "note"
    cleaned = re.sub(r'[\\/:*?"<>|#^\[\]]', "", first_line)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned[:limit].rstrip() or "note")


def write_note(content, category="general", created=None):
    """Write one note into the vault. Returns the note's path, or None if the vault is off."""
    if not enabled():
        return None
    created = created or datetime.now()
    category = category if category in CATEGORY_FOLDERS else "general"
    folder = jarvis_dir() / CATEGORY_FOLDERS[category]
    folder.mkdir(parents=True, exist_ok=True)

    base = f"{created:%Y-%m-%d %H%M} {_slug(content)}"
    path = folder / f"{base}.md"
    n = 2
    while path.exists():
        path = folder / f"{base} ({n}).md"
        n += 1

    tags = ["jarvis", category] + (["todo"] if category == "reminder" else [])
    path.write_text(
        "---\n"
        f"created: {created.isoformat(timespec='seconds')}\n"
        f"category: {category}\n"
        f"tags: [{', '.join(tags)}]\n"
        "---\n\n"
        f"{content.strip()}\n",
        encoding="utf-8",
    )
    _link_in_daily(path, created)
    return path


def _link_in_daily(note_path, created):
    daily = jarvis_dir() / "Daily" / f"{created:%Y-%m-%d}.md"
    daily.parent.mkdir(parents=True, exist_ok=True)
    if not daily.exists():
        daily.write_text(f"# {created:%A, %B %d, %Y}\n\n", encoding="utf-8")
    with open(daily, "a", encoding="utf-8") as f:
        f.write(f"- {created:%H:%M} [[{note_path.stem}]]\n")


def _vault_files():
    root = vault_root()
    for path in root.rglob("*.md"):
        if not SKIP_DIRS.intersection(path.relative_to(root).parts):
            yield path


def search_vault(query, limit=5):
    if not enabled():
        return "Obsidian vault isn't connected. Set OBSIDIAN_VAULT_PATH in .env."
    words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    if not words:
        return "Give me a word or two to search for."
    scored = []
    for path in _vault_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lower = text.lower()
        title = path.stem.lower()
        score = sum(lower.count(w) + 5 * title.count(w) for w in words)
        if score:
            scored.append((score, path, text))
    if not scored:
        return f"Nothing in the vault matches '{query}'."
    scored.sort(key=lambda s: -s[0])
    out = []
    for _, path, text in scored[:limit]:
        idx = min((text.lower().find(w) for w in words if w in text.lower()), default=0)
        start = max(0, idx - 150)
        snippet = re.sub(r"\s+", " ", text[start:start + 450]).strip()
        out.append(f"## {path.stem}\n({path.relative_to(vault_root())})\n…{snippet}…")
    return "\n\n".join(out)


def read_vault_note(title, max_chars=12000):
    if not enabled():
        return "Obsidian vault isn't connected. Set OBSIDIAN_VAULT_PATH in .env."
    wanted = title.lower().removesuffix(".md").strip()
    matches = [p for p in _vault_files() if p.stem.lower() == wanted]
    if not matches:
        matches = [p for p in _vault_files() if wanted in p.stem.lower()]
    if not matches:
        return f"No note called '{title}'. Try search_vault first."
    path = matches[0]
    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[cut off at {max_chars} characters]"
    return f"# {path.stem}\n\n{text}"


def rebuild_index():
    """Rewrite '<Jarvis folder>/Jarvis Home.md' so it links every note, grouped by folder."""
    if not enabled():
        return "Obsidian vault isn't connected. Set OBSIDIAN_VAULT_PATH in .env."
    home_dir = jarvis_dir()
    home_dir.mkdir(parents=True, exist_ok=True)
    groups = {}
    for path in _vault_files():
        rel = path.relative_to(home_dir) if home_dir in path.parents else None
        if rel is None or path.name == "Jarvis Home.md":
            continue
        folder = rel.parts[0] if len(rel.parts) > 1 else "Top level"
        groups.setdefault(folder, []).append(path.stem)

    lines = ["# Jarvis Home", "", f"Rebuilt {datetime.now():%Y-%m-%d %H:%M}. Every note Jarvis knows about, by folder.", ""]
    order = ["Top level", "Inbox", "Reminders", "Streaming", "Business", "Personal", "IFA", "Claude Docs", "Daily"]
    for folder in order + sorted(set(groups) - set(order)):
        if folder not in groups:
            continue
        names = sorted(groups[folder], reverse=(folder == "Daily"))
        lines.append(f"## {folder} ({len(names)})")
        lines += [f"- [[{n}]]" for n in names]
        lines.append("")
    (home_dir / "Jarvis Home.md").write_text("\n".join(lines), encoding="utf-8")
    return f"Index rebuilt: {sum(len(v) for v in groups.values())} notes in {len(groups)} folders."


def import_json_notes(json_path):
    """Copy notes from Jarvis's old notes.json into the vault. Safe to run once."""
    if not enabled():
        return "Obsidian vault isn't connected. Set OBSIDIAN_VAULT_PATH in .env."
    json_path = Path(json_path)
    if not json_path.exists():
        return f"No notes file at {json_path}."
    notes = json.loads(json_path.read_text(encoding="utf-8"))
    for n in notes:
        try:
            created = datetime.fromisoformat(n.get("created", ""))
        except ValueError:
            created = datetime.now()
        write_note(n["content"], n.get("category", "general"), created)
    return f"Imported {len(notes)} notes into {jarvis_dir()}."


def register_obsidian_tools(registry):
    registry.register(
        name="search_vault",
        description=(
            "Search the user's Obsidian vault: their notes plus every Claude doc they exported "
            "(Crunch plans, content plans, RichyRich.TV, IFA study guide, resumes, life plans). "
            "Use this before answering questions about their plans, past work or anything they "
            "say 'I already have' or 'you should know'. Returns the best-matching notes with snippets."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to look for."},
                "limit": {"type": "integer", "description": "Max notes to return. Default 5."},
            },
            "required": ["query"],
        },
        fn=search_vault,
    )
    registry.register(
        name="read_vault_note",
        description="Read one note from the Obsidian vault in full, by its title (from search_vault).",
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string", "description": "The note's title."}},
            "required": ["title"],
        },
        fn=read_vault_note,
    )
    registry.register(
        name="organize_vault",
        description=(
            "Rebuild the 'Jarvis Home' index note in Obsidian so it links every note by folder. "
            "Use when the user asks to organize or tidy their Obsidian notes."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        fn=rebuild_index,
    )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    if "--import" in sys.argv:
        data_dir = Path(os.environ.get("JARVIS_DATA_DIR", "."))
        print(import_json_notes(data_dir / "data" / "notes.json"))
    if "--index" in sys.argv or "--import" in sys.argv:
        print(rebuild_index())
    if not {"--import", "--index"} & set(sys.argv):
        print(__doc__)
