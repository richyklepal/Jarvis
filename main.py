import os
import sys
from dotenv import load_dotenv

load_dotenv()

import brain
from system_prompt import build_system_prompt


def run() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[Setup] ANTHROPIC_API_KEY is not set.")
        print("Copy .env.example to .env and paste your key from console.anthropic.com\n")
        sys.exit(1)

    system = build_system_prompt()
    history: list[dict] = []

    print("\nJarvis online. Type 'exit' to stop.\n")

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
        full_reply = ""
        ok = True

        for event, data in brain.stream(history, system):
            if event == "text":
                print(data, end="", flush=True)
                full_reply += data
            elif event == "error":
                print(data)
                ok = False
                break

        print("\n")

        if ok and full_reply:
            history.append({"role": "assistant", "content": full_reply})


if __name__ == "__main__":
    run()
