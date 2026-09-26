#!/usr/bin/env python3
"""
fetch_stats.py
──────────────
Fetches live GitHub stats for Wader444 using the GitHub REST & GraphQL APIs.
Outputs a JSON blob (also writes stats.json) consumed by generate_svg.py.

Required environment variable:
    GH_TOKEN  – Personal Access Token with `repo` + `read:user` scopes.

Usage:
    python fetch_stats.py            # prints JSON to stdout + writes stats.json
    python fetch_stats.py --json     # same
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# ── Constants ────────────────────────────────────────────────────────────────
USERNAME = "Wader444"
API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

# ── Auth helpers ─────────────────────────────────────────────────────────────

def get_token() -> str:
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        sys.exit(
            "ERROR: GH_TOKEN environment variable is not set.\n"
            "Create a PAT at https://github.com/settings/tokens and export it."
        )
    return token


def rest_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def graphql_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

# ── REST helpers ─────────────────────────────────────────────────────────────

def paginate_rest(url: str, headers: dict, params: dict | None = None) -> list:
    """Follow GitHub Link: next pagination and collect all pages."""
    items: list = []
    params = dict(params or {})
    params.setdefault("per_page", 100)
    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            items.extend(data)
        else:
            items.append(data)
        # next page
        url = resp.links.get("next", {}).get("url", "")
        params = {}  # params already encoded in the next URL
    return items

# ── GraphQL helpers ───────────────────────────────────────────────────────────

def run_graphql(query: str, variables: dict, headers: dict) -> dict:
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]

# ── Stat collectors ───────────────────────────────────────────────────────────

def fetch_user_basics(token: str) -> dict:
    """followers, public_repos via REST /users/{username}"""
    url = f"{API_BASE}/users/{USERNAME}"
    resp = requests.get(url, headers=rest_headers(token), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {
        "followers": data.get("followers", 0),
        "public_repos": data.get("public_repos", 0),
    }


def fetch_stars(token: str) -> int:
    """Total stargazers across all owned repos (including forks)."""
    url = f"{API_BASE}/users/{USERNAME}/repos"
    repos = paginate_rest(
        url, rest_headers(token), {"type": "owner", "per_page": 100}
    )
    return sum(r.get("stargazers_count", 0) for r in repos)


def fetch_commit_count(token: str) -> int:
    """
    Total commit contributions from the contribution calendar (GraphQL).
    This counts commits across ALL repositories the user contributed to.
    """
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    data = run_graphql(query, {"login": USERNAME}, graphql_headers(token))
    col = data["user"]["contributionsCollection"]
    # Include private contributions if the user has "Share private contributions" on
    return (
        col["totalCommitContributions"] + col["restrictedContributionsCount"]
    )


def fetch_lines_of_code(token: str, max_repos: int = 30) -> dict:
    """
    Sum additions + deletions across the most-recently-pushed repos.
    Uses /repos/{owner}/{repo}/stats/contributors (REST).
    GitHub computes these asynchronously; we retry on 202.
    Returns {"additions": int, "deletions": int, "lines_changed": int}
    """
    # Get list of repos
    url = f"{API_BASE}/users/{USERNAME}/repos"
    repos = paginate_rest(
        url, rest_headers(token), {"type": "owner", "sort": "pushed", "per_page": 100}
    )
    repos = repos[:max_repos]  # cap to avoid rate limit exhaustion

    total_add = 0
    total_del = 0

    for repo in repos:
        repo_name = repo["name"]
        stats_url = f"{API_BASE}/repos/{USERNAME}/{repo_name}/stats/contributors"
        for attempt in range(5):
            r = requests.get(stats_url, headers=rest_headers(token), timeout=30)
            if r.status_code == 204 or r.text.strip() in ("", "[]", "null"):
                break  # empty repo
            if r.status_code == 202:
                # GitHub is computing stats, wait and retry
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code != 200:
                break  # skip on error
            contributors = r.json()
            if not isinstance(contributors, list):
                break
            for c in contributors:
                if c.get("author", {}).get("login", "").lower() == USERNAME.lower():
                    for week in c.get("weeks", []):
                        total_add += week.get("a", 0)
                        total_del += week.get("d", 0)
            break

    return {
        "additions": total_add,
        "deletions": total_del,
        "lines_changed": total_add + total_del,
    }

# ── Uptime helper ─────────────────────────────────────────────────────────────

def compute_uptime(since_year: int = 2021) -> str:
    """Returns human-readable uptime since the given year."""
    now = datetime.now(timezone.utc)
    start = datetime(since_year, 1, 1, tzinfo=timezone.utc)
    delta = now - start
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = delta.days % 30
    parts = []
    if years:
        parts.append(f"{years}y")
    if months:
        parts.append(f"{months}m")
    if days or not parts:
        parts.append(f"{days}d")
    return " ".join(parts)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    token = get_token()

    print("Fetching user basics…", file=sys.stderr)
    basics = fetch_user_basics(token)

    print("Fetching total stars…", file=sys.stderr)
    stars = fetch_stars(token)

    print("Fetching commit count…", file=sys.stderr)
    commits = fetch_commit_count(token)

    print("Fetching lines-of-code stats (may take ~30 s)…", file=sys.stderr)
    loc = fetch_lines_of_code(token)

    stats = {
        "username": USERNAME,
        "followers": basics["followers"],
        "public_repos": basics["public_repos"],
        "stars": stars,
        "commits": commits,
        "lines_added": loc["additions"],
        "lines_deleted": loc["deletions"],
        "lines_changed": loc["lines_changed"],
        "uptime": compute_uptime(since_year=2021),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Write stats.json for downstream scripts
    out_path = os.path.join(os.path.dirname(__file__), "stats.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # Also print to stdout
    print(json.dumps(stats, indent=2))
    print(f"\nstats.json written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
