import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

import agent
from system_prompt import build_system_prompt
from tool_registry import ToolRegistry
from tools.ifa import register_ifa_tools
from tools.notes import register_notes_tools


def build_registry():
    registry = ToolRegistry()
    register_ifa_tools(registry)
    register_notes_tools(registry)
    return registry


def run_text(system, registry):
    history = []
    print(f"\nJarvis online. {len(registry)} tools ready. Type 'exit' to stop.\n")

    while True:
        try:
            raw = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nJarvis: Signing off.")
            sys.exit(0)

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "bye"):
            print("Jarvis: Later. Stay on it.")
            break

        history.append({"role": "user", "content": raw})

        print("Jarvis: ", end="", flush=True)
        history, reply = agent.run_turn(history, system, registry)

        if reply:
            print(reply)
        print()


def run_voice(system, registry):
    from audio.capture import record_ptt
    from audio.stt import transcribe
    from audio import tts

    history = []
    print(f"\nJarvis voice mode. {len(registry)} tools ready.")
    print("Hold F5 to speak — release when done. Say 'exit' to stop.")
    print("Transcript prints next to your reply so you can see what Jarvis heard.\n")
    print("Mac note: if F5 doesn't respond, go to System Settings → Privacy & Security")
    print("→ Accessibility and grant Terminal access.\n")

    while True:
        try:
            audio_bytes = record_ptt(on_press_callback=tts.stop)
        except KeyboardInterrupt:
            print("\nJarvis: Signing off.")
            break

        if not audio_bytes:
            continue

        try:
            transcript = transcribe(audio_bytes)
        except Exception as e:
            print(f"[STT error: {e}]")
            continue

        if not transcript:
            print("[nothing heard — try again]")
            continue

        print(f"You [{transcript}]")

        if transcript.lower().strip() in ("exit", "quit", "stop", "bye", "jarvis stop"):
            print("Jarvis: Later.")
            tts.speak("Later.")
            break

        history.append({"role": "user", "content": transcript})

        print("Jarvis: ", end="", flush=True)
        history, reply = agent.run_turn(history, system, registry)

        if reply:
            print(reply)
            tts.speak_async(reply)

        print()


def run():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[Setup] ANTHROPIC_API_KEY is not set.")
        print("Add it to your .env file (copy from .env.example).\n")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Jarvis AI Assistant")
    parser.add_argument("--voice", action="store_true", help="Push-to-talk voice mode")
    args = parser.parse_args()

    registry = build_registry()
    system = build_system_prompt()

    if args.voice:
        run_voice(system, registry)
    else:
        run_text(system, registry)


if __name__ == "__main__":
    run()
