"""Embed new articles and group them into stories (D8)."""
from datetime import datetime, timedelta, timezone

import numpy as np
from openai import OpenAI

from monitor import config, db

client = OpenAI()          # reads OPENAI_API_KEY from the environment


def embed(texts: list[str]) -> np.ndarray:
    """One fingerprint (3,072 numbers) per text; sent in batches of 100 per API call."""
    vectors = []
    for i in range(0, len(texts), 100):
        resp = client.embeddings.create(model=config.EMBED_MODEL, input=texts[i:i + 100])
        vectors += [d.embedding for d in resp.data]
    return np.array(vectors, dtype=np.float32)


def run() -> dict:
    conn = db.connect()
    pending = conn.execute("""SELECT id, title, summary FROM items WHERE embedding IS NULL
                              ORDER BY COALESCE(published_at, fetched_at)""").fetchall()
    if not pending:
        return {"embedded": 0, "new_stories": 0, "joined": 0, "merged": 0}

    # The stories we can join: everything already grouped in the last 48 hours.
    since = (datetime.now(timezone.utc) - timedelta(hours=config.STORY_WINDOW_H)).isoformat()
    recent = conn.execute("""SELECT embedding, story_id FROM items WHERE story_id IS NOT NULL
                             AND COALESCE(published_at, fetched_at) >= ?""", (since,)).fetchall()
    matrix = [np.frombuffer(r["embedding"], dtype=np.float32) for r in recent]
    story_ids = [r["story_id"] for r in recent]

    vectors = embed([f'{r["title"]}\n{r["summary"] or ""}' for r in pending])
    new_stories = joined = merged = 0
    for row, vec in zip(pending, vectors):
        scores = np.array(matrix) @ vec if matrix else np.array([])
        matches = [i for i in range(len(scores)) if scores[i] >= config.SIMILARITY_THRESHOLD]
        if not matches:
            story, score = row["id"], None                             # start a new story
            new_stories += 1
        else:
            best = max(matches, key=lambda i: scores[i])
            story, score = story_ids[best], float(scores[best])        # join the best match's story
            joined += 1
            # Matches in other stories mean those stories are the same event: merge them in.
            for other in {story_ids[i] for i in matches} - {story}:
                conn.execute("UPDATE items SET story_id = ? WHERE story_id = ?", (story, other))
                db.merge_story_decisions(conn, story, other)
                story_ids = [story if s == other else s for s in story_ids]
                merged += 1
        conn.execute("UPDATE items SET embedding = ?, story_id = ?, story_score = ? WHERE id = ?",
                     (vec.tobytes(), story, score, row["id"]))
        matrix.append(vec)                     # later articles in this run can join it too
        story_ids.append(story)
    conn.commit()
    return {"embedded": len(pending), "new_stories": new_stories, "joined": joined, "merged": merged}


if __name__ == "__main__":
    print(run())
