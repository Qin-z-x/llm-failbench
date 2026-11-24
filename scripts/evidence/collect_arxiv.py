#!/usr/bin/env python3
"""Collect arXiv paper candidates for the FailBench evidence atlas.

Data source
-----------
arXiv export API (no authentication required, Atom XML):
    http://export.arxiv.org/api/query?search_query=all:"<phrase>"&start=0
        &max_results=25&sortBy=relevance

Rate limits / politeness
------------------------
The arXiv API documentation asks for no more than one request every three
seconds. This script defaults to ``--sleep 3.0`` between requests, sends a
descriptive User-Agent, retries up to 3 times with exponential backoff and
uses a 60 s timeout. Keep batches small (<= 10 queries per run).

Ethics
------
Only bibliographic metadata plus a *short* verbatim excerpt of the abstract
(<= 200 chars, used for the ``quote`` field) is recorded. The atlas links to
the paper; no full text is copied.

Usage
-----
    python scripts/evidence/collect_arxiv.py \
        --query "lost in the middle" \
        --query "needle in a haystack" \
        --raw-dir _scratch/w1/raw/context_retrieval \
        --out _scratch/w1/raw/context_retrieval/cand_arxiv.jsonl

Each query produces:
  * one raw dump ``<raw-dir>/<timestamp>_arxiv_<slug>.json`` with the query,
    API URL, fetch timestamp and normalized candidate entries;
  * candidate JSON lines appended to ``--out`` (or stdout when omitted).

Candidate line shape (underscore keys are provenance hints, not evidence
fields):

    {
      "source_type": "arxiv",
      "source_url": "https://arxiv.org/abs/2307.03172",
      "source_title": "Lost in the Middle: How Language Models Use Long Contexts",
      "publisher": "arXiv",
      "published_date": "2023-07-06",
      "_arxiv_id": "2307.03172",
      "_abstract": "<abstract, whitespace-normalized>",
      "_quote_suggestion": "<exact <=200-char excerpt of _abstract>",
      "_categories": ["cs.CL"],
      "_authors": ["..."],
      "_query": "lost in the middle",
      "_updated": "2024-03-21"
    }

``_abstract`` is whitespace-normalized (runs of whitespace -> one space) so
that a chosen quote is an exact substring of it; in the raw Atom XML the same
text may be line-wrapped. Verify any quote you build with
``quote in entry["_abstract"]``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

API_BASE = "http://export.arxiv.org/api/query?"
USER_AGENT = (
    "failbench-evidence-collector/0.1 "
    "(public LLM failure atlas; polite research crawler)"
)
ABS_URL = "https://arxiv.org/abs/{arxiv_id}"
ATOM = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit].strip("-") or "query")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def fetch_text(url: str, timeout: float, retries: int, sleep: float) -> str:
    """Fetch one Atom document with retries and an identifying User-Agent."""
    last_error: Any = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", "replace")
        except Exception as exc:  # network / HTTP errors
            last_error = exc
            if attempt < retries:
                time.sleep(sleep * (2 ** attempt))
    raise SystemExit(f"FATAL: request failed after {retries} attempts: {url} ({last_error})")


def _suggest_quote(abstract: str, limit: int = 200) -> str:
    """Return a verbatim <=limit-char excerpt, preferring a sentence boundary."""
    if not abstract:
        return ""
    if len(abstract) <= limit:
        return abstract
    window = abstract[:limit]
    sentence_end = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
    if sentence_end >= 60:
        return window[: sentence_end + 1].strip()
    space = window.rfind(" ")
    if space >= 60:
        return window[:space].strip()
    return window.strip()


def _arxiv_id_from_url(raw_id: str) -> str:
    match = re.search(r"arxiv\.org/abs/(.+?)(?:v\d+)?$", (raw_id or "").strip())
    return match.group(1) if match else ""


def candidates_from_atom(xml_text: str, query: str) -> List[Dict[str, Any]]:
    """Normalize Atom entries into evidence candidates."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SystemExit(f"FATAL: arXiv returned unparsable XML for {query!r}: {exc}")

    candidates: List[Dict[str, Any]] = []
    for rank, entry in enumerate(root.findall("atom:entry", ATOM), 1):
        raw_id = entry.findtext("atom:id", default="", namespaces=ATOM) or ""
        arxiv_id = _arxiv_id_from_url(raw_id)
        title = _normalize_ws(entry.findtext("atom:title", default="", namespaces=ATOM) or "")
        if not arxiv_id or not title:
            continue
        abstract = _normalize_ws(entry.findtext("atom:summary", default="", namespaces=ATOM) or "")
        published = (entry.findtext("atom:published", default="", namespaces=ATOM) or "").strip()
        updated = (entry.findtext("atom:updated", default="", namespaces=ATOM) or "").strip()
        categories = [
            cat.get("term")
            for cat in entry.findall("atom:category", ATOM)
            if cat.get("term")
        ]
        authors = [
            _normalize_ws(author.findtext("atom:name", default="", namespaces=ATOM) or "")
            for author in entry.findall("atom:author", ATOM)
        ]
        candidates.append(
            {
                "source_type": "arxiv",
                "source_url": ABS_URL.format(arxiv_id=arxiv_id),
                "source_title": title,
                "publisher": "arXiv",
                "published_date": published[:10] or None,
                "_arxiv_id": arxiv_id,
                "_abstract": abstract,
                "_quote_suggestion": _suggest_quote(abstract),
                "_categories": categories,
                "_authors": [name for name in authors if name],
                "_query": query,
                "_rank": rank,
                "_updated": updated[:10] or None,
            }
        )
    return candidates


def build_api_url(query: str, max_results: int, sort_by: str) -> str:
    params = urllib.parse.urlencode(
        {
            "search_query": f'all:"{query}"',
            "start": "0",
            "max_results": str(max_results),
            "sortBy": sort_by,
        }
    )
    return API_BASE + params


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect arXiv paper candidates via the arXiv export API."
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="phrase searched with all:\"<phrase>\" (repeatable; one API call per query)",
    )
    parser.add_argument(
        "--max-results", type=int, default=25, help="max entries per query, default 25"
    )
    parser.add_argument(
        "--sort-by",
        choices=("relevance", "submittedDate"),
        default="relevance",
        help="arXiv sort order, default relevance",
    )
    parser.add_argument(
        "--raw-dir", default=None, help="directory for raw normalized API dumps"
    )
    parser.add_argument(
        "--out", default=None, help="JSONL file for candidate lines (default: stdout)"
    )
    parser.add_argument(
        "--sleep", type=float, default=3.0, help="seconds between requests (arXiv asks >= 3)"
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="per-request timeout")
    parser.add_argument("--retries", type=int, default=3, help="per-request retry count")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.query:
        parser.error("at least one --query is required")
    if not 1 <= args.max_results <= 200:
        parser.error("--max-results must be between 1 and 200")
    if args.sleep < 0:
        parser.error("--sleep must be >= 0")

    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    out_lines: List[str] = []
    total_kept = 0
    for index, query in enumerate(args.query):
        api_url = build_api_url(query, args.max_results, args.sort_by)
        xml_text = fetch_text(api_url, args.timeout, args.retries, args.sleep)
        candidates = candidates_from_atom(xml_text, query)
        total_kept += len(candidates)
        if raw_dir is not None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dump = {
                "source": "arxiv",
                "query": query,
                "sort_by": args.sort_by,
                "api_url": api_url,
                "fetched_at": _utc_now(),
                "candidates": candidates,
            }
            write_json(raw_dir / f"{stamp}_arxiv_{_slugify(query)}.json", dump)
        for candidate in candidates:
            out_lines.append(json.dumps(candidate, ensure_ascii=False))
        print(
            f"[arxiv] query={query!r} kept={len(candidates)} total_kept={total_kept}",
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
        print(f"[arxiv] wrote {len(out_lines)} candidate lines to {out_path}", file=sys.stderr)
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
