"""
GitHub issues fetcher module.
"""
import json
import os
import urllib.request
from models import FeedbackItem

MAX_GITHUB_ITEMS = 25


def fetch_github_issues(repo, limit=MAX_GITHUB_ITEMS):
    """Pull open issues from a public repo (supports GITHUB_TOKEN for higher rate limits)."""
    url = "https://api.github.com/repos/%s/issues?state=open&per_page=%d" % (repo, limit)
    headers = {"User-Agent": "feedback-radar"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "token %s" % token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print("[warn] GitHub: could not fetch %s (%s) — continuing without it" % (repo, e))
        return []

    items = []
    for issue in data:
        if "pull_request" in issue:  # the issues API also returns PRs
            continue
        body = (issue.get("body") or "")[:1500]
        items.append(FeedbackItem(
            id="gh-%s" % issue["number"],
            source="GitHub",
            author=issue["user"]["login"],
            text=("%s\n\n%s" % (issue["title"], body)).strip(),
            url=issue["html_url"],
            created=issue["created_at"],
        ))
    print("[ok] GitHub: fetched %d feedback items from %s" % (len(items), repo))
    return items
