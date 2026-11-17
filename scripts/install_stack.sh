#!/usr/bin/env bash
# Clone (or update) every repo in stack/repos.json into $JARVIS_STACK_DIR (default ~/jarvis-stack).
# Shallow clones — source + docs, no builds. Each app's README has its own install/run steps.
#   scripts/install_stack.sh            all repos
#   scripts/install_stack.sh chatwoot   only repos whose name/slug matches
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${JARVIS_STACK_DIR:-$HOME/jarvis-stack}"
FILTER="${1:-}"
mkdir -p "$DEST"

python3 -c "import json,sys; [print(r['repo']) for r in json.load(open('$ROOT/stack/repos.json'))['repos']]" |
while read -r repo; do
  [[ -n "$FILTER" && "${repo,,}" != *"${FILTER,,}"* ]] && continue
  dir="$DEST/${repo//\//__}"
  if [[ -d "$dir/.git" ]]; then
    echo "↻ updating $repo"; git -C "$dir" pull -q --ff-only || echo "  ! could not update $repo"
  else
    echo "↓ cloning  $repo"; git clone -q --depth 1 "https://github.com/$repo.git" "$dir" || echo "  ! could not clone $repo"
  fi
done
echo "Done → $DEST"
echo "Next: python3 scripts/study_stack.py   (writes a knowledge note per repo into your Obsidian vault)"
