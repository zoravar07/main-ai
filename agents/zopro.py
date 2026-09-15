import os
from style import STYLE
import claude_cli
from apps import ask_apps
from crewai import Agent, Task, Crew, LLM
from internship_buddy import ask_internship_buddy, query_memory
from zmoney import ask_zmoney
from hungryvar import ask_hungryvar
from research import ask_researcher
from calendar_agent import ask_calendar
from gmail_agent import ask_gmail

llm = LLM(model="claude-sonnet-4-5-20250929")

ROUTES = ("internship", "zmoney", "hungryvar", "research", "calendar", "mail", "apps", "direct")

def _router():
    return Agent(
    role="Zopro Router",
    goal="Decide whether a request should go to a specialist or be answered directly",
    backstory="""You classify incoming requests. You have three specialists:

    'internship' - internship work, resumes, interview prep, job search, career.

    'zmoney' - Zoravar's investment research system. Anything about his portfolio,
    holdings, trades, proposals, conviction scores, pipeline runs, tickers, or the
    Zmoney codebase itself. Note that Zmoney was originally called Zopro, so a
    question about trading is 'zmoney' even if it says Zopro.

    'hungryvar' - Zoravar's meal planning app. Meals, recipes, groceries, pantry,
    what he's eating or planning to eat, shopping lists, food budget.

    'research' - anything needing real work rather than recall. Two kinds:
    looking things up (current events, prices, products, comparisons, drafting
    documents), and anything about files or folders on this Mac — tidying,
    organising, finding, renaming, what's in a directory, disk clutter. If
    answering would need going and actually looking, it's 'research'.

Reply with ONLY one word: 'internship', 'zmoney', 'hungryvar', 'research',
    or 'direct' if it matches none of them.""" + STYLE,
    llm=llm,
        verbose=False,
    )


ROUTE_DESC = """
internship - internship work, resumes, interview prep, job search, career.
zmoney - his investment system: portfolio, holdings, trades, proposals,
  conviction scores, tickers. Was once called Zopro, so trading questions
  about "Zopro" are zmoney.
hungryvar - meal planning: meals, recipes, groceries, pantry, food budget.
research - needs going and finding out: current events, prices, products,
  comparisons, drafting documents, or anything about files and folders on
  this Mac. Not questions about Zoravar's own past, which are internship.
calendar - his schedule, appointments, when he is free.
mail - his email: unread, who wrote, summarising, drafting a reply.
apps - doing something on his Mac: open an app or a web page, play or pause
  music, what's playing, add a reminder or a note, list reminders, read or
  summarise the page he's looking at now, list his open tabs.
direct - none of the above, or general chat.
"""


def classify(question: str) -> str:
    r = claude_cli.classify(question, ROUTE_DESC)
    for route in ROUTES:
        if route in r:
            return route
    return "direct"


def answer_directly(question: str):
    """General chat, free via Claude Code. Memory is fetched first so it never
    has to invent facts about Zoravar."""
    ctx = ""
    low = question.lower()
    if any(w in low for w in ("i ","my ","me ","zoravar")):
        try:
            from internship_buddy import query_memory
            ctx = query_memory.run(question)
        except Exception:
            pass
    return claude_cli.answer(question,
        "You are Zopro, a personal assistant for Zoravar. If asked your name, "
        "what you are, or what model you run on, say you're Zopro — never "
        "mention Claude, Anthropic, or Sonnet. Never invent facts about him, "
        "his work or his projects. If the data below does not answer it, say "
        "you do not know. Greet him by name, briefly, like a friend would.", ctx)


def ask_zopro(question: str):
    route = classify(question)

    if route == "internship":
        print("[Zopro] Routing to Internship & Career Assistant...")
        return ask_internship_buddy(question)

    if route == "zmoney":
        print("[Zopro] Routing to Zmoney Analyst...")
        return ask_zmoney(question)

    if route == "hungryvar":
        print("[Zopro] Routing to Hungryvar Assistant...")
        return ask_hungryvar(question)

    if route == "research":
        print("[Zopro] Routing to Research Assistant...")
        return ask_researcher(question)

    if route == "calendar":
        print("[Zopro] Routing to Calendar Assistant...")
        return ask_calendar(question)

    if route == "mail":
        print("[Zopro] Routing to Mail Assistant...")
        return ask_gmail(question)

    if route == "apps":
        print("[Zopro] Routing to Mac Assistant...")
        return ask_apps(question)

    print("[Zopro] Handling directly...")
    return answer_directly(question)


if __name__ == "__main__":
    question = input("Ask Zopro: ")
    response = ask_zopro(question)
    print(response)
