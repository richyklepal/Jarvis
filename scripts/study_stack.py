#!/usr/bin/env python3
"""Have Jarvis study every repo in stack/repos.json into the Obsidian vault
(Jarvis/Knowledge/GitHub/*.md), plus an index note linking them all."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from tools import obsidian  # noqa: E402
from tools.github_learn import study_repo  # noqa: E402

repos = json.loads((ROOT / "stack" / "repos.json").read_text())["repos"]
print(obsidian.status_line())
index = ["---", "type: jarvis-knowledge", "tags: [jarvis, stack]", "---", "# Jarvis stack", ""]
for r in repos:
    print(f"studying {r['repo']} …")
    print("  " + study_repo(r["repo"]))
    note = f"Jarvis/Knowledge/GitHub/{r['repo'].replace('/', '__')}"
    index.append(f"- [[{note}|{r['name']}]] ({r['kind']}) — {r['use']}")
obsidian.vault_write("Jarvis/Knowledge/Stack.md", "\n".join(index), mode="overwrite")
print("Index → Jarvis/Knowledge/Stack.md")
