#!/usr/bin/env python3
"""Collect Hacker News *story* candidates for the FailBench evidence atlas.

Data source
-----------
Hacker News Algolia search API (no authentication required):
    https://hn.algolia.com/api/v1/search?query=<q>&tags=story&hitsPerPage=30
    https://hn.algolia.com/api/v1/search_by_date?query=<q>&tags=story&hitsPerPage=30

Rate limits / politeness
------------------------
The Algolia HN API is generous but not unlimited. This script sends one
request per ``--query`` with a descriptive User-Agent, a 30 s timeout, up to
3 retries with exponential backoff, and a default 1.0 s pause between
requests (``--sleep``). Keep batches small (<= 12 queries per run).

Ethics
------
Only public item metadata is recorded (title, item id, points, comment count,
creation date). No article text is copied; the atlas links back to the
original Hacker News item.

Usage
-----
    python scripts/evidence/collect_hn.py \
        --query "lost in the middle" \
        --query "context rot" \
        --raw-dir _scratch/w1/raw/context_retrieval \
        --out _scratch/w1/raw/context_retrieval/cand_hn.jsonl

Each query produces:
  * one raw API dump ``<raw-dir>/<timestamp>_hn_<slug>.json`` containing the
    query, API URL, fetch timestamp and the *normalized* candidate list;
  * candidate JSON lines appended to ``--out`` (or stdout when omitted).

Candidate line shape (underscore keys are provenance hints, not evidence
fields):

    {
      "source_type": "hn_story",
      "source_url": "https://news.ycombinator.com/item?id=46720395",
      "source_title": "<exact HN story title>",
      "publisher": "Hacker News",
      "published_date": "2026-01-22",
      "metrics": {"hn_points": 937, "hn_comments": 507},
      "_objectID": "46720395",
      "_query": "hallucination",
      "_rank": 1,
      "_created_at": "2026-01-22T15:20:48Z",
      "_story_url": "https://gptzero.me/news/neurips/",
      "_author": "whoever"
    }

Stories with fewer than ``--min-points`` points (default 2) are dropped;
stories without a title or item id are always dropped.
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

API_BASE = "https://hn.algolia.com/api/v1/"
USER_AGENT = (
    "failbench-evidence-collector/0.1 "
    "(public LLM failure atlas; polite research crawler)"
)
ITEM_URL = "https://news.ycombinator.com/item?id={object_id}"


def _slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit].strip("-") or "query")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_json(url: str, timeout: float, retries: int, sleep: float) -> Dict[str, Any]:
    """Fetch one JSON document with retries and an identifying User-Agent."""
    last_error: Any = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8", "replace")
            return json.loads(payload)
        except Exception as exc:  # network / HTTP / JSON errors
            last_error = exc
            if attempt < retries:
                time.sleep(sleep * (2 ** attempt))
    raise SystemExit(f"FATAL: request failed after {retries} attempts: {url} ({last_error})")


def _as_int(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def candidates_from_response(
    payload: Dict[str, Any], query: str, min_points: int
) -> List[Dict[str, Any]]:
    """Normalize Algolia hits into evidence candidates (sorted by points desc)."""
    hits = payload.get("hits") or []
    candidates: List[Dict[str, Any]] = []
    for rank, hit in enumerate(hits, 1):
        if not isinstance(hit, dict):
            continue
        object_id = hit.get("objectID")
        title = hit.get("title") or hit.get("story_title")
        if not object_id or not isinstance(title, str) or not title.strip():
            continue
        title = " ".join(title.split())
        points = _as_int(hit.get("points"))
        if points is not None and points < min_points:
            continue
        num_comments = _as_int(hit.get("num_comments"))
        created_at = hit.get("created_at")
        published_date = created_at[:10] if isinstance(created_at, str) and len(created_at) >= 10 else None
        metrics: Dict[str, int] = {}
        if points is not None:
            metrics["hn_points"] = points
        if num_comments is not None:
            metrics["hn_comments"] = num_comments
        candidate: Dict[str, Any] = {
            "source_type": "hn_story",
            "source_url": ITEM_URL.format(object_id=object_id),
            "source_title": title,
            "publisher": "Hacker News",
            "published_date": published_date,
            "_objectID": str(object_id),
            "_query": query,
            "_rank": rank,
            "_created_at": created_at,
            "_story_url": hit.get("url"),
            "_author": hit.get("author"),
        }
        if metrics:
            candidate["metrics"] = metrics
        candidates.append(candidate)
    candidates.sort(key=lambda c: (c.get("metrics", {}).get("hn_points", 0), c.get("metrics", {}).get("hn_comments", 0)), reverse=True)
    return candidates


def build_api_url(query: str, tags: str, hits: int, sort: str) -> str:
    endpoint = "search_by_date" if sort == "search_by_date" else "search"
    params = urllib.parse.urlencode(
        {"query": query, "tags": tags, "hitsPerPage": str(hits)}
    )
    return f"{API_BASE}{endpoint}?{params}"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect Hacker News story candidates via the Algolia API."
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="search query (repeatable; one API call per query)",
    )
    parser.add_argument(
        "--tags",
        default="story",
        help="Algolia tag filter, default 'story' (see HN Algolia docs)",
    )
    parser.add_argument("--hits", type=int, default=30, help="hitsPerPage, default 30")
    parser.add_argument(
        "--sort",
        choices=("relevance", "search_by_date"),
        default="relevance",
        help="relevance (search) or recency (search_by_date); default relevance",
    )
    parser.add_argument(
        "--min-points",
        type=int,
        default=2,
        help="drop stories below this point count; default 2",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="directory for raw API dumps (JSON, normalized candidates)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="JSONL file for candidate lines (default: stdout)",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="per-request timeout")
    parser.add_argument("--retries", type=int, default=3, help="per-request retry count")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.query:
        parser.error("at least one --query is required")
    if args.hits < 1 or args.hits > 100:
        parser.error("--hits must be between 1 and 100 (Algolia allows up to 1000)")
    if args.min_points < 0:
        parser.error("--min-points must be >= 0")

    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    out_lines: List[str] = []
    total_kept = 0
    for index, query in enumerate(args.query):
        api_url = build_api_url(query, args.tags, args.hits, args.sort)
        payload = fetch_json(api_url, args.timeout, args.retries, args.sleep)
        candidates = candidates_from_response(payload, query, args.min_points)
        total_kept += len(candidates)
        if raw_dir is not None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dump = {
                "source": "hn",
                "query": query,
                "tags": args.tags,
                "sort": args.sort,
                "min_points": args.min_points,
                "api_url": api_url,
                "fetched_at": _utc_now(),
                "nb_hits_available": payload.get("nbHits"),
                "candidates": candidates,
            }
            write_json(
                raw_dir / f"{stamp}_hn_{_slugify(query)}.json",
                dump,
            )
        for candidate in candidates:
            out_lines.append(json.dumps(candidate, ensure_ascii=False))
        print(
            f"[hn] query={query!r} hits={len(payload.get('hits') or [])} "
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
        print(f"[hn] wrote {len(out_lines)} candidate lines to {out_path}", file=sys.stderr)
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
