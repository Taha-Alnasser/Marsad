"""The web endpoints n8n calls. Python does the work; n8n decides when (D6)."""
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from monitor import alerts, briefing, classify, config, dashboard, db, demo, ingest, stories

app = FastAPI(title="Media monitor")


@app.get("/health")
def health():
    return {"status": "ok"}


INGEST_LOCK = Lock()     # one run at a time: a clock tick and a button press must not overlap


@app.post("/ingest")
def run_ingest():
    """Fetch all feeds, group new articles into stories, then label them."""
    if not INGEST_LOCK.acquire(blocking=False):
        return {"busy": True, "alerts": []}             # a run is already going; skip this one
    try:
        return ingest_once()
    finally:
        INGEST_LOCK.release()


def ingest_once():
    sources = ingest.run()
    # If OpenAI is down, each step fails on its own: articles are already saved,
    # and the next successful run picks up whatever was missed (D8).
    try:
        grouping = stories.run()
    except Exception as e:
        grouping = {"error": str(e)[:200]}
    try:
        labels = classify.run()
    except Exception as e:
        labels = {"error": str(e)[:200]}
    return {
        "alerts": alerts.pending(),          # new high-risk stories for n8n to send to the analyst
        "new_articles": sum(s["new"] for s in sources),
        "sources_down": [{"source": s["source"], "error": s["error"]}
                         for s in sources if s["status"] == "error"],
        "stories": grouping,
        "classified": labels,
    }


@app.post("/briefing")
def run_briefing():
    """Draft today's briefing; n8n calls this at 06:00 and sends it to the analyst."""
    return briefing.run()


class Decision(BaseModel):
    status: str        # "approved" or "rejected"
    text: str = ""     # the briefing as the analyst left it
    by: str = ""       # who decided


@app.post("/briefing/{briefing_id}/decision")
def record_decision(briefing_id: int, d: Decision):
    """The audit trail: what was approved, by whom, when (D19)."""
    conn = db.connect()
    conn.execute("""UPDATE briefings SET status = ?, final_text = ?, decided_by = ?, decided_at = ?
                    WHERE id = ?""", (d.status, d.text, d.by,
                                      datetime.now(timezone.utc).isoformat(timespec="seconds"), briefing_id))
    conn.commit()
    return {"ok": True, "html": briefing.to_email_html(d.text, d.by)}   # the email for the DG's office


@app.get("/demo/feed.xml")
def demo_feed():
    """The demo feed, read by the pipeline like any other RSS source (enable it in sources.yaml)."""
    text = demo.FEED.read_text(encoding="utf-8") if demo.FEED.exists() else "<rss><channel></channel></rss>"
    return Response(text, media_type="application/rss+xml")


# --- The control room (read-only page for the analyst and the demo) ---------------------------
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def control_room():
    return FileResponse(STATIC / "index.html")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/overview")
def overview():
    return dashboard.overview()


@app.get("/briefing/{briefing_id}/view", response_class=HTMLResponse)
def view(briefing_id: int):
    """The email exactly as the DG's office received it (or the draft, if not yet approved)."""
    row = db.connect().execute("SELECT * FROM briefings WHERE id = ?", (briefing_id,)).fetchone()
    return briefing.to_email_html(row["final_text"] or row["text"], row["decided_by"] or "")


@app.post("/run/{job}")
def run_now(job: str):
    """The control room's buttons: start an n8n workflow now instead of waiting for its schedule.
    job = "ingest" (fetch news now), "briefing" (send the briefing to the analyst now) or "crisis" (demo)."""
    message = {"ingest": "Fetching news now.", "briefing": "Started. The analyst email is on its way."}.get(job)
    if job == "crisis":
        message = f"Published “{demo.add()}”. Fetching news now."
        job = "ingest"
    try:
        httpx.post(f"{config.N8N_URL}/webhook/{job}-now", timeout=10).raise_for_status()
    except Exception:
        return {"ok": False, "message": f"n8n didn't answer. Is the '{job}' workflow switched on?"}
    return {"ok": True, "message": message}
