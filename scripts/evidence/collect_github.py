#!/usr/bin/env python3
"""Collect GitHub *issue search* results for the FailBench evidence atlas.

Data source
-----------
GitHub REST API issue search (unauthenticated):
    https://api.github.com/search/issues?q=<keywords>+repo:<owner/repo>
        &sort=reactions&order=desc&per_page=10

Rate limits / politeness
------------------------
Unauthenticated GitHub *search* is limited to **10 requests per minute**
(the core REST API is 60/hour). This script therefore defaults to a 10 second
pause between queries (``--sleep``), refuses more than 10 queries per run
(``--max-queries``), sends a descriptive User-Agent and the
``application/vnd.github+json`` Accept header, and stops cleanly (reporting
the remaining queries as skipped) when the API answers 403/429.

Ethics
------
Only public issue metadata is recorded (title, HTML URL, repo, created date,
reaction/comment counts). No issue body text is copied and no quote is
recorded, so the atlas links back to the issue.

Usage
-----
    python scripts/evidence/collect_github.py \
        --query "invalid json repo:vllm-project/vllm" \
        --query "agent loop repo:langchain-ai/langchain" \
        --raw-dir _scratch/w1/raw/github \
        --out _scratch/w1/raw/github/cand_github.jsonl

Candidate JSONL line shape:

    {
      "source_type": "github_issue",
      "source_url": "https://github.com/openai/openai-python/issues/1763",
      "source_title": "<exact issue title>",
      "publisher": "openai/openai-python",
      "published_date": "2024-09-30",
      "metrics": {"github_reactions": 13, "github_comments": 23},
      "_query": "...", "_number": 1763, "_state": "open",
      "_is_pull_request": false
    }
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

API_BASE = "https://api.github.com/search/issues?"
USER_AGENT = (
    "failbench-evidence-collector/0.1 "
    "(public LLM failure atlas; polite research crawler)"
)


def _slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit].strip("-") or "query")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_int(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def fetch_json(
    url: str, timeout: float, retries: int, sleep: float
) -> tuple[Dict[str, Any] | None, str | None]:
    """Fetch one JSON document. Returns (payload, error)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    last_error: Any = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8", "replace")
            return json.loads(payload), None
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            last_error = f"HTTP {exc.code}: {body}"
            if exc.code in (403, 429):
                return None, last_error  # rate limited: do not hammer
        except Exception as exc:  # network / JSON errors
            last_error = repr(exc)
            if attempt < retries:
                time.sleep(sleep * (2 ** attempt))
    return None, last_error


def candidates_from_response(payload: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for rank, item in enumerate(payload.get("items") or [], 1):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        html_url = item.get("html_url")
        if not isinstance(title, str) or not title.strip() or not isinstance(html_url, str):
            continue
        repository_url = item.get("repository_url") or ""
        publisher = repository_url.split("/repos/")[-1] if "/repos/" in repository_url else None
        created_at = item.get("created_at") or ""
        reactions = item.get("reactions") or {}
        reaction_total = _as_int(reactions.get("total_count")) if isinstance(reactions, dict) else None
        comments = _as_int(item.get("comments"))
        metrics: Dict[str, int] = {}
        if reaction_total is not None:
            metrics["github_reactions"] = reaction_total
        if comments is not None:
            metrics["github_comments"] = comments
        candidate: Dict[str, Any] = {
            "source_type": "github_issue",
            "source_url": html_url,
            "source_title": " ".join(title.split()),
            "publisher": publisher,
            "published_date": created_at[:10] or None,
            "_query": query,
            "_rank": rank,
            "_number": item.get("number"),
            "_state": item.get("state"),
            "_is_pull_request": "pull_request" in item,
        }
        if metrics:
            candidate["metrics"] = metrics
        candidates.append(candidate)
    return candidates


def build_api_url(query: str, per_page: int) -> str:
    params = urllib.parse.urlencode(
        {"q": query, "sort": "reactions", "order": "desc", "per_page": str(per_page)}
    )
    return API_BASE + params


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect GitHub issue-search candidates (unauthenticated)."
    )
    parser.add_argument("--query", action="append", default=[], help="search q= expression (repeatable)")
    parser.add_argument("--per-page", type=int, default=10, help="results per query, default 10")
    parser.add_argument("--max-queries", type=int, default=10, help="safety cap, default 10")
    parser.add_argument("--raw-dir", default=None, help="directory for raw normalized dumps")
    parser.add_argument("--out", default=None, help="JSONL file for candidate lines (default stdout)")
    parser.add_argument(
        "--sleep",
        type=float,
        default=10.0,
        help="seconds between queries; GitHub search allows 10 requests/minute",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="per-request timeout")
    parser.add_argument("--retries", type=int, default=2, help="per-request retry count")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.query:
        parser.error("at least one --query is required")
    if len(args.query) > args.max_queries:
        parser.error(f"refusing {len(args.query)} queries (max {args.max_queries} per run)")
    if not 1 <= args.per_page <= 100:
        parser.error("--per-page must be between 1 and 100")

    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    out_lines: List[str] = []
    total_kept = 0
    skipped: List[str] = []
    for index, query in enumerate(args.query):
        api_url = build_api_url(query, args.per_page)
        payload, error = fetch_json(api_url, args.timeout, args.retries, args.sleep)
        if payload is None:
            skipped = args.query[index:]
            print(
                f"[github] stop at query {index + 1}: {error}",
                file=sys.stderr,
            )
            print(f"[github] skipped {len(skipped)} remaining query(ies)", file=sys.stderr)
            break
        candidates = candidates_from_response(payload, query)
        total_kept += len(candidates)
        if raw_dir is not None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dump = {
                "source": "github",
                "query": query,
                "api_url": api_url,
                "fetched_at": _utc_now(),
                "total_count": payload.get("total_count"),
                "candidates": candidates,
            }
            write_json(raw_dir / f"{stamp}_github_{_slugify(query)}.json", dump)
        out_lines.extend(json.dumps(candidate, ensure_ascii=False) for candidate in candidates)
        print(
            f"[github] query={query!r} total_count={payload.get('total_count')} "
            f"kept={len(candidates)} total_kept={total_kept}",
            file=sys.stderr,
        )
        if index < len(args.query) - 1:
            time.sleep(args.sleep)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            for line in out_lines:
                handle.write(line + "\n")
        print(f"[github] wrote {len(out_lines)} candidate lines to {out_path}", file=sys.stderr)
    else:
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
        for line in out_lines:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
