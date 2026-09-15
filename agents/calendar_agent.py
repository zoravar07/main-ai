"""Google Calendar specialist. Read-only.

First run opens a browser for you to approve access. The token is cached in
.google/token.json so it only happens once.

Nothing here writes to your calendar — no creating, moving, or deleting events.
That is a separate decision.
"""

import datetime as dt
from pathlib import Path

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

    _svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _svc


def _fmt(e):
    s = e.get("start", {})
    when = s.get("dateTime") or s.get("date") or "?"
    if "T" in when:
        when = when[:16].replace("T", " ")
    loc = e.get("location")
    who = [a.get("email") for a in e.get("attendees", []) if not a.get("self")]
    bits = [when, e.get("summary", "(no title)")]
    if loc:
        bits.append(f"at {loc}")
    if who:
        bits.append(f"with {', '.join(who[:4])}")
    return " · ".join(bits)


@tool("List calendar events")
def list_events(days: int = 7) -> str:
    """Upcoming events from the primary calendar. days is how far ahead to
    look: 1 for today, 7 for this week, 30 for the month. Returns everything in
    that window — do not try to filter, just pick the window and read the
    results. Read-only."""
    try:
        now = dt.datetime.now(dt.timezone.utc)
        end = now + dt.timedelta(days=max(1, min(days, 90)))
        days = int(days)
        kw = dict(calendarId="primary", timeMin=now.isoformat(),
                  timeMax=end.isoformat(), singleEvents=True,
                  orderBy="startTime", maxResults=50)
        events = _service().events().list(**kw).execute().get("items", [])
    except Exception as e:
        return f"Calendar unavailable: {e}"

    if not events:
        return f"Nothing in the next {days} day(s)."
    return "\n".join(_fmt(e) for e in events)


@tool("Find free time")
def free_time(days: int = 5) -> str:
    """Busy blocks over the next few days, so gaps can be worked out.
    Read-only."""
    try:
        now = dt.datetime.now(dt.timezone.utc)
        end = now + dt.timedelta(days=max(1, min(days, 30)))
        body = {"timeMin": now.isoformat(), "timeMax": end.isoformat(),
                "items": [{"id": "primary"}]}
        busy = _service().freebusy().query(body=body).execute()
        slots = busy["calendars"]["primary"].get("busy", [])
    except Exception as e:
        return f"Calendar unavailable: {e}"

    if not slots:
        return f"Nothing booked in the next {days} days."
    return "\n".join(
        f"{b['start'][:16].replace('T', ' ')} to {b['end'][11:16]}" for b in slots)


@tool("List calendars")
def list_calendars() -> str:
    """Which calendars this account has access to. Read-only."""
    try:
        items = _service().calendarList().list().execute().get("items", [])
    except Exception as e:
        return f"Calendar unavailable: {e}"
    return "\n".join(
        f"{c.get('summary')}{' (primary)' if c.get('primary') else ''}" for c in items)


import claude_cli as _cc
import datetime as _dt


def ask_calendar(question: str):
    try:
        ctx=list_events.run(days=14)
    except Exception as e:
        ctx=f"Calendar unavailable: {e}"
    today=_dt.datetime.now().strftime("%A %d %B %Y, %H:%M")
    return _cc.answer(f"Today is {today}.\n\n{question}",
        "You read Zoravar's calendar. You cannot create or change events. "
        "Work out what 'tomorrow' and 'next week' mean from today's date and "
        "name the actual day. Answer only from the events given.", ctx)


if __name__ == "__main__":
    print(ask_calendar(input("Ask the calendar: ")))
