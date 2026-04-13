import json
import os
import logging
from openai import AsyncOpenAI
from openai._types import NOT_GIVEN

logger = logging.getLogger(__name__)


def get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY env var is not set")
    return AsyncOpenAI(api_key=api_key)


async def call_llm(
    messages: list[dict],
    system_prompt: str,
    model: str = "gpt-4.1-mini",
    is_json: bool = False,
    tools: list[dict] | None = None,
) -> dict:
    """
    Single async LLM call using the OpenAI Responses API.

    Args:
        messages:      Conversation turns — list of {"role": "user"|"assistant", "content": "..."}.
                       Also accepts function_call / function_call_output items for tool loops.
        system_prompt: System instructions. Passed as `instructions` to the Responses API.
        model:         OpenAI model ID.
        is_json:       If True, forces JSON output format (use for the planner).
        tools:         Tool definitions in Responses API format (from config.py ALL_TOOLS).

    Returns:
        {
          "text": str,             # model's text response ("" if only tool calls were made)
          "tool_calls": [          # empty list if no tool calls
            {"name": str, "args": dict, "call_id": str}
          ]
        }
    """
    client = get_client()

    # The Responses API requires the word "json" to appear somewhere in `input`
    # (not just `instructions`) when using json_object format.
    input_messages = messages + [{"role": "user", "content": "Return valid JSON."}] if is_json else messages

    kwargs: dict = {
        "model": model,
        "instructions": system_prompt,
        "input": input_messages,
        "tools": tools or [],
    }
    if is_json:
        kwargs["text"] = {"format": {"type": "json_object"}}

    logger.debug("llm.call model=%s is_json=%s n_tools=%s", model, is_json, len(tools or []))

    response = await client.responses.create(**kwargs)

    tool_calls = [
        {
            "name": item.name,
            "args": json.loads(item.arguments),
            "call_id": item.call_id,
        }
        for item in response.output
        if item.type == "function_call"
    ]

    text = response.output_text or ""

    logger.debug("llm.call.ok text_len=%s n_tool_calls=%s", len(text), len(tool_calls))
    return {"text": text, "tool_calls": tool_calls}
