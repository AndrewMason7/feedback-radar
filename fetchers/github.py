"""
GitHub issues fetcher module.
"""
import json
import os
import time
import urllib.error
import urllib.request
from models import FeedbackItem

MAX_GITHUB_ITEMS = 25


def fetch_github_issues(repo, limit=MAX_GITHUB_ITEMS):
    """Pull open issues from a public repo (supports GITHUB_TOKEN for higher rate limits)."""
    url = "https://api.github.com/repos/%s/issues?state=open&per_page=%d" % (repo, limit)
    headers = {"User-Agent": "feedback-radar"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer %s" % token
    req = urllib.request.Request(url, headers=headers)

    data = None
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                break
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (401, 404, 422):  # deterministic — retrying won't help
                break
            time.sleep(0.5 * (2 ** attempt))
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (2 ** attempt))

    if data is None:
        print("[warn] GitHub: could not fetch %s (%s) — continuing without it" % (repo, last_err))
        return []
    if not isinstance(data, list):
        print("[warn] GitHub: unexpected payload from %s — continuing without it" % repo)
        return []

    items = []
    for issue in data:
        if "pull_request" in issue:  # the issues API also returns PRs
            continue
        try:
            body = (issue.get("body") or "")[:1500]
            items.append(FeedbackItem(
                id="gh-%s" % issue["number"],
                source="GitHub",
                author=(issue.get("user") or {}).get("login", "unknown"),
                text=("%s\n\n%s" % (issue.get("title", "(no title)"), body)).strip(),
                url=issue.get("html_url", ""),
                created=issue.get("created_at", ""),
            ))
        except (KeyError, TypeError, AttributeError) as e:
            print("[warn] GitHub: skipping malformed issue (%s)" % e)
    print("[ok] GitHub: fetched %d feedback items from %s" % (len(items), repo))
    return items
