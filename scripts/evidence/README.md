# Evidence collection (W1)

This directory contains the **network-enabled** collectors that mined the public
evidence behind the FailBench atlas (`data/evidence/*.jsonl`). Everything else
in the repository is offline; only these scripts talk to the internet, and they
are never imported by `failbench`.

The atlas records *publicly reported* LLM failure modes: what users reported,
what researchers measured, and how much attention each item received. Each
record has a real source URL that an API call returned during collection, plus
the popularity signal the source exposes. No page text is copied: records keep
a link and, for arXiv only, a verbatim abstract excerpt of at most 200
characters.

## Files

| file | purpose |
|---|---|
| `collect_hn.py` | Hacker News story search via the Algolia API (no auth). |
| `collect_arxiv.py` | arXiv paper search via the export API (Atom XML, no auth). |
| `collect_github.py` | GitHub issue search (unauthenticated; rate-limited, lead-only small batches). |
| `build_index.py` | Rebuild `data/evidence/index.json` from the JSONL files on disk. |
| `verify_provenance.py` | Re-verify every record against the stored raw API dumps (anti-fabrication gate) and check index counts. |

Raw API dumps are written to a scratch directory (default examples below use
`_scratch/w1/raw/`), which is git-ignored and not shipped. The dumps hold the
normalized candidates exactly as the APIs returned them, which is what
`verify_provenance.py` checks the committed evidence against.

## Quick start

```bash
# Hacker News: one invocation, repeated --query (30 hits each, >=2 points)
python scripts/evidence/collect_hn.py \
  --query "context rot" --query "lost in the middle" \
  --hits 30 --min-points 2 --sleep 1.0 \
  --raw-dir _scratch/w1/raw/context_retrieval \
  --out _scratch/w1/raw/context_retrieval/cand_hn.jsonl

# arXiv: phrase search, 25 results per query, 3 s between requests
python scripts/evidence/collect_arxiv.py \
  --query "lost in the middle" --query "needle in a haystack" \
  --max-results 25 --sort-by relevance --sleep 3.0 \
  --raw-dir _scratch/w1/raw/context_retrieval \
  --out _scratch/w1/raw/context_retrieval/cand_arxiv.jsonl

# GitHub issue search: unauthenticated, keep batches tiny
python scripts/evidence/collect_github.py \
  --query "infinite loop in:title repo:langchain-ai/langchain" \
  --sleep 10 --raw-dir _scratch/w1/raw/github \
  --out _scratch/w1/raw/github/cand_github.jsonl

# Rebuild the index and re-verify provenance
python scripts/evidence/build_index.py
python scripts/evidence/verify_provenance.py
```

Each collector prints progress to stderr and writes candidate JSONL plus raw
dumps. Candidates carry `_`-prefixed provenance hints (`_query`, `_rank`,
`_abstract`, `_quote_suggestion`, …) that are not part of the evidence schema;
the committed record copies only contract fields from the candidate.

## Record schema

The authoritative schema is `docs/CONTRACT.md` section 4 and
`failbench/schema.py::validate_evidence`. Required: `id`, `class`, `title`,
`source_type`, `source_url`, `status`, `collected_by`, `collected_at`.
Optional: `source_title`, `publisher`, `published_date`, `metrics`, `quote`,
`summary`, `probe_ids`, `notes`.

Conventions used by this collection run (2026-11-24):

- `collected_by` = `W1/<worker-name>`; `collected_at` = `2026-11-24`;
  `status` = `cited`; `probe_ids` = `[]`.
- `title` is the FailBench statement of the failure (our wording, 5–200 chars);
  `source_title` is the source's own title, verbatim from the API.
- `published_date` is the API creation/publication date (`YYYY-MM-DD`).
- `metrics` for HN stories: `hn_points`, `hn_comments`; for GitHub issues:
  `github_reactions`, `github_comments`. These are snapshots taken at
  collection time and will drift. arXiv records carry no metric, so the index
  field `citations_known` is always `0` — no citation counts were fetched and
  none may be claimed.
- `quote` is an exact substring of the arXiv abstract (whitespace-normalized by
  the collector; the same sentence in the raw Atom XML may be line-wrapped) and
  `""` for HN/GitHub records, whose API payloads carry no quotable body text in
  this pipeline.

## Rate limits and politeness

| source | limit | behavior of the collector |
|---|---|---|
| HN Algolia | generous, but not unlimited | 1 request per `--query`, 1.0 s pause (`--sleep`), User-Agent, 3 retries with backoff, 30 hits/request. |
| arXiv export API | asks for <= 1 request / 3 s | default `--sleep 3.0`, 25 results/query, 60 s timeout, 3 retries; batches of <= 10 queries. Several workers' queries hit HTTP 429 during the concurrent 10-worker batch; they were retried only after cooldowns, never in a tight loop. |
| GitHub issue search | 10 requests/minute unauthenticated | default `--sleep 10`, `--max-queries 10` safety cap, stops cleanly on 403/429. Only the W1 lead ran it, in small batches. |

## Queries used for the 2026-11-24 collection

Ten workers, one per failure class, each used at most 6 HN queries + 5 arXiv
phrase queries from the fixed plan below. Where a planned phrase returned zero
results or the arXiv API answered HTTP 429 (several workers hit the shared-IP
throttle), the worker substituted a known paper-title phrase inside the same
budget and reported the substitution; the exact query string for every request
is stored in its raw dump (`_scratch/w1/raw/<class>/*.json`). GitHub rows were
added by the W1 lead after the class workers finished (2 each for five classes).
The class-record counts are from the final validated files; see the stats table
below.

- **hallucination** (hal) — HN: `hallucination`, `AI hallucinated`, `fabricated citations`, `AI lawyer fake cases`, `fake citations AI research`, `GPTZero hallucination`; arXiv: `hallucination detection`, `citation hallucination`, `factuality large language models`, `TruthfulQA`, `hallucination survey`.
- **instruction_following** (if) — HN: `ignores instructions`, `instruction following`, `system prompt`, `instruction following benchmark`, `LLM won't follow instructions`, `negative constraints LLM`; arXiv: `instruction following evaluation`, `instruction hierarchy`, `constraint following large language models`, `follow instructions benchmark`, `instruction following`.
- **context_retrieval** (ctx) — HN: `lost in the middle`, `context rot`, `needle in a haystack LLM`, `long context benchmark`, `context window`, `long context retrieval`; arXiv: `lost in the middle`, `needle in a haystack`, `long context retrieval`, `distractor context language models`, `context windows` (one query hit HTTP 429).
- **reasoning_consistency** (rea) — HN: `LLM reasoning`, `self-consistency`, `LLM math`, `reasoning benchmark`, `Apple reasoning paper`, `chain of thought`; arXiv: `self-consistency chain of thought`, `reasoning consistency large language models`, `paraphrase robustness reasoning`, `arithmetic reasoning benchmark`, `reasoning benchmark`.
- **sycophancy** (syc) — HN: `sycophancy`, `sycophantic AI`, `ChatGPT sycophancy`, `GPT-4o sycophancy`, `AI flattery`, `AI agrees with everything`; arXiv: `sycophancy language models`, `sycophantic behavior`, `stance changes large language models`, `social pressure language models`, `sycophancy`.
- **structured_output** (str) — HN: `structured output`, `JSON mode`, `invalid JSON`, `function calling`, `tool calling`, `JSON schema LLM`; arXiv: `structured output language models`, `function calling large language models`, `constrained decoding`, `Efficient Guided Generation for Large Language Models`, `JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models`.
- **multilingual** (ml) — HN: `multilingual LLM`, `tokenizer`, `non-English LLM`, `multilingual benchmark`, `Chinese tokenizer`, `low-resource language model`; arXiv: `multilingual large language models`, `code-switching language models`, `cross-lingual transfer`, `tokenization multilingual`, `multilingual`.
- **safety_consistency** (saf) — HN: `over-refusal`, `overrefusal`, `AI refuses`, `false refusal`, `safety filter`, `exaggerated safety`; arXiv: `exaggerated safety behaviors`, `over-refusal large language models`, `false refusal`, `refusal safety alignment`, `safety alignment`.
- **agentic_reliability** (agt) — HN: `AI agents`, `agentic`, `computer use agent`, `autonomous agents`, `agent tool use`, `SWE-bench`; arXiv: `agentic language models`, `tool use large language models`, `agent benchmark`, `failure modes multi-agent systems`, `AI agents`.
- **determinism_calibration** (det) — HN: `deterministic LLM`, `temperature 0`, `non-deterministic`, `LLM calibration`, `LLM confidence`, `abstention LLM`; arXiv: `calibration large language models`, `uncertainty quantification language models`, `determinism language model inference`, `abstention language models`, `confidence language models`.
- **GitHub issue search** (lead only, one small batch) — `invalid json repo:vllm-project/vllm`, `agent loop repo:langchain-ai/langchain`, `system prompt repo:ollama/ollama`, `chinese repo:ollama/ollama`, `hallucination in:title`, `infinite loop in:title repo:langchain-ai/langchain`, `system prompt in:title repo:ollama/ollama`, `json in:title repo:vllm-project/vllm`, `deterministic in:title repo:vllm-project/vllm`, `garbled in:title`. Sorted by reactions; only class-relevant issue reports were kept.

## Final collection stats (2026-11-24)

`python -m failbench.schema` reports `probes=100 evidence=110 errors=0 warnings=0`
on this snapshot. "High-attention" counts records with `hn_points >= 100` or
`github_reactions >= 20`. Canonical totals live in `data/evidence/index.json`;
regenerate with `build_index.py` after any change.

| class | records | HN | arXiv | GitHub | HN points | GitHub reactions | high-attention |
|---|---:|---:|---:|---:|---:|---:|---:|
| hallucination | 12 | 6 | 4 | 2 | 2585 | 39 | 7 |
| instruction_following | 12 | 5 | 5 | 2 | 811 | 4 | 2 |
| context_retrieval | 10 | 5 | 5 | 0 | 569 | 0 | 2 |
| reasoning_consistency | 10 | 6 | 4 | 0 | 1361 | 0 | 4 |
| sycophancy | 10 | 6 | 4 | 0 | 2228 | 0 | 6 |
| structured_output | 12 | 5 | 5 | 2 | 2272 | 14 | 5 |
| multilingual | 10 | 5 | 5 | 0 | 1615 | 0 | 3 |
| safety_consistency | 10 | 5 | 5 | 0 | 737 | 0 | 2 |
| agentic_reliability | 12 | 6 | 4 | 2 | 5930 | 1 | 6 |
| determinism_calibration | 12 | 5 | 5 | 2 | 381 | 105 | 2 |
| **total** | **110** | **54** | **46** | **10** | | | |

## Re-running / extending the atlas

1. Re-run the collectors for the class you are extending (they overwrite their
   `--out` candidate file; raw dumps accumulate with timestamps).
2. Add/modify records in `data/evidence/<class>.jsonl` using candidate values.
3. `python scripts/evidence/verify_provenance.py` — must print `errors=0`.
4. `python scripts/evidence/build_index.py` — refreshes counts in `index.json`.
5. `python -m failbench.schema` — whole-repo schema check (probes + evidence).

## Ethics and licensing

- Only public metadata and short excerpts are recorded; full page or issue
  bodies are not copied. Each record links to the original source.
- No usernames, email addresses or other personal data are included.
- No harmful content: the safety class records over-refusal on harmless
  prompts and refusal-boundary inconsistency, not jailbreak payloads.
- HN points / GitHub reactions are time-stamped snapshots, not endorsements.
- The evidence data is licensed CC-BY-4.0; the collectors are MIT. HN, arXiv
  and GitHub content remains under the respective source's terms; check them
  before any redistribution beyond linking and short quoting.
- Metadata-only collection does not establish correctness of a source's claim;
  `status` stays `cited` unless a FailBench probe run is linked.

## Verification

```bash
python scripts/evidence/verify_provenance.py   # 0 errors expected
python scripts/evidence/build_index.py         # rewrites index.json
python -m failbench.schema                     # probes + evidence, 0 errors expected
```
