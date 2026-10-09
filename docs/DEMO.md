# Demo script

The live demonstration (part 3 of the presentation): **about 8 minutes**, from ingestion to an approved briefing, then a live alert. Everything runs on this laptop.

---

## Before you present

**The day before**
- [ ] `./start.sh` works from a fresh Terminal; the control room opens.
- [ ] Both n8n workflows are **switched on** (Active), and "Ingest every 5 minutes" shows a green run in the last 5 minutes.
- [ ] Record a **backup screen recording** of the whole demo below (QuickTime → New Screen Recording). If Wi-Fi or OpenAI fails on the day, you play this.
- [ ] Take screenshots of: the control room, the analyst email, the form, the DG's briefing email, the alert email.

**30 minutes before**
1. `./start.sh`
2. `.venv/bin/python -m monitor.demo reset` (removes earlier demo articles and alerts)
3. Control room: click **Fetch news now** so the page shows fresh news.
4. Open these **browser tabs, in this order** (light mode, zoom 110–125% for the room):

| Tab | Page |
|---|---|
| 1 | Control room: http://127.0.0.1:8000/ |
| 2 | n8n: the **Ingest every 5 minutes** workflow |
| 3 | n8n: the **Daily briefing** workflow |
| 4 | The analyst inbox |
| 5 | The DG's office inbox |

5. Close everything else. Turn on Do Not Disturb.

---

## The demo

### 1. What the system sees (Tab 1, control room): 1 min
> "This is the analyst's view. Nine publisher feeds, five in Arabic, all green. In the last 24 hours the system read [N] articles, recognised them as [N] stories, and found [N] that matter to this directorate."

Point at one story card:
> "Each story shows the AI's reason in one sentence, how many outlets carried it, and which ones. This one was carried by eight outlets in two languages; the system recognised it as one story."

### 2. How it runs (Tabs 2–3, n8n): 1 min
> "n8n is the clock and the switchboard; Python does the work. Every 5 minutes this runs: fetch, group, label. Every morning at 06:00 this one drafts the briefing and sends it to a named analyst."

Click the **Executions** tab of the ingest workflow:
> "Every run is logged here. A failure would show in red."

### 3. The morning briefing (Tabs 4 → 5): 3 min
Control room: click **Send briefing now**. In the analyst inbox, open **"Daily briefing draft – …"**:
> "At 06:00 the analyst gets this. Notice the number check: every number in the draft was matched against its source automatically."

Click **Review and approve**. In the form:
> "The analyst reads the full draft and can change anything." **Delete one line live** (e.g. a story that shouldn't be there): "The AI included this, but it's outside our remit. The analyst removes it."

Choose **Approve and send**, type your name, submit. Switch to **Tab 5 (Hotmail)**:
> "Seconds later, the Director General's office receives this." Scroll: overview, the stories with photos, every sentence linked to its source, "Reviewed and approved by …" at the bottom.

### 4. A crisis breaks (Tabs 1 → 2 → 4 → 5): 2 min
> "Now the second problem: a negative story breaking at two in the afternoon."

Tab 1: click **Simulate a crisis**.
> "I've just published a synthetic article: tourists injured at a Riyadh Season concert. The system doesn't know it's a demo."

The button also fetches straight away, so there's no waiting for the 5-minute run.
> "The AI judges it about us, and negative and serious. The code counts its spread: an international outlet. Both conditions hold, so it alerts, once."

Tab 4: open **"⚠ High-risk alert: …"**, show the **"Why it alerted"** line, approve. Tab 5: the alert arrives.
> "From publication to the Director General's office in a few minutes, with a person in between."

### 5. The audit trail (Tab 1): 30 s
Scroll to **Approvals**, click the alert:
> "Every briefing and alert is recorded: the AI's draft, what the analyst changed, who approved it and when. That's the answer to 'can I trust what reaches the Director General's desk?'"

---

## If something goes wrong

| Problem | What to do |
|---|---|
| An email doesn't arrive within 30 s | Check Gmail's spam folder; otherwise switch to the backup recording |
| A node turns red in n8n | Say "this is the failure handling": open the execution and show the error, then use the backup recording |
| OpenAI is slow or down | The briefing falls back to the raw story list (show it: that's the designed behaviour), or use the backup recording |
| The control room is blank | `./start.sh` again in Terminal; it's safe to re-run |

**After the demo:** `.venv/bin/python -m monitor.demo reset`
