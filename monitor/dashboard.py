"""Everything the control-room page shows, in one read of the database. Read-only."""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from monitor import config, db

RIYADH = ZoneInfo("Asia/Riyadh")


def riyadh(ts: str | None) -> str | None:
    return datetime.fromisoformat(ts).astimezone(RIYADH).strftime("%d %b %H:%M") if ts else None


def overview() -> dict:
    conn = db.connect()
    names = {s["id"]: s["name"] for s in config.load_sources()}
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    langs = {s["id"]: s["lang"] for s in config.load_sources()}
    per_source = dict(conn.execute("SELECT source_id, COUNT(*) FROM items WHERE fetched_at >= ? GROUP BY source_id",
                                   (since,)).fetchall())
    sources = [{"name": names.get(r["source_id"], r["source_id"]), "demo": r["source_id"] == "demo",
                "status": r["status"], "error": r["error"], "lang": langs.get(r["source_id"], ""),
                "today": per_source.get(r["source_id"], 0)}
               for r in conn.execute("""SELECT * FROM source_runs WHERE id IN
                                        (SELECT MAX(id) FROM source_runs GROUP BY source_id) ORDER BY source_id""")]
    count = lambda sql: conn.execute(sql, (since,)).fetchone()[0]
    funnel = {
        "articles": count("SELECT COUNT(*) FROM items WHERE fetched_at >= ?"),
        "stories": count("SELECT COUNT(DISTINCT story_id) FROM items WHERE fetched_at >= ?"),
        "on_topic": count("""SELECT COUNT(*) FROM items i JOIN classifications c ON c.item_id = i.id
                             WHERE c.relevance = 'on_topic' AND i.fetched_at >= ?"""),
        "alerts": count("SELECT COUNT(*) FROM briefings WHERE kind = 'alert' AND created_at >= ?"),
        "alerts_approved": count("""SELECT COUNT(*) FROM briefings WHERE kind = 'alert' AND status = 'approved'
                                    AND created_at >= ?"""),
        "needs_response": count("""SELECT COUNT(*) FROM stories s JOIN story_spread sp ON sp.id = s.id
                                   WHERE s.priority IN ('high', 'medium') AND sp.last_seen >= ?"""),
    }
    labels = conn.execute("""SELECT c.themes, c.sentiment FROM items i JOIN classifications c ON c.item_id = i.id
                             WHERE c.relevance = 'on_topic' AND i.fetched_at >= ?""", (since,)).fetchall()
    themes = {t: 0 for t in ("strategy_visitors", "destinations_projects", "aviation_visa_entry", "reputational_risk")}
    sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    for row in labels:
        for t in json.loads(row["themes"]):
            themes[t] = themes.get(t, 0) + 1
        sentiment[row["sentiment"]] = sentiment.get(row["sentiment"], 0) + 1

    now = datetime.now(timezone.utc)
    # The next 06:00 Riyadh briefing.
    local = now.astimezone(RIYADH)
    nxt = local.replace(hour=6, minute=0, second=0, microsecond=0)
    nxt = nxt if nxt > local else nxt + timedelta(days=1)
    left = int((nxt - local).total_seconds() // 60)
    next_briefing = f"{nxt:%a} 06:00 · in {left // 60}h {left % 60:02d}m"
    stories = []
    intl = {r["id"] for r in config.load_sources() if r["tier"] == "international"}
    for s in conn.execute("""SELECT s.id, s.priority, s.alerted_at, sp.outlet_count, sp.has_international, sp.first_seen, sp.last_seen
                             FROM stories s JOIN story_spread sp ON sp.id = s.id
                             WHERE s.priority != 'none' AND sp.last_seen >= ?
                             ORDER BY CASE s.priority WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC,
                                      sp.last_seen DESC LIMIT 30""", (since,)):
        lead = conn.execute("""SELECT i.*, c.justification, c.themes, c.sentiment FROM items i
                               JOIN classifications c ON c.item_id = i.id
                               WHERE i.story_id = ? AND c.relevance = 'on_topic' ORDER BY i.id LIMIT 1""",
                            (s["id"],)).fetchone()
        if not lead:
            continue
        outlets = [{"name": names.get(r[0], r[0]), "intl": r[0] in intl} for r in conn.execute(
            "SELECT DISTINCT source_id FROM items WHERE story_id = ?", (s["id"],))]
        alert = conn.execute("""SELECT status, decided_by, decided_at FROM briefings
                                WHERE kind = 'alert' AND text LIKE ? ORDER BY id DESC LIMIT 1""",
                             (f"%{lead['url']}%",)).fetchone() if s["alerted_at"] else None
        stories.append({"alert": {"status": alert["status"], "by": alert["decided_by"],
                                  "at": riyadh(alert["decided_at"])} if alert else None,
                        "source_id": lead["source_id"], "priority": s["priority"], "title": lead["title"], "url": lead["url"],
                        "image": lead["image_url"], "lang": lead["lang"], "why": lead["justification"],
                        "sentiment": lead["sentiment"], "last_seen": riyadh(s["last_seen"]),
                        "themes": json.loads(lead["themes"]), "outlets": outlets,
                        "international": bool(s["has_international"]), "first_seen": riyadh(s["first_seen"])})
    same = lambda a, b: " ".join((a or "").split()) == " ".join((b or "").split())
    reviews = [{"id": r["id"], "kind": r["kind"], "status": r["status"], "by": r["decided_by"],
                "edited": r["final_text"] is not None and not same(r["text"], r["final_text"]),
                "created": riyadh(r["created_at"]), "decided": riyadh(r["decided_at"]),
                "title": r["text"].split("\n")[0].lstrip("# ")}
               for r in conn.execute("SELECT * FROM briefings ORDER BY id DESC LIMIT 12")]
    last_run = conn.execute("SELECT MAX(run_at) FROM source_runs").fetchone()[0]
    return {"now": datetime.now(RIYADH).strftime("%A %d %B · %H:%M"), "last_run": riyadh(last_run),
            "next_briefing": next_briefing, "sources": sources, "funnel": funnel, "stories": stories,
            "reviews": reviews, "themes": themes, "sentiment": sentiment}
