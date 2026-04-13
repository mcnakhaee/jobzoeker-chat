"""
CLI entry point — run the agent from the terminal without the HTTP server.

Usage:
    python chat.py
    python chat.py "Find ggplot2 jobs in Amsterdam"
"""

import asyncio
import logging
import sys
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING)  # keep CLI output clean

from agent.planner import plan
from agent.executor import run
from agent.context import ContextWindow


async def chat_loop(initial_query: str | None = None) -> None:
    context = ContextWindow()

    print("Jobzoeker Chat  (type 'quit' to exit, 'reset' to clear context)\n")

    while True:
        if initial_query:
            user_input = initial_query
            initial_query = None
        else:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "reset":
            context = ContextWindow()
            print("Context cleared.\n")
            continue

        context.add_user(user_input)

        # Plan
        print("\nPlanning...")
        try:
            plan_dict = await plan(query=user_input, context=context)
        except ValueError as e:
            print(f"[error] Planning failed: {e}\n")
            continue

        print(f"\nGoal: {plan_dict['goal']}")
        print("Tasks:")
        for t in plan_dict["tasks"]:
            print(f"  [{t['id']}] {t['description']}  (tool: {t['tool']})")

        print()

        # Execute
        results = await run(plan_dict=plan_dict, context=context)

        for r in results:
            status_icon = "✓" if r["status"] == "done" else "✗"
            print(f"  {status_icon} Task {r['task_id']}: {r['summary']}\n")


def main() -> None:
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    asyncio.run(chat_loop(query))


if __name__ == "__main__":
    main()
