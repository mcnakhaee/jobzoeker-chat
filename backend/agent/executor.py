import json
import logging
from typing import AsyncGenerator
from services.llm import call_llm
from agent.context import ContextWindow
from config import ALL_TOOLS
from tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)

EXECUTOR_PROMPT = """\
You are a job search assistant executing a specific task. You have access to tools.
Call the appropriate tool to complete the task, then stop.

Rules:
- Call at most one tool per task. If no tool is needed, reply directly.
- After a tool returns, summarize the result clearly. Do not dump raw JSON.
- If the tool returns an error or empty result, say so and suggest an alternative.
- Never invent job listings or company information.

Output format:
- Job results: numbered list with title, company, location, one-line summary.
- Notion actions: confirm what was saved and the page title.
- Cover letters: return the full letter text.
- Company info: 3-5 sentence paragraph.

Current task: {task_description}
"""

TOOL_DISPLAY_NAMES = {
    "find_similar_jobs":    "Searching jobs",
    "save_jobs_to_notion":  "Saving to Notion",
    "create_notion_page":   "Creating Notion page",
    "compose_cover_letter": "Writing cover letter",
    "search_company_info":  "Looking up company",
}








async def _compress(tool: str, text: str) -> str:
    if tool in ("none", "job_search"):
        return text
    if tool == "notion":
        return f"[notion] {text.strip().splitlines()[0]}"
    if tool == "cover_letter":
        response = await call_llm(
            messages=[{"role": "user", "content": text}],
            system_prompt="Summarise this cover letter in one sentence: who it's for and what role.",
        )
        return f"[cover_letter] {response['text']}"
    return text


async def run(plan_dict: dict, context: ContextWindow, model: str = "gpt-4o-mini") -> list[dict]:
    """Blocking run — used by CLI. Consumes the generator and discards log events."""
    results = []
    for task in plan_dict["tasks"]:
        task["status"] = "running"
        summary = ""
        async for event in _execute_task(task, context, model):
            if event["type"] == "task_result":
                summary = event["text"]
        task["status"] = "done"
        context.add_assistant(await _compress(task["tool"], summary))
        results.append({"task_id": task["id"], "status": "done", "summary": summary})
    return results



async def _execute_task(
    task: dict,
    context: ContextWindow,
    model: str,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that executes a single task and yields log events throughout.

    Yields (in order):
      {"type": "agent_log",    "task_id": N, "message": str}
      {"type": "tool_call",   "task_id": N, "tool": str, "message": str}
      {"type": "tool_result", "task_id": N, "tool": str, "message": str}
      {"type": "task_result", "task_id": N, "text": str}   ← always last
    """
    task_id = task["id"]
    messages = list(context.get_messages())
    response = {"text": "", "tool_calls": []}

    yield {"type": "agent_log", "task_id": task_id, "message": "Thinking…"}

    for attempt in range(3):
        response = await call_llm(
            messages=messages,
            system_prompt=EXECUTOR_PROMPT.format(task_description=task["description"]),
            model=model,
            tools=ALL_TOOLS,
        )

        if not response["tool_calls"]:
            break

        for tc in response["tool_calls"]:
            name = tc["name"]
            args = tc["args"]
            call_msg = _tool_call_message(name, args)

            logger.info("tool_call tool=%s args=%s", name, args)
            yield {"type": "tool_call", "task_id": task_id, "tool": name, "message": call_msg}

            messages.append({
                "type": "function_call",
                "name": name,
                "arguments": json.dumps(args),
                "call_id": tc["call_id"],
            })

            tool_fn = TOOL_REGISTRY.get(name)
            result = await tool_fn(**args) if tool_fn else {"error": f"unknown tool: {name}"}

            try:
                output = json.dumps(result)
            except (TypeError, ValueError):
                output = json.dumps({"result": str(result)})

            messages.append({
                "type": "function_call_output",
                "call_id": tc["call_id"],
                "output": output,
            })

            result_msg = _tool_result_message(name, result)
            yield {"type": "tool_result", "task_id": task_id, "tool": name, "message": result_msg}

        if attempt < 2:
            yield {"type": "agent_log", "task_id": task_id, "message": "Summarising…"}

    yield {"type": "task_result", "task_id": task_id, "text": response["text"]}

async def run_stream(plan_dict: dict, context: ContextWindow, model: str = "gpt-4o-mini"):
    """
    Async generator for SSE — used by POST /chat/run.

    Event sequence per task:
      task_start → agent_log | tool_call | tool_result (interleaved) → task_done

    Followed by a single `complete` event when all tasks finish.
    """
    for task in plan_dict["tasks"]:
        task["status"] = "running"
        yield {"type": "task_start", "task_id": task["id"]}

        summary = ""
        async for event in _execute_task(task, context, model):
            if event["type"] == "task_result":
                summary = event["text"]
            else:
                yield event  # forward agent_log / tool_call / tool_result to SSE

        task["status"] = "done"
        context.add_assistant(await _compress(task["tool"], summary))
        yield {"type": "task_done", "task_id": task["id"], "summary": summary}

    yield {"type": "complete"}


def _tool_call_message(name: str, args: dict) -> str:
    """Human-readable one-liner for a tool invocation."""
    label = TOOL_DISPLAY_NAMES.get(name, name)
    if name == "find_similar_jobs":
        kw = args.get("keyword", "")
        loc = args.get("location")
        return f"{label}: {kw!r}" + (f" in {loc}" if loc else "")
    if name in ("save_jobs_to_notion", "create_notion_page"):
        return f"{label}: {args.get('database_name') or args.get('title', '')!r}"
    if name == "search_company_info":
        return f"{label}: {args.get('company_name', '')!r}"
    if name == "compose_cover_letter":
        snippet = (args.get("job_description") or "")[:60]
        return f"{label}: {snippet}…" if snippet else label
    return label


def _tool_result_message(name: str, result: object) -> str:
    """Human-readable one-liner for a tool result."""
    if not isinstance(result, dict):
        return str(result)[:120]
    if result.get("status") == "error":
        return f"Error: {result.get('message', 'unknown error')}"
    if name == "find_similar_jobs":
        count = result.get("count", 0)
        return f"Found {count} job{'s' if count != 1 else ''}"
    if name == "save_jobs_to_notion":
        return f"Saved to database: {result.get('database_name', '')!r}"
    if name == "create_notion_page":
        return f"Page created: {result.get('title', '')!r}"
    if name == "compose_cover_letter":
        return "Cover letter written"
    if name == "search_company_info":
        return "Company info retrieved"
    return "Done"