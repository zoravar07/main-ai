"""Live data for the Zopro dashboard. Real sources only."""
import os, json, sqlite3, requests
from datetime import datetime

ZMONEY_DB = "/Users/zoravarsingh/Desktop/z money agent/data/z_money.db"
SUPABASE_URL = (os.environ.get("VITE_SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("VITE_SUPABASE_ANON_KEY", "")
LAT, LON = 3.139, 101.6869
RATES = {"haiku": (0.80, 4.00), "sonnet": (3.00, 15.00), "opus": (15.00, 75.00)}

def _q(sql, params=()):
    try:
        conn = sqlite3.connect(f"file:{ZMONEY_DB}?mode=ro", uri=True)
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return None

def _cost(model, tin, tout):
    if not model or tin is None or tout is None:
        return None
    m = model.lower()
    for k, (a, b) in RATES.items():
        if k in m:
            return (tin / 1e6) * a + (tout / 1e6) * b
    return None

_pxcache = {"t": 0, "d": {}}


def _prices(tickers):
    """Current price and day change from yfinance. Cached 5 minutes."""
    import time
    if time.time() - _pxcache["t"] < 300 and _pxcache["d"]:
        return _pxcache["d"]
    out = {}
    try:
        import yfinance as yf
        data = yf.download(" ".join(tickers), period="2d", progress=False,
                           auto_adjust=False, threads=True)
        close = data["Close"]
        for tk in tickers:
            try:
                col = close[tk] if hasattr(close, "columns") else close
                vals = [v for v in col.tolist() if v == v]
                if len(vals) >= 2:
                    out[tk] = {"price": vals[-1], "chg": (vals[-1] - vals[-2]) / vals[-2] * 100}
                elif vals:
                    out[tk] = {"price": vals[-1], "chg": None}
            except Exception:
                continue
        _pxcache["t"] = time.time()
        _pxcache["d"] = out
    except Exception:
        pass
    return out


def zmoney():
    runs = _q("SELECT id, started_at, finished_at, status FROM runs ORDER BY id DESC LIMIT 8")
    if runs is None:
        return {"available": False}
    if not runs:
        return {"available": True, "runs": [], "latest": None}
    tok = _q("SELECT run_id, model, SUM(input_tokens) ti, SUM(output_tokens) tos FROM research_outputs GROUP BY run_id, model") or []
    per = {}
    for r in tok:
        c = _cost(r.get("model"), r.get("ti"), r.get("tos"))
        if c is not None:
            per[r["run_id"]] = per.get(r["run_id"], 0) + c
    for r in runs:
        r["cost"] = per.get(r["id"])
        m = _q("SELECT COUNT(*) c FROM research_outputs WHERE run_id = ?", (r["id"],))
        s = _q("SELECT COUNT(*) c FROM conviction WHERE run_id = ?", (r["id"],))
        r["memos"] = m[0]["c"] if m else None
        r["scores"] = s[0]["c"] if s else None
        r["verified"] = (r["memos"] is not None and r["scores"] is not None and r["memos"] >= r["scores"])
    rid = runs[0]["id"]
    wl = _q("SELECT ticker, reason, distance_to_trigger FROM watchlist_items WHERE run_id = (SELECT MAX(run_id) FROM watchlist_items) LIMIT 30")
    nav = _q("SELECT * FROM nav_snapshots ORDER BY rowid DESC LIMIT 1")
    return {
        "available": True, "latest": runs[0], "runs": runs,
        "proposals": _q("SELECT ticker, action, quantity, limit_price, est_cost, conviction, trigger_type, status, rationale FROM proposals WHERE run_id = ? ORDER BY ticker", (rid,)) or [],
        "positions": _q("SELECT ticker, qty, avg_cost, conviction_at_entry, peak_price_since_activation, last_verified_at FROM positions ORDER BY ticker") or [],
        "conviction": _q("SELECT ticker, score FROM conviction WHERE run_id = ? ORDER BY score DESC", (rid,)) or [],
        "watchlist": wl if wl is not None else [],
        "risk_events": _q("SELECT type, detail_json FROM risk_events WHERE run_id = ? LIMIT 12", (rid,)) or [],
        "nav": nav[0] if nav else None,
        "prices": _prices([p["ticker"] for p in (_q(
            "SELECT ticker FROM positions") or [])]) if _q("SELECT 1 FROM positions LIMIT 1") else {},
    }

def _tok():
    e, p = os.environ.get("HUNGRYVAR_EMAIL"), os.environ.get("HUNGRYVAR_PASSWORD")
    if not (SUPABASE_URL and SUPABASE_KEY and e and p):
        return None
    try:
        r = requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                          headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
                          json={"email": e, "password": p}, timeout=12)
        return r.json()["access_token"] if r.status_code == 200 else None
    except Exception:
        return None

def _sb(t, table, params):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                         headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {t}"},
                         params=params, timeout=12)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def hungryvar():
    t = _tok()
    if not t:
        return {"available": False}
    weeks = _sb(t, "weeks", "select=*&status=neq.archived&order=week_start.desc&limit=1") or []
    week = weeks[0] if weeks else None
    plan = week.get("plan") if week else None
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except Exception:
            plan = None
    return {
        "available": True,
        "week": {k: v for k, v in (week or {}).items() if k != "plan"} if week else None,
        "plan": plan,
        "pantry": _sb(t, "pantry", "select=*&limit=60") or [],
        "staples": _sb(t, "staples", "select=*&limit=60") or [],
        "supplements": _sb(t, "supplements", "select=*&limit=40") or [],
        "shops": _sb(t, "grocery_shops", "select=*&limit=20") or [],
        "logs": _sb(t, "meal_logs", "select=*&order=id.desc&limit=20") or [],
    }

def weather():
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": LAT, "longitude": LON,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "Asia/Kuala_Lumpur", "forecast_days": 3}, timeout=12)
        if r.status_code != 200:
            return {"available": False}
        d = r.json()
        return {"available": True, "place": "Kuala Lumpur", "current": d.get("current"), "daily": d.get("daily")}
    except Exception:
        return {"available": False}

def calendar_now():
    try:
        import datetime as _dt
        from calendar_agent import _service
        now = _dt.datetime.now(_dt.timezone.utc)
        r = _service().events().list(
            calendarId="primary", timeMin=now.isoformat(),
            timeMax=(now + _dt.timedelta(days=1)).isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=10).execute()
        out = []
        for e in r.get("items", []):
            st = e.get("start", {})
            w = st.get("dateTime") or st.get("date") or ""
            w = w[5:16].replace("T", " ") if "T" in w else w[5:]
            out.append({"when": w, "title": e.get("summary", "(no title)")})
        return {"available": True, "events": out}
    except Exception:
        return {"available": False}


def mail_now():
    try:
        from gmail_agent import _service as _g
        s = _g()
        def cnt(query):
            return s.users().messages().list(
                userId="me", q=query, maxResults=1).execute().get("resultSizeEstimate", 0)
        return {"available": True, "unread": cnt("is:unread in:inbox category:primary"),
                "unread_today": cnt("is:unread in:inbox category:primary newer_than:1d")}
    except Exception:
        return {"available": False}


def _today_meals(plan):
    """Today's meals. Plan days are weekday abbreviations; falls back to the
    first day when the plan is for a future week."""
    import datetime as _d
    if not plan:
        return None
    days = plan if isinstance(plan, list) else (plan.get("days") or [])
    if not isinstance(days, list) or not days:
        return None
    today = _d.date.today().strftime("%a")
    pick = next((d for d in days if isinstance(d, dict)
                 and str(d.get("day", "")).startswith(today)), None)
    future = pick is None
    if pick is None:
        pick = days[0]
    meals = pick.get("meals") or []
    if not isinstance(meals, list):
        return None
    return {"day": pick.get("day"), "future": future,
            "meals": [{"slot": m.get("slot"), "name": m.get("name"),
                       "kcal": m.get("kcal"), "protein": m.get("protein")}
                      for m in meals if isinstance(m, dict)]}


def _hv():
    h = hungryvar()
    if h.get("available"):
        h["today"] = _today_meals(h.get("plan"))
    return h


def full_status():
    return {"time": datetime.now().isoformat(), "zmoney": zmoney(),
            "hungryvar": _hv(), "weather": weather(),
            "calendar": calendar_now(), "mail": mail_now()}
