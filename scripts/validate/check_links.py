#!/usr/bin/env python3
"""Network link checker for FailBench evidence source URLs.

Standalone QA tool, NOT part of offline CI because it contacts external hosts.
It loads ``<root>/data/evidence/*.jsonl`` (via :mod:`failbench.schema` when
importable, else a standalone UTF-8 JSONL parser), collects unique
``source_url`` values in file order, and checks them sequentially with
``--delay`` seconds between requests. HEAD is tried first, retried once with
GET on 400/403/405/501 or URLError. GitHub API hosts are skipped by default
because the contract wants page URLs (``--allow-api`` overrides with a warning).

Usage::

    python scripts/validate/check_links.py [--root PATH] [--limit N]
        [--timeout SECONDS] [--delay SECONDS] [--json PATH] [--allow-api]

Exit codes: 0 = ok (dead ratio <= 5%), 1 = dead ratio (4xx + 5xx + dead) /
checked > 5%, 2 = no evidence files/URLs found or the run could not complete.
Stdlib only (Python 3.8+); no ANSI colors; writes no files unless
``--json PATH`` is passed.
"""

from __future__ import annotations

import argparse, http.client, json, socket, ssl, sys, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = "failbench-link-checker/0.1.1 (+https://github.com/Qin-z-x/llm-failbench)"
MAX_BODY_BYTES = 4096
RETRY_WITH_GET_CODES = frozenset({400, 403, 405, 501})
DEAD_RATIO_LIMIT = 0.05
HTTP_SCHEMES = frozenset({"http", "https"})

class EvidenceLoadError(RuntimeError):
    """Evidence files exist but cannot be read or parsed."""

def _out(text: str = "") -> None:
    """Write a line to stdout without crashing on a legacy code page."""
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        sys.stdout.write(text.encode(enc, "backslashreplace").decode(enc) + "\n")

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _one_line(value: Any, limit: int = 160) -> str:
    """Flatten a value to one truncated line so terminal output stays readable."""
    text = " ".join(str(value if value is not None else "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."

def _reason(exc: BaseException) -> str:
    reason = getattr(exc, "reason", None)
    if reason is None or (isinstance(reason, str) and not reason.strip()):
        reason = exc
    return _one_line(reason) or type(exc).__name__

def _safe_geturl(response: Any) -> Optional[str]:
    try:
        return response.geturl() or None
    except Exception:  # defensive: never fail a check over metadata
        return None

def _read_and_close(response: Any, method: str) -> None:
    try:
        if method == "GET":
            response.read(MAX_BODY_BYTES)
    except Exception:  # a truncated body is still a reachable link
        pass
    finally:
        try:
            response.close()
        except Exception:
            pass

def _classify(code: Optional[int]) -> str:
    if code is None:
        return "DEAD"
    for low, high, name in ((200, 300, "OK"), (300, 400, "REDIRECT"),
                            (400, 500, "CLIENT_ERROR"), (500, 600, "SERVER_ERROR")):
        if low <= code < high:
            return name
    return "DEAD"

def _open(url: str, method: str, timeout: float) -> Any:
    request = urllib.request.Request(
        url, method=method, headers={"User-Agent": USER_AGENT}
    )
    return urllib.request.urlopen(request, timeout=timeout)

def _result(url, status, code, final_url, error, started) -> Dict[str, Any]:
    return {
        "url": url, "status": status, "final_url": final_url, "error": error,
        "code": int(code) if isinstance(code, int) else None,
        "elapsed_ms": int(round((time.monotonic() - started) * 1000)),
    }

def _check_url(url: str, timeout: float) -> Dict[str, Any]:
    """Check one URL, retrying once with GET when HEAD is rejected."""
    started, method = time.monotonic(), "HEAD"
    while True:
        try:
            response = _open(url, method, timeout)
        except urllib.error.HTTPError as exc:
            code, final_url = getattr(exc, "code", None), _safe_geturl(exc)
            try:
                exc.close()
            except Exception:
                pass
            if method == "HEAD" and code in RETRY_WITH_GET_CODES:
                method = "GET"
                continue
            return _result(url, _classify(code), code, final_url, None, started)
        except (urllib.error.URLError, socket.timeout, ssl.SSLError, TimeoutError) as exc:
            if method == "HEAD":
                method = "GET"
                continue
            return _result(url, "DEAD", None, None, "dead: " + _reason(exc), started)
        except http.client.HTTPException as exc:
            return _result(url, "DEAD", None, None,
                           "dead: HTTP protocol error: " + _reason(exc), started)
        except Exception as exc:  # never traceback because of one bad URL
            error = "dead: {}: {}".format(type(exc).__name__, _reason(exc))
            return _result(url, "DEAD", None, None, _one_line(error), started)

        try:
            code = getattr(response, "status", None) or response.getcode()
            final_url = _safe_geturl(response)
        finally:
            _read_and_close(response, method)
        if code is None:
            return _result(
                url, "DEAD", None, final_url, "dead: no HTTP status available", started
            )
        return _result(url, _classify(code), code, final_url, None, started)

def _parse_url(url: str) -> Optional[urllib.parse.SplitResult]:
    try:
        return urllib.parse.urlsplit(url)
    except ValueError:
        return None

def _github_api_reason(parts: urllib.parse.SplitResult) -> str:
    host, path = (parts.hostname or "").lower(), parts.path or ""
    if host == "api.github.com":
        return "github api host (rate limits; page URLs only)"
    if host.endswith(".github.com") and (
        path.startswith("/repos") or path.startswith("/search")
    ):
        return "github api path (rate limits; page URLs only)"
    return ""

def _skip_reason(url: str, allow_api: bool) -> Tuple[Optional[str], bool]:
    """Return ``(reason_to_skip_or_None, is_github_api_url)``."""
    parts = _parse_url(url)
    if parts is None:
        return "invalid URL (unparseable)", False
    if (parts.scheme or "").lower() not in HTTP_SCHEMES:
        return "bad scheme (data defect)", False
    if not parts.hostname:
        return "invalid URL (no host)", False
    api_reason = _github_api_reason(parts)
    if api_reason and not allow_api:
        return api_reason, True
    return None, bool(api_reason)

def _load_standalone(files: List[Path]) -> List[Dict[str, Any]]:
    """Parse UTF-8 JSONL evidence files without importing failbench."""
    records: List[Dict[str, Any]] = []
    for path in files:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise EvidenceLoadError(f"cannot read {path}: {exc}") from exc
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvidenceLoadError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise EvidenceLoadError(f"{path}:{lineno}: evidence record must be a JSON object")
            records.append(record)
    return records

def _try_import_schema(root: Path) -> Optional[Any]:
    """Temporarily put ``root`` on sys.path and import ``failbench.schema``."""
    root_text = str(root)
    added = root_text not in sys.path
    if added:
        sys.path.insert(0, root_text)
    try:
        from failbench import schema as schema_module
    except Exception:
        schema_module = None
    finally:
        if added and schema_module is None:
            sys.path.remove(root_text)
    return schema_module

def _collect_urls(records: List[Dict[str, Any]]) -> Tuple[List[str], int]:
    """Collect unique stripped source URLs in file order; count unusable ones."""
    seen, urls, missing = set(), [], 0
    for record in records:
        raw = record.get("source_url")
        if not isinstance(raw, str) or not raw.strip():
            missing += 1
            continue
        value = raw.strip()
        if value not in seen:
            seen.add(value)
            urls.append(value)
    return urls, missing

def _load_source_urls(root: Path) -> Optional[Dict[str, Any]]:
    """Return evidence metadata plus unique URLs; ``None`` when no files exist."""
    evidence_dir = root / "data" / "evidence"
    files = (
        sorted(p for p in evidence_dir.glob("*.jsonl") if p.is_file())
        if evidence_dir.is_dir()
        else []
    )
    if not files:
        return None
    schema_module = _try_import_schema(root)
    if schema_module is not None:
        loader = "failbench.schema"
        try:
            records = schema_module.load_evidence(evidence_root=evidence_dir)
        except (ValueError, OSError) as exc:
            raise EvidenceLoadError(str(exc)) from exc
    else:
        loader = "standalone"
        records = _load_standalone(files)
    urls, missing = _collect_urls(records)
    return {"urls": urls, "missing": missing, "files": len(files),
            "records": len(records), "loader": loader, "evidence_dir": evidence_dir}

def _summarise(results, unique_urls: int, selected: int) -> Dict[str, Any]:
    checked = [r for r in results if r["status"] != "SKIP"]
    counts = {name: sum(1 for r in checked if r["status"] == name)
              for name in ("OK", "CLIENT_ERROR", "SERVER_ERROR", "DEAD")}
    redirects = sum(1 for r in checked if r["status"] == "REDIRECT"
                    or (r["final_url"] and r["final_url"] != r["url"]))
    bad = counts["CLIENT_ERROR"] + counts["SERVER_ERROR"] + counts["DEAD"]
    return {
        "unique_urls": unique_urls, "selected": selected, "checked": len(checked),
        "ok": counts["OK"], "redirects": redirects,
        "client_errors": counts["CLIENT_ERROR"], "server_errors": counts["SERVER_ERROR"],
        "dead": counts["DEAD"], "skipped": len(results) - len(checked),
        "dead_ratio": round(bad / len(checked), 6) if checked else 0.0,
    }

def _write_json_report(path_text: str, report: Dict[str, Any]) -> Optional[str]:
    """Write the JSON report; return an error message instead of raising."""
    try:
        text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        Path(path_text).expanduser().write_text(text, encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        return str(exc)
    return None

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_links.py",
        description=(
            "Check that FailBench evidence source_url values are reachable. "
            "Network use is intentional; this is not part of offline CI."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Exit codes: 0 = ok, 1 = dead ratio > 5%, 2 = nothing to check / could not run.",
    )
    parser.add_argument("--root", default=None,
                        help="Repository root (default: inferred from this script's location)")
    parser.add_argument("--limit", type=int, default=0, help="Check only the first N unique URLs (0 = all)")
    parser.add_argument("--timeout", type=float, default=8.0, help="Per-request timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="Seconds to sleep between requests (not before the first)")
    parser.add_argument("--json", dest="json_path", default=None, metavar="PATH",
                        help="Write a machine-readable JSON report to PATH")
    parser.add_argument("--allow-api", action="store_true",
                        help="Also check GitHub API URLs instead of skipping them (may rate-limit)")
    return parser

def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.timeout <= 0 or args.delay < 0 or args.limit < 0:
        _out("ERROR: --timeout must be > 0, --delay must be >= 0, --limit must be >= 0")
        return 2
    root = (Path(args.root).expanduser().resolve() if args.root
            else Path(__file__).resolve().parents[2])
    try:
        loaded = _load_source_urls(root)
    except (EvidenceLoadError, OSError) as exc:
        _out(f"ERROR: cannot load evidence records: {exc}")
        return 2
    if loaded is None:
        _out(f"ERROR: no evidence files found under {root / 'data' / 'evidence'} (expected *.jsonl); nothing to check.")
        return 2
    urls_all = loaded["urls"]
    if not urls_all:
        _out(f"ERROR: no source_url values found in {loaded['records']} evidence record(s) under "
             f"{loaded['evidence_dir']}; nothing to check.")
        return 2

    selected = urls_all if args.limit <= 0 else urls_all[: args.limit]
    plans, github_api_urls = [], 0
    for url in selected:
        reason, is_api = _skip_reason(url, args.allow_api)
        github_api_urls += 1 if is_api else 0
        plans.append((url, reason))
    to_check = sum(1 for _, reason in plans if reason is None)
    _out(f"NETWORK CHECK: contacting {to_check} external URLs (not part of offline CI)")
    _out(f"root: {root}")
    _out(f"evidence: {loaded['files']} file(s), {loaded['records']} record(s), "
         f"loader={loaded['loader']}, unique URLs={len(urls_all)}, selected={len(selected)}")
    if loaded["missing"]:
        _out(f"WARNING: {loaded['missing']} evidence record(s) have no usable "
             "source_url (data defect)")
    if args.allow_api and github_api_urls:
        _out(f"WARNING: --allow-api is set; checking {github_api_urls} GitHub API "
             "URL(s) may hit rate limits")
    _out()

    results: List[Dict[str, Any]] = []
    requests_made = 0
    try:
        for url, reason in plans:
            if reason is not None:
                results.append({"url": url, "status": "SKIP", "code": None,
                                "final_url": None, "error": reason, "elapsed_ms": 0})
                _out(f"SKIP {reason} {url}")
                continue
            if requests_made:
                time.sleep(args.delay)
            result = _check_url(url, args.timeout)
            requests_made += 1
            results.append(result)
            if result["status"] == "DEAD":
                detail = result["error"] or "dead: unknown error"
            else:
                detail = str(result["code"])
            line = f"{result['status']} {detail} {url}"
            final_url = result.get("final_url")
            if final_url and final_url != url:
                line += f" -> {final_url}"
            _out(line)
    except KeyboardInterrupt:
        _out()
        _out("ERROR: interrupted by user")
        return 2

    totals = _summarise(results, len(urls_all), len(selected))
    percentage = totals["dead_ratio"] * 100.0
    _out()
    _out("Summary:")
    for label, value in (
        ("unique URLs collected", totals["unique_urls"]), ("selected (after limit)", totals["selected"]),
        ("total checked", totals["checked"]), ("ok (2xx)", totals["ok"]), ("redirects", totals["redirects"]),
        ("client errors (4xx)", totals["client_errors"]), ("server errors (5xx)", totals["server_errors"]),
        ("dead", totals["dead"]), ("skipped", totals["skipped"]),
    ):
        _out(f"  {label + ':':<24}{value}")
    _out(f"  {'dead ratio:':<24}{percentage:.1f}% (fail threshold: >{DEAD_RATIO_LIMIT * 100.0:.1f}%)")

    if args.json_path:
        report = {"root": str(root), "checked_at_utc": _now_utc(), "timeout": args.timeout,
                  "delay": args.delay, "totals": totals, "results": results,
                  "dead_ratio": totals["dead_ratio"]}
        error = _write_json_report(args.json_path, report)
        if error:
            _out(f"ERROR: could not write JSON report: {error}")
            return 2
        _out(f"  {'JSON report:':<24}{args.json_path}")
    _out()

    if totals["checked"] == 0:
        _out("RESULT: nothing checked (all selected URLs were skipped)")
        return 0
    if totals["dead_ratio"] > DEAD_RATIO_LIMIT:
        _out(f"RESULT: FAIL - dead ratio {percentage:.1f}% is above the {DEAD_RATIO_LIMIT * 100.0:.1f}% threshold")
        return 1
    _out(f"RESULT: PASS - dead ratio {percentage:.1f}% is within the {DEAD_RATIO_LIMIT * 100.0:.1f}% threshold")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
