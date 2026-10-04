# Build plan

Our ticket board, in place of Linear. We plan one chunk at a time and agree on each ticket before building it.
Decisions behind the tickets go in `DECISIONS.md`.

Status: `todo` · `doing` · `done` · `cut`

## Status

**Planning is done (2026-10-02).** Chunks 1–2 are planned here in detail. Chunks 3–8 follow `GROOMING_NOTES.txt` plus decisions D17–D22. Next: build.

## Build order for build day (with checkpoints)

1. **Setup** (chunk 0): repo, venv, n8n Docker (TZ=Asia/Riyadh), `.env`
2. **Ingestion** (chunk 1): fetch → SQLite → source health → embeddings (every new article) → stories → demo feed
3. **Classification** (chunk 2)
4. **Briefing** (chunk 4): Sol draft with citations + number check
5. **n8n loop** (chunk 5): 5-min trigger, 06:00 draft → form approval → 06:50 escalation → email
   **✔ Checkpoint (~hour 6): the core loop runs end to end. Everything after this adds quality.**
6. **Alerts** (chunk 6): high → form → email
7. **Label 30 items by hand** (chunk 3) → **evals** (chunk 7)
8. **Failure handling, minimal** (chunk 8): LLM-down email, sources-down note, 15-min health check
9. **Q&A** (chunk 9) if time allows
   - *Stretch:* **"Add a source" n8n form** → Python tests the feed (responds? has articles?) → appends to `sources.yaml`. A live demo moment: add a source in front of the panel. Production: an admin page with permissions (analyst suggests, supervisor approves).
10. **README, n8n export, architecture note, slides** (chunk 10)
    - **`./start.sh`**: one command for the demo and the README. Starts n8n (`docker compose up -d`), starts the Python server in the background with a log file, waits for both health checks, prints the links. Option to decide then: run the Python server in Docker too, so `docker compose up` starts everything and the panel needs no Python install.

Cut, and said so on a slide: look-ahead section, full threshold tuning (spot-check only), Q&A if time runs out.

## The chunks

Ordered to protect the core loop the brief names first: **ingest → classify → draft → approve → deliver**. Chunks 6–9 come after the core loop. Q&A (chunk 9) is **kept**, not cuttable (D16): it reuses the stored embeddings, so it's cheap to build.

| # | Chunk | What it delivers | Day | Status |
|---|---|---|---|---|
| 0 | Setup | Repo, Python env, n8n in Docker (**timezone = Asia/Riyadh**), `.env` with the OpenAI key | 1 | done |
| 1 | **Ingestion** | 9 feeds (D26) polled every 5 min, stored, deduped, health logged per source | 1 | done (1.6 tuning + 1.7 demo feed later) |
| 2 | Classification | LLM on every new article (no keyword filter, D23): relevance, theme, sentiment, priority, justification | 1 | done |
| 3 | Labelled eval set | 60 hand-labelled items (EN + AR + tricky cases), labelled *before* seeing model output | 1–2 | done |
| 4 | Briefing | Daily briefing in the directorate's structure, every claim cited; number check | 2 | done |
| 5 | Approval + delivery (n8n) | 06:00 draft → analyst edits/approves → 06:50 escalation → 07:30 email to the DG's office | 2 | done |
| 6 | Alerts | High-risk rule, alert within 15 min, on-call analyst approves | 2 | done |
| 7 | Evals | Classification recall, claim-level faithfulness judge, judge vs your labels | 3 | done |
| 8 | Failure handling | 15-min health check, degraded briefing when the LLM or a feed is down | 3 | todo |
| 9 | Q&A over the archive | "What was written about visas this week, and by whom?", search reuses the stored embeddings | 3 | todo |
| ✔ | **Full review** | Whole system end to end, against every brief requirement and the 5 rubric criteria, before building | before build | todo |
| 10 | Write-up | Cost estimate, security/governance, README, architecture note, n8n export, slides | 3 + | todo |

---

## Chunk 1 — Ingestion

**Goal:** every 5 minutes, pull all 10 feeds, store new items, recognise the same story across outlets, and record whether each source worked.

**Done when:** a run pulls all 10 feeds, a broken feed doesn't stop the others, re-running adds no duplicates, and we can see which sources failed in the last run.

| Ticket | What | Done when | Status |
|---|---|---|---|
| 1.1 | **Feed fetcher:** read `sources.yaml`, fetch each feed with a User-Agent and a timeout, parse into items | All 10 return items; a bad URL is logged, not a crash | done |
| 1.2 | **Storage (SQLite):** an `items` table (source, url, title, summary, language, published/fetched time), unique on URL | Re-running adds 0 rows | done |
| 1.3 | **Source health:** a record per source per run (ok / error, item count, error message, last success) | We can list the sources that failed in the last run | done |
| 1.4 | **Story clustering (embeddings, `text-embedding-3-large`, D9):** embed title + summary, match against the last 48 h, assign `story_id`, update outlet count | Flydubai test: Guardian + Saudi Gazette + BBC Arabic = 1 story, 3 outlets | done |
| 1.7 | **Demo source:** a local RSS file of synthetic articles we can add to live; same pipeline as every other feed | Adding a synthetic high-risk item live produces an alert within 15 min | todo |
| 1.6 | **Tune the threshold:** hand-check ~30 item pairs (same story / different), pick the cut-off | Threshold chosen with a measured hit rate (goes on an eval slide) | todo |
| 1.5 | **Trigger:** n8n schedule calls the Python ingest endpoint every 5 minutes | Runs on its own; new items appear | done |

### What we store

- **`items`**: one row per article: id, source_id, url (unique), title, summary, lang, published_at, fetched_at, embedding, story_id
- **`stories`**: one row per real-world story: id, first_seen, last_seen, outlet_count (→ "3+ outlets" rule), has_international (→ "top-tier outlet" rule)
- **`source_runs`**: one row per source per run: source_id, run_at, status, items_found, items_new, error (→ "sources down" note on the briefing)
- Later chunks add `classifications`, `briefings` (with **approved_by / approved_at**: the audit trail) and `alerts`.

Open decisions, to settle together before building:
- [x] Where the data lives: **SQLite** (D7)
- [x] What triggers the 5-minute run: **n8n schedule → Python endpoint** (D6)
- [x] How to detect "same story": **embeddings only**, 48 h window, no vector DB (D8)

---

## Chunk 2 — Classification

**Goal:** for every new item, decide whether it's on topic, which of the four themes it belongs to, its sentiment, its priority, and a one-line justification an analyst can check.

**The brief requires:** classify each item against the four themes (1. national tourism strategy and visitor numbers, 2. destination and giga-project launches, 3. aviation, visa and entry policy, 4. reputational risk or negative coverage), and assign a sentiment and a priority level with a short justification.

**Done when:** every new item from a run has a stored classification, and the output is always valid (no free-text the code can't read).

| Ticket | What | Done when | Status |
|---|---|---|---|
| 2.1 | ~~Keyword pre-filter~~ | Removed: every article goes to the AI (D23) | cut |
| 2.2 | **Label scheme:** written definitions of every theme, sentiment and priority level | One page an analyst would agree with; it doubles as the labelling guide for chunk 3 | done |
| 2.3 | **Classifier prompt + structured output:** the LLM returns fixed fields, not prose | 100% of outputs parse | done |
| 2.4 | **Spread facts + re-judging:** code builds the story facts (outlets, international count, first seen) for the prompt; re-classify a story when its outlet count rises | A story going from 2 → 3 outlets gets re-judged | done |
| 2.6 | **Embedding outage (simplified):** articles wait unlabelled until grouping works again, then get labelled on the next run. No alerts during the outage, so the health check must flag it | Articles saved during an outage are labelled after it | done |
| 2.5 | **Storage:** a `classifications` table (+ model name and prompt version) | We can say which prompt version produced any label | done |

Open decisions:
- [x] What the LLM decides vs the code: **LLM decides all labels; code passes the spread facts; re-judge when a story spreads** (D10, D11)
- [x] The label scheme (D12)
- [x] Which LLM: **GPT-6 Luna** for classification, **GPT-6.1 Sol** for the briefing; the eval can upgrade Luna to Sol (D14)
- [x] Prompt design: English, ~6 trap examples (never from the eval set), one item per call, justification first, versioned (D15)

---

## Notes for later chunks

- **Chunk 2 (stories table):** when two stories merge (D27), their decisions must merge too: if either was already alerted, the merged story was alerted; keep the higher priority.
- **Ticket 1.6 test cases:** the Flydubai split (should be one story) and the Asian Games blend (several medal events merged), both from the 2026-10-03 run.

- **Chunk 5 (approval):** the analyst must be able to **correct a classification**, not only edit the briefing text ("what good looks like"). Every correction is saved and becomes extra eval data.
- **Volume:** our 10 feeds give roughly 600–800 items/day; the client sees ~1,500 from 40 outlets. Cost is estimated at **their** volume; the demo runs at **ours**.
- **Limitations slide:** no social accounts (X API is paid); no visa specialist source; no Saudi local press without feeds.
