"""The SQLite database: one file (D7). Store what was decided, compute what can be counted."""
import sqlite3

from monitor.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY,
    url           TEXT NOT NULL UNIQUE,     -- same article twice is impossible (D7)
    source_id     TEXT NOT NULL,            -- matches an id in sources.yaml
    source_tier   TEXT NOT NULL,            -- 'national' or 'international', at fetch time
    lang          TEXT NOT NULL,
    title         TEXT NOT NULL,
    summary       TEXT,
    published_at  TEXT,                     -- when the publisher posted it (UTC)
    fetched_at    TEXT NOT NULL,            -- when we first saw it (UTC)
    image_url     TEXT,                     -- the publisher's own image from the feed (for the email)
    embedding     BLOB,                     -- the meaning as numbers (D8); filled after fetch
    story_id      INTEGER,                  -- id of the first item in its story
    story_score   REAL                      -- similarity to the best match (NULL = started a new story)
);

CREATE TABLE IF NOT EXISTS source_runs (
    id           INTEGER PRIMARY KEY,
    run_at       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    status       TEXT NOT NULL,             -- 'ok' or 'error'
    items_found  INTEGER NOT NULL DEFAULT 0,
    items_new    INTEGER NOT NULL DEFAULT 0,
    error        TEXT                       -- e.g. 'HTTP 403', shown in the briefing
);

-- The AI's judgement of each article.
CREATE TABLE IF NOT EXISTS classifications (
    id             INTEGER PRIMARY KEY,
    item_id        INTEGER NOT NULL,
    created_at     TEXT NOT NULL,
    model          TEXT NOT NULL,           -- which model judged it (D14)
    outlet_count   INTEGER NOT NULL,        -- the spread the AI was shown
    justification  TEXT NOT NULL,
    relevance      TEXT NOT NULL,           -- on_topic / off_topic
    themes         TEXT NOT NULL,           -- JSON list, e.g. ["aviation_visa_entry"]
    sentiment      TEXT,
    priority       TEXT NOT NULL            -- high / medium / low / none
);

-- Decisions about a story: things that can't be counted from its articles.
CREATE TABLE IF NOT EXISTS stories (
    id                  INTEGER PRIMARY KEY,  -- same as items.story_id
    priority            TEXT,                 -- highest current priority of its articles
    judged_outlet_count INTEGER,              -- spread at the last judgement; more now = re-judge (D10)
    alerted_at          TEXT                  -- when an alert went out (one alert per story)
);

-- Each daily briefing or alert: the draft, the number-check warnings, and later the approval.
CREATE TABLE IF NOT EXISTS briefings (
    id          INTEGER PRIMARY KEY,
    created_at  TEXT NOT NULL,
    text        TEXT NOT NULL,              -- the full draft, header to source list
    warnings    TEXT NOT NULL,              -- JSON list, shown to the analyst only
    status      TEXT NOT NULL DEFAULT 'draft',  -- draft / approved / rejected
    kind        TEXT NOT NULL DEFAULT 'briefing',  -- 'briefing' or 'alert': both go through the same approval
    final_text  TEXT,                       -- what was actually sent, after the analyst's edits
    decided_by  TEXT,
    decided_at  TEXT
);

-- Spread of each story, computed fresh from items, so the counts can never be out of date.
CREATE VIEW IF NOT EXISTS story_spread AS
SELECT story_id                                        AS id,
       MIN(fetched_at)                                 AS first_seen,
       MAX(fetched_at)                                 AS last_seen,
       COUNT(DISTINCT source_id)                       AS outlet_count,
       MAX(source_tier = 'international')              AS has_international
FROM items
WHERE story_id IS NOT NULL
GROUP BY story_id;
"""


def connect() -> sqlite3.Connection:
    """Open the database, creating the file and tables on first use."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts: row["title"]
    conn.executescript(SCHEMA)
    return conn


def merge_story_decisions(conn, keep: int, other: int) -> None:
    """When two stories merge (D27), merge their decisions too: alerted stays alerted."""
    rows = {r["id"]: r for r in conn.execute("SELECT * FROM stories WHERE id IN (?, ?)", (keep, other))}
    if other not in rows:
        return
    if keep not in rows:
        conn.execute("UPDATE stories SET id = ? WHERE id = ?", (keep, other))
        return
    alerts = [r["alerted_at"] for r in rows.values() if r["alerted_at"]]
    conn.execute("UPDATE stories SET alerted_at = ? WHERE id = ?",
                 (min(alerts) if alerts else None, keep))           # earliest alert, if any
    conn.execute("DELETE FROM stories WHERE id = ?", (other,))
