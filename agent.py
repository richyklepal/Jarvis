import brain
from tools import obsidian


def _last_user_text(messages):
    for m in reversed(messages):
        if m["role"] == "user" and isinstance(m["content"], str):
            return m["content"]
    return ""


def run_turn(messages, system, registry):
    """
    Full agent turn: call model, run any tool calls in a loop, return final reply.
    Returns (updated_messages, final_reply_text).
    """
    tools = registry.get_definitions()
    obsidian.log_event("user", _last_user_text(messages))

    try:
        response = brain.call(messages, system, tools)
    except RuntimeError as e:
        obsidian.log_event("error", str(e))
        return messages, str(e)

    while response.stop_reason == "tool_use":
        # Append assistant's response (with tool_use blocks) to history
        messages = messages + [{"role": "assistant", "content": response.content}]

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\n  [Jarvis → {block.name}]", flush=True)
                result = registry.run(block.name, dict(block.input))
                obsidian.log_event(
                    "tool",
                    f"input: {dict(block.input)}\n\nresult:\n{result}",
                    block.name,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages = messages + [{"role": "user", "content": tool_results}]

        try:
            response = brain.call(messages, system, tools)
        except RuntimeError as e:
            obsidian.log_event("error", str(e))
            return messages, str(e)

    # Extract final text reply
    reply = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    obsidian.log_event("jarvis", reply or "(no text reply)")

    if reply:
        messages = messages + [{"role": "assistant", "content": reply}]

    return messages, reply
