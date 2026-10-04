# Source selection — decision log

How we chose the news sources the agent ingests, and why each one is in or out.
The machine-readable list lives in `sources.yaml`; this file is the reasoning behind it.

## How we judge a source

Every candidate is asked four questions:

1. **Does it work?** Live-tested: returns fresh items, doesn't block bots.
2. **Is it on topic?** Share of items about Saudi tourism, visas, giga-projects. A general feed is mostly noise — and every off-topic item costs an LLM call unless filtered first.
3. **What job does it do?** It must fill a gap, not just add to the count.
4. **What text does it give us?** Summary vs headline only. The number check in the eval can only verify against text we actually have.

## Rule: no scraping

We only use what publishers put in their own RSS feeds: no scraping, and no aggregators. The brief allows only "sanctioned scraping", and for a government client the clean position is no scraping at all: no robots.txt arguments, no extraction code that breaks when a site redesigns. The cost is that fact checks can only verify against the text in the feed (title + summary). The briefing only claims what the feed says.

## The jobs a source can do

| Job | Why we need it |
|---|---|
| **National voice** | What Saudi media is saying — the body of the briefing. |
| **International amplifier** | Our high-risk rule says "amplified" = a top-tier/international outlet carries it. Without these outlets that rule can't fire. |
| **Official channel** | To flag "misinformation about policy" we need the official version to compare against. |
| **Arabic** | The cultural reading is the hard part; without Arabic the system can't help where it matters most. |

## Target: 10 sources

The brief asks for at least 8. We take 10: if a feed dies mid-demo we're still above 8, and every extra source is more upkeep ("narrow and working beats broad and unfinished"). Slots are assigned by job, so each source has to fill a gap:

| Job | Slots |
|---|---|
| National voice (EN) | 2 |
| Arabic | 3 |
| International amplifier | 3 |
| Official channel | 1 |
| Trade press (aviation/visa) | 1 |

## Decisions

Tested on 2026-10-02. "On topic" = keyword match on title + summary, out of one pull.

| # | Source | Lang | Job | Works | On topic | Text | Decision |
|---|---|---|---|---|---|---|---|
| 1 | Saudi Gazette | EN | National voice | ✅ 50 items, fresh | 33/50 | Summary | **Keep** |
| 2 | Arab News | EN | National voice | ❌ blocks honest User-Agent | 16/50 | Summary | **Dropped (D26)** |
| 3 | Asharq Al-Awsat | AR | Arabic | ✅ 300 items / ~27h | ~40/300 | Short summary | **Keep** |
| 4 | BBC Arabic | AR | Arabic + international amplifier | ✅ 25 items | ~3/25 | Summary | **Keep** |
| 5 | Al Jazirah (الجزيرة) | AR | Arabic national voice | ✅ 7 items, once a day | 4/7 | Summary | **Keep** |
| 6 | Al-Monitor | EN | International amplifier | ✅ 20 items, fresh | 6/20 | Summary | **Keep** |
| 7 | Al Jazeera Arabic (الجزيرة نت) | AR | Arabic + international amplifier | ✅ 25 items, fresh | 2/25 | Summary | **Keep** |
| 8 | The Guardian — Saudi Arabia tag | EN | International amplifier | ✅ 20 items | 18/20 | Summary | **Keep** |
| 9 | BBC News — Middle East | EN | International amplifier | ✅ 30 items | 4/30 | Summary | **Keep** |
| 10 | Skift | EN | Trade press | ✅ 10 items | 1/10 | Summary | **Keep** |

### 1. Saudi Gazette — keep
Reliable Saudi-focused base with full summaries. Close to the official line, so it rarely breaks negative stories: it helps the *coverage by theme* section more than the alerts.

### 2. Arab News — dropped 2026-10-03 (D26)
The first real ingestion run got HTTP 403. Arab News accepts only the vaguest User-Agent (`Mozilla/5.0`) and rejects one that honestly identifies a monitoring tool, even a full Chrome string. Getting around that would contradict D2, so it's treated like Al Arabiya. Original reasoning kept below.

Largest English Saudi daily. Overlaps Saudi Gazette, which is useful: real duplicates to test dedup on, and the "3+ outlets" amplification rule needs several outlets covering the same beat. Two-thirds off-topic (sport, culture), so most of its items will be marked off-topic by the AI. English only: no Arabic edition (its Arabic sister paper under the same publisher, SRMG, is Asharq Al-Awsat).

### 3. Asharq Al-Awsat (Arabic) — keep
Saudi-owned pan-Arab heavyweight, the strongest Arabic outlet we can actually reach. Noisy (~13% on topic); the AI marks the rest off-topic.

**Lesson: Arabic keyword matching is crude.** Testing this feed, "العلا" (AlUla) matched *العلاقات* ("relations"), "طيران" matched a footballer suing an airline, and "سياحة" matched *Egyptian* tourism. Arabic attaches prefixes and suffixes to words, so:
- a keyword filter would wrongly drop or admit stories, so there is none (D23); the AI decides relevance;
- these become tricky cases in the 60-item labelled eval set.

### 4. BBC Arabic — keep
Rarely about Saudi tourism, so it adds little to the daily briefing, but it's what the alerts are for: a critical BBC Arabic piece reaches millions of Arabic readers. It's the Arabic-language half of the "amplified" rule.

### 5. Al Jazirah (الجزيرة) — keep
Saudi Arabic daily based in Riyadh (al-jazirah.com). **Not** Al Jazeera, the Qatari network (aljazeera.net), which we tested separately and rejected. Easy to mix up, so be precise in the presentation. The feed is the print edition: ~7 lead stories and op-eds, published once a day at midnight. That's a good fit for the morning briefing (today: an op-ed on AlUla as a year-round destination) and no use for alerts.

### 6. Al-Monitor — keep
Middle East specialist outlet, read in Washington policy circles. Best on-topic rate of the international candidates (6/20, vs France 24 EN 7/30, NYT Middle East 4/44). A critical Al-Monitor piece on visa or giga-project policy reaches exactly the foreign-official audience the directorate cares about.

### 7. Al Jazeera Arabic — keep
Qatari network (aljazeera.net), not to be confused with Al Jazirah (#5). Rarely on topic today (2/25), but it's one of the highest-reach Arabic outlets, and when it does cover Saudi tourism, a critical angle is likely. That makes it a source the alerts exist for, like BBC Arabic. Takes the spare slot freed by dropping the official channel (D4). Arabic edition chosen over English: English scored 0/25, and the Arabic audience is the one that matters most to the directorate.

### 8. The Guardian (Saudi Arabia tag) — keep
A Saudi-only tag, so almost no noise (18/20). Critical Western coverage often appears here first: human rights, labour conditions on giga-projects, diplomatic rows. Mostly politics, so it's mainly for alerts.

### 9. BBC News Middle East — keep
The highest-reach English outlet. A Saudi tourism story here has gone global. It's the English counterpart to BBC Arabic. Mostly off-topic (4/30); the AI handles that.

### 10. Skift — keep
Leading travel-industry outlet: tourism strategy, visitor numbers, destination launches, airline deals (themes 1–2). Industry insiders read it. Low volume. Beat Simple Flying (aviation only, 0/10 on topic).

### Known gap
No source specialises in **visa and entry policy** (theme 3). It arrives via Arab News, Saudi Gazette and Al-Monitor. Goes on the limitations slide.

## Rejected without a slot

| Source | Why out |
|---|---|
| Al Jazeera English | 0/25 on topic |
| France 24 EN/AR, NYT Middle East, FT Middle East, DW, CNN Arabic, Independent Arabia, Simple Flying | Work, but lost the slot to better-fitting feeds |
| The National (UAE) | 4/100 on topic |
| Asharq Al-Awsat English | Headlines only, duplicates the Arabic edition |
| Reddit r/saudiarabia | Weak, noisy social signal |
| Al Arabiya EN/AR, Sabq, Argaam | 403, bot protection |
| Arab News (dropped after selection) | Rejects an honest User-Agent; see D26 |
| Al Riyadh, Al Eqtisadiah | 404 |
| Okaz, Al Watan, Al Madina, Al Yaum, SPA site | Responds but no usable feed |
| Middle East Eye, Arabian Business | Timeout |
| X/Twitter | API is paid, out of scope |
| Google News (EN + AR queries) | Aggregator, not a publisher. Headline-only behind Google redirect links; getting article text means decoding the links through an unofficial Google endpoint and scraping the outlet (tested: worked on 14/15, but that's scraping). Dropped to keep the story simple: publishers' own feeds only. **Cost:** we lose Saudi local Arabic press with no feed (Okaz, Sabq, Al Watan). Production fix: a licensed news feed or the directorate's existing monitoring subscription. |
| Saudi Press Agency, Ministry of Tourism | No working RSS (empty / 403) |
| Sky News Arabia | TLS handshake fails |
| Al Arabiya (other feed URLs) | 403 |
