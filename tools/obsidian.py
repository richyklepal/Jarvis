"""
Obsidian vault integration.

An Obsidian vault is just a folder of Markdown files, so Jarvis writes to it
directly. Everything Jarvis does lands under <vault>/Jarvis/:

  Jarvis/Sessions/YYYY-MM-DD.md   every conversation turn + tool call, timestamped
  Jarvis/Notes/<category>.md      notes saved via save_note
  Jarvis/Memory.md                long-term facts, loaded into every session
  Jarvis/Knowledge/...            things Jarvis has studied (e.g. GitHub repos)

Set OBSIDIAN_VAULT_PATH in .env to your vault folder. If unset, Jarvis falls
back to ./data/vault so nothing is lost, and says so at startup.
"""
import os
import re
from datetime import datetime
from pathlib import Path

_FALLBACK = Path(__file__).parent.parent / "data" / "vault"
_MAX_LOG_CHARS = 4000  # truncate huge tool results in the session log


def vault_path() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    return Path(raw).expanduser() if raw else _FALLBACK


def is_configured() -> bool:
    return bool(os.environ.get("OBSIDIAN_VAULT_PATH", "").strip())


def jarvis_root() -> Path:
    root = vault_path() / "Jarvis"
    root.mkdir(parents=True, exist_ok=True)
    return root


def status_line() -> str:
    if is_configured():
        if not vault_path().exists():
            return f"[Obsidian] WARNING: OBSIDIAN_VAULT_PATH does not exist: {vault_path()}"
        return f"[Obsidian] Logging to vault: {vault_path() / 'Jarvis'}"
    return (
        f"[Obsidian] OBSIDIAN_VAULT_PATH not set — logging to local fallback {_FALLBACK}. "
        "Point it at your vault in .env."
    )


def _safe_rel(rel: str) -> Path:
    """Resolve a vault-relative path and refuse anything escaping the vault."""
    vault = vault_path().resolve()
    rel = rel.strip().lstrip("/")
    if not rel.endswith(".md"):
        rel += ".md"
    p = (vault / rel).resolve()
    if vault != p and vault not in p.parents:
        raise ValueError("Path escapes the vault.")
    return p


def _append(path: Path, text: str, header: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if new and header:
            f.write(header)
        f.write(text)


def _clip(text: str) -> str:
    text = str(text)
    if len(text) > _MAX_LOG_CHARS:
        return text[:_MAX_LOG_CHARS] + f"\n… [truncated, {len(text)} chars total]"
    return text


# ---------------------------------------------------------------- session log

def _session_file() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    return jarvis_root() / "Sessions" / f"{today}.md"


def _session_header() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"---\ntype: jarvis-session\ndate: {today}\ntags: [jarvis, session]\n---\n# Jarvis session log — {today}\n\n"


def log_event(kind: str, content: str, detail: str = ""):
    """Append one event to today's session log. Never raises — logging must not break Jarvis."""
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        labels = {"user": "🧑 You", "jarvis": "🤖 Jarvis", "tool": "🛠 Tool", "error": "⚠️ Error", "system": "⚙️ System"}
        label = labels.get(kind, kind)
        block = f"### {ts} — {label}" + (f" `{detail}`" if detail else "") + "\n"
        body = _clip(content) if kind == "tool" else str(content)
        if kind == "tool":
            block += f"```\n{body}\n```\n\n"
        else:
            block += f"{body}\n\n"
        _append(_session_file(), block, _session_header())
    except Exception as e:  # pragma: no cover
        print(f"\n[Obsidian log failed: {e}]")


def log_session_start(mode: str):
    log_event("system", f"Session started ({mode} mode).", "")


# ---------------------------------------------------------------- notes

def write_note_entry(category: str, content: str):
    path = jarvis_root() / "Notes" / f"{category}.md"
    header = f"---\ntype: jarvis-notes\ncategory: {category}\ntags: [jarvis, notes, {category}]\n---\n# {category.title()} notes\n\n"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    _append(path, f"- [{stamp}] {content}\n", header)


# ---------------------------------------------------------------- memory

def _memory_file() -> Path:
    return jarvis_root() / "Memory.md"


def load_memory_facts() -> list[str]:
    path = _memory_file()
    if not path.exists():
        return []
    facts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*-\s+(?:\[[^\]]*\]\s*)?(.+)$", line)
        if m:
            facts.append(m.group(1).strip())
    return facts


def remember_fact(fact: str):
    fact = " ".join(fact.split())
    if fact in load_memory_facts():
        return f"Already known: {fact}"
    header = (
        "---\ntype: jarvis-memory\ntags: [jarvis, memory]\n---\n# Jarvis memory\n\n"
        "Long-term facts Jarvis loads into every session. Edit freely — one fact per bullet.\n\n"
    )
    stamp = datetime.now().strftime("%Y-%m-%d")
    _append(_memory_file(), f"- [{stamp}] {fact}\n", header)
    log_event("system", f"Remembered: {fact}")
    return f"Remembered: {fact}"


# ---------------------------------------------------------------- vault tools

def vault_search(query: str, limit: int = 10):
    vault = vault_path()
    if not vault.exists():
        return "Vault not found."
    terms = [t.lower() for t in query.split() if t]
    hits = []
    for p in vault.rglob("*.md"):
        if any(part.startswith(".") for part in p.relative_to(vault).parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        low = text.lower()
        name = p.stem.lower()
        score = sum(low.count(t) + 5 * name.count(t) for t in terms)
        if score and all(t in low or t in name for t in terms):
            idx = low.find(terms[0]) if terms else 0
            start = max(0, idx - 120)
            snippet = " ".join(text[start:start + 300].split())
            hits.append((score, str(p.relative_to(vault)), snippet))
    hits.sort(reverse=True)
    if not hits:
        return f"No vault notes match '{query}'."
    return "\n\n".join(f"**{rel}** (score {s})\n…{snip}…" for s, rel, snip in hits[:limit])


def vault_read(path: str):
    p = _safe_rel(path)
    if not p.exists():
        return f"No note at '{path}'."
    return _clip(p.read_text(encoding="utf-8", errors="ignore"))


def vault_write(path: str, content: str, mode: str = "append"):
    p = _safe_rel(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if mode == "overwrite":
        p.write_text(content, encoding="utf-8")
    else:
        with open(p, "a", encoding="utf-8") as f:
            f.write(("\n" if p.exists() and p.stat().st_size else "") + content + "\n")
    rel = p.relative_to(vault_path().resolve())
    log_event("system", f"Wrote vault note ({mode}): [[{rel.with_suffix('')}]]")
    return f"Wrote {rel} ({mode})."


def register_obsidian_tools(registry):
    registry.register(
        name="remember_fact",
        description=(
            "Store a durable fact about the user, their businesses, preferences, or goals in "
            "long-term memory (Obsidian Jarvis/Memory.md). Loaded into every future session. "
            "Use whenever the user tells you something worth knowing next time."
        ),
        input_schema={
            "type": "object",
            "properties": {"fact": {"type": "string", "description": "One concise fact."}},
            "required": ["fact"],
        },
        fn=remember_fact,
    )
    registry.register(
        name="vault_search",
        description=(
            "Search the user's Obsidian vault (all notes, past session logs, memory, and "
            "knowledge Jarvis has studied, like GitHub repo summaries). Use before answering "
            "anything about the user's past work, plans, or projects."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for."},
                "limit": {"type": "integer", "description": "Max results. Default 10."},
            },
            "required": ["query"],
        },
        fn=vault_search,
    )
    registry.register(
        name="vault_read",
        description="Read a note from the Obsidian vault by its vault-relative path (from vault_search).",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "e.g. 'Jarvis/Memory.md'"}},
            "required": ["path"],
        },
        fn=vault_read,
    )
    registry.register(
        name="vault_write",
        description=(
            "Create or append to a note in the Obsidian vault. Default mode 'append' is safe. "
            "'overwrite' replaces the note — only use it on notes Jarvis itself created, and "
            "never overwrite a user note without explicit confirmation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault-relative path, e.g. 'Jarvis/Plans/TikTok.md'"},
                "content": {"type": "string", "description": "Markdown content."},
                "mode": {"type": "string", "enum": ["append", "overwrite"]},
            },
            "required": ["path", "content"],
        },
        fn=vault_write,
    )
