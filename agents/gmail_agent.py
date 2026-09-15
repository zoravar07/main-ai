"""Gmail specialist.

Reads mail and creates drafts. It cannot send — the send scope is deliberately
not requested, so sending is not merely disallowed but impossible. Drafts land
in Gmail for Zoravar to review and send himself.
"""

import base64
from email.message import EmailMessage
from pathlib import Path

from style import STYLE
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

GDIR = Path(__file__).parent / ".google"
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

_svc = None


def _service():
    global _svc
    if _svc:
        return _svc
    tok = GDIR / "token.json"
    creds = None
    if tok.exists():
        creds = Credentials.from_authorized_user_file(str(tok), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(GDIR / "credentials.json"), SCOPES)
            creds = flow.run_local_server(port=0)
        tok.write_text(creds.to_json())
    _svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return _svc


def _header(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _body(msg):
    def walk(part):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
        for p in part.get("parts", []) or []:
            got = walk(p)
            if got:
                return got
        return ""
    return walk(msg.get("payload", {})) or msg.get("snippet", "")


@tool("Search inbox")
def search_mail(query: str = "in:inbox", limit: int = 10) -> str:
    """Search Gmail and return matching messages: id, date, sender, subject and
    a snippet. query uses Gmail's own syntax — "is:unread", "from:someone@x.com",
    "newer_than:2d", "has:attachment". Default is the inbox. Read-only."""
    try:
        limit = max(1, min(int(limit), 25))
        res = _service().users().messages().list(
            userId="me", q=query, maxResults=limit).execute()
        ids = [m["id"] for m in res.get("messages", [])]
    except Exception as e:
        return f"Gmail unavailable: {e}"

    if not ids:
        return f"No messages match: {query}"

    out = []
    for i in ids:
        try:
            m = _service().users().messages().get(
                userId="me", id=i, format="metadata",
                metadataHeaders=["From", "Subject", "Date"]).execute()
            out.append(f"[{i}] {_header(m,'Date')[:31]} · {_header(m,'From')}\n"
                       f"    {_header(m,'Subject')}\n    {m.get('snippet','')[:160]}")
        except Exception:
            continue
    return "\n\n".join(out)


@tool("Read an email")
def read_mail(message_id: str) -> str:
    """Full text of one message. Use an id from search_mail. Read-only."""
    try:
        m = _service().users().messages().get(
            userId="me", id=message_id, format="full").execute()
    except Exception as e:
        return f"Could not read that message: {e}"
    return (f"From: {_header(m,'From')}\nTo: {_header(m,'To')}\n"
            f"Date: {_header(m,'Date')}\nSubject: {_header(m,'Subject')}\n\n"
            f"{_body(m)[:6000]}")


@tool("Create a draft")
def create_draft(to: str, subject: str, body: str) -> str:
    """Save a draft in Gmail. It is NOT sent — Zoravar reviews and sends it
    himself. Say clearly that you have drafted, not sent."""
    try:
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        d = _service().users().drafts().create(
            userId="me", body={"message": {"raw": raw}}).execute()
    except Exception as e:
        return f"Could not create the draft: {e}"
    return f"Draft saved (id {d['id']}). It has not been sent — review it in Gmail."


@tool("Inbox summary")
def inbox_counts() -> str:
    """How much unread mail there is, overall and in the last day. Read-only."""
    try:
        s = _service()
        out = []
        for label, q in (("unread", "is:unread"),
                         ("unread today", "is:unread newer_than:1d"),
                         ("inbox", "in:inbox")):
            r = s.users().messages().list(userId="me", q=q, maxResults=1).execute()
            out.append(f"{label}: {r.get('resultSizeEstimate', 0)}")
        return " · ".join(out)
    except Exception as e:
        return f"Gmail unavailable: {e}"


llm = LLM(model="claude-sonnet-4-5-20250929")

gmail_agent = Agent(
    role="Mail Assistant",
    goal="Handle Zoravar's email — read it, summarise it, draft replies.",
    backstory="""You read Zoravar's Gmail and can save drafts.

    You cannot send. The send permission was never granted, so nothing you do
    puts mail in anyone's outbox. When you draft something, say you have
    drafted it and that he needs to send it — never imply it went out.

    When summarising a busy inbox, lead with what actually needs him: things
    waiting on a reply, deadlines, anything from a real person rather than a
    mailing list. Skip the newsletters unless he asks.

    Quote senders and subjects accurately. Never invent an email that isn't in
    the results.""" + STYLE,
    llm=llm,
    tools=[search_mail, read_mail, create_draft, inbox_counts],
    verbose=True,
)


def _ask_gmail_agent(question: str):
    task = Task(
        description=question,
        expected_output="A direct answer from real messages. Drafts are drafts, never sent.",
        agent=gmail_agent,
    )
    return Crew(agents=[gmail_agent], tasks=[task]).kickoff()


if __name__ == "__main__":
    print(ask_gmail(input("Ask about mail: ")))


import claude_cli as _cc


def ask_gmail(question: str):
    """Reading is free via Claude Code. Drafting still needs the agent, since
    it has to call the Gmail API to save the draft."""
    low=question.rsplit("\n\n",1)[-1].lower()
    if any(w in low for w in ("draft","reply","write","respond","compose","send")):
        return _ask_gmail_agent(question)
    try:
        ctx=search_mail.run(query="in:inbox category:primary", limit=15)
        ctx+="\n\n"+inbox_counts.run()
    except Exception as e:
        ctx=f"Gmail unavailable: {e}"
    return _cc.answer(question,
        "You read Zoravar's inbox. Lead with what actually needs him: things "
        "waiting on a reply, deadlines, mail from real people. Skip "
        "newsletters unless asked. Quote senders and subjects accurately and "
        "never invent an email.", ctx)
