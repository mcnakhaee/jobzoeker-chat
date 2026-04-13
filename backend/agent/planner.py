import json
import logging
from services.llm import call_llm
from agent.context import ContextWindow

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """\
You are a job search planning assistant. Your only job is to read the user's message
and break it into a short, ordered list of concrete tasks.

## Available tools
- job_search   : find_similar_jobs(keyword, location) — search for job listings
- notion       : save_jobs_to_notion(database_name, jobs_summary)
               | create_notion_page(title, content)
- cover_letter : compose_cover_letter(job_description, user_profile)
- company_info : search_company_info(company_name)
- none         : no tool needed — pure reasoning or a clarifying reply

## Rules
1. Return ONLY valid JSON. No markdown fences, no explanation outside the JSON.
2. Keep tasks minimal — do not add steps the user did not ask for.
3. If the request is a simple question or greeting, return a single task with tool "none".
4. If the user refers to results from a previous turn ("those jobs", "the first one"),
   do not re-search — create a task that works with what is already in context.
5. Each task must have exactly these fields: id, description, tool, args, status.
6. status is always "pending" in your output.

## Output schema
{
  "goal": "<one sentence restatement of what the user wants>",
  "tasks": [
    {
      "id": 1,
      "description": "<what this step does, in plain English>",
      "tool": "job_search | notion | cover_letter | company_info | none",
      "args": {},
      "status": "pending"
    }
  ]
}

## Examples

User: "Find Python jobs in Amsterdam"
{"goal":"Find Python job listings in Amsterdam","tasks":[{"id":1,"description":"Search for Python jobs in Amsterdam","tool":"job_search","args":{"keyword":"Python","location":"Amsterdam"},"status":"pending"}]}

User: "Find ggplot2 jobs in Amsterdam and save them to my Notion board"
{"goal":"Find ggplot2 jobs in Amsterdam and save the results to Notion","tasks":[{"id":1,"description":"Search for ggplot2 jobs in Amsterdam","tool":"job_search","args":{"keyword":"ggplot2","location":"Amsterdam"},"status":"pending"},{"id":2,"description":"Save the job results to the Notion jobs board","tool":"notion","args":{"database_name":"ggplot2 Jobs - Amsterdam","jobs_summary":"<results from task 1>"},"status":"pending"}]}

User: "Write me a cover letter for this role: Senior Data Scientist at ASML"
{"goal":"Write a cover letter for a Senior Data Scientist role at ASML","tasks":[{"id":1,"description":"Generate a tailored cover letter","tool":"cover_letter","args":{"job_description":"Senior Data Scientist at ASML","user_profile":""},"status":"pending"}]}

User: "Hi, what can you do?"
{"goal":"Explain the assistant's capabilities","tasks":[{"id":1,"description":"Answer the user's question directly","tool":"none","args":{},"status":"pending"}]}
"""


async def plan(query: str, context: ContextWindow, model: str = "gpt-4.1-mini") -> dict:
    """
    Convert a user query into a structured task plan.

    Args:
        query:   The user's raw message.
        context: Current conversation context (provides history so the planner
                 can detect follow-up turns and avoid re-searching).
        model:   OpenAI model to use.

    Returns:
        Parsed plan dict: {"goal": str, "tasks": [{"id", "description", "tool", "args", "status"}]}

    Raises:
        ValueError: If the LLM returns invalid JSON or the schema is missing required fields.
    """
    messages = context.get_messages() + [{"role": "user", "content": query}]

    logger.info("planner.plan query=%s", query[:80])

    response = await call_llm(
        messages=messages,
        system_prompt=PLANNER_PROMPT,
        model=model,
        is_json=True,
    )

    try:
        plan_dict = json.loads(response["text"])
    except json.JSONDecodeError as e:
        logger.error("planner.invalid_json raw=%s", response["text"][:200])
        raise ValueError(f"Planner returned invalid JSON: {e}") from e

    _validate_plan(plan_dict)

    logger.info("planner.plan.ok goal=%s n_tasks=%s", plan_dict.get("goal", ""), len(plan_dict.get("tasks", [])))
    return plan_dict


def _validate_plan(plan_dict: dict) -> None:
    """Raise ValueError if the plan is missing required fields."""
    if "goal" not in plan_dict:
        raise ValueError("Plan missing 'goal' field")
    if "tasks" not in plan_dict or not isinstance(plan_dict["tasks"], list):
        raise ValueError("Plan missing 'tasks' list")

    required_task_fields = {"id", "description", "tool", "args", "status"}
    for task in plan_dict["tasks"]:
        missing = required_task_fields - set(task.keys())
        if missing:
            raise ValueError(f"Task {task.get('id', '?')} missing fields: {missing}")
