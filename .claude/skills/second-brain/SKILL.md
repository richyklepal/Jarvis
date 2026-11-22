---
name: second-brain
description: Turn an interview, voice memo, or long conversation transcript into Richy's Obsidian second brain (linked notes for Identity, Story, Goals, Projects, Money, People, Beliefs, Spiritual, Health, Skills, Ideas) and load durable facts into Jarvis's memory. Use when the user shares a transcript or voice memo of themselves talking, finishes an interview, or asks to build or update their second brain.
---

# Second brain

Jarvis already has the whole pipeline in `tools/brain_builder.py`. Use it rather than writing notes by hand.

## Steps

1. Find the source.
   - Telegram interviews are saved word for word in `<vault>/Jarvis/Interviews/`.
   - A voice memo (m4a, mp3, wav, ogg) gets transcribed first with local Whisper.
   - A pasted transcript: save it as a new file in `<vault>/Jarvis/Interviews/` with the frontmatter `type: interview`.
2. Build:
   ```bash
   python -m tools.brain_builder "<path to transcript .md or voice memo>"
   ```
   With no path, `build_brain()` uses the latest interview.
3. Report back: how many notes were created and updated, and how many facts went into `Jarvis/Memory.md`. Point the user to `Second Brain Home` in Obsidian.

## Rules

- Never invent details. Every note must trace to the transcript, and each note quotes the lines it came from.
- Existing notes are appended to with an "Update from <interview>" section, never overwritten.
- IFA material: record only what the user chose to say. Don't add teachings from elsewhere.
- The vault is private. Don't commit vault contents to this repository (it is public).
