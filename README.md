# Jobzoeker Chat


This project is a job-search agent that, based on the user's request, generates structured plans to help the user with their job search and executes them step by step.

For example, you are looking for AI Enginnering jobs in Amsterdam and you want to generate cover letters for one of the jobs you find interesting and save them to one of your Notion pages.

The project was inspired by my own need and a previous CI/CD pipeline I created to search jobs on LinkedIn and Indeed, filter them and show them in a dashboard/Telegram. (https://github.com/mcnakhaee/jobzoeker_telegram)

---

## What it does

You describe your job search goal to the AI agent. The AI agent then breaks it into tasks, runs each one using (real) defined tools, and reports back.

```
You:   "Find ggplot2 jobs in Amsterdam and save them to Notion"

Plan:  1. Search for LLM jobs in Amsterdam (RAG)  [job_search]
       2. Save results to Notion jobs board       [notion]

Agent: Found 4 jobs. Saved to "ggplot2 Jobs – Amsterdam" in Notion.
```

---

## Agent loop

It uses the built-in OpenAI function calling API and no extra frameworks are used. The loop is three functions:

```
plan(query, context)      →  {"goal": ..., "tasks": [...]}
run(plan, context)        →  [{"task_id", "status", "summary"}, ...]
```

**Planner** — one LLM call with `is_json=True`. Takes the user message and conversation history, returns a structured task list of planned tasks and never calls tools.

**Executor** — iterates over tasks. For each task:
1. LLM call with the task description and all available tools
2. If the model makes a tool call → tool is executed, results are returned, calls the LLM again
3. Repeats up to 3 rounds, then forces a no-tool plain-text response
4. Adds the summary to the shared context so later tasks can reference earlier results (it also performs context management/trimming explained later)

Both stages have their own system prompt (instruction in OpenAI's new response API) and share a `ContextWindow` that carries only `user` and `assistant` messages.

Note: raw tool outputs stay local to the executor loop and are never written to shared context.

---

## Tools

| Tool | Implementation | Notes |
|---|---|---|
| `find_similar_jobs` | A RAG Based on Weaviate vector database and job description to retrieve similar jobs and location | |
| `save_jobs_to_notion` | Notion API — finds or creates a database, appends a page | Real API call |
| `create_notion_page` | Notion API — freeform page | Used for cover letters, notes |
| `compose_cover_letter` | LLM call with structured prompt and user profile information | |
| `search_company_info` | LLM call over the LLM's internal knowledge, no external web search is used | It uses Mistral embedding models and weaviate so it requires configuration|

---

## Context Management strategy

The context window holds only `user` and `assistant` role messages.
It contains no raw JSON, no tool call items, no plan injection.

```
[user]      original query
[assistant] task 1 summary   ← compressed before storage
[user]      follow-up query
[assistant] task 2 summary
...
```

**Rolling Window:** last 10 messages (5 exchanges). Oldest turns dropped first. System prompt and task description are passed fresh on every call and are never stored.

**Compression before storage** — assistant messages are compressed by tool type before being written to context:

| Tool | What gets stored |
|---|---|
| `job_search` | Full summary — planner needs job titles and companies for follow-up turns |
| `notion` | First line only, e.g. `[notion] Saved "ggplot2 Jobs – Amsterdam"` |
| `cover_letter` | LLM-compressed to one sentence, e.g. `[cover_letter] Letter for Data Scientist role at Booking.com` |
| `none` | Full response |

**Text normalisation** — before any message enters the window, noise is stripped:
- User messages: stopwords removed (`a`, `the`, `is`, `to`, etc.)
- Assistant messages: Inspired by this project (https://github.com/JuliusBrussee/caveman/tree/main), a caveman compression is applied which means articles, fillers (`just`, `basically`, `actually`), pleasantries (`certainly`, `of course`), and hedging (`might`, `perhaps`) are dropped from the context (hardcoded).

**Not every tool contains equally important information.**
Information on tools such as saving to Notion or composing a cover letter does not contain the same value as the user's job search query, so they are heavily trimmed in the context. `job_search` results are kept in full so the planner can reference specific jobs by name across turns.

TODO: add layered/tiered context; for example, information specific to the user can be stored in a layer different from the retrieved jobs, since user-specific information could be more important.

---

## Project structure

```
backend/
├── agent/
│   ├── planner.py        # query → task plan (JSON)
│   ├── executor.py       # task loop + tool execution
│   └── context.py        # rolling message window
├── tools/
│   ├── job_search.py     # delegates to RAG service
│   ├── notion.py         # Notion async client
│   ├── cover_letter_generator.py
│   ├── web_search.py
│   └── registry.py       # name → callable mapping
├── services/
│   ├── llm.py            # single call_llm() function (OpenAI Responses API)
│   └── rag.py            # Weaviate async client + near_text search 
├── data/
│   └── index_jobs.py     # one-time indexing script for weaviate (I used Mistral embedding models)
├── config.py             # tool definitions (OpenAI function-calling format)
├── main.py               # FastAPI app
└── test_agent.ipynb      # end-to-end test notebook
```

---

## Setup

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in API keys
```

Required env vars: `OPENAI_API_KEY`, `MISTRAL_API_KEY`, `WEAVIATE_URL`, `WEAVIATE_API_KEY`, `NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID`.

Index jobs into Weaviate (run once, requires `recent_jobs.csv` in `backend/data/`):

```bash
cd backend
python -m data.index_jobs
```

Start the API:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Frontend

Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```

The UI is served at `http://localhost:5173` and expects the backend at `http://localhost:8000`. Both must be running at the same time.


---

## Evaluation scenarios

The simplest systematic way to evaluate the planning and execution stages is a golden dataset: fixed queries mapped to expected tool sequences, then measuring exact-match and partial-match rates. That is not implemented here due to time. Instead, below are five concrete scenarios with explicit pass/fail criteria that can be checked manually or scripted.

---

**Scenario 1 — Basic job search**

> *"Find Python data engineering jobs in Amsterdam"*

| Check | Success |
|---|---|
| Planner produces exactly 1 task with `tool = "job_search"` | ✅ |
| `find_similar_jobs` is called with `keyword` containing "Python" and `location = "Amsterdam"` | ✅ |
| Response contains ≥ 1 job with title, company, and location fields | ✅ |
| No Notion or cover-letter tool is called | ✅ |

---

**Scenario 2 — Multi-step plan (search + save)**

> *"Find ggplot2 jobs in Amsterdam and save them to Notion"*

| Check | Success |
|---|---|
| Planner produces exactly 2 tasks: `job_search` then `notion` | ✅ |
| Task 1 calls `find_similar_jobs`; task 2 calls `save_jobs_to_notion` | ✅ |
| A new page appears in the Notion database | ✅ |
| Task 2 summary references the database name | ✅ |

---

**Scenario 3 — Cover letter with empty profile**

> *"Write a cover letter for a Senior Data Scientist role at ASML"*
> (user profile left blank)

| Check | Success |
|---|---|
| Planner produces 1 task with `tool = "cover_letter"` | ✅ |
| Agent response asks the user for background information rather than hallucinating experience | ✅ |
| No job search is triggered | ✅ |

---

**Scenario 4 — Context carry-over (follow-up turn)**

> Turn 1: *"Find ML engineer jobs in Amsterdam"*
> Turn 2: *"Save the first result to Notion"*

| Check | Success |
|---|---|
| Turn 2 planner does NOT emit a new `job_search` task | ✅ |
| Turn 2 planner emits a `notion` task referencing the job from turn 1 context | ✅ |
| Notion page is created without re-querying Weaviate | ✅ |

Failure here means the context window or caveman compression dropped enough information that the planner couldn't identify the earlier result.

---

**Scenario 5 — Graceful tool error**

> *"Find Fortran jobs in Amsterdam"* (no such jobs in the index)

| Check | Success |
|---|---|
| `find_similar_jobs` returns `count = 0` | ✅ |
| Agent response acknowledges no results were found and suggests an alternative (different keyword or location) | ✅ |
| Agent does not fabricate job listings | ✅ |
| No crash or 500 from the backend | ✅ |


## Trade-offs

**Plan-then-execute vs. ReAct**: The agent generates the full plan before executing anything. This makes the plan visible and debuggable, but it cannot be adjusted during execution if a tool returns something unexpected or fails. Using a ReAct loop could be more flexible but harder to visualise.

**Caveman trimming**: As I explained before, I applied caveman trimming to keep the context short; however, this approach might result in a loss of accuracy in tool calling (it requires investigation to find out what the trade-off is between accuracy and saving tokens).

**Tiered context compression** — Notion and cover letter results are heavily compressed before being stored in the shared context window. They are never referenced again in most conversations, so storing the full text wastes the token budget. Job search results are exempt because the planner needs them for follow-up conversations.

**Sequential vs. parallel agent running** — For now, the agents are run in a sequential manner, meaning failure in one step could lead to failure in subsequent steps. For this particular use case this should be fine, but if the user has more complex queries, ideally we might want the sub-agents to run in parallel.

**Limited tool functionality**: some of the tools are not capable of complext tasks (due to lack of time), for example if a user asks for AI Engineering and MLOps jobs in Rotterdam or Amsterdam the find similar jobs tool cannot divide it into sub-tasks.

---

## Example transcript
![AI job search execution](file://done-scr.png)

![Agent thinking process](file://thinking-scr.png)
Real session captured from the chat UI. User goal: find AI engineering jobs in Amsterdam, save them to Notion, and look up one company.

---

**User →** Find AI engineering jobs in Amsterdam and save them to Notion

**Agent generates plan:**
```
Goal: Find AI engineering jobs in Amsterdam, save the results to Notion,
      
Tasks:
  1. Search for AI engineering jobs in Amsterdam          [job_search]
  2. Save the job results to a Notion database            [notion]
```

**User clicks "Run plan"**

---

**Task 1 — Search for AI engineering jobs in Amsterdam**
```
· Thinking…
→ Searching jobs: 'AI engineering' in Amsterdam
← Found 7 jobs
```
*Summary:*
```
1. AI Engineer — Booking.com (Amsterdam) — Building recommendation models for travel products
2. ML Engineer — Adyen (Amsterdam) — Fraud detection using real-time transaction data
3. Applied AI Engineer — TomTom (Amsterdam) — Navigation and mapping AI systems
4. NLP Engineer — Randstad Digital (Amsterdam) — Conversational AI for HR workflows
5. Computer Vision Engineer — ASML (Eindhoven/Remote) — Semiconductor inspection systems
6. AI Platform Engineer — ABN AMRO (Amsterdam) — Internal LLM tooling and deployment
7. Senior AI Engineer — bol.com (Utrecht) — Product ranking and personalisation
```

**Task 2 — Save results to Notion**
```
· Thinking…
→ Saving to Notion: 'AI Engineering Jobs – Amsterdam'
← Saved to database: 'AI Engineering Jobs – Amsterdam'
```
*Summary:* Saved 7 job listings to the "AI Engineering Jobs – Amsterdam" database in Notion.

**Done** ✓ — 3/3 tasks completed


## How I spend my time spent


| Phase | Time | Notes |
|---|---|---|
| Architecture design | ~%25 | Deciding what tools to use and how the interaction should work between the user and the agent, edge cases and where it might fail |
| Agent planning and execution loop| 30% min |`planner.py`, `executor.py`, `context.py`  Based on two-phase plan/execute mentioned in the assignment |
| Context management | 15% | Rolling window, caveman compression, stopword stripping, per-tool compression rules |
| Tools | 15% | Weaviate RAG setup, Notion API and cover letter prompt were straightforward since I had already worked on similar project |
| Frontend | 10% | I used coding agent and most of the time spent on fine-tunning|
| Debugging and integration | ~%5  | |



**Disclaimer**: I used coding agents (Claude Code) to design and implement the frontend and the chat UI. The backend and the logic were implemented by hand but I used coding agent to add typing, docstrings, overall improvement and debugging.