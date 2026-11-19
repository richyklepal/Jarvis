"""
Skills: Jarvis can use any SKILL.md workflow installed in .claude/skills/
(the same skills Claude Code uses in this repo, e.g. the 30 SEO skills).

list_skills shows name + one-line description; load_skill returns the full
instructions so Jarvis can follow them mid-conversation.
"""
import re
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / ".claude" / "skills"


def _parse(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    front = m.group(1) if m else ""
    name = re.search(r"^name:\s*(.+)$", front, re.M)
    # description may be a folded block (>-) spanning indented lines
    desc = re.search(r"^description:\s*(?:>-?|\|)?\s*\n?((?:.+\n?)(?:^[ \t]+.+\n?)*)", front, re.M)
    description = " ".join(desc.group(1).split()).strip('"\'') if desc else ""
    return (name.group(1).strip() if name else path.parent.name), description, text


def _all():
    if not SKILLS_DIR.exists():
        return {}
    out = {}
    for p in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        name, desc, text = _parse(p)
        out[name] = (desc, text, p.parent)
    return out


def list_skills(query: str = ""):
    skills = _all()
    if not skills:
        return "No skills installed. Run scripts/install_skills.sh."
    q = query.lower().split()
    rows = [
        f"- **{n}** — {d[:220]}"
        for n, (d, _, _) in skills.items()
        if not q or all(t in (n + " " + d).lower() for t in q)
    ]
    return "\n".join(rows) or f"No skills match '{query}'."


def load_skill(name: str):
    skills = _all()
    hit = skills.get(name) or next((v for k, v in skills.items() if k.lower() == name.lower()), None)
    if not hit:
        return f"No skill named '{name}'. Use list_skills to see what's installed."
    _, text, folder = hit
    extras = [str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file() and p.name != "SKILL.md"]
    if extras:
        text += "\n\n---\nSupporting files in this skill: " + ", ".join(extras)
    return text


def register_skill_tools(registry):
    registry.register(
        name="list_skills",
        description=(
            "List installed skill workflows (SEO, GEO/AI-search, content, copywriting, marketing, "
            "link building, YouTube SEO, etc.). Optional keyword filter. Check this whenever the user "
            "asks for SEO, marketing, copy or content work — a skill may already define the playbook."
        ),
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Keywords to filter by."}},
            "required": [],
        },
        fn=list_skills,
    )
    registry.register(
        name="load_skill",
        description="Load a skill's full step-by-step instructions by name, then follow them.",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Skill name from list_skills."}},
            "required": ["name"],
        },
        fn=load_skill,
    )
