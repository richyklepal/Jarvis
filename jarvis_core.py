"""One Jarvis brain shared by every interface (terminal, web page, Telegram).

Each conversation (a browser tab, a Telegram chat) keeps its own history, and
everything still logs to Obsidian through agent.run_turn.
"""

import threading

import agent
from system_prompt import build_system_prompt
from tools import obsidian

MAX_HISTORY = 40  # messages kept per conversation; older ones drop off


def _trim(history, keep=MAX_HISTORY):
    """Keep the last `keep` messages, starting on a plain user message so
    tool calls and their results are never split apart."""
    if len(history) <= keep:
        return history
    cut = len(history) - keep
    while cut < len(history):
        m = history[cut]
        if m["role"] == "user" and isinstance(m["content"], str):
            return history[cut:]
        cut += 1
    return []


class Jarvis:
    def __init__(self, mode):
        from main import build_registry

        self.registry = build_registry()
        self.facts = obsidian.load_memory_facts()
        self.system = build_system_prompt(self.facts)
        self._histories = {}
        self._locks = {}
        self._guard = threading.Lock()
        obsidian.log_session_start(mode)

    def _lock_for(self, conv_id):
        with self._guard:
            return self._locks.setdefault(conv_id, threading.Lock())

    def ask(self, conv_id, text, keep=MAX_HISTORY):
        """Send one message in a conversation and return Jarvis's reply.
        keep = how many messages of history to carry (interviews keep more)."""
        text = (text or "").strip()
        if not text:
            return ""
        with self._lock_for(conv_id):
            history = self._histories.get(conv_id, []) + [{"role": "user", "content": text}]
            history, reply = agent.run_turn(history, self.system, self.registry)
            self._histories[conv_id] = _trim(history, keep)
            return reply or "(No reply — check the terminal for errors.)"

    def reset(self, conv_id):
        with self._lock_for(conv_id):
            self._histories.pop(conv_id, None)
