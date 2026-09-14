import os
import requests
from style import STYLE
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

ANYTHINGLLM_URL = "http://localhost:3001/api/v1"
ANYTHINGLLM_KEY = os.environ["ANYTHINGLLM_API_KEY"]
WORKSPACE_SLUG = "zopro-brain"

@tool("Query Zoravar's Memory")
def query_memory(question: str) -> str:
    """Query zopro-brain (AnythingLLM) for real facts about Zoravar's background, 
    work, and projects. Use this before answering anything that needs real details."""
    response = requests.post(
        f"{ANYTHINGLLM_URL}/workspace/{WORKSPACE_SLUG}/chat",
        headers={"Authorization": f"Bearer {ANYTHINGLLM_KEY}"},
        json={"message": question, "mode": "chat"}
    )
    return response.json().get("textResponse", "No answer found.")

llm = LLM(model="claude-sonnet-4-5-20250929")

internship_buddy = Agent(
    role="Internship & Career Assistant",
    goal="Help Zoravar with internship work, resumes, interview prep, and job search using his REAL background. Never invent numbers or details, always check memory first.",
    backstory="""You help Zoravar with career/internship tasks. You do NOT know 
    his background from memory - you must use the Query Zoravar's Memory tool to 
    look up real facts before answering. Never invent metrics, numbers, or specific 
    details you haven't confirmed. Talk like a smart, casual friend, not corporate, 
    not stiff, minimal bold formatting, no headers-everywhere, no Pro Tips sections. 
    Lead with the answer, then explain why.""" + STYLE,
    llm=llm,
    tools=[query_memory],
    verbose=True
)

def ask_internship_buddy(question: str):
    task = Task(
        description=question,
        expected_output="A direct, useful answer using ONLY real facts retrieved from memory. Flag clearly if specific numbers or metrics aren't available rather than making them up.",
        agent=internship_buddy
    )
    crew = Crew(agents=[internship_buddy], tasks=[task])
    result = crew.kickoff()
    return result

if __name__ == "__main__":
    question = input("Ask Internship Buddy: ")
    response = ask_internship_buddy(question)
    print(response)


import claude_cli as _cc


def ask_internship_buddy(question: str):
    """Free path: pull memory deterministically, reason in Claude Code."""
    try:
        ctx = query_memory.run(question)
    except Exception:
        ctx = ""
    return _cc.answer(question,
        "You are Zoravar's internship and career assistant. Answer only from "
        "the data given. Never invent metrics, dates or achievements. Say "
        "plainly where the record is thin.", ctx)
