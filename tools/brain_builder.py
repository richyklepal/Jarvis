"""Second brain: interview the user, keep the session word for word, turn it into notes.

Flow
  1. Interview  — Telegram /interview (or any chat): Jarvis asks one question at a time.
                  Every question and answer is saved verbatim to
                  <vault>/Jarvis/Interviews/<date time> Interview.md
  2. Build      — Telegram /build, the build_second_brain tool, or the command below:
                  the transcript becomes linked notes under <vault>/Jarvis/Second Brain/<Folder>/,
                  each with the quotes it came from, and the key facts go into Jarvis's memory.

Phone voice memo instead of Telegram:
    python -m tools.brain_builder ~/Downloads/walk.m4a      # transcribe with Whisper, then build
    python -m tools.brain_builder "<vault>/Jarvis/Interviews/2026-11-22 0900 Interview.md"
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from tools import obsidian

FOLDERS = ["Identity", "Story", "Goals", "Projects", "Money", "People", "Beliefs",
           "Spiritual", "Health", "Skills", "Ideas"]
CHUNK_WORDS = 9000

INTERVIEW_KICKOFF = """We're starting an interview to build my second brain. You are the interviewer now.

Rules for this interview:
- Ask ONE question at a time, short and conversational. I'm walking and answering by voice.
- Follow up on anything interesting before moving on: ask for the story, the example, the number, the name.
- Cover, in roughly this order: who I am and where I'm from; my story (football, FSU, what came after);
  what I do now and how I make money; every project and business; my goals for 90 days, 1 year, 5 years;
  the people who matter (family, partners, clients, mentors); my beliefs and how I make decisions;
  IFA and my practice, only what I choose to share; health and training; my skills; ideas I haven't acted on.
- Don't give advice or summaries during the interview. Just listen and dig.
- Every so often, tell me in one line which area we're in and what's left.
- When I say "done" or send /build, stop asking.

Start with your first question."""

EXTRACT_SYSTEM = """You turn interview transcripts into an Obsidian second brain for one person (the interviewee, "the user").

Return ONLY a JSON object, no prose, in this shape:
{"notes": [{"folder": "...", "title": "...", "body": "...", "quotes": ["...", "..."]}],
 "facts": ["...", "..."]}

Rules:
- folder is exactly one of: %s
- One note per distinct thing: a person, a project, a goal, a belief, a chapter of their story, a skill.
  Prefer many small notes over a few big ones. Title is short and specific ("Matt Chibbs", "FSU years",
  "Crunch MIT goal"), no dates, no slashes.
- body is Markdown written in the third person about the user (by name if the transcript gives it). Include concrete details: names, numbers, dates, places. Link related notes with
  [[Title]] using titles you are creating in this batch.
- quotes: 1-4 short verbatim lines from the transcript that support the note. Copy them exactly.
- Never invent anything that isn't in the transcript. If something is unclear, leave it out.
- facts: 5-25 durable one-line facts worth loading into every future conversation
  (identity, goals, key people, preferences, current situation). Only from the transcript.""" % ", ".join(FOLDERS)


# ---------------------------------------------------------------- interviews

def interviews_dir() -> Path:
    d = obsidian.jarvis_root() / "Interviews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def start_interview(source="telegram") -> Path:
    now = datetime.now()
    path = interviews_dir() / f"{now:%Y-%m-%d %H%M} Interview.md"
    path.write_text(
        f"---\ntype: interview\ndate: {now:%Y-%m-%d}\nsource: {source}\nstatus: in-progress\n"
        "tags: [jarvis, interview, second-brain]\n---\n"
        f"# Interview — {now:%A, %B %d, %Y %H:%M}\n\nVerbatim transcript.\n\n",
        encoding="utf-8",
    )
    return path


def append_turn(path: Path, speaker: str, text: str):
    stamp = datetime.now().strftime("%H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"**{speaker}** ({stamp}): {text.strip()}\n\n")


def latest_interview() -> Path | None:
    files = sorted(interviews_dir().glob("*.md"))
    return files[-1] if files else None


def transcribe_to_interview(audio_path) -> Path:
    """Transcribe a voice memo (m4a, mp3, wav, ogg) with local Whisper into an interview file."""
    from audio.stt import transcribe_file

    audio_path = Path(audio_path).expanduser()
    print(f"[Transcribing {audio_path.name} with Whisper — a 2-hour memo can take a while]", flush=True)
    text = transcribe_file(audio_path)
    path = start_interview(source=f"voice memo: {audio_path.name}")
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    return path


# ---------------------------------------------------------------- building notes

def _transcript_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)


def _chunks(text: str):
    words = text.split()
    for i in range(0, len(words), CHUNK_WORDS):
        yield " ".join(words[i:i + CHUNK_WORDS])


def _ask_model(chunk: str, part: int, total: int) -> dict:
    import brain

    client = brain._get_client()
    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
    msg = client.messages.create(
        model=model,
        max_tokens=16000,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": f"Transcript part {part} of {total}:\n\n{chunk}"}],
    )
    raw = "".join(b.text for b in msg.content if hasattr(b, "text"))
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise RuntimeError("The model didn't return notes for part %d." % part)
    return json.loads(m.group(0))


def _clean_title(title: str) -> str:
    title = re.sub(r'[\\/:*?"<>|#^\[\]]', "", str(title)).strip()
    return re.sub(r"\s+", " ", title)[:80] or "Untitled"


def _write_note(folder: str, title: str, body: str, quotes, source: Path):
    folder = folder if folder in FOLDERS else "Ideas"
    path = obsidian.jarvis_root() / "Second Brain" / folder / f"{title}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    quotes = [str(q).strip() for q in (quotes or []) if str(q).strip()]
    if quotes:
        quote_block = "\n".join(f"> {q}" for q in quotes)
        section = f"{body.strip()}\n\n**Said in [[{source.stem}]]:**\n\n{quote_block}\n\n"
    else:
        section = f"{body.strip()}\n\nSource: [[{source.stem}]]\n\n"
    if path.exists():
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n## Update from {source.stem}\n\n{section}")
        return path, False
    path.write_text(
        f"---\ntype: second-brain\nfolder: {folder}\ntags: [second-brain, {folder.lower()}]\n---\n"
        f"# {title}\n\n{section}",
        encoding="utf-8",
    )
    return path, True


def _rebuild_home():
    root = obsidian.jarvis_root() / "Second Brain"
    lines = ["# Second Brain", "", "Built from your interviews. Each note links to the conversation it came from.", ""]
    for folder in FOLDERS:
        notes = sorted(p.stem for p in (root / folder).glob("*.md")) if (root / folder).exists() else []
        if notes:
            lines.append(f"## {folder} ({len(notes)})")
            lines += [f"- [[{n}]]" for n in notes]
            lines.append("")
    interviews = sorted(p.stem for p in interviews_dir().glob("*.md"))
    if interviews:
        lines += ["## Interviews"] + [f"- [[{n}]]" for n in reversed(interviews)]
    (root / "Second Brain Home.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_brain(transcript_path=None) -> str:
    """Turn an interview transcript into second-brain notes. Defaults to the latest interview."""
    path = Path(transcript_path).expanduser() if transcript_path else latest_interview()
    if not path or not path.exists():
        return "No interview found. Start one with /interview, or give me a transcript or voice memo."
    text = _transcript_text(path)
    if len(text.split()) < 40:
        return "That interview is too short to build notes from yet."

    parts = list(_chunks(text))
    created, updated, facts_added = [], [], 0
    for i, chunk in enumerate(parts, 1):
        print(f"[Second brain] reading part {i} of {len(parts)}…", flush=True)
        data = _ask_model(chunk, i, len(parts))
        for n in data.get("notes", []):
            if not n.get("body"):
                continue
            note, is_new = _write_note(n.get("folder", "Ideas"), _clean_title(n.get("title")),
                                       n["body"], n.get("quotes"), path)
            (created if is_new else updated).append(note.stem)
        for fact in data.get("facts", []):
            if not obsidian.remember_fact(str(fact)).startswith("Already known"):
                facts_added += 1

    text_now = path.read_text(encoding="utf-8").replace("status: in-progress", "status: built", 1)
    path.write_text(text_now, encoding="utf-8")
    _rebuild_home()
    obsidian.log_event("system", f"Second brain built from {path.name}: {len(created)} new notes, "
                                 f"{len(updated)} updated, {facts_added} facts remembered.")
    return (f"Second brain built from {path.stem}: {len(created)} new notes, {len(set(updated))} updated, "
            f"{facts_added} new facts in memory. Open 'Second Brain Home' in Obsidian.")


def register_brain_tools(registry):
    registry.register(
        name="build_second_brain",
        description=(
            "Turn an interview transcript into the user's second-brain notes in Obsidian "
            "(Identity, Story, Goals, Projects, People, Beliefs and more) and load key facts into memory. "
            "Use when the user says they're done with an interview or asks to build/update their second brain. "
            "Takes a few minutes for long interviews."
        ),
        input_schema={
            "type": "object",
            "properties": {"transcript_path": {
                "type": "string",
                "description": "Path to an interview file. Omit to use the latest interview."}},
            "required": [],
        },
        fn=build_brain,
    )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    src = Path(sys.argv[1]).expanduser()
    if src.suffix.lower() != ".md":
        src = transcribe_to_interview(src)
        print(f"[Saved transcript] {src}")
    print(build_brain(src))
