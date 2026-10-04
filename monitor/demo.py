"""The demo feed: synthetic articles served as an RSS feed, so a live alert can be shown on demand.

    python -m monitor.demo add      # publish the next synthetic article into the feed
    python -m monitor.demo reset    # remove demo articles, their alerts and unapproved drafts (clean slate)
"""
import json
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

from monitor import config, db

FEED = config.ROOT / "data" / "demo_feed.xml"
LOG = config.ROOT / "data" / "demo_published.json"     # which demo articles are already out
ARTICLES = [   # invented for the demo; also used as synthetic cases in the eval
    ("Workers at Red Sea Global resort site went unpaid for months, rights group alleges",
     "A human rights organisation says dozens of migrant construction workers at a luxury resort site on "
     "Saudi Arabia's Red Sea coast were not paid for up to five months, citing interviews and payslips."),
    ("Several tourists injured as stage structure collapses at Riyadh Season concert",
     "At least six visitors were taken to hospital after part of a stage structure collapsed during a concert "
     "at a Riyadh Season venue on Friday night, witnesses said."),
]


def add() -> str:
    """Publish the next synthetic article (fresh link, current time) and rewrite the feed."""
    published = json.loads(LOG.read_text()) if LOG.exists() else []
    title, summary = ARTICLES[len(published) % len(ARTICLES)]
    now = datetime.now(timezone.utc)
    published.append({"title": title, "summary": summary, "date": format_datetime(now),
                      "link": f"http://127.0.0.1:8000/demo/{now:%Y%m%d%H%M%S}"})
    LOG.write_text(json.dumps(published))
    items = "".join(f"<item><title>{escape(a['title'])}</title><description>{escape(a['summary'])}</description>"
                    f"<link>{a['link']}</link><pubDate>{a['date']}</pubDate></item>" for a in published)
    FEED.write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                    f"<title>Demo feed</title>{items}</channel></rss>", encoding="utf-8")
    print("Published:", title)
    return title


def reset() -> None:
    """Empty the demo feed and delete every demo article, its labels and its alerts."""
    conn = db.connect()
    story_ids = [r[0] for r in conn.execute("SELECT DISTINCT story_id FROM items WHERE source_id = 'demo'")]
    conn.execute("DELETE FROM classifications WHERE item_id IN (SELECT id FROM items WHERE source_id = 'demo')")
    conn.execute("DELETE FROM items WHERE source_id = 'demo'")
    conn.executemany("DELETE FROM stories WHERE id = ?", [(i,) for i in story_ids])
    conn.execute("DELETE FROM briefings WHERE kind = 'alert' AND text LIKE '%Demo feed%'")
    conn.execute("DELETE FROM briefings WHERE status = 'draft'")      # test drafts nobody approved
    conn.commit()
    LOG.unlink(missing_ok=True)
    FEED.unlink(missing_ok=True)
    print("Demo data removed.")


if __name__ == "__main__":
    {"add": add, "reset": reset}[sys.argv[1]]()
