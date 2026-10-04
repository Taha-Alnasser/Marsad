# Decisions log

Every significant decision on the project: what we chose, why, what it costs, and how to say it to the panel.
Newest at the bottom. Source-by-source detail lives in `SOURCES.md`.

Each entry:
- **Decision:** what we chose
- **Why:** the reasoning
- **Trade-off:** what we gave up, said out loud
- **For the panel:** a one-liner for the presentation (senior, non-technical)
- **Rubric:** which assessment criterion it serves

---

## D1 — 10 sources, assigned by job
*2026-10-02 · Status: decided*

**Decision:** Ingest 10 sources, not as many as possible. Each one fills a slot for a job: national voice (EN), Arabic, international amplifier, trade press.

**Why:** The brief asks for at least 8 and says "narrow and working beats broad and unfinished". 10 leaves room for a feed dying mid-demo. Assigning slots by job means every source has a reason to be there, rather than padding the count.

**Trade-off:** Less coverage than the analysts' ~40 outlets today. The source list is a config file (`sources.yaml`), so analysts can add outlets without code changes.

**For the panel:** "We picked ten sources, and each one has a job. Adding the next thirty is editing a list, not a rebuild."

**Rubric:** Product judgement & scoping (20%).

---

## D2 — Publishers' own RSS feeds only: no scraping, no aggregators
*2026-10-02 · Status: decided*

**Decision:** We only ingest what publishers put in their own RSS feeds. No scraping of article pages, and no aggregators such as Google News.

**Why:**
- The brief allows only "sanctioned scraping". For a government client the cleanest position is none: no robots.txt or copyright questions.
- Fewer moving parts: nothing breaks when a site redesigns.
- We tested the alternative. Google News + link decoding + article extraction got full text for 14/15 Arabic items. But it relies on an unofficial Google endpoint and is scraping, so it's harder to defend.

**Trade-off:**
- **Fact checks only see feed text** (title + summary). The briefing only claims what the feed says.
- **We lose Saudi local Arabic press that has no feed** (Okaz, Sabq, Al Watan, SPA). Production fix: a licensed news feed, or the directorate's existing media-monitoring subscription.

**Why publishers offer RSS at all:** it's a shop window. Headline + teaser + link, designed to bring readers back to their site (where the ads and subscriptions are). They block what takes the article itself, i.e. scraping. We read the window, cite it and link back, and never republish their text: exactly what RSS exists for. Many terms describe RSS as for personal or non-commercial use, so **a government deployment should license its news content**, as commercial monitoring services do.

**For the panel:** "Everything we ingest, the publisher chose to publish as a feed. Nothing is scraped. For full coverage in production, you'd plug in a licensed feed."

**Rubric:** Production readiness (20%), Product judgement (20%).

---

## D3 — Arabic keyword filter stays loose; the LLM decides relevance
*2026-10-02 · Status: **superseded by D23** (no keyword filter at all)*

**Decision:** A cheap keyword filter drops items that are clearly irrelevant before they reach the LLM. In Arabic it is deliberately loose, and the LLM makes the real relevance call.

**Why:** Testing Asharq Al-Awsat showed how crude Arabic keyword matching is. "العلا" (AlUla) matched *العلاقات* ("relations"), "طيران" matched a footballer suing an airline, and "سياحة" matched *Egyptian* tourism. Arabic attaches prefixes and suffixes to words, so a strict filter would wrongly drop real stories.

**Trade-off:** More items reach the LLM than a strict filter would allow, so it costs a little more. Missing a story costs more than an extra LLM call.

**For the panel:** "Arabic is where simple tools fail. We saw it on day one, so the cheap filter only removes the obvious noise and the model makes the judgement."

**Rubric:** Agent & system design (25%). These cases also go into the labelled eval set.

---

## D4 — No dedicated "official channel" source
*2026-10-02 · Status: decided*

**Decision:** Drop the official-channel slot.

**Why:** Neither the Saudi Press Agency nor the Ministry of Tourism has a working RSS feed (empty / 403). Saudi Gazette and Arab News already run SPA wire stories, so the official line still comes in through them.

**Trade-off:** Official statements arrive second-hand, via national outlets. It's harder to flag "misinformation about policy" without the original statement. In production, the client's own press releases would be an internal source.

**For the panel:** "The official line reaches us through the national press today. In production, your own press releases would be the reference we check coverage against."

**Rubric:** Product judgement (20%).

---

## D5 — Final source list (10, now 9 after D26)
*2026-10-02 · Status: decided*

**Decision:** 10 publisher feeds, 5 English and 5 Arabic, split between national and international outlets:

| | National | International |
|---|---|---|
| **EN** | Saudi Gazette, ~~Arab News~~ (dropped, D26) | Al-Monitor, The Guardian (Saudi tag), BBC Middle East, Skift (trade) |
| **AR** | Asharq Al-Awsat, Al Jazirah | BBC Arabic, Al Jazeera Arabic |

**Why:** National outlets feed the daily briefing. International outlets are what the "amplified" part of the alert rule checks against. Arabic is half the list because the cultural reading is the hard part.

**Trade-off:** No visa/entry-policy specialist (theme 3); it arrives via Arab News, Saudi Gazette, Al-Monitor. No Saudi local Arabic press without feeds (see D2).

**For the panel:** "Half our sources are Arabic, and half are the international outlets where a local story becomes a reputational problem."

**Rubric:** Product judgement (20%), Working outcome (20%).

---

## D6 — n8n triggers ingestion; Python does the work
*2026-10-02 · Status: decided*

**Decision:** An n8n schedule calls a Python ingestion endpoint every 5 minutes. Python fetches, stores and dedups; n8n decides *when*.

**Why:**
- The brief assigns n8n "triggers, scheduling, routing". All schedules live in one place: ingestion, the 06:00 draft, the 06:50 escalation, the 07:30 delivery.
- Every run appears in n8n's execution history, so we get monitoring for free: you can see a failed run without reading logs.
- It's visible evidence of "an n8n workflow that does real work" (Agent & system design, 25%).

**Trade-off:** If n8n is down, ingestion stops too. The 15-minute health check (chunk 8) has to catch "no new run" as well as "run failed".

**For the panel:** "n8n is the clock and the switchboard; Python is the engine. You can see every run, and every failure, in one screen."

**Rubric:** Agent & system design (25%), Production readiness (20%).

---

## D7 — SQLite for the prototype, Postgres in production
*2026-10-02 · Status: decided*

**Decision:** Store everything in SQLite: one file (`data/monitor.db`), no database server.

**What SQLite is:** A database that lives in a single file. Most databases (Postgres, MySQL) are a program running all the time that you connect to. SQLite has no server: the engine is a library inside the Python program (`import sqlite3`, built in). It's still real SQL with tables, queries and unique constraints. It runs in every iPhone and Chrome browser, and n8n stores its own data in SQLite by default.

**Why:**
- No setup: the README must run in under 15 minutes.
- Volume is small for it: 1,500 items/day ≈ 550k/year; SQLite handles millions.
- Free dedup: URL is unique, so re-pulling a feed adds nothing (tested: second Saudi Gazette pull added 0 rows).
- Built-in full-text search (FTS5), reusable for the Q&A chunk.
- Inspectable: open the file in *DB Browser for SQLite* to show the raw data.

**Trade-off:** One writer at a time (fine: only ingestion writes, every 5 min). **No users or permissions**, so it can't "control who can see what". That's why production moves to Postgres inside the client's environment.

**For the panel:** "SQLite for the prototype: zero setup, one file. In production it becomes Postgres inside your environment, because that's where access control lives."

**Rubric:** Working outcome (20%), Production readiness (20%).

---

## D8 — Same-story detection: embeddings only
*2026-10-02 · Status: decided*

**Decision:** Group items into stories by comparing embeddings of title + summary, within a 48-hour window. No title-similarity fallback. URL uniqueness still applies as a database rule (D7).

**What an embedding is:** The meaning of a piece of text turned into a list of numbers. Texts that mean the same thing get similar numbers, even in different languages, so an Arabic and an English headline about the same event land close together.

**Why:**
- Works across Arabic and English; title similarity can't. Real example from 2026-10-02: the Flydubai incident in the Guardian, Saudi Gazette and BBC Arabic.
- Catches rewritten headlines, not just near-identical ones.
- Cheap: a fraction of a cent per day at 1,500 items.
- Embeddings stored in SQLite; Python compares a new item with the last 48 h (~3,000 items) in milliseconds. **No vector database needed.**

**Trade-off:** If the embedding API is down, grouping pauses. Items are still stored and get grouped when it returns, but "3+ outlets" can't be counted meanwhile, so the health check must flag it. The similarity threshold needs tuning on hand-checked pairs.

**For the panel:** "The system recognises the same story in Arabic and English, which is how it knows a story is spreading, not just being mentioned."

**Rubric:** Agent & system design (25%).

---

## D9 — Embedding model: OpenAI `text-embedding-3-large` (prototype), `bge-m3` (production)
*2026-10-02 · Status: decided*

**Decision:** Prototype uses OpenAI `text-embedding-3-large`. Production, once internal documents are involved, switches to `bge-m3`, an open-source multilingual model running inside the client's environment.

**Options considered:**

| Option | Arabic | Cost/month at 1,500 items/day* | Data leaves client? |
|---|---|---|---|
| OpenAI `text-embedding-3-small` | Good | ~$0.07 | Yes |
| **OpenAI `text-embedding-3-large`** | Better | ~$0.50 | Yes |
| `bge-m3` (open source, local) | Strong | $0 API, local CPU | No |

\*~80 tokens/item → ~3.6M tokens/month. Prices to re-check in the cost ticket.

**Why:**
- Cost is negligible for every option, so we picked on quality. Arabic matters most, and large is the stronger multilingual model.
- Same vendor as the LLM: one key, one bill.
- `bge-m3` is a 2 GB download, which hurts the 15-minute README and adds demo risk, so it's held back for production.

**Trade-off:** Public news text goes to OpenAI (acceptable: it's public). Switching models later means re-embedding the archive, because embeddings from different models can't be compared. That's cheap, but it has to be planned.

**For the panel:** "On public news we use OpenAI because it's simplest. The moment confidential documents arrive, embeddings switch to a model running inside your walls. It's swappable by design."

**Rubric:** Production readiness (20%), Agent & system design (25%).

---

## D10 — The LLM decides every label, including "high"; the code gives it the spread facts
*2026-10-02 · Status: decided*

**Decision:** The LLM assigns relevance, themes, sentiment, priority and the justification. It can't see how far a story has spread, so the code counts that from the `stories` table and passes it into the prompt (number of outlets, which ones, how many international, when first seen).

**Why:** Judging risk needs reading and cultural nuance, which is what the LLM is for. Counting outlets is mechanical, so the code does it and the LLM weighs it.

**Consequences:**
- **Re-judge when a story spreads.** When a story's outlet count rises, the LLM looks at the story again. A "medium" story at 13:00 can become "high" at 13:40 when a third outlet picks it up. That's "alert on the spike, not the mention" in practice.
- **The justification must name its facts** (who, what allegation, which outlets), because it's the audit trail for every alert.
- **The eval must show the LLM's "high" matches human labels**, with recall measured first (chunk 7).

**Trade-off:** Less deterministic than a coded rule. We rely on the prompt, the justification and the eval instead.

**For the panel:** "The system counts how far a story has spread; the AI weighs that with what the article actually says. Every alert comes with a one-line reason an analyst can check in seconds."

**Rubric:** Agent & system design (25%), Production readiness (20%).

---

## D11 — Only "high" alerts, and every alert goes to an analyst first
*2026-10-02 · Status: decided*

**Decision:** Only priority **high** triggers an alert: on-call analyst → approve, edit or dismiss → forwarded to the Director's office. Medium and low wait for the morning briefing.

**Why:** The brief: "nothing reaches the Director General without human sign-off". Alerting only on high keeps the analyst from drowning in noise and starting to ignore alerts.

**For the panel:** "The AI raises its hand; a person decides whether it reaches the Director General."

**Rubric:** Product judgement (20%), Production readiness (20%).

---

## D12 — Label scheme
*2026-10-02 · Status: decided (definitions refined in ticket 2.2)*

**Decision:**
- **Relevance:** on_topic / off_topic. Off-topic stops here.
- **Themes (multi-label):** 1. tourism strategy & visitor numbers, 2. destination & giga-project launches, 3. aviation, visa & entry policy, 4. reputational risk / negative coverage. An item can have more than one.
- **Sentiment toward the sector**, not the tone of the article: positive / neutral / negative.
- **Priority:** high (meets the high-risk definition → alert) · medium (needs a response → "items requiring a response") · low (awareness → coverage by theme).
- **Justification:** one English sentence that says *why* and names its facts.

**Why:**
- Multi-label: "visa rules tightened after pilgrim deaths" is both visa policy and reputational risk; forcing one theme loses information.
- Sentiment toward the sector: "Saudi Arabia denies reports of suicide bomber at Grand Mosque" is a frightening event but, for the entity, a denial. Tone and stance differ.
- The three priority levels map directly onto the briefing's sections and the alert, so every label has a consequence.

**For the panel:** "Every label decides where an article goes: an alert, the response list, or the coverage section."

**Rubric:** Product judgement (20%).

---

## D13 — Classify each item once, on arrival; both the briefing and the alerts reuse it
*2026-10-02 · Status: decided*

**Decision:** Each 5-minute run sends the LLM only *new* items that passed the keyword filter (plus stories whose outlet count rose). The stored labels feed both the 06:00 briefing and the alerts.

**Why:** At 1,500 items/day that's ~5 items per run. Cost: ~$4–7/month on GPT-6 Luna (see D14 for verified prices). Prompt caching and batching several items per call lower it further.

**For the panel:** "Classifying every article the directorate sees costs roughly what one lunch costs per month. Cost is not the constraint here; accuracy is."

**Rubric:** Agent & system design (25%); feeds the cost estimate.

---

## D14 — LLMs: GPT-6 Luna classifies, GPT-6.1 Sol writes the briefing
*2026-10-02 · Status: decided (Luna confirmed or upgraded by the eval)*

**Decision:** Two OpenAI models, each matched to its job.
- **Classification → GPT-6 Luna.** Narrow, high-volume, fixed labels: what OpenAI positions Luna for ("focused, high-volume tasks").
- **Daily briefing → GPT-6.1 Sol.** One call a day, but it must be faithful and cite every claim: the place where quality matters most.

**Options considered** (prices verified 2026-10-02, per 1M tokens in / out; cached input ~10× cheaper):

| Model | Positioning | Price | Classification cost/month* |
|---|---|---|---|
| GPT-6 Astra | Most capable | $10 / $50 | ~$700 |
| GPT-6.1 Sol | Near-Astra, lower cost | $2 / $10 | ~$85–145 |
| **GPT-6 Luna** | Efficient, high-volume | $0.10 / $0.50 | **~$4–7** |

\*1,500 items/day ≈ 45M tokens in + 5.4M out per month.

**Estimated total:** ~$10–15/month (classification ~$4–7, briefing on Sol ~$4, embeddings ~$0.50). Evals are a small one-off cost on top.

**Why:**
- Cost doesn't constrain us; accuracy does. So we start cheap and **let the eval decide**: if Luna's recall on high-risk items (especially Arabic and tricky cases) falls short on the 60 labelled items, classification moves to Sol (~$85/month).
- All three support structured outputs (fixed JSON we can always parse) and are multilingual.
- Same vendor as the embeddings (D9): one key, one bill.

**Trade-off:** OpenAI is hosted outside the Gulf. Fine for public news. Confidential documents need an in-region deployment (planned in chunk 10).

**For the panel:** "A cheap model for the thousands of routine labels, a stronger one for the single document the Director General reads. Under $15 a month total, and we let the evaluation decide whether to pay more."

**Rubric:** Agent & system design (25%): "disciplined use of the LLM API"; the brief's "why you chose it and what it costs".

Sources: [OpenAI pricing](https://developers.openai.com/api/docs/pricing) · [OpenAI models](https://developers.openai.com/api/docs/models)

---

## D15 — Classifier prompt design
*2026-10-02 · Status: decided*

**Decision:**
- **English instructions; English justifications.** Names of people, places and outlets stay as written in the original. (Briefing language is a separate decision in chunk 4.)
- **~6 worked examples in the prompt**, taken from traps we actually found: "العلاقات" (≠ AlUla) → off-topic; Egyptian tourism → off-topic; "Saudi Arabia denies suicide bomber reports" → about us, a denial; foreign-government criticism of visa policy → high if spread; positive giga-project launch → low/positive; Flydubai incident → aviation, but is it about us?
- **Examples never come from the 60-item eval set.** Otherwise the test is worthless.
- **One item per call.** With caching the repeated instructions are ~10× cheaper, so batching saves little; one item per call keeps failures isolated and every label traceable to one call.
- **Justification before the label** in the output format: the model reasons first, then decides.
- ~~Versioned prompt~~ (dropped by D30): one prompt file, `prompts/classify.md`, edited in place; git keeps its history.

**For the panel:** "The prompt is a versioned document, tested against cases it has never seen. When we change it, we can show whether it got better or worse."

**Rubric:** Agent & system design (25%), Production readiness (20%).

---

## D16 — Q&A over the archive is kept, not cut
*2026-10-02 · Status: decided*

**Decision:** Keep chunk 9 (analysts ask the archive questions in plain language), even though the brief lists it among the things that can be dropped.

**Why:** Every article already has a stored embedding (D8), which is exactly what's needed to search the archive. The hard part is already built, so it's cheap. It's also requirement 6 of the brief, and it's the feature the analysts use every day.

**Trade-off:** It's still built after the core loop. If time runs out, the core loop is protected first.

**For the panel:** "The same fingerprints that tell us a story is spreading let analysts search everything we've ever ingested."

**Rubric:** Working outcome (20%), Product judgement (20%).

---

## D17–D22 — Briefing, approval and eval defaults
*2026-10-02 · Status: decided*

| ID | Decision | Why | For the panel |
|---|---|---|---|
| **D17** | **Briefing in English**; Arabic names kept as written | One language for the faithfulness judge and the number check; an Arabic version can be added later | "One language, every claim checked. Arabic output is a switch, not a rebuild." |
| **D18** | **Email via n8n (Gmail)** to the DG's office | Matches the scope; simplest reliable channel for a demo | "It arrives where the Director already works." |
| **D19** | **Approval through an n8n form:** the analyst gets an emailed link to the draft in an editable box, with Approve / Reject. Alerts use the same form | Human sign-off with no custom front end (the brief allows n8n forms) | "Nothing moves without a person pressing Approve." |
| **D20** | **Send as soon as it's approved, 07:30 at the latest** | Meets the brief's "by 07:15" example whenever the analyst approves early, and the 07:30 deadline either way | "Approve at 06:40, and it's on the desk at 06:40." |
| **D21** | **Analyst can correct each item's priority** in the form (dropdown); corrections are saved | The brief's "what good looks like" has the analyst correcting a classification. Corrections become extra eval data | "Every correction teaches us where the model is weak." |
| **D22** | **Eval on 30 hand-labelled items** (60 if time allows), always including Arabic and trap cases. **Labels are done by hand**; only the eval code and the judge are AI | The labels are the ground truth the AI is measured against. AI-written labels would mean the AI grading itself | "I labelled the test set myself, then checked whether the AI judge agrees with me before trusting it." |

**Rubric:** Product judgement (20%), Production readiness (20%), Working outcome (20%).

---

## D23 — No keyword filter: every new article goes to the AI
*2026-10-03 · Status: decided · replaces D3*

**Decision:** Remove the keyword pre-filter. Every new article is embedded and classified; the AI's on-topic / off-topic label does the filtering.

**Why:**
- **An allowlist only catches what we predicted.** A new project name or an unexpected phrasing would be silently dropped: the worst kind of miss for a monitoring system. (Taha's call.)
- **A blocklist fails the other way.** "Football" looks safe to block, but the Club World Cup, Formula 1 in Jeddah and the Esports World Cup in Riyadh are tourism stories.
- **It costs almost nothing.** The cost estimate (~$4–7/month on Luna, D14) already assumed every article reaches the AI. Embedding everything is ~$0.50/month.
- One component fewer to build and explain, and the Arabic word-matching problem (D3) disappears.

**Trade-off:** Off-topic articles also get embedded and grouped into stories. Harmless: they never reach the briefing or alerts.

**For the panel:** "We don't guess keywords. Every article is read by the AI, because missing a story costs more than reading one."

**Rubric:** Product judgement (20%), Agent & system design (25%).

---

## D24 — No escalation for unanswered alerts (prototype)
*2026-10-03 · Status: decided*

**Decision:** If the on-call analyst doesn't respond to a high-risk alert, nothing escalates automatically in the prototype. The briefing's 06:50 escalation to the backup analyst stays.

**Why:** Build time is better spent on the core loop. This is a known gap, explained rather than built.

**Trade-off:** An alert that arrives while the analyst is away from email can sit unanswered, which is the exact problem the brief describes ("urgent negative stories can sit unnoticed for hours"). In production: a phone push (Teams / WhatsApp) plus escalation to a backup after 15 minutes without acknowledgement, using the same n8n wait-with-timeout pattern as the 06:50 briefing rule.

**For the panel:** "Today an alert reaches one analyst by email. Next step: a phone push, and if nobody acknowledges within 15 minutes, it goes to the backup. The briefing already works this way."

**Rubric:** Product judgement (20%), Communication (15%): honest about limitations.

---

## D25 — No agent framework: direct OpenAI calls
*2026-10-03 · Status: decided*

**Decision:** No LangChain, LlamaIndex or other agent framework, and no vector database (D8). Every AI call is a plain call through the official `openai` library. The whole stack is 8 pinned libraries (`requirements.txt`).

**Why:**
- The rubric asks for "disciplined use of the LLM API". A framework hides exactly the parts the panel will ask about: the prompt, the model, the parameters, what happens on failure.
- The brief: "you must be able to explain and defend every line". Direct calls are short and readable.
- Our "agent" is a fixed pipeline (fetch → embed → group → classify → brief) with n8n as the orchestrator. It doesn't need an autonomous tool-calling loop.

**Trade-off:** We write small pieces ourselves (retries, parsing structured output) that a framework would give us for free.

**For the panel:** "Every AI call is a few lines you can read. Nothing is hidden behind a framework, so every answer the system gives can be traced to one prompt and one model."

**Rubric:** Agent & system design (25%).

---

## D26 — Drop Arab News: it blocks an honest User-Agent
*2026-10-03 · Status: decided*

**Decision:** Remove Arab News. We now ingest **9 sources** (4 English, 5 Arabic), still above the brief's minimum of 8.

**What happened:** The first real ingestion run got HTTP 403 from Arab News. Testing showed it accepts only the vaguest User-Agent (`Mozilla/5.0`) and rejects anything that identifies a monitoring tool, even a full, real Chrome browser string.

**Why drop it:** Sending a vaguer identity to get past their filter is a mild way of circumventing a block, the opposite of D2's "only what publishers choose to give machines". We dropped Al Arabiya for the same reason. Saudi Gazette covers the same national-English role.

**Trade-off:** We lose the largest English Saudi daily. In production, with licensed content (D2), this disappears.

**For the panel:** "When a publisher blocked our honest identification, we dropped them rather than disguise ourselves. That's the standard a government client should hold its vendors to."

**Rubric:** Production readiness (20%), Product judgement (20%).

---

## D27 — Stories merge when an article matches more than one
*2026-10-03 · Status: decided*

**Decision:** A new article is compared with every recent article. It joins the story of its best match, and **if it also matches (above the threshold) articles in other stories, those stories are merged into one.**

**Why, measured on the first real run (478 articles):** Matching only the single best article split the Flydubai incident into an English story (6 outlets) and an Arabic one: the early Arabic articles started their own story, and later English ones never scored high enough against them. **Spread was under-counted, which can hide an alert.** With merging: **one story, 7 outlets, 35 articles.** The only Flydubai articles left outside are genuine new developments (flights suspended to Tel Aviv; Netanyahu's threat).

**Alternatives considered:** a lower threshold (risks joining unrelated stories everywhere); giving each story an *average* fingerprint and comparing with stories instead of articles (averages blur: a 30-article story drifts toward its most common angle).

**Trade-off: over-merging.** Ten articles about Saudi medals at the Asian Games (different golds, a bronze, show jumping) merged into one topic story. That **over-counts** spread, which risks false alarms, never missed ones. With recall first (missing a crisis is the expensive mistake), that's the safer direction to be wrong. Threshold tuning (ticket 1.6) keeps both errors small; the Flydubai split and the Asian Games blend are the first test cases.

**For the panel:** "On the first real run, the system split one event into an Arabic and an English story. We added merging, measured it, and chose to err toward false alarms, because a missed crisis costs more."

**Rubric:** Agent & system design (25%), Production readiness (20%): evaluation, honest about limits.

---

## D28 — What counts as "on topic" (the relevance boundary)
*2026-10-03 · Status: decided*

**Decision:** The directorate's scope is the tourism sector as a destination. **Out of scope:**
- **Hajj, Umrah, pilgrims and the holy sites**, including safety reports at the Grand Mosque.
- **Saudi defence, security, oil and diplomacy**, unless the story affects visitors.
- **Saudi athletes competing abroad.** Only events *hosted in* Saudi Arabia count.
- **Incidents on foreign airlines** that say nothing about Saudi Arabia as a destination (e.g. the Flydubai incident, despite its emergency landing in Tabuk).

**Why:** Taha's judgement as the analyst. These were the five judgement calls in the classifier prompt draft (`prompts/classify_v1.md`). Religious tourism likely sits with a different ministry; a medal in Japan or a crime on a UAE airline doesn't change how the world sees Saudi Arabia as a destination.

**Trade-off:** The biggest story of the week (Flydubai, 35 articles, 7 outlets) is deliberately **not** briefed. If the DG's office expects aviation incidents on Saudi soil, this boundary moves; it's one paragraph in the prompt.

**For the panel:** "The hardest part wasn't the code, it was deciding what this directorate is responsible for. That boundary is written in plain words in the prompt, so your team can move it."

**Rubric:** Product judgement (20%).

---

## D29 — Classifier prompt v2: tighter events, at least one theme
*2026-10-03 · Status: decided*

**Decision:** The classifier prompt (`prompts/classify.md`) changed:
- Hosted events count only when the article is about **visitors, attendance, tickets or the hosting itself**. Match reports, results, line-ups, referees and coaches' comments are off-topic.
- **Every on-topic article has at least one theme.** If none of the four fits, it's off-topic (the brief requires classification against the four themes).

**Evidence (v1 vs v2 on the 12 articles v1 called on-topic, 2026-10-03):** 8 Gulf Cup previews, a fight night and a horse show flipped to off-topic as intended. The airport shuttle, Riyadh Season tickets, AlUla, and fans' joy at the Gulf Cup stayed on-topic. One borderline item (Jeddah architecture guidelines) also flipped without being targeted: **the model isn't perfectly consistent between calls**, which is why quality is measured on a labelled set, not on single answers.

**For the panel:** "When the first run showed football previews labelled as tourism, we tightened one sentence in the prompt, versioned it, and measured the change before and after."

**Rubric:** Production readiness (20%): evaluation and versioned prompts.

---

## D30 — Keep it minimal: one prompt file, no prompt versions
*2026-10-03 · Status: decided · replaces the versioning part of D15*

**Decision:** One prompt file per job (`prompts/classify.md`), edited in place. No version numbers, no version-tracking code or columns. **Git is the version history:** every change to the prompt is a commit you can show.

**Why:** What matters most is that every part of the system can be explained simply on a slide. Version-tracking code adds machinery without changing what the system does. Taha's call.

**Trade-off:** The database doesn't record which wording produced each label. Before/after comparisons (like D29's) are run by hand when the prompt changes.

**For the panel:** "The AI's instructions are one plain-English file your team can read and edit. Every change is in the project history."

**Rubric:** Communication (15%), Agent & system design (25%).

---

## D31 — The daily briefing: structure, citations, length
*2026-10-03 · Status: decided*

**Decision:**
- **Structure (the brief's):** three headline lines, items requiring a response, coverage by theme. **The look-ahead is cut**, which the brief explicitly allows; said on a slide.
- **Input:** on-topic stories from the last 24 hours, grouped by story.
- **Citations are numbered by the code, not the AI.** The AI writes `[4]`; the code attaches the source list with real links. The AI never sees or writes a URL, so it can't invent a source.
- **Header facts come from the database, written by code:** date, coverage window, sources checked and sources unavailable.
- **Number check (plain Python):** every number in a sentence must appear in the article it cites. Failures are shown as warnings to the analyst on the approval form, never sent to the DG's office.
- **Length:** exactly 3 headlines; every item requiring a response; at most 5 bullets per theme, with "+N more lower-priority items" so nothing silently disappears. One page, about 2 minutes to read.

**For the panel:** "The DG gets one page; the analyst sees everything. Every sentence points to a numbered source, the links come from our database, and any number that doesn't match its source is flagged to a person before approval."

**Rubric:** Working outcome (20%), Production readiness (20%): catching hallucinated facts.

---

## D32 — The DG's email reads like a brief, not a list
*2026-10-03 · Status: decided*

**Decision:**
- **Tone (prompt):** "Good morning." plus a three-sentence overview (the brief's three-line summary), then "Needs your attention", then "Today's coverage" as short human paragraphs. Empty themes are left out (no "No coverage"); a story appears once.
- **Look (code, after approval):** one card per story, with the **publisher's own image from the RSS feed** (7 of 9 feeds include one, so it's not scraping, D2), outlet, linked headline and the AI's paragraph. Theme tags replace empty headings. Citations become small clickable numbers. A footer lists sources and "Reviewed and approved by …".
- **The analyst still edits plain text.** Cards are built only after approval, from the citations in the text.

**Why:** The first version read like a database dump ("Reputational risk: No coverage."). A DG's office reads a brief that leads with what matters, the way Google News briefings do. Taha's call.

**For the panel:** "The Director gets something that reads like a note from a trusted analyst, and every sentence still links to its source."

**Rubric:** Working outcome (20%): "output a client user would find useful"; Communication (15%).

---

## D33 — Classification eval: results, and widening "about us"
*2026-10-03 · Status: decided*

**Setup:** 30 articles (22 real from 2026-10-03, 8 synthetic to cover crises the day didn't have; 9 Arabic). Labels drafted against the written rules (D28), then reviewed and confirmed by Taha: all 30 kept. Prompt-example stories (Flydubai, the Grand Mosque denial) excluded (D15). Script: `eval/run_eval.py`; outputs in `eval/results_classification_before.txt` and `eval/results_classification.txt`.

| | Run 1 | Run 2 (after widening) |
|---|---|---|
| **Recall on high-risk** | 3/4 | **4/4** |
| False alarms | 0 | 0 |
| Relevance agreement | 29/30 | 28/30 |
| Priority agreement | 28/30 | 28/30 |

**The miss in run 1:** tourists injured at a Riyadh Season concert (4 outlets, 2 international) came out medium. The AI followed the written rule: "about us" listed only the entity, leadership, giga-projects and visa policy. **A definition gap, not a model failure.** Fix: "Harm to visitors' safety at any destination or hosted event in the Kingdom also counts as about us."

**Remaining disagreements:** two borderline items (Jeddah heritage architecture rules; a fan story at the Gulf Cup) labelled on/low by the AI and off by Taha. Jeddah flipped between runs with no related prompt change: **the model isn't fully consistent on genuinely borderline cases.** Both err toward including a low item, which the analyst trims at approval.

**Honest caveat:** run 2 re-tests on the same 30 items after a fix, so it partly reflects tuning to this set. In production: a fresh labelled set each month, plus every analyst correction at approval (D21) added to it.

**For the panel:** "Recall first: missing a crisis is the expensive mistake. On 30 hand-labelled articles, every crisis caught and no false alarms. The one miss came from our own definition being too narrow; we fixed the definition, not the model."

**Rubric:** Production readiness (20%): evaluation.

---

## D34 — No LLM judge in the prototype; eval stops at classification + the number check
*2026-10-03 · Status: decided*

**Decision:** The eval is: (1) classification measured on 30 hand-labelled articles (D33); (2) the number check on every live briefing (D31); (3) analyst review of every briefing, with the AI draft and the sent version both kept (D19). No LLM judge.

**Why:** Taha's call: keep everything minimal and explainable. The judge (a second AI checking each briefing sentence against its source) is a separate system that itself needs evaluating before it can be trusted.

**Trade-off:** Wrong names and contradictions in a briefing are caught only by the analyst, not automatically. The number check catches numeric errors only.

**For the panel:** "Today, every number is checked automatically and every briefing is reviewed by an analyst before it's sent. Next, I'd add an AI checker for names and contradictions, but only after showing it agrees with our analysts."

**Rubric:** Production readiness (20%), Communication (15%): honest about limits; feeds "what we'd build next".

---

## D35 — The alert rule: AI judges content, code counts spread
*2026-10-03 · Status: decided · refines D10*

**Decision:** An alert fires only when a story is **high** (the AI judged it about us, and negative and serious) **and** the `story_spread` view shows it's **amplified**: an international outlet, **or** 3+ outlets. The alert states why it qualified, e.g. "amplified (counted): 3 outlet(s), including an international outlet".

**Why:** Taha's check: alerts must follow the three-part rule, not just "anything the AI calls high". Rules 1–2 need reading and cultural judgement (the AI). Rule 3 is pure counting, so code makes it deterministic and auditable: an alert can always be traced to which outlets carried the story.

**For the panel:** "The AI reads; the code counts. An alert needs both: the AI judging the story serious and about us, and our data showing it has spread."

**Rubric:** Agent & system design (25%), Production readiness (20%).

---

## D36 — Failure handling: the briefing always arrives
*2026-10-03 · Status: decided · Q&A cut (D16 reversed for time)*

**Decision:**
- **AI down at 06:45:** `briefing.py` writes a fallback itself, with every overnight story (outlet, priority, title, citation) and a bold note: "The AI draft failed this morning. Please write the summary manually." Same email, form, approval and audit trail; n8n unchanged. Tested by forcing a failure.
- **A feed down:** the briefing header names the unavailable sources (from `source_runs`).
- **AI or embeddings down mid-run:** articles are saved anyway; the next good run groups and labels them (D8).
- **A whole workflow fails** (e.g. the Python server is down): n8n's built-in Error Workflow emails the team.
- **Q&A over the archive is cut** for time, which the brief explicitly allows. It reverses D16 and goes on the "next two weeks" slide.

**Why:** From Taha's grooming notes: "if the LLM API is down we just send the analyst the ingested news, with a message telling them that the LLM is down." Each failure degrades to *less automation*, never to *nothing arriving*.

**For the panel:** "If the AI fails at 06:45, the analyst still gets every story at 06:00-something, with a note to write the summary by hand. The Director's briefing is late by minutes, never missing."

**Rubric:** Production readiness (20%): error handling.

---

## D37 — The control room: one shadcn-style page, no second app
*2026-10-03 · Status: decided*

**Decision:** A read-only page at `http://127.0.0.1:8000/`, served by the existing Python server: source status, the last-24-hours funnel (articles → stories → on topic → alerts), on-topic stories with the AI's reason, the approvals trail with the exact emails sent, and one **Publish demo crisis** button. Built with **Basecoat** (shadcn/ui's design ported to plain HTML) and Tailwind, both saved inside the project so it works offline. The demo feed is always on and stays empty until the button is pressed.

**Why:** Taha wants a demo that looks polished and is organised on a screen share. Next.js + shadcn + Skiper UI would add a second app (Node, npm, a build step, React) and paid components; Basecoat gives the same shadcn look in one HTML file that's easy to explain.

**For the panel:** "This is what the analyst sees: what the system read, what it thinks matters and why, and who approved what reached the Director General."

**Rubric:** Working outcome (20%), Communication (15%).

---

## D38 — Cost, measured
*2026-10-04 · Status: decided · updates D13/D14's estimates*

**Measured on live calls:** classification 1,543 input tokens per article, 1,540 served from OpenAI's prompt cache, ~195 output; embeddings 142 tokens per article. At ~45,000 articles a month: classification ≈ $5.10, embeddings ≈ $0.83, daily briefing ≈ $0.70, alerts $0. **AI total ≈ $7 a month**, lower than the earlier $10–15 estimate, which didn't account for caching. Without caching, classification alone would be ~$11.

**For the panel:** "Reading every article the directorate sees costs about seven dollars a month. We measured it rather than estimating it."
