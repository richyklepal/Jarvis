import os
import anthropic

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = anthropic.Anthropic(api_key=key)
    return _client


def call(messages, system, tools=None):
    """Non-streaming call with optional tool support. Returns a raw Message object."""
    client = _get_client()
    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

    kwargs = {
        "model": model,
        "max_tokens": 4096,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    try:
        return client.messages.create(**kwargs)
    except anthropic.APIConnectionError:
        raise RuntimeError("[Can't reach the API — check your connection.]")
    except anthropic.RateLimitError:
        raise RuntimeError("[Rate limit — wait a moment and try again.]")
    except anthropic.AuthenticationError:
        raise RuntimeError("[Auth failed — check ANTHROPIC_API_KEY in your .env.]")
    except anthropic.APIError as e:
        raise RuntimeError(f"[API error: {e}]")


def stream(messages, system):
    """Streaming text call (no tools). Yields ("text", chunk) or ("error", msg)."""
    client = _get_client()
    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

    try:
        with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system,
            messages=messages,
        ) as s:
            for chunk in s.text_stream:
                yield "text", chunk

    except anthropic.APIConnectionError:
        yield "error", "[Can't reach the API — check your connection.]"
    except anthropic.RateLimitError:
        yield "error", "[Rate limit — wait a moment and try again.]"
    except anthropic.AuthenticationError:
        yield "error", "[Auth failed — check ANTHROPIC_API_KEY in your .env.]"
    except anthropic.APIError as e:
        yield "error", f"[API error: {e}]"
