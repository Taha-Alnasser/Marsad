# Concepts

Plain-language explanations of the technical ideas the project uses: read before the presentation.
Why we chose each one is in `DECISIONS.md`.

---

## SQLite
*Used for: all storage (D7)*

**A database that is a single file.** Most databases (Postgres, MySQL) are a program running all the time that you connect to, like n8n in Docker. SQLite has no server: the engine is a library inside the Python program (`import sqlite3`, built in), and all data lives in one file, e.g. `data/monitor.db`.

It's still a real database: **tables** (like spreadsheet sheets with fixed columns, one row per thing), SQL queries, and rules like "this URL must be unique". It runs in every iPhone and Chrome browser; n8n stores its own data in it by default.

- **Good at:** zero setup, millions of rows, free dedup via unique columns, built-in text search (FTS5), easy to inspect (*DB Browser for SQLite*).
- **Not good at:** many writers at once, **users and permissions**. That's why production moves to Postgres inside the client's environment.

> "SQLite for the prototype: zero setup, one file. In production it becomes Postgres inside your environment, because that's where access control lives."

---

## Embeddings
*Used for: detecting the same story across outlets and languages (D8)*

**The meaning of a text, written as a list of numbers.** Picture a map where every sentence has a location and sentences that *mean* similar things sit close together. An embedding is that location. A real map uses 2 coordinates; an embedding model uses thousands (our model, `text-embedding-3-large`, uses 3,072), so it can capture many aspects of meaning at once (topic, people and places, tone, kind of event).

**Where the numbers come from:** an *embedding model*, a neural network trained on huge amounts of text, including translations. It learned that "pilot" and "طيار" appear in the same contexts, so it places them close together. One cheap API call per item: it doesn't generate text, it only places it on the map.

```
"Flydubai co-pilot assaulted captain"  →  [0.021, -0.113, 0.064, … 3,072 numbers]
```

**Comparing two items:** *cosine similarity*, a score from 0 to 1 for how closely two items point the same way.

Real scores, measured 2026-10-03 with `text-embedding-3-large` on live articles (title + summary), each compared with Saudi Gazette's "Flydubai co-pilot assaulted captain":

| Score | Article | Relation |
|---|---|---|
| 0.68 | Al Jazirah, **Arabic**, same event | same story, other language |
| 0.61 | BBC, English, same event | same story |
| 0.59 | Al-Monitor explainer on the flight | same story |
| 0.45 | "Trump vows to hit Iran if Tehran was behind it" | political angle |
| 0.33 | "Flydubai suspends Tel Aviv flights" (Arabic) | follow-up event |
| 0.26 | Jiu-jitsu gold medal | unrelated |

Real same-story scores are **0.59–0.68**, lower than intuition suggests, because summaries differ even when the event is the same. Arabic matched as well as English. OpenAI returns vectors of length 1, so the plain multiply-and-add (`@`) *is* cosine similarity.

**The threshold:** above the cut-off (tuned in ticket 1.6), a new item joins an existing story from the last 48 h; otherwise it starts a new one. On the scores above, ~0.55 separates them, but the gap is narrow (0.45 vs 0.59), hence tuning on ~30 hand-checked pairs. Open judgement: political angles ("Trump vows…") arguably belong *in* the story for spread counting; leaving them out undercounts spread and misses alerts.

**Where it goes wrong:**
1. **Same topic ≠ same story**: "Flydubai co-pilot attack" vs "Flydubai adds Riyadh route" may score close. Merging them inflates "3+ outlets" and raises a false alarm. Mitigated by the 48 h window and a tested threshold.
2. **Short text is weak**: headline-only items give noisier scores.
3. **Arabic is slightly weaker** than English in most multilingual models: test it, don't assume.
4. **Text goes to the API provider**: fine for public news. For internal documents, use an open-source embedding model running inside the client's environment.

> "Each article gets a fingerprint of its meaning. The same event has a similar fingerprint in Arabic or English, and that's how we count how many outlets are carrying it."

---

## RSS
*Used for: every source we ingest (D2)*

**A standard file format news sites publish so that software, not people, can read their latest articles.** The website is designed for humans; next to it, most publishers put a plain list of their newest articles at a fixed URL, in a strict format (XML). Around since ~2000; every podcast is an RSS feed underneath. It's the **publisher's own sanctioned channel**, which is why "no scraping" (D2) is easy to defend.

Each article is an `<item>` with a `<title>`, a `<link>` (our unique ID, D7) and a `<description>` (the summary we classify and fact-check against):

```xml
<item>
  <title><![CDATA[Omar Nada wins jiu-jitsu gold ... Nagoya 2026]]></title>
  <link><![CDATA[https://saudigazette.com.sa/article/665058/...]]></link>
  <description><![CDATA[NAGOYA — Saudi Arabia's Omar Nada captured the gold medal ...]]></description>
  <pubDate>Fri, 02 Oct 2026 17:45:15 +0300</pubDate>
</item>
```

> "We only read what publishers choose to publish for machines: their RSS feeds."

---

## feedparser and httpx
*Used for: turning feeds into clean Python items (ingest.py)*

Every publisher bends the RSS standard slightly differently, and dates come in many formats. **feedparser reads any feed and returns the same clean object every time:** `e.title`, `e.link`, `e.summary` (from `<description>`), and `e.published_parsed`, a real date converted to UTC. Same-format UTC dates let us compare `published_at` with `fetched_at` to prove the 15-minute alert target.

**httpx** downloads the feed first, so we control the timeout (10 s) and the browser User-Agent (Arab News returns nothing without one). Then feedparser parses the downloaded bytes.

---

## numpy
*Used for: comparing embeddings (stories.py) and searching the archive (Q&A)*

**OpenAI gives us coordinates (embeddings) but doesn't compare them.** Deciding whether a new article is close to any article from the last 48 hours is our job: cosine similarity, i.e. multiply two lists of 3,072 numbers pairwise and add them up. One new article vs ~3,000 recent ones ≈ 9 million multiplications.

Measured on this laptop: plain Python 0.245 s; numpy 0.001 s (~250× faster). numpy runs the math in optimised C code.

Plain Python would survive at our volume (~1 s per 5-minute run), but numpy is still the right call:
1. **Q&A searches the whole archive.** After a year (~550,000 articles): plain Python ~45 s per question, numpy well under a second.
2. **Shorter code:** the whole comparison is one line, `recent @ new`.

> "OpenAI turns each article into coordinates. numpy measures the distance between coordinates. That's one line of code, and it scales to the full archive."

---

## Articles vs stories
*Used for: spread counting, the briefing, alerts (D8, D10)*

**We only ever pull articles.** An article is one piece by one outlet (what RSS gives us). A story is the real-world event the articles are about. Stories are **created by our system** by grouping articles.

For each new article: embed it, compare it with every article from the last 48 hours, take the best match. Above the threshold → **join that article's story** (copy its `story_id`). Otherwise → **start a new story** (`story_id` = its own id).

| id | outlet | title | story_id |
|---|---|---|---|
| 101 | saudigazette | Flydubai co-pilot assaulted… | **101** (new story) |
| 102 | guardian_saudi | 'I was fighting for my life'… | **101** (matched #101) |
| 103 | bbc_arabic | …طيار فلاي دبي… | **101** (matched #102, in Arabic) |
| 104 | arabnews | NEOM hotel opens… | **104** (no match, new story) |

A story is *all articles sharing a `story_id`*. **Store what was decided, compute what can be counted:** the `story_spread` **view** counts the spread (outlets, international or not, first/last seen) fresh every time, so it can never be out of date; a `stories` **table** stores decisions about the story (already alerted? priority? outlet count at the last AI judgement, which tells us when to re-judge).

**Why group at all:** "picked up by 3+ outlets" is a question about a story, not an article; the briefing shows each event once with all its citations; one alert per event, not one per article. Real scale: by 2026-10-03 the Flydubai incident was **33 articles across 7 of our 10 outlets**.

> "We pull articles; the system recognises when several of them are the same event, in any language, and that's how it knows a story is spreading."

---

## User-Agent
*Used for: every feed request (config.py, D26)*

**A label sent with every web request saying what program is asking.** Chrome sends `Mozilla/5.0 (Macintosh; ...) Chrome/129.0 ...`; our code sends `Mozilla/5.0 (Macintosh) MediaMonitor/0.1`.

**Why it exists:** in the 1990s, browsers differed a lot, so sites read the label to serve a page that would display correctly. Netscape (code name *Mozilla*) got the advanced pages first, so other browsers began claiming to be "Mozilla-compatible". Every client still starts with `Mozilla/5.0`, which today just means "a normal web client".

**Used today for:** mobile vs desktop layouts; statistics; and **identifying bots.** Well-behaved bots announce themselves (`Googlebot`), and publishers allow, slow or block them by name (their `robots.txt` rules are written per User-Agent).

**It's an honour system:** self-declared, never verified. Changing the label to get past a block is disguising yourself, which is why we dropped Arab News instead (D26). Ours works with every feed (`Mozilla/5.0`) and says what we are (`MediaMonitor/0.1`), so any publisher can see us in their logs and block us if they choose.

> "Our requests say who we are. When a publisher blocked that, we respected it."
