#!/usr/bin/env bash
# (Re)install the SEO skill pack from Illyism/seo-skills into .claude/skills/.
# Used by Claude Code in this repo AND by Jarvis (list_skills / load_skill tools).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git clone -q --depth 1 https://github.com/Illyism/seo-skills.git "$TMP/seo-skills"
mkdir -p "$ROOT/.claude/skills"
n=0
while read -r f; do
  d="$(dirname "$f")"; rm -rf "$ROOT/.claude/skills/$(basename "$d")"
  cp -r "$d" "$ROOT/.claude/skills/"; n=$((n+1))
done < <(find "$TMP/seo-skills"/{seo,content,marketing,copywriting} -name SKILL.md)
echo "Installed $n skills from Illyism/seo-skills@$(git -C "$TMP/seo-skills" rev-parse --short HEAD)"
