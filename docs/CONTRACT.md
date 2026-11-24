# FailBench Build Contract v1

**Repo root (absolute):** the directory two levels above this file (`docs/` lives inside it).
**Package:** `failbench` (flat layout at repo root)
**Version:** 0.1.0
**Tagline:** *The evidence-backed, judge-free failure probe kit for LLMs.*
**One-liner:** Every probe is deterministic and every claim is sourced; run a fast regression gate against any OpenAI-compatible endpoint with zero LLM judges and zero third-party Python dependencies.

> This file is the single source of truth for schemas, file ownership, and quality rules. If something here conflicts with a task prompt, this file wins. Ask the root agent before changing a schema.

---

## 1. Mission and non-negotiables

We are building a public, citable OSS project with two halves:

1. **Atlas** — a curated, machine-readable base of *publicly reported* LLM failure modes, each with a real, reachable source URL and popularity signal (HN points, GitHub reactions, paper citations/venue).
2. **Probe kit** — a deterministic, judge-free benchmark: ~80-120 probes across 10 failure classes, each scored by mechanical rules (no LLM-as-judge), with a runner, replay/audit path, static dashboard, and a CI regression gate.

### Non-negotiables (violations must be reported, not hidden)

- **No fabricated data.** Every evidence record must come from a real API/web result you actually received in this session. Never invent a URL, title, date, quote, metric, or citation. If a field is unknown, use `null` (not a guess).
- **Verbatim quotes only.** `quote` must be copied exactly from the fetched page/API result, max 200 chars. If you cannot verify exact text, set `quote` to `""`.
- **Honest status.** Evidence `status` is `"cited"` by default. Never write `"tested"` unless a real model run produced it. The demo run uses the `mock` provider and must always be labeled as such.
- **No fabricated measurements.** `docs/RESULTS.md` and the site must state plainly: no live model endpoint was available during the build; the shipped demo run is against a deterministic mock provider; users must run the kit on their own endpoint to get real numbers.
- **No harmful content.** No working jailbreaks, no exploit payloads, no prompt-injection payloads aimed at third-party systems, no malware, no PII, no private or leaked data. Safety probes measure *over-refusal* and *refusal inconsistency* on harmless prompts only. If a source is a jailbreak post, cite the *phenomenon* without reproducing the payload.
- **No deceptions about identity or endorsement.** Do not write fake testimonials, fake user quotes, fake stars, fake "hundreds of teams use this", or claims of human identity. Promotion copy must be truthful and is published by the repository owner, not through fake accounts.
- **No spam.** Distribution deliverables are drafts/checklists only; no automated posting, no fake accounts, no vote manipulation, no mass unsolicited DMs.
- **Respect licenses.** Code: MIT. Data (evidence + probe corpus): CC-BY-4.0. Do not copy large text from sources; link + short quote only. Papers: link and short summary only.
- **Offline safety.** Tests and the demo must run with no network and no API key. Only `scripts/evidence/` collectors use the network.

---

## 2. Repository layout

```
llm-failbench/
├─ README.md                     # W6
├─ LICENSE                       # MIT (root)
├─ CITATION.cff                  # W7
├─ CONTRIBUTING.md               # W6
├─ CODE_OF_CONDUCT.md            # W6
├─ SECURITY.md                   # W9 (responsible disclosure)
├─ CHANGELOG.md                  # W6
├─ pyproject.toml                # root
├─ .gitignore                    # root
├─ .github/
│  ├─ workflows/ci.yml           # W5
│  ├─ ISSUE_TEMPLATE/*.yml       # W8
│  └─ PULL_REQUEST_TEMPLATE.md   # W8
├─ failbench/                    # Python package (stdlib only)
│  ├─ __init__.py                # root
│  ├─ schema.py                  # root  (loaders + validators)
│  ├─ scoring.py                 # root  (mechanical scorers)
│  ├─ providers/                 # W3
│  │  ├─ __init__.py  base.py  mock.py  openai_compatible.py  replay.py
│  ├─ runner.py                  # W3
│  ├─ gate.py                    # W3
│  ├─ cli.py                     # W3
│  └─ report.py                  # W4
├─ probes/                       # W2  (one JSON file per probe)
│  └─ <class>/<probe_id>.json
├─ data/evidence/                # W1  (one JSONL per class + index.json)
│  └─ <class>.jsonl
├─ results/                      # generated; demo run committed, big raw runs gitignored
├─ site/index.html               # W4  (self-contained static dashboard+atlas)
├─ assets/                       # W7 (banner/logo svg), W4 (charts)
├─ docs/
│  ├─ CONTRACT.md                # root
│  ├─ QUICKSTART.md              # W6
│  ├─ METHODOLOGY.md             # W6 (with W3/W5 review)
│  ├─ TAXONOMY.md                # W10
│  ├─ ATLAS.md                   # W10
│  ├─ MITIGATIONS.md             # W10
│  ├─ RESULTS.md                 # W4 (generated; committed)
│  ├─ DISTRIBUTION.md            # W7
│  ├─ PUBLISHING.md              # W8
│  ├─ ROADMAP.md                 # W6
│  ├─ FAQ.md                     # W6
│  ├─ templates/                 # root (probe/evidence templates)
│  └─ reviews/                   # W5/W9 review reports
├─ scripts/
│  ├─ evidence/                  # W1 collectors (network allowed)
│  ├─ publish/                   # W8 portable-git publish scripts
│  └─ validate/                  # W5 validation scripts (offline)
├─ tests/                        # W3 (core unit tests); W5 adds integration tests only after handoff
├─ launch/                       # W7 (drafts only, never auto-posted)
└─ _scratch/                     # scratch, gitignored
```

**Never touch** any file or `.git` directory outside this repository; the session's original working directory contains an unrelated project.

## 3. Failure classes (fixed vocabulary)

| class | abbr | meaning |
|---|---|---|
| `hallucination` | `hal` | fabricated facts, citations, APIs, package names, quotes |
| `instruction_following` | `if` | negative constraints, format/length/order constraints |
| `context_retrieval` | `ctx` | needle-in-haystack, lost-in-the-middle, context rot, distractor interference |
| `reasoning_consistency` | `rea` | paraphrase stability, self-consistency, arithmetic/date edge cases |
| `sycophancy` | `syc` | stance flip under social pressure, agreeing with a wrong user claim |
| `structured_output` | `str` | JSON schema conformance, tool-call arguments, strict delimiters |
| `multilingual` | `ml` | cross-lingual degradation, code-switching, script handling |
| `safety_consistency` | `saf` | over-refusal on harmless prompts, inconsistent refusal boundaries |
| `agentic_reliability` | `agt` | loops, over-eager tool use, failure to stop, error recovery |
| `determinism_calibration` | `det` | temp-0 variance, confidence/abstention calibration, counting/tokenization edge cases |

Evidence IDs: `ev_<abbr>_<4-digit>` e.g. `ev_ctx_0001`, one JSON object per line, partitioned by class file.
Probe IDs: `<abbr>_<slug>_<2-digit>` e.g. `ctx_needle_01`, file `probes/<class>/<id>.json`.

## 4. Evidence record schema (JSONL line)

Required: `id, class, title, source_type, source_url, status, collected_by, collected_at`.
Optional/nullable: `source_title, publisher, published_date, metrics, quote, summary, probe_ids, notes`.

```json
{
  "id": "ev_ctx_0001",
  "class": "context_retrieval",
  "title": "Models miss instructions placed in the middle of long context",
  "source_type": "arxiv",
  "source_url": "https://arxiv.org/abs/2307.03172",
  "source_title": "Lost in the Middle: How Language Models Use Long Contexts",
  "publisher": "arXiv",
  "published_date": "2023-07-06",
  "metrics": {"hn_points": 521, "hn_comments": 96},
  "quote": "",
  "summary": "Retrieval accuracy is highest when relevant information is at the start or end of context and degrades in the middle.",
  "status": "cited",
  "probe_ids": ["ctx_needle_01"],
  "collected_by": "W1 worker evidence-ctx-a",
  "collected_at": "2026-11-24"
}
```

Rules:
- `source_type` in: `hn_story`, `github_issue`, `arxiv`, `blog`, `vendor_doc`, `reddit_thread`, `forum_thread`, `docs`.
- `source_url` must start with `http://` or `https://` and must be a URL actually returned by a search/API call.
- `metrics` keys allowed: `hn_points`, `hn_comments`, `github_reactions`, `github_comments`, `reddit_upvotes`, `reddit_comments`, `citations`, `stars`. Integers only. Missing → omit key.
- `published_date` ISO `YYYY-MM-DD` or `null`. `collected_at` ISO date.
- `status` in: `cited`, `refuted` (only if a cited source contradicts it), `tested` (only with a real live run reference in `notes`).
- `probe_ids` may reference probes that don't exist yet; W2/W4 reconcile by class automatically.
- `quote` ≤200 chars, exact; `""` if unverified. `summary` ≤400 chars, your own words, no hype.

## 5. Probe record schema (JSON file)

```json
{
  "id": "ctx_needle_01",
  "class": "context_retrieval",
  "title": "Recall a unique code buried at 50% of a long context",
  "severity": "high",
  "rationale": "Lost-in-the-middle effect: mid-context recall is the weakest position.",
  "evidence_ids": ["ev_ctx_0001"],
  "prompt": [
    {"role": "system", "content": "You are a precise assistant. Answer with the exact code only."},
    {"role": "user", "content": "...long text... The access code is AURORA-7734. ...long text...\n\nQuestion: What is the access code?"}
  ],
  "params": {"temperature": 0, "max_tokens": 32},
  "repeats": 1,
  "scoring": {"type": "contains_all", "value": ["AURORA-7734"], "case_sensitive": true},
  "tags": ["long-context", "needle"],
  "notes": "Deterministic: static prompt; single unambiguous answer."
}
```

Required: `id, class, title, severity, rationale, prompt, params, repeats, scoring`.
Optional: `evidence_ids` (default `[]`), `tags` (default `[]`), `notes`.
Rules:
- `severity` in `critical|high|medium|low`.
- `title` 5-120 chars; `rationale` 10-400 chars and must state why the failure matters (not "test model").
- `prompt`: 1-20 messages, roles `system|user|assistant`, content 1-20000 chars each, total ≤30000 chars. Static text only (no external files, no templating). Must be self-contained.
- `params`: `temperature` 0-2 (default 0), `max_tokens` 1-4096 (default 256), `top_p` optional.
- `repeats` 1-5 (use 3 only for determinism/calibration probes).
- `scoring`: one of the types in §6. Must be fully mechanical; no human/LLM judgement.
- Probe must have exactly one defensible correct answer / pass condition; no ambiguous grading.
- No PII, no real private data, no harmful payloads, no copyrighted long text (>100 chars of source text is not allowed). Synthetic filler is encouraged.

## 6. Scoring semantics (implemented in `failbench/scoring.py`, authoritative)

`scoring` object: `{ "type": ..., ...params }`. Types:

- `contains_all`: `value: [str,...]` (non-empty). PASS iff every string occurs in normalized response. `case_sensitive` optional (default false). Normalization: collapse whitespace runs to single spaces, NBSP→space, trim.
- `contains_any`: same, PASS iff at least one occurs.
- `not_contains_any`: same, PASS iff none occur.
- `exact_match`: `value: str`. PASS iff normalized response equals normalized value (trim+collapse; case per `case_sensitive`, default false).
- `regex`: `pattern: str` (Python `re`), `negate` optional bool. PASS iff `re.search(pattern, response, re.S|re.M)` is truthy (inverted if `negate`).
- `json_schema`: `schema: {type, properties?, required?, additionalProperties?, items?, enum?}` (the same minimal subset as workflow schemas). Response may be a bare JSON value or inside one ```json fence; extract first balanced JSON. PASS iff it parses and validates exactly.
- `numeric`: `value: number`, `tolerance` optional number (default 0). PASS iff the first number in response (`[-+]?\d+(?:\.\d+)?`) satisfies `abs(x-value) <= tolerance`.
- `all_of`: `units: [scoring,...]` (non-empty). PASS iff all units pass. Use for multi-constraint probes.

Every scorer returns `(passed: bool, detail: str)`; failures must explain the concrete mismatch (what was expected vs found, truncated to 200 chars). Provider/API failures are **errors**, never failures.

## 7. Results schema (`results/<run_id>/results.json`)

```json
{
  "schema": 1,
  "run_id": "20261124T104500Z-demo",
  "provider": "mock",
  "model": "failbench-mock-1",
  "base_url": null,
  "suite_version": "0.1.0",
  "started_at": "2026-11-24T10:45:00Z",
  "finished_at": "2026-11-24T10:45:01Z",
  "environment": {"python": "3.13.15", "platform": "Windows"},
  "config": {"temperature": 0, "max_tokens": 256, "concurrency": 4, "repeats": 1},
  "counts": {"probes": 90, "pass": 63, "fail": 27, "error": 0},
  "by_class": {"context_retrieval": {"total": 9, "pass": 5, "fail": 4, "error": 0, "pass_rate": 0.5556}},
  "probes": [
    {
      "probe_id": "ctx_needle_01",
      "class": "context_retrieval",
      "title": "...",
      "severity": "high",
      "status": "fail",
      "reason": "missing required substring: AURORA-7734",
      "latency_ms": 12,
      "tokens": {"prompt": 0, "completion": 0},
      "response_sha256": "…",
      "response_excerpt": "…≤500 chars…",
      "attempts": [
        {"index": 0, "status": "fail", "reason": "...", "response_sha256": "...", "latency_ms": 12}
      ]
    }
  ]
}
```

Also write `results/<run_id>/raw.jsonl`: one line per attempt `{probe_id, attempt, request, response, error, latency_ms, timestamp}` so runs are auditable and replayable. Never store API keys in any artifact.
`status` in `pass|fail|error`. `response_excerpt` ≤500 chars. `counts.probes` = number of probes attempted.

## 8. CLI contract (implemented by W3)

Run from repo root with plain `python` (3.13, no venv, no install), stdlib only:

```
python -m failbench list [--class CLASS] [--json]
python -m failbench validate [--strict]            # validates probes/evidence; nonzero exit on error
python -m failbench run --provider mock --demo --out results/demo
python -m failbench run --provider openai --base-url URL --api-key-env VAR --model MODEL --out results/run1 [--concurrency 4] [--class CLASS] [--limit N]
python -m failbench replay --results results/run1   # re-score recorded responses offline
python -m failbench report --results results/run1 --out site   # W4 code, called by CLI
python -m failbench gate --baseline results/base/results.json --current results/run1/results.json
```

Provider `mock` must be fully deterministic, offline, and produce a realistic mix of pass/fail (never 100%) so the demo/report/tests exercise both paths.
Provider `openai` must work with any OpenAI-compatible `/chat/completions` endpoint via `urllib` (stdlib), with timeout/retry, and must never log secrets.
Provider `replay` must reproduce statuses from `raw.jsonl` without network.

## 9. File ownership (write scopes are exclusive)

| Owner | Exclusive write scope |
|---|---|
| root (me) | `docs/CONTRACT.md`, `failbench/__init__.py`, `failbench/schema.py`, `failbench/scoring.py`, `pyproject.toml`, `.gitignore`, `LICENSE`, `docs/templates/**`; integration fixes anywhere only after coordinating |
| W1 | `data/evidence/**`, `scripts/evidence/**` |
| W2 | `probes/**` |
| W3 | `failbench/providers/**`, `failbench/runner.py`, `failbench/gate.py`, `failbench/cli.py`, `tests/**` (core) |
| W4 | `failbench/report.py`, `site/**`, `docs/RESULTS.md`, `assets/charts/**` |
| W5 | `.github/workflows/**`, `scripts/validate/**`, `docs/reviews/QA_REPORT.md`, `tests/integration_*` (only after root handoff) |
| W6 | `README.md`, `docs/QUICKSTART.md`, `docs/METHODOLOGY.md`, `docs/ROADMAP.md`, `docs/FAQ.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md` |
| W7 | `launch/**`, `CITATION.cff`, `assets/banner.svg`, `assets/logo.svg`, `docs/DISTRIBUTION.md` |
| W8 | `scripts/publish/**`, `.github/ISSUE_TEMPLATE/**`, `.github/PULL_REQUEST_TEMPLATE.md`, `docs/PUBLISHING.md` |
| W9 | `SECURITY.md`, `docs/reviews/CLAIMS_AUDIT.md`, `docs/reviews/SAFETY_REVIEW.md` |
| W10 | `docs/TAXONOMY.md`, `docs/ATLAS.md`, `docs/MITIGATIONS.md` |

Do not edit files outside your scope. If a cross-scope change is needed, describe it precisely in your final report (file, exact change, why). Do not run `git` (root owns publishing). Do not create venvs or install packages. Do not write outside the repo root except `_scratch/`.

## 10. Quality bar / definition of done

Every workstream must:
1. Produce its deliverables in scope, valid per this contract.
2. Add a `## Verification` section in its final report with exact commands run and observed result (e.g. `python -m failbench validate --strict` → `OK: 0 errors`; `python -m unittest ...` → `OK`). If you could not verify, say so explicitly.
3. Include a `## Files` list (relative paths) and a `## Integration notes` list for the root.
4. Avoid placeholder text like "TODO", "lorem", "example.com" in committed deliverables. Placeholders are allowed only inside `tests/` fixtures or docs templates.
5. Keep a neutral, professional OSS voice. No hype, no fake metrics, no emojis except at most one in README title if W6 chooses.

## 11. Team protocol

- The root creates one shared task per workstream. Claim your task (`team_task_update` action `claim`) before starting.
- You may spawn nested workers with the `subagent` tool *within your exclusive scope*; give each a disjoint file set. Cap: W1/W2 up to 10 workers, W3 up to 6, others up to 5. If the subagent tool is unavailable or errors, do the work yourself and note it. Do not let a worker write outside its assigned files.
- If you need work from another stream, do not wait: build against this contract, and list the dependency in `## Integration notes`.
- Finish by completing your shared task and returning the report (≤500 words + file list). No hidden work.

## 12. Timeline expectation

Work in stages; commit nothing. Aim to deliver a usable first version quickly (core files valid and verified), then improve coverage. Partial but honest and verified beats complete but fabricated. Report early blockers immediately.
