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


def run():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[Setup] ANTHROPIC_API_KEY is not set.")
        print("Copy .env.example to .env and add your key from console.anthropic.com\n")
        sys.exit(1)

    registry = build_registry()
    system = build_system_prompt()
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


if __name__ == "__main__":
    run()
