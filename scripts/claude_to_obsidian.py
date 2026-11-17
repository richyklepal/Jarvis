#!/usr/bin/env python3
"""
Claude Code hook: mirror Claude Code sessions into the Obsidian vault.

Wired up in .claude/settings.json on the Stop and SessionEnd events. Claude Code
passes JSON on stdin with `session_id` and `transcript_path`; this script reads
the transcript (JSONL), and appends every entry it hasn't logged yet — your
prompts, Claude's replies, and the tools Claude ran — to:

    <vault>/Jarvis/Claude/YYYY-MM-DD.md

Vault location: OBSIDIAN_VAULT_PATH (env or the repo's .env). Never fails the
session: any error is swallowed after printing to stderr.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAX_TOOL_CHARS = 1500


def _vault():
    v = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if not v:
        env = REPO / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith("OBSIDIAN_VAULT_PATH="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
    return Path(v).expanduser() if v else REPO / "data" / "vault"


def _text_of(content):
    """Turn a transcript message's content into (kind, text) pieces."""
    if isinstance(content, str):
        return [("text", content)]
    out = []
    for b in content or []:
        t = b.get("type")
        if t == "text" and b.get("text", "").strip():
            out.append(("text", b["text"]))
        elif t == "tool_use":
            inp = json.dumps(b.get("input", {}), ensure_ascii=False)
            out.append(("tool", f"{b.get('name')}: {inp[:MAX_TOOL_CHARS]}"))
        elif t == "tool_result":
            c = b.get("content")
            if isinstance(c, list):
                c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
            c = str(c or "")
            if len(c) > MAX_TOOL_CHARS:
                c = c[:MAX_TOOL_CHARS] + f"\n… [truncated, {len(c)} chars]"
            out.append(("result", c))
    return out


def main():
    data = json.load(sys.stdin)
    session = data.get("session_id", "unknown")
    transcript = Path(data.get("transcript_path", "")).expanduser()
    if not transcript.is_file():
        return

    vault = _vault()
    state_dir = vault / "Jarvis" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"claude-{session}.json"
    done = json.loads(state_file.read_text()).get("lines", 0) if state_file.exists() else 0

    lines = transcript.read_text(encoding="utf-8", errors="ignore").splitlines()
    new = lines[done:]
    if not new:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    log = vault / "Jarvis" / "Claude" / f"{today}.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    if not log.exists():
        chunks.append(
            f"---\ntype: claude-session\ndate: {today}\ntags: [jarvis, claude]\n---\n"
            f"# Claude sessions — {today}\n\n"
        )
    chunks.append(f"## Session `{session[:8]}` — {data.get('hook_event_name', '')} "
                  f"{datetime.now().strftime('%H:%M:%S')}\n\n")

    for raw in new:
        try:
            e = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if e.get("type") not in ("user", "assistant") or e.get("isMeta"):
            continue
        ts = (e.get("timestamp") or "")[11:19]
        msg = e.get("message", {})
        for kind, text in _text_of(msg.get("content")):
            if kind == "text":
                who = "🧑 You" if e["type"] == "user" else "🤖 Claude"
                chunks.append(f"### {ts} — {who}\n{text}\n\n")
            elif kind == "tool":
                chunks.append(f"- 🛠 `{ts}` {text}\n")
            elif kind == "result":
                chunks.append(f"  ```\n  {text.replace(chr(10), chr(10) + '  ')}\n  ```\n")
    chunks.append("\n")

    with open(log, "a", encoding="utf-8") as f:
        f.write("".join(chunks))
    state_file.write_text(json.dumps({"lines": len(lines)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never break the Claude session
        print(f"[claude_to_obsidian] {exc}", file=sys.stderr)
