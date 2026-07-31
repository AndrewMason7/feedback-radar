"""
Fetchers subpackage for Feedback Radar ingestion routines.
"""
from models import FeedbackItem
from fetchers.github import fetch_github_issues
from fetchers.sheets import fetch_google_sheet
from fetchers.gmail import fetch_gmail
from fetchers.demo import demo_data

__all__ = [
    "FeedbackItem",
    "fetch_github_issues",
    "fetch_google_sheet",
    "fetch_gmail",
    "demo_data",
]
