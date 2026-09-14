import os
import sqlite3
import requests
from style import STYLE
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

ANYTHINGLLM_URL = "http://localhost:3001/api/v1"
ANYTHINGLLM_KEY = os.environ["ANYTHINGLLM_API_KEY"]
WORKSPACE_SLUG = "zopro-brain"

ZMONEY_DB = "/Users/zoravarsingh/Desktop/z money agent/data/z_money.db"


@tool("Query Zoravar's Memory")
def query_memory(question: str) -> str:
    """Query zopro-brain (AnythingLLM) for background on the Zmoney project — its
    architecture, strategy, known bugs, and design decisions. Use this for questions
    about how Zmoney works. Use query_zmoney_db for live data."""
    response = requests.post(
        f"{ANYTHINGLLM_URL}/workspace/{WORKSPACE_SLUG}/chat",
        headers={"Authorization": f"Bearer {ANYTHINGLLM_KEY}"},
        json={"message": question, "mode": "chat"}
    )
    return response.json().get("textResponse", "No answer found.")


@tool("Query Zmoney Database")
def query_zmoney_db(sql: str) -> str:
    """Run a read-only SELECT against the live Zmoney SQLite database for current
    state: runs, positions, proposals, conviction scores, risk events.

    Tables and their real columns:
      runs(id, started_at, finished_at, status, config_snapshot_json, error)
      positions(id, ticker, qty, avg_cost, opened_at, source, last_verified_at,
                conviction_at_entry, peak_price_since_activation)
      proposals(id, run_id, ticker, action, quantity, order_type, limit_price,
                est_cost, conviction, rationale, risk_checks_json, trigger_type,
                status, created_at, filled_at, fill_price)
      conviction(id, run_id, ticker, score, weights_snapshot_json, derivation_json)
      candidates, research_outputs, risk_events, briefings, nav_snapshots,
      journal_entries, watchlist_items, position_imports, config_versions

    Notes: positions has no run_id — it is the current book, not a per-run snapshot.
    filled_at and fill_price are never written and are always NULL.
    Always include run_id when reporting proposals or conviction scores.
    """
    stripped = sql.strip().rstrip(";").strip()
    if not stripped.lower().startswith("select"):
        return "Refused: only SELECT statements are allowed."
    if ";" in stripped:
        return "Refused: only one statement at a time."

    try:
        conn = sqlite3.connect(f"file:{ZMONEY_DB}?mode=ro", uri=True)
        cur = conn.execute(stripped)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(100)
        conn.close()
    except Exception as e:
        return f"Query failed: {e}"

    if not rows:
        return "No rows returned."
    lines = [" | ".join(cols)]
    lines += [" | ".join("NULL" if v is None else str(v) for v in r) for r in rows]
    return "\n".join(lines)


llm = LLM(model="claude-sonnet-4-5-20250929")

zmoney = Agent(
    role="Zmoney Analyst",
    goal="""Answer Zoravar's questions about his Zmoney trading system using its real
    memory and its live database. Never invent numbers, tickers, or outcomes.""",
    backstory="""You are the specialist for Zmoney, Zoravar's semi-automated investment
    research system. Two tools: query_memory for how the system works, query_zmoney_db
    for what it currently says.

    Zmoney generates proposals. It does not place trades — there is no broker connection
    in the codebase. Zoravar types every order into IBKR himself. Never describe a
    proposal as a trade that happened.

    Always report the run_id alongside any proposal or conviction score.

    A known bug once let a fabricated conviction fire real exit proposals when
    research memos failed. Before treating any proposal or conviction score from a
    run as real, verify that run produced research: compare
    COUNT(*) FROM research_outputs WHERE run_id = N against
    COUNT(*) FROM conviction WHERE run_id = N. If memos are fewer than convictions,
    some scores have no research behind them — say so and treat the affected
    proposals as suspect.

    Do not reason about whether a specific score "looks" fabricated. A score near 50
    is not evidence of the bug, and a score far from 50 is not evidence against it.
    The memo count is the only check that means anything. If you have not run it, say
    you have not verified rather than implying the numbers are sound.

    Talk like a smart, casual friend. No headers everywhere, no emoji, no "Pro Tips"
    sections, minimal bold. Lead with the answer. If the data does not support an
    answer, say that plainly instead of filling the gap.""" + STYLE,
    llm=llm,
    tools=[query_memory, query_zmoney_db],
    verbose=True
)


def ask_zmoney(question: str):
    task = Task(
        description=question,
        expected_output="A direct, useful answer using only real facts from memory or the database. Flag missing data rather than inventing it.",
        agent=zmoney
    )
    crew = Crew(agents=[zmoney], tasks=[task])
    return crew.kickoff()


if __name__ == "__main__":
    question = input("Ask Zmoney: ")
    print(ask_zmoney(question))


import claude_cli as _cc
import json as _json


def ask_zmoney(question: str):
    """Free path: read the database in Python, reason in Claude Code."""
    try:
        from status import zmoney as _z
        ctx = _json.dumps(_z(), default=str)[:14000]
    except Exception as e:
        ctx = f"Database unavailable: {e}"
    return _cc.answer(question,
        "You are the analyst for Zmoney, Zoravar's investment research system. "
        "It generates proposals; it does not place trades. Never call a proposal "
        "a completed trade. Always give the run_id with any proposal or score. "
        "Answer only from the data given.", ctx)
