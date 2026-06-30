import json
from pathlib import Path

_ODU_DB = None


def _get_db():
    global _ODU_DB
    if _ODU_DB is None:
        db_path = Path(__file__).parent.parent / "data" / "ifa" / "odu.json"
        if not db_path.exists():
            _ODU_DB = {}
            return _ODU_DB
        with open(db_path) as f:
            data = json.load(f)
        index = {}
        for odu in data.get("odu", []):
            index[odu["id"]] = odu
            for name in [
                odu.get("name", ""),
                odu.get("nigerian_name", ""),
                odu.get("cuban_name", ""),
            ] + odu.get("also_known_as", []):
                if name:
                    index[name.lower()] = odu
                    index[name.lower().replace(" ", "_")] = odu
                    index[name.lower().replace("-", "_")] = odu
        _ODU_DB = index
    return _ODU_DB


def odu_lookup(name, aspect="full"):
    db = _get_db()
    key = name.lower().strip()
    odu = db.get(key) or db.get(key.replace(" ", "_")) or db.get(key.replace("-", "_"))

    if not odu:
        return (
            f"'{name}' is not yet in the local knowledge base. "
            "The database is seeded with all 16 Meji and Iwori Ofun. "
            "Combination Odu (Amulu) will be added incrementally. "
            "For now, I can answer from my full IFA knowledge directly."
        )

    if aspect == "ebo":
        ebo = odu.get("ebo", {})
        lines = [f"**{odu['name']} — Ebo**", ""]
        if ebo.get("note"):
            lines.append(f"Note: {ebo['note']}")
            lines.append("")
        for item in ebo.get("general", []):
            lines.append(f"• {item}")
        return "\n".join(lines)

    if aspect == "akose":
        akose = odu.get("akose", {})
        lines = [f"**{odu['name']} — Akose**", ""]
        if akose.get("note"):
            lines.append(f"Note: {akose['note']}")
            lines.append("")
        for item in akose.get("remedies", []):
            lines.append(f"• {item}")
        return "\n".join(lines)

    if aspect == "themes":
        lines = [f"**{odu['name']} — Core Themes**", ""]
        for t in odu.get("themes", []):
            lines.append(f"• {t}")
        return "\n".join(lines)

    # Full
    lines = [f"**{odu['name']}**"]
    if odu.get("personal_note"):
        lines.append(f"*{odu['personal_note']}*")
    if odu.get("also_known_as"):
        lines.append(f"Also known as: {', '.join(odu['also_known_as'])}")
    if odu.get("ruling_orisha"):
        lines.append(f"\nRuling Orisha: {', '.join(odu['ruling_orisha'])}")
    if odu.get("themes"):
        lines.append("\n**Themes:**")
        for t in odu["themes"]:
            lines.append(f"• {t}")
    if odu.get("strengths"):
        lines.append("\n**Strengths:**")
        for s in odu["strengths"]:
            lines.append(f"• {s}")
    if odu.get("warnings"):
        lines.append("\n**Warnings:**")
        for w in odu["warnings"]:
            lines.append(f"• {w}")
    if odu.get("ese_ifa_summary"):
        lines.append(f"\n**Ese IFA (summary):** {odu['ese_ifa_summary']}")
    if odu.get("nigerian_tradition_notes"):
        lines.append(f"\n**Nigerian tradition:** {odu['nigerian_tradition_notes']}")
    if odu.get("cuban_tradition_notes"):
        lines.append(f"\n**Afrocuban/Lukumí tradition:** {odu['cuban_tradition_notes']}")
    if odu.get("ebo", {}).get("general"):
        lines.append("\n**Ebo (general guidance):**")
        if odu["ebo"].get("note"):
            lines.append(f"*{odu['ebo']['note']}*")
        for item in odu["ebo"]["general"]:
            lines.append(f"• {item}")

    return "\n".join(lines)


def register_ifa_tools(registry):
    registry.register(
        name="odu_lookup",
        description=(
            "Look up an Odu from the IFA knowledge base — covers both traditional Nigerian IFA "
            "and Afrocuban (Lukumí) lineages. Use this whenever the user asks about a specific Odu "
            "by name, asks about readings/consultas, ebo, akose, or the themes and warnings of a sign. "
            "The aspect parameter filters the output: 'full' (default), 'ebo', 'akose', or 'themes'. "
            "Iwori Ofun is the user's personal Odu and has the most detailed entry."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the Odu, e.g. 'Iwori Ofun', 'Ogbe Meji', 'Ofun Meji'",
                },
                "aspect": {
                    "type": "string",
                    "enum": ["full", "ebo", "akose", "themes"],
                    "description": "Which aspect to return. Default: 'full'",
                },
            },
            "required": ["name"],
        },
        fn=odu_lookup,
    )
