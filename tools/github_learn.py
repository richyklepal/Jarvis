"""
GitHub learning: Jarvis studies the user's repositories and files what it learns
into the Obsidian vault under Jarvis/Knowledge/GitHub/<repo>.md, so the knowledge
is searchable (vault_search) and survives restarts.

Uses the GitHub REST API via urllib (no extra dependency). Public repos work with
no token; set GITHUB_TOKEN in .env to include private repos and raise rate limits.
"""
import base64
import json
import os
import urllib.error
import urllib.request
from datetime import datetime

from tools import obsidian

_API = "https://api.github.com"
_KEY_FILES = (
    "README.md", "readme.md", "AGENT.md", "CLAUDE.md", "package.json",
    "requirements.txt", "pyproject.toml", "main.py", "app.py", "index.js",
)
_MAX_FILE_CHARS = 6000


def _get(path: str):
    req = urllib.request.Request(_API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "jarvis-assistant",
    })
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _default_owner():
    return os.environ.get("GITHUB_USER", "richyklepal")


def list_repos(owner: str = ""):
    owner = owner or _default_owner()
    try:
        if os.environ.get("GITHUB_TOKEN"):
            repos = _get("/user/repos?per_page=100&sort=pushed&affiliation=owner")
        else:
            repos = _get(f"/users/{owner}/repos?per_page=100&sort=pushed")
    except urllib.error.HTTPError as e:
        return f"GitHub error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"Can't reach GitHub: {e.reason}"
    if not repos:
        return f"No repos found for {owner}."
    lines = []
    for r in repos:
        vis = "private" if r.get("private") else "public"
        lines.append(f"- {r['full_name']} ({vis}, {r.get('language') or '—'}) — {r.get('description') or 'no description'}")
    return "\n".join(lines)


def _file(full_name: str, path: str, ref: str):
    try:
        data = _get(f"/repos/{full_name}/contents/{path}?ref={ref}")
    except urllib.error.HTTPError:
        return None
    if isinstance(data, dict) and data.get("encoding") == "base64":
        text = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return text[:_MAX_FILE_CHARS] + ("\n… [truncated]" if len(text) > _MAX_FILE_CHARS else "")
    return None


def study_repo(repo: str):
    """Pull a repo's overview, structure, recent commits and key files into the vault."""
    full_name = repo if "/" in repo else f"{_default_owner()}/{repo}"
    try:
        meta = _get(f"/repos/{full_name}")
        ref = meta.get("default_branch", "main")
        tree = _get(f"/repos/{full_name}/git/trees/{ref}?recursive=1").get("tree", [])
        commits = _get(f"/repos/{full_name}/commits?per_page=15&sha={ref}")
    except urllib.error.HTTPError as e:
        return f"GitHub error {e.code} on {full_name}: {e.reason} (private repo or rate limit? set GITHUB_TOKEN)"
    except urllib.error.URLError as e:
        return f"Can't reach GitHub: {e.reason}"

    paths = [t["path"] for t in tree if t.get("type") == "blob"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [
        "---", "type: jarvis-knowledge", "source: github", f"repo: {full_name}",
        f"studied: {now}", "tags: [jarvis, knowledge, github]", "---",
        f"# {full_name}", "",
        f"- **Description:** {meta.get('description') or '—'}",
        f"- **Language:** {meta.get('language') or '—'}",
        f"- **Default branch:** {ref}",
        f"- **Last push:** {meta.get('pushed_at')}",
        f"- **URL:** {meta.get('html_url')}", "",
        "## Recent commits",
    ]
    for c in commits:
        msg = c["commit"]["message"].splitlines()[0]
        out.append(f"- `{c['sha'][:7]}` {c['commit']['author']['date'][:10]} — {msg}")
    out += ["", f"## File tree ({len(paths)} files)", "```"]
    out += paths[:300]
    if len(paths) > 300:
        out.append(f"… {len(paths) - 300} more")
    out += ["```", ""]

    wanted = [p for p in paths if p.split("/")[-1] in _KEY_FILES and p.count("/") <= 1]
    for p in wanted[:8]:
        text = _file(full_name, p, ref)
        if text:
            lang = p.rsplit(".", 1)[-1] if "." in p else ""
            fence = "````" if "```" in text else "```"
            out += [f"## {p}", f"{fence}{lang}", text, fence, ""]

    rel = f"Jarvis/Knowledge/GitHub/{full_name.replace('/', '__')}.md"
    obsidian.vault_write(rel, "\n".join(out), mode="overwrite")
    return (
        f"Studied {full_name}: {len(paths)} files, {len(commits)} recent commits, "
        f"{len(wanted[:8])} key files read. Saved to [[{rel[:-3]}]]. "
        "Use vault_read on that note for details, and remember_fact for anything worth keeping."
    )


def register_github_tools(registry):
    registry.register(
        name="github_list_repos",
        description="List the user's GitHub repositories (public, plus private if GITHUB_TOKEN is set).",
        input_schema={
            "type": "object",
            "properties": {"owner": {"type": "string", "description": "GitHub user/org. Defaults to the user's account."}},
            "required": [],
        },
        fn=list_repos,
    )
    registry.register(
        name="github_study_repo",
        description=(
            "Study one of the user's GitHub repos: description, recent commits, file tree, README "
            "and key files. Writes a knowledge note into the Obsidian vault so Jarvis can recall it "
            "later. Use when the user asks you to learn a repo, or when you need context on a project."
        ),
        input_schema={
            "type": "object",
            "properties": {"repo": {"type": "string", "description": "'owner/name' or just 'name'."}},
            "required": ["repo"],
        },
        fn=study_repo,
    )
