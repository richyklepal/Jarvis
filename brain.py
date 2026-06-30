import os
from collections.abc import Generator
import anthropic

_client: anthropic.Anthropic | None = None


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


def stream(
    messages: list[dict],
    system: str,
) -> Generator[tuple[str, str], None, None]:
    """Stream a conversation turn through Claude.

    Yields (event_type, data) tuples:
      ("text",  chunk_str)  — a piece of the reply as it arrives
      ("error", msg_str)    — something went wrong; no more chunks follow

    Tier 2 will extend this to also yield ("tool_call", {...}).
    """
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
