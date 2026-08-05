# Radar 📡

**Every voice, one dashboard.**

Radar collects user feedback from **GitHub Issues**, **Google Sheets**, and **Gmail**,
triages it with a **Google Antigravity SDK** agent, and renders a live, filterable
HTML dashboard — so your morning standup starts with answers, not archaeology.

![Radar dashboard](docs/screenshot-1-dashboard.png)

## Why Radar?

Feedback is everywhere; insight is nowhere. Radar reads every rant, praise, and
"it would be nice if…" so you don't have to — then tells you what actually matters.

- 📌 **Titles for everything** — short auto-generated titles, even when the rant has none
- 🏷️ **Classification** — bug / feature / question / docs / praise / rant
- 🔴 **Prioritization** — importance, estimated difficulty, and ETA per item
- 😡 **Sentiment tracking** — frustrated / neutral / excited, plus an overall mood bar
- ⧉ **2-pass duplicate merging** — clusters the same complaint across every source
- ⚡ **Quick Wins** — high impact + low effort, flagged automatically
- ☕ **Executive morning brief** — the three things you need to know today
- 🎛️ **Fully filterable dashboard** — type, importance, source, duplicates, quick wins, live search

---

## How It Works ⚙️

```
 GitHub Issues ┐
 Google Sheets ┼─► 1. FETCH      concurrent async ingestion from all sources
 Gmail         ┘
                   │
                   ▼
               2. CACHE       SQLite content hashing (db.py) —
                              already-triaged items skip the LLM entirely
                   │
                   ▼
               3. TRIAGE      Antigravity agent classifies uncached items in
                              batches of 10, with guaranteed-JSON output via
                              the SDK's response_schema (structured output)
                   │
                   ▼
               4. DEDUP       Pass 2: a second agent pass clusters duplicates
                              globally, across sources and batches
                   │
                   ▼
               5. BRIEF       A third agent pass synthesizes the executive
                              summary + mood breakdown
                   │
                   ▼
               6. RENDER      XSS-safe HTML dashboard with client-side
                              filtering and live search
```

Every LLM step degrades gracefully: if the API is unreachable, over quota, or the
SDK isn't installed, Radar falls back to a built-in heuristic classifier and
structural summaries. The dashboard always ships. 📦

---

## Try It in 30 Seconds 🚀

No API key required:

```bash
python radar.py --demo
```

Fetches real open issues from `google-antigravity/antigravity-sdk-python` plus
sample sheet data, triages them with the heuristic classifier, and renders
`dashboard.html` instantly.

## Real AI Run 🤖

```bash
pip install google-antigravity
export GEMINI_API_KEY="your_key"   # from aistudio.google.com
python radar.py
```

### Keep it fresh: scheduled rebuilds ⏰

```bash
python radar.py --serve
```

Runs once immediately, then rebuilds every `RADAR_SERVE_INTERVAL` seconds
(default: 86400 = daily) using the SDK's official `every()` trigger mechanism
with non-blocking async I/O.

---

## Architecture 🏗️

Radar follows a strict **Separation of Concerns** package structure:

```
feedback-radar/
├── radar.py                 # Lean CLI entry point & orchestrator (~137 lines)
├── db.py                    # SQLite persistence & content hashing layer
├── models.py                # Core dataclasses (FeedbackItem, Card) & enum normalizers
├── fetchers/                # Ingestion subpackage
│   ├── github.py            # GitHub issues fetcher (REST + GITHUB_TOKEN + retries)
│   ├── sheets.py            # Google Sheets CSV fetcher with column length heuristics
│   ├── gmail.py             # Gmail API & OAuth token manager
│   └── demo.py              # Live repo preview fetcher (google-antigravity/antigravity-sdk-python)
├── engine/                  # Processing subpackage
│   ├── triage.py            # Batch triage, Pass 2 global dedup, brief synthesis, heuristic fallback
│   ├── prompts.py           # Prompt templates (paired with SDK response schemas)
│   └── sdk.py               # Antigravity SDK agent configuration & hooks
└── ui/                      # Presentation subpackage
    ├── static/style.css     # Material 3 CSS layout & styles
    ├── static/app.js        # Client-side filtering & search JS
    └── renderer.py          # HTML template renderer & URL scheme sanitization
```

---

## Configuration 🎛️

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | Gemini API key for the triage agent | unset |
| `RADAR_API_KEY` | Optional override — takes precedence over `GEMINI_API_KEY` | unset |
| `RADAR_GITHUB_REPO` | Public repo `owner/repo` | `google-antigravity/antigravity-sdk-python` |
| `GITHUB_TOKEN` | Optional GitHub PAT (boosts rate limits to 5,000 req/hr) | unset |
| `RADAR_SHEET_CSV` | Published Google Sheet CSV URL | local `sample_feedback.csv` |
| `RADAR_GMAIL_QUERY` | Gmail search query | `label:feedback newer_than:30d` |
| `RADAR_MODEL` | Override the default model | SDK default |
| `RADAR_SERVE_INTERVAL` | Seconds between rebuilds in `--serve` mode | `86400` |

A `.env` file next to `radar.py` is picked up automatically (see `.env.example`).

### Google Sheets as a source
1. Open the sheet (e.g. Google Form responses)
2. **File → Share → Publish to web → CSV**
3. Set `RADAR_SHEET_CSV` to that link

Expected columns: `feedback, author, date` (lenient — column-length heuristics
kick in if headers differ).

### Gmail as a source (optional)
```bash
pip install google-api-python-client google-auth-oauthlib
```
1. Enable the **Gmail API** in Google Cloud Console
2. Create OAuth credentials (Desktop app), save `credentials.json` next to the script
3. First run opens a consent screen and saves `token.json` (chmod 600)

If setup is missing, the source skips itself silently.

---

## Resilience 🛡️

Radar is built to never crash or lose data, even on a bad network:

1. **HTTP retries** — GitHub API requests use 3-attempt exponential backoff.
2. **Batch isolation** — triage runs in 10-item chunks; if batch #3 hits a 429,
   batches #1 & #2 stay cached in `radar.db` and batch #3 falls back to heuristics.
3. **Graceful dedup & brief** — if Gemini is unreachable during Pass 2 or summary
   synthesis, Radar keeps Pass 1 links and structural fallback summaries.
4. **SDK-level retries** — `RetryConfig` with exponential backoff and jitter,
   plus `ToolExecutionError` hooks that tell the agent how to recover.

## Security 🔒

- Feedback text is treated as **untrusted data** — the agent is instructed to
  ignore any instructions embedded inside it (prompt-injection guard)
- The agent runs with the SDK default **read-only** policy — it never touches your filesystem
- All feedback content is HTML-escaped and URL-sanitized before rendering (XSS-safe)
- All links are strictly limited to `http://` / `https://` schemes
- `credentials.json`, `token.json`, and `radar.db` are git-ignored — never commit them

---

## Tests ✅

Run all 20 unit tests:

```bash
python test_radar.py
```

or via pytest:

```bash
pip install pytest
pytest test_radar.py -v
```

---

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Built with the [Google Antigravity SDK](https://github.com/google-antigravity/antigravity-sdk-python) 🤖


