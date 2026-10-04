"""Fetch every feed, save only new articles, record each feed's health."""
import html
import re
from datetime import datetime, timezone

import feedparser
import httpx

from monitor import config, db


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean(text: str) -> str:
    """Feeds contain HTML tags and codes like &#039;: turn them into plain text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def image_of(e) -> str | None:
    """The publisher's own image for this article, if the feed includes one."""
    for key in ("media_content", "media_thumbnail"):
        if e.get(key) and e[key][0].get("url"):
            return e[key][0]["url"]
    for link in e.get("links", []):
        if link.get("type", "").startswith("image"):
            return link.get("href")
    found = re.search(r'<img[^>]+src="([^"]+)"', e.get("summary", "") or "")
    return found.group(1) if found else None


def fetch(source: dict) -> list:
    """Download one feed and parse it. Raises on timeouts and HTTP errors."""
    r = httpx.get(source["url"], headers={"User-Agent": config.USER_AGENT},
                  timeout=config.FETCH_TIMEOUT_S, follow_redirects=True)
    r.raise_for_status()
    return feedparser.parse(r.content).entries


def ingest_source(conn, source: dict, run_at: str) -> dict:
    """Fetch one source and store its new items. One failing feed never stops the others."""
    try:
        entries = fetch(source)
    except httpx.TimeoutException:
        return log_run(conn, source, run_at, "error", error=f"timeout after {config.FETCH_TIMEOUT_S}s")
    except httpx.HTTPStatusError as e:
        return log_run(conn, source, run_at, "error", error=f"HTTP {e.response.status_code}")
    except Exception as e:
        return log_run(conn, source, run_at, "error", error=str(e)[:200])

    new = 0
    for e in entries:
        if not e.get("link") or not e.get("title"):
            continue
        published = e.get("published_parsed") or e.get("updated_parsed")
        cur = conn.execute(
            """INSERT OR IGNORE INTO items
               (url, source_id, source_tier, lang, title, summary, image_url, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (e.link, source["id"], source["tier"], source["lang"], clean(e.title),
             clean(e.get("summary")), image_of(e),
             datetime(*published[:6], tzinfo=timezone.utc).isoformat() if published else None,
             now_utc()))
        new += cur.rowcount            # 1 if inserted, 0 if the URL was already stored
    return log_run(conn, source, run_at, "ok", found=len(entries), new=new)


def log_run(conn, source, run_at, status, found=0, new=0, error=None) -> dict:
    conn.execute("""INSERT INTO source_runs (run_at, source_id, status, items_found, items_new, error)
                    VALUES (?, ?, ?, ?, ?, ?)""", (run_at, source["id"], status, found, new, error))
    conn.commit()
    return {"source": source["id"], "status": status, "found": found, "new": new, "error": error}


def run() -> list[dict]:
    conn, run_at = db.connect(), now_utc()
    return [ingest_source(conn, s, run_at) for s in config.load_sources()]


if __name__ == "__main__":
    for r in run():
        print(r)
