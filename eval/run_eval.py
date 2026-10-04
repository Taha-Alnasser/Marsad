"""Eval layer 1: does the classifier agree with the analyst's labels? Recall on high-risk first."""
import csv
from concurrent.futures import ThreadPoolExecutor

from monitor import classify, config, db

ROOT = config.ROOT / "eval"


def text_for(conn, row: dict) -> str:
    """Real articles: exactly what the live pipeline sends. Synthetic: same format, spread from the sheet."""
    if row["type"] == "real":
        item = conn.execute("SELECT * FROM items WHERE id = ?", (int(row["id"].split("-")[1]),)).fetchone()
        return classify.describe(conn, item)[0]
    tier = "international" if int(row["international"]) else "national"
    return (f"Source: {row['source']} ({tier})\nTitle: {row['title']}\nSummary: {row['summary']}\n\n"
            f"Story spread: {row['outlets']} outlet(s), {row['international']} international.")


def main():
    conn = db.connect()
    rows = list(csv.DictReader(open(ROOT / "labels.csv", encoding="utf-8-sig")))
    texts = [text_for(conn, r) for r in rows]
    with ThreadPoolExecutor(max_workers=8) as pool:
        preds = list(pool.map(classify.judge, texts))

    results, wrong = [], []
    for r, p in zip(rows, preds):
        human_rel, human_pri = r["YOUR relevance (on/off)"], r["YOUR priority (high/medium/low/none)"]
        ai_rel, ai_pri = p["relevance"].replace("_topic", ""), p["priority"]
        results.append((human_rel, human_pri, ai_rel, ai_pri))
        if (human_rel, human_pri) != (ai_rel, ai_pri):
            wrong.append(f"  {r['id']:12} you: {human_rel}/{human_pri:6}  AI: {ai_rel}/{ai_pri:6}  {r['title'][:60]}\n"
                         f"               AI's reason: {p['justification']}")

    n = len(results)
    high = [x for x in results if x[1] == "high"]
    caught = sum(x[3] == "high" for x in high)
    false_alarms = sum(x[3] == "high" and x[1] != "high" for x in results)
    print(f"Articles: {n}  (high-risk in your labels: {len(high)})")
    print(f"RECALL on high-risk: {caught}/{len(high)}  <- the number that matters most")
    print(f"False alarms (AI high, you not): {false_alarms}")
    print(f"Relevance agreement: {sum(x[0] == x[2] for x in results)}/{n}")
    print(f"Priority agreement:  {sum(x[1] == x[3] for x in results)}/{n}")
    print("\nDisagreements:\n" + ("\n".join(wrong) or "  none"))


if __name__ == "__main__":
    main()
