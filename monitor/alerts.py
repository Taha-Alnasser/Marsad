"""High-risk stories that meet all three alert rules and haven't been alerted yet (D11, D35)."""
from datetime import datetime, timezone

from monitor import config, db


def pending() -> list[dict]:
    """Prepare an alert for each new high story and mark it alerted, so it never repeats."""
    conn = db.connect()
    names = {s["id"]: s["name"] for s in config.load_sources()}
    alerts = []
    # Rules 1-2 (about us; negative and serious) are judged by the AI as part of "high".
    # Rule 3 (amplified) is counted by code: an international outlet, or 3+ outlets.
    for story in conn.execute("""SELECT s.id, sp.outlet_count, sp.has_international FROM stories s
                                 JOIN story_spread sp ON sp.id = s.id
                                 WHERE s.priority = 'high' AND s.alerted_at IS NULL
                                 AND (sp.has_international = 1 OR sp.outlet_count >= 3)"""):
        articles = conn.execute("""
            SELECT i.title, i.url, i.source_id, c.justification FROM items i
            JOIN classifications c ON c.item_id = i.id
            WHERE i.story_id = ? ORDER BY c.priority = 'high' DESC, i.id""", (story["id"],)).fetchall()
        why = (f"Why it alerted: about us, negative and serious (AI judgement); amplified (counted): "
               f"{story['outlet_count']} outlet(s){', including an international outlet' if story['has_international'] else ''}.")
        lines = [f"# Reputational risk alert\n\n{articles[0]['justification']} "
                 + "".join(f"[{n}]" for n in range(1, len(articles) + 1)), why, "## Coverage"]
        lines += [f"{names.get(a['source_id'], a['source_id'])} reported: {a['title']} [{n}]"
                  for n, a in enumerate(articles, 1)]
        lines.append("## SOURCES\n" + "\n".join(
            f"- [{n}] {names.get(a['source_id'], a['source_id'])} · [{a['title']}]({a['url']})"
            for n, a in enumerate(articles, 1)))
        text = "\n\n".join(lines)
        row = conn.execute("INSERT INTO briefings (created_at, text, warnings, kind) VALUES (?, ?, '[]', 'alert')",
                           (datetime.now(timezone.utc).isoformat(timespec="seconds"), text))
        alerts.append({"id": row.lastrowid, "headline": articles[0]["title"], "text": text})
        conn.execute("UPDATE stories SET alerted_at = ? WHERE id = ?",
                     (datetime.now(timezone.utc).isoformat(timespec="seconds"), story["id"]))
    conn.commit()
    return alerts
