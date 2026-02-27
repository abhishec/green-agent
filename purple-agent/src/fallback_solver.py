from __future__ import annotations
import asyncio
from typing import Callable, Awaitable

import anthropic

from src.config import FALLBACK_MODEL, ANTHROPIC_API_KEY

MAX_ITERATIONS = 20


async def solve_with_claude(
    task_text: str,
    policy_doc: str,
    tools: list[dict],
    on_tool_call: Callable[[str, dict], Awaitable[dict]],
    session_id: str,
) -> str:
    """
    Direct Claude SDK fallback when BrainOS is unavailable.
    Runs an agentic tool-use loop, calling on_tool_call for each tool_use block.
    Returns the final text answer.
    """
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = f"""You are a helpful business operations assistant.

POLICY:
{policy_doc}

Use the available tools to complete the task. Be precise with tool calls.
After completing all necessary actions, provide a clear summary of what was done."""

    messages: list[dict] = [{"role": "user", "content": task_text}]

    for _ in range(MAX_ITERATIONS):
        response = await client.messages.create(
            model=FALLBACK_MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        # Collect assistant message content
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn":
            # Extract final text
            for block in assistant_content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason != "tool_use":
            break

        # Process tool calls
        tool_results = []
        for block in assistant_content:
            if block.type != "tool_use":
                continue
            tool_name = block.name
            tool_params = block.input if isinstance(block.input, dict) else {}
            result = await on_tool_call(tool_name, tool_params)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return "Task completed. See tool call results for details."
