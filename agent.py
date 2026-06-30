import brain


def run_turn(messages, system, registry):
    """
    Full agent turn: call model, run any tool calls in a loop, return final reply.
    Returns (updated_messages, final_reply_text).
    """
    tools = registry.get_definitions()

    try:
        response = brain.call(messages, system, tools)
    except RuntimeError as e:
        return messages, str(e)

    while response.stop_reason == "tool_use":
        # Append assistant's response (with tool_use blocks) to history
        messages = messages + [{"role": "assistant", "content": response.content}]

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\n  [Jarvis → {block.name}]", flush=True)
                result = registry.run(block.name, dict(block.input))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages = messages + [{"role": "user", "content": tool_results}]

        try:
            response = brain.call(messages, system, tools)
        except RuntimeError as e:
            return messages, str(e)

    # Extract final text reply
    reply = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    if reply:
        messages = messages + [{"role": "assistant", "content": reply}]

    return messages, reply
