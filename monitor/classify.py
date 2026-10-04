"""Label each new article with GPT-6 Luna, using the spread of its story (D10, D12, D14, D15)."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from openai import OpenAI

from monitor import config, db

INSTRUCTIONS = (config.ROOT / "prompts" / "classify.md").read_text(encoding="utf-8")
RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
client = OpenAI()

# The fixed output format. Justification comes first so the model reasons before it labels.
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["justification", "relevance", "themes", "sentiment", "priority"],
    "properties": {
        "justification": {"type": "string"},
        "relevance": {"type": "string", "enum": ["on_topic", "off_topic"]},
        "themes": {"type": "array", "items": {"type": "string", "enum": [
            "strategy_visitors", "destinations_projects", "aviation_visa_entry", "reputational_risk"]}},
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "priority": {"type": "string", "enum": ["high", "medium", "low", "none"]},
    },
}


def describe(conn, item) -> tuple[str, int]:
    """The text the model reads: the article plus how far its story has spread."""
    names = {s["id"]: s["name"] for s in config.load_sources()}
    spread = conn.execute("SELECT * FROM story_spread WHERE id = ?", (item["story_id"],)).fetchone()
    outlets = [r["source_id"] for r in conn.execute(
        "SELECT DISTINCT source_id FROM items WHERE story_id = ?", (item["story_id"],))]
    intl = conn.execute("""SELECT COUNT(DISTINCT source_id) FROM items
                           WHERE story_id = ? AND source_tier = 'international'""",
                        (item["story_id"],)).fetchone()[0]
    text = (f"Source: {names.get(item['source_id'], item['source_id'])} ({item['source_tier']})\n"
            f"Title: {item['title']}\nSummary: {item['summary'] or '(none)'}\n\n"
            f"Story spread: {spread['outlet_count']} outlet(s) "
            f"({', '.join(names.get(o, o) for o in outlets)}), {intl} international, "
            f"first seen {spread['first_seen']}.")
    return text, spread["outlet_count"]


def judge(text: str) -> dict:
    resp = client.responses.create(
        model=config.CLASSIFY_MODEL, instructions=INSTRUCTIONS, input=text,
        text={"format": {"type": "json_schema", "name": "label", "schema": SCHEMA, "strict": True}})
    return json.loads(resp.output_text)


def run() -> dict:
    conn = db.connect()
    todo = conn.execute("""SELECT * FROM items WHERE story_id IS NOT NULL
                           AND id NOT IN (SELECT item_id FROM classifications)""").fetchall()
    inputs = [describe(conn, item) for item in todo]
    with ThreadPoolExecutor(max_workers=8) as pool:           # 8 calls at a time, not one by one
        results = list(pool.map(lambda x: safe(judge, x[0]), inputs))

    done = failed = 0
    for item, (_, outlets), label in zip(todo, inputs, results):
        if label is None:
            failed += 1                                        # retried on the next run
            continue
        conn.execute("""INSERT INTO classifications (item_id, created_at, model,
                        outlet_count, justification, relevance, themes, sentiment, priority)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (item["id"], datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      config.CLASSIFY_MODEL, outlets, label["justification"],
                      label["relevance"], json.dumps(label["themes"]), label["sentiment"],
                      label["priority"]))
        update_story(conn, item["story_id"], outlets)
        done += 1
    conn.commit()
    return {"classified": done, "failed": failed}


def update_story(conn, story_id: int, outlets: int) -> None:
    """The story's priority is the highest current priority among its articles."""
    latest = conn.execute("""SELECT c.priority FROM classifications c JOIN items i ON i.id = c.item_id
                             WHERE i.story_id = ? AND c.id IN
                             (SELECT MAX(id) FROM classifications GROUP BY item_id)""", (story_id,))
    priority = max((r["priority"] for r in latest), key=RANK.get, default="none")
    conn.execute("""INSERT INTO stories (id, priority, judged_outlet_count) VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET priority = excluded.priority,
                    judged_outlet_count = excluded.judged_outlet_count""", (story_id, priority, outlets))


def safe(fn, arg):
    """One failed API call must not stop the batch."""
    try:
        return fn(arg)
    except Exception as e:
        print(f"classify failed ({type(e).__name__}): {str(e)[:150]}")
        return None


if __name__ == "__main__":
    print(run())
