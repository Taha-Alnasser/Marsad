"""Draft the daily briefing with GPT-6.1 Sol, then check its numbers (D31)."""
import html
import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from openai import OpenAI

from monitor import config, db

INSTRUCTIONS = (config.ROOT / "prompts" / "briefing.md").read_text(encoding="utf-8")
RIYADH = ZoneInfo("Asia/Riyadh")
client = OpenAI()


def collect(conn, since: str) -> list:
    """On-topic articles from the window, most important stories first."""
    return conn.execute("""
        SELECT i.*, c.priority, c.justification, sp.outlet_count
        FROM items i
        JOIN classifications c ON c.item_id = i.id
        JOIN stories s ON s.id = i.story_id
        JOIN story_spread sp ON sp.id = i.story_id
        WHERE c.relevance = 'on_topic' AND i.fetched_at >= ?
        ORDER BY CASE s.priority WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC,
                 sp.outlet_count DESC, i.story_id, i.id""", (since,)).fetchall()


def numbers(text: str) -> set[str]:
    """Every number in a text, written plainly: '1,500' -> '1500'. Arabic digits count too."""
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,.]*", text)}


def check(body: str, sources: dict[int, str]) -> list[str]:
    """Each number in a line must appear in an article that line cites. No AI involved."""
    warnings = []
    for line in body.splitlines():
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", line)]
        for n in cited:
            if n not in sources:
                warnings.append(f"Cites [{n}], which is not one of the articles: «{line.strip()[:80]}»")
        plain = re.sub(r"\[\d+\]", "", line)
        plain = re.sub(r"^\s*\d+\.\s", "", plain)          # ignore headline numbering "1. "
        found = set().union(*(numbers(sources[n]) for n in cited if n in sources))
        for num in numbers(plain) - found:
            warnings.append(f"'{num}' not found in the cited article(s): «{line.strip()[:80]}»")
    return warnings


def run() -> dict:
    conn = db.connect()
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat()
    articles = collect(conn, since)
    names = {s["id"]: s["name"] for s in config.load_sources()}
    # What each citation can vouch for: the article's text, plus its story's outlet count (from our database).
    sources = {n: f'{a["title"]} {a["summary"] or ""} {a["outlet_count"]}' for n, a in enumerate(articles, 1)}

    if articles:
        lines, story = [], None
        for n, a in enumerate(articles, 1):
            if a["story_id"] != story:
                story = a["story_id"]
                lines.append(f'\nStory (priority {a["priority"]}, {a["outlet_count"]} outlet(s))')
            lines.append(f'[{n}] {names.get(a["source_id"], a["source_id"])}: {a["title"]}\n'
                         f'    {a["summary"] or ""}\n    Analyst note: {a["justification"]}')
        try:
            body = client.responses.create(model=config.BRIEFING_MODEL, instructions=INSTRUCTIONS,
                                           input="\n".join(lines)).output_text.strip()
        except Exception as e:
            # The AI is down: the analyst still gets every story on time, and writes the summary by hand.
            body = (f"**The AI draft failed this morning ({type(e).__name__}). Please write the summary "
                    f"manually from the stories below.**\n\n## Overnight stories\n\n"
                    + "\n\n".join(f'{names.get(a["source_id"], a["source_id"])} ({a["priority"]}): '
                                     f'{a["title"]} [{n}]' for n, a in enumerate(articles, 1)))
    else:
        body = "No relevant coverage in the last 24 hours."

    down = [r["source_id"] for r in conn.execute("""SELECT source_id, status FROM source_runs
             WHERE id IN (SELECT MAX(id) FROM source_runs GROUP BY source_id)""") if r["status"] == "error"]
    local = now.astimezone(RIYADH)
    header = (f"# Daily media briefing\n\n"
              f"*{local:%A %d %B %Y} · covers the 24 hours to {local:%H:%M} Riyadh time · "
              f"{len(names)} sources checked · unavailable: {', '.join(names.get(d, d) for d in down) or 'none'}*")
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", body)} & sources.keys())
    source_list = "\n".join(f'- [{n}] {names.get(articles[n-1]["source_id"])} · '
                            f'[{articles[n-1]["title"]}]({articles[n-1]["url"]})' for n in cited)
    text = f"{header}\n\n{body}" + (f"\n\n## SOURCES\n{source_list}" if source_list else "")

    warnings = check(body, sources)
    cur = conn.execute("INSERT INTO briefings (created_at, text, warnings) VALUES (?, ?, ?)",
                       (now.isoformat(timespec="seconds"), text, json.dumps(warnings, ensure_ascii=False)))
    conn.commit()
    return {"id": cur.lastrowid, "text": text, "warnings": warnings}


def to_email_html(text: str, approved_by: str = "") -> str:
    """The approved briefing as an email: an overview, then one card per story with its image."""
    text = text.replace("\r\n", "\n")
    body, _, source_part = text.partition("## SOURCES")
    sources = {int(n): (outlet, title, url) for n, outlet, title, url in
               re.findall(r"- \[(\d+)\] (.+?) · \[(.+?)\]\((.+?)\)", source_part)}
    conn = db.connect()
    images = {url: img for url, img in conn.execute("SELECT url, image_url FROM items WHERE image_url IS NOT NULL")}

    def cite(par: str) -> str:            # [2][5] -> small clickable numbers "2, 5" linking to the articles
        def links(m):
            nums = [int(n) for n in re.findall(r"\d+", m[0]) if int(n) in sources]
            return "<sup>" + ", ".join(f'<a href="{sources[n][2]}" style="color:#8a6d1f;text-decoration:none">{n}</a>'
                                       for n in nums) + "</sup>"
        return re.sub(r"(?:\[\d+\])+", links, html.escape(par))

    out, theme, in_section = [], "", False      # in_section: past the overview, where stories become cards
    for block in [b.strip() for b in body.split("\n\n") if b.strip()]:
        if block.startswith("# "):
            out.append(f'<h1 style="font:600 26px Georgia,serif;margin:0 0 4px">{html.escape(block[2:])}</h1>')
        elif block.startswith("*") and block.endswith("*"):
            out.append(f'<p style="color:#6b7280;font-size:13px;margin:0 0 24px">{html.escape(block.strip("*"))}</p>')
        elif block.startswith("## "):
            theme, in_section = "", True
            out.append(f'<h2 style="font:600 19px Georgia,serif;margin:32px 0 12px;padding-top:16px;'
                       f'border-top:1px solid #e5e7eb">{html.escape(block[3:])}</h2>')
        elif block.startswith("### "):
            theme = block[4:]
        elif in_section and (cited := [int(n) for n in re.findall(r"\[(\d+)\]", block) if int(n) in sources]):
            outlet, title, url = sources[cited[0]]         # the card shows the first article it cites
            img = images.get(url)
            out.append(
                '<table role="presentation" width="100%" style="border-collapse:collapse;margin:0 0 14px">'
                '<tr><td style="vertical-align:top;padding:14px 16px;background:#f8f7f4;border-radius:8px">'
                + (f'<div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#0a6b57;'
                   f'margin-bottom:6px">{html.escape(theme)}</div>' if theme else "")
                + f'<div style="font-size:12px;color:#6b7280">{html.escape(outlet)}</div>'
                f'<a href="{url}" dir="auto" style="display:block;font:600 16px Georgia,serif;color:#111827;'
                f'text-decoration:none;margin:2px 0 6px">{html.escape(title)}</a>'
                f'<div style="font-size:14px;line-height:1.55;color:#374151">{cite(block)}</div></td>'
                + (f'<td width="116" style="vertical-align:top;padding:14px 0 14px 12px">'
                   f'<img src="{img}" width="116" style="border-radius:6px;display:block" alt=""></td>' if img else "")
                + "</tr></table>")
        else:
            out.append(f'<p style="font-size:16px;line-height:1.6;margin:0 0 12px">{cite(block)}</p>')

    listing = "".join(f'<div>[{n}] {html.escape(o)} · <a href="{u}" style="color:#6b7280">{html.escape(t)}</a></div>'
                      for n, (o, t, u) in sorted(sources.items()))
    footer = (f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid #e5e7eb;font-size:12px;'
              f'color:#6b7280;line-height:1.7"><b>Sources</b>{listing}'
              + (f'<div style="margin-top:10px">Reviewed and approved by {html.escape(approved_by)}.</div>'
                 if approved_by else "") + "</div>")
    return ('<div style="font-family:Arial,Helvetica,sans-serif;color:#1f2328;max-width:640px;margin:0 auto">'
            + "".join(out) + footer + "</div>")


if __name__ == "__main__":
    result = run()
    print(result["text"], "\n\nWARNINGS:", result["warnings"] or "none")
