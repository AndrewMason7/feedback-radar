# Radar 📡

Every voice, one dashboard.

Radar collects feedback from **GitHub Issues**, **Google Sheets**, and **Gmail**, triages it
with a **Google Antigravity SDK** agent, and renders a live, filterable HTML dashboard.

![Radar dashboard](docs/screenshot-1-dashboard.png)

- 📌 Short auto-generated title for every item (invented when the rant has none)
- 🏷️ Category: bug / feature / question / docs / praise / rant
- 🔴 Importance + 🛠️ estimated difficulty + ⏱️ ETA
- 😡 Sentiment (frustrated / neutral / excited)
- ⧉ Automatic 2-Pass duplicate merging (multi-source duplicate clustering)
- ⚡ Quick Wins: high impact + low effort, flagged automatically
- ☕ Executive morning brief + overall mood bar
- 💾 SQLite caching (`db.py`) — skips previously triaged items to save LLM API quota
- 🎛️ Fully filterable: type, importance, source, duplicates, quick wins, live search
- 🔁 Automatic retries with exponential backoff (SDK v0.1.9 `RetryConfig`)
- 🛟 Tool failures recover gracefully (SDK v0.1.9 `ToolExecutionError` hooks)
- ⏰ `--serve` mode rebuilds the dashboard daily via the SDK trigger system with non-blocking async I/O

---

## Modular Architecture 🏗️

Radar follows a strict **Separation of Concerns (SoC)** package structure:

```
feedback-radar/
├── radar.py                 # Lean CLI entry point & orchestrator (~120 lines)
├── db.py                    # SQLite persistence & content hashing layer
├── models.py                # Core dataclasses (FeedbackItem, Card) & enum normalizers
├── fetchers/                # Ingestion subpackage
│   ├── github.py            # GitHub issues fetcher (REST + GITHUB_TOKEN support)
│   ├── sheets.py            # Google Sheets CSV fetcher with column length heuristics
│   ├── gmail.py             # Gmail API & OAuth token manager
│   └── demo.py              # Offline demo dataset
├── engine/                  # Processing subpackage
│   ├── triage.py            # Resilient batch LLM triage pass
│   ├── dedup.py             # Pass 2 global deduplication engine
│   ├── brief.py             # Executive morning brief synthesizer
│   ├── prompts.py           # Strict JSON prompt templates
│   └── sdk.py               # Antigravity SDK agent configuration & hooks
└── ui/                      # Presentation subpackage
    ├── static/style.css     # Material 3 CSS layout & styles
    ├── static/app.js        # Client-side filtering & search JS
    └── renderer.py          # HTML template renderer & XSS escaping
```

---

## Try it in 30 seconds (no API key)

```bash
python radar.py --demo
```

Open `dashboard.html` — same pipeline, precomputed data.

---

## Real run

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
(default: 86400 = daily) using the SDK's official `every()` trigger mechanism.

---

### Sources & Configuration (environment variables)

| Variable | Description | Default |
|---|---|---|
| `RADAR_GITHUB_REPO` | Public repo `owner/repo` | `google-antigravity/antigravity-sdk-python` |
| `GITHUB_TOKEN` | Optional GitHub Personal Access Token (boosts rate limits to 5,000 req/hr) | unset |
| `RADAR_SHEET_CSV` | Published Google Sheet CSV URL | local `sample_feedback.csv` |
| `RADAR_GMAIL_QUERY` | Gmail search query | `label:feedback newer_than:30d` |
| `RADAR_MODEL` | Override the default model | SDK default |
| `RADAR_SERVE_INTERVAL` | Seconds between rebuilds in `--serve` mode | `86400` |

### Google Sheets as a source
1. Open the sheet (e.g. Google Form responses)
2. **File → Share → Publish to web → CSV**
3. Set `RADAR_SHEET_CSV` to that link

Expected columns: `feedback, author, date` (lenient — uses column length heuristics if header names differ).

### Gmail as a source (optional)
```bash
pip install google-api-python-client google-auth-oauthlib
```
1. Enable the **Gmail API** in Google Cloud Console
2. Create OAuth credentials (Desktop app), save `credentials.json` next to the script
3. First run opens a consent screen and saves `token.json` (chmod 600)

If setup is missing, the source skips itself silently.

---

## Security notes 🔒
- Feedback text is treated as **untrusted data** — the agent is instructed to ignore any
  instructions embedded inside it (prompt-injection guard)
- Agent runs with the SDK default **read-only** policy — it never touches your filesystem
- All feedback content is HTML-escaped before rendering (XSS-safe)
- `credentials.json`, `token.json`, and `radar.db` are git-ignored — never commit them

---

## Tests

```bash
python test_radar.py
```

or via pytest:

```bash
pip install pytest
pytest test_radar.py -v
```

---

## Roadmap
- GitHub MCP server instead of REST (deeper pulls)
- Cron-expression triggers (SDK currently ships `every()` only)
- More sources: Discord, Play Store reviews, X

---

Built with [Google Antigravity SDK](https://github.com/google-antigravity/antigravity-sdk-python) v0.1.9 🤖
