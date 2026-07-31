"""
Offline demo mock dataset for Feedback Radar.
"""
from models import Card


def demo_data():
    """Full offline demo — same pipeline, precomputed analysis, no API key needed."""
    cards = [
        Card("gh-12", "Agent hangs when tool output exceeds buffer", "bug", "high", "medium",
             "days", "Long tool outputs freeze the agent loop instead of truncating gracefully.",
             "frustrated", "GitHub", "https://github.com/example/issues/12", "devfarhan", None, 3),
        Card("gh-31", "Support TypeScript SDK", "feature", "high", "hard", "weeks",
             "Many teams want a TS version of the agent harness.", "excited",
             "GitHub", "https://github.com/example/issues/31", "sara_codes", None, 4),
        Card("gh-32", "Please add a Node/TS version", "feature", "high", "hard", "weeks",
             "Duplicate request for TypeScript support.", "excited",
             "GitHub", "https://github.com/example/issues/32", "mo_oss", "gh-31"),
        Card("gh-33", "TS bindings when?", "feature", "high", "hard", "weeks",
             "Same TypeScript request, different wording.", "neutral",
             "GitHub", "https://github.com/example/issues/33", "linus_w", "gh-31"),
        Card("gs-1", "TypeScript support would unblock our whole team", "feature", "high", "hard",
             "weeks", "Sheet respondent echoes the TypeScript demand.", "excited",
             "Google Sheet", "", "fatimah.dev", "gh-31"),
        Card("gs-2", "JS version please", "feature", "medium", "hard", "weeks",
             "Short duplicate of the TypeScript ask.", "neutral",
             "Google Sheet", "", "anon", "gh-31"),
        Card("gh-18", "Docs for hooks are confusing", "docs", "medium", "easy", "hours",
             "New users cannot tell Inspect from Transform hooks from the current docs.",
             "frustrated", "GitHub", "https://github.com/example/issues/18", "noor_writes", None, 1),
        Card("gs-3", "I cannot figure out hooks from the README", "docs", "medium", "easy",
             "hours", "Same documentation gap reported via the form.", "frustrated",
             "Google Sheet", "", "khalid", "gh-18"),
        Card("gh-21", "Add retry config for transient API errors", "feature", "high", "easy",
             "days", "Built-in exponential-backoff retry would remove lots of boilerplate.",
             "neutral", "GitHub", "https://github.com/example/issues/21", "api_junkie", None, 0),
        Card("gs-4", "Agent sometimes answers in the wrong language", "bug", "medium", "medium",
             "days", "Locale occasionally ignored in structured output mode.", "frustrated",
             "Google Sheet", "", "amani", None, 0),
        Card("gh-25", "This SDK replaced our whole in-house harness", "praise", "low", "easy",
             "hours", "Team deleted their custom agent loop after adopting the SDK.", "excited",
             "GitHub", "https://github.com/example/issues/25", "ex_msft", None, 0),
        Card("gs-5", "How do I run this with Vertex instead of an API key?", "question", "low",
             "easy", "hours", "Auth path for Vertex/ADC unclear to newcomers.", "neutral",
             "Google Sheet", "", "yunus", None, 0),
    ]
    summary = {
        "headline": "TypeScript support is the loudest demand (5 merged reports), while the "
                    "hook-docs gap is today's cheapest frustration to fix.",
        "bullets": [
            "5 duplicates merged into 2 root issues — the real queue is shorter than it looks.",
            "Quick win: rewrite the hooks docs (high impact, hours of effort).",
            "One high-importance hang bug needs reproduction before it spreads.",
        ],
        "mood": {"frustrated": 38, "neutral": 29, "excited": 33},
    }
    return cards, summary
