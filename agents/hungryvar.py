import os
import requests
from dotenv import load_dotenv
from style import STYLE
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

load_dotenv("/Users/zoravarsingh/Desktop/hungryvar_Main/.env.local")

ANYTHINGLLM_URL = "http://localhost:3001/api/v1"
ANYTHINGLLM_KEY = os.environ["ANYTHINGLLM_API_KEY"]
WORKSPACE_SLUG = "zopro-brain"

SUPABASE_URL = os.environ["VITE_SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["VITE_SUPABASE_ANON_KEY"]
HUNGRYVAR_EMAIL = os.environ["HUNGRYVAR_EMAIL"]
HUNGRYVAR_PASSWORD = os.environ["HUNGRYVAR_PASSWORD"]

TABLES = (
    "weeks", "meal_logs", "grocery_shops", "pantry", "custom_items",
    "supplements", "staples", "have_enough", "profile", "rules",
)

_session_token = None


def _get_token() -> str:
    """Sign in once per process and cache the access token. Every table has row
    level security, so an unauthenticated request returns zero rows."""
    global _session_token
    if _session_token:
        return _session_token

    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        json={"email": HUNGRYVAR_EMAIL, "password": HUNGRYVAR_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Hungryvar sign-in failed ({r.status_code}): {r.text[:200]}")

    _session_token = r.json()["access_token"]
    return _session_token


@tool("Query Zoravar's Memory")
def query_memory(question: str) -> str:
    """Query zopro-brain (AnythingLLM) for background on Zoravar and his projects.
    Use query_hungryvar for live meal planning data."""
    response = requests.post(
        f"{ANYTHINGLLM_URL}/workspace/{WORKSPACE_SLUG}/chat",
        headers={"Authorization": f"Bearer {ANYTHINGLLM_KEY}"},
        json={"message": question, "mode": "chat"}
    )
    return response.json().get("textResponse", "No answer found.")


@tool("Query Hungryvar")
def query_hungryvar(table: str, params: str = "select=*&limit=20") -> str:
    """Read a table from the Hungryvar Supabase database (read-only).

    Tables: weeks, meal_logs, grocery_shops, pantry, custom_items, supplements,
    staples, have_enough, profile, rules

    params is a PostgREST query string. Examples:
      "select=*&limit=5"                       first five rows, all columns
      "select=*&order=created_at.desc&limit=10" ten most recent
      "select=*&name=eq.rice"                  rows where name equals rice

    If you don't know a table's columns, query it with "select=*&limit=1" first
    and read the column names off the result.

    Planned meals live in 'weeks'. 'meal_logs' is for meals actually eaten and is
    currently empty — a question about what's planned for a given day is a 'weeks'
    question, not a 'meal_logs' one.
    """
    if table not in TABLES:
        return f"Unknown table '{table}'. Available: {', '.join(TABLES)}"

    try:
        token = _get_token()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}"},
            params=params,
            timeout=20,
        )
    except Exception as e:
        return f"Request failed: {e}"

    if r.status_code != 200:
        return f"Query failed ({r.status_code}): {r.text[:300]}"

    rows = r.json()
    if not rows:
        return "No rows returned."
    return str(rows[:20])


llm = LLM(model="claude-sonnet-4-5-20250929")

hungryvar = Agent(
    role="Hungryvar Assistant",
    goal="""Answer Zoravar's questions about his meal planning app using its real
    data. Never invent meals, ingredients, quantities, or logged entries.""",
    backstory="""You are the specialist for Hungryvar, Zoravar's meal planning app.
    It's a React frontend on Vercel with data in Supabase. You read that data with
    query_hungryvar; use query_memory for background on Zoravar himself.

    You read the database, you don't write to it. If Zoravar wants something added
    or changed, tell him what to do in the app rather than claiming you've done it.

    If a table is empty or a query returns nothing, say so plainly. Don't fill the
    gap with a plausible-sounding meal plan — an invented answer here is worse than
    no answer, because he might shop from it.

    Talk like a smart, casual friend. No headers everywhere, no emoji, minimal bold,
    no "Pro Tips" sections. Lead with the answer.""" + STYLE,
    llm=llm,
    tools=[query_memory, query_hungryvar],
    verbose=True
)


def ask_hungryvar(question: str):
    task = Task(
        description=question,
        expected_output="A direct, useful answer using only real data from Hungryvar. Flag missing data rather than inventing it.",
        agent=hungryvar
    )
    crew = Crew(agents=[hungryvar], tasks=[task])
    return crew.kickoff()


if __name__ == "__main__":
    question = input("Ask Hungryvar: ")
    print(ask_hungryvar(question))


import claude_cli as _cc
import json as _json


def ask_hungryvar(question: str):
    try:
        from status import _hv
        ctx=_json.dumps(_hv(),default=str)[:14000]
    except Exception as e:
        ctx=f"Hungryvar unavailable: {e}"
    return _cc.answer(question,
        "You are the assistant for Hungryvar, Zoravar's meal planning app. "
        "You read its data; you do not change it. Never invent meals or "
        "ingredients. If a table is empty, say so.", ctx)
