# FailBench

**The evidence-backed, judge-free failure probe kit for LLMs.**

[![CI](https://github.com/Qin-z-x/llm-failbench/actions/workflows/ci.yml/badge.svg)](https://github.com/Qin-Z-x/llm-failbench/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/Qin-Z-x/llm-failbench?sort=semver)](https://github.com/Qin-Z-x/llm-failbench/releases)
[![license](https://img.shields.io/github/license/Qin-Z-x/llm-failbench)](LICENSE)
[![dashboard](https://img.shields.io/badge/dashboard-live-blue)](https://qin-z-x.github.io/llm-failbench/)
[![discussions](https://img.shields.io/github/discussions/Qin-Z-x/llm-failbench)](https://github.com/Qin-Z-x/llm-failbench/discussions)

> **If this is useful, a star or fork helps others find it.** It is a small, unaided project; stars/fork counts are the honest signal that keeps it maintained. No accounts, no telemetry, no paid promotion.

FailBench is an open benchmark and evidence atlas for LLM failure modes. It ships
100 deterministic probes across ten failure classes, each probe scored by a
mechanical rule instead of an LLM judge, and a curated atlas of publicly reported
failures with real source URLs. The same kit runs against any OpenAI-compatible
`/chat/completions` endpoint and provides a CI regression gate, an offline replay
path and a self-contained static dashboard.

Repository: <https://github.com/Qin-z-x/llm-failbench>

**Status: pre-release v0.2.0.** The committed demo results were produced by the
deterministic `mock` provider shipped with the kit, not by a live model
endpoint. No live-model numbers are claimed anywhere in this repository. From
[`docs/CONTRACT.md`](docs/CONTRACT.md) section 1:

> "no live model endpoint was available during the build; the shipped demo run
> is against a deterministic mock provider; users must run the kit on their own
> endpoint to get real numbers."

The generated report states it plainly as well: "No live model endpoint was
available during this build, so the committed demo numbers exercise the pipeline
rather than measure any model" ([docs/RESULTS.md](docs/RESULTS.md)).

Run the kit on your own endpoint to get numbers for your models
([docs/QUICKSTART.md](docs/QUICKSTART.md)).

## Why this exists

Most LLM evaluation today is mediated by a second model acting as judge. That
design has recurring, well-known failure modes:

- **Judge stochasticity and vendor dependence.** A judge model's verdict can
  change with its version, provider, sampling parameters or prompt template, so
  scores are not portable across time or vendors.
- **Position and verbosity bias.** Judges are sensitive to the order in which
  candidates are presented and tend to reward longer, more confident answers
  regardless of correctness.
- **Non-reproducibility.** A prose rubric plus a sampled judge produces verdicts
  that are hard to reproduce, hard to audit and hard to bisect when they change.
- **Cost and latency.** Every graded item costs a second model call, which adds
  latency and spend to every run of the suite.
- **Judge blind spots.** A judge can share the failure modes of the model it is
  grading, for example accepting a fabricated citation that looks plausible.

FailBench takes a different approach: each probe is a fixed, self-contained
prompt with exactly one defensible pass condition, checked by a pure function of
the recorded response. There is no judge, no sampling and no network during
scoring, so a result is reproducible from the recorded artifact. Probes and
public reports are organized under the same ten failure classes, so each class
pairs what practitioners reported with a checkable instance of the behaviour;
per-probe evidence ids are reserved for future grounding and are empty in
v0.2.0.

## Quick-start demo

From the repository root, with plain `python` (no install, no API key, no
network). The name refers to reading the walkthrough, not to a benchmark
runtime: the offline mock demo finishes in seconds, while a live run's duration
depends on your endpoint's latency.

```shell
python -m failbench validate
python -m failbench run --provider mock --demo --out results/demo
python -m failbench report --results results/demo --out site
```

The `validate` command checks every probe and evidence record against the
contract schema. The demo command writes `results/demo/results.json` (per-probe
statuses and aggregates) and `results/demo/raw.jsonl` (one auditable line per
attempt). The report command writes a single self-contained `site/index.html` and
regenerates `docs/RESULTS.md`. The committed demo run used the deterministic mock
provider; see [docs/RESULTS.md](docs/RESULTS.md) for the generated report.

## Suite at a glance

All volatile counts live in this one table. Counts are from the repository at the
v0.2.0 build snapshot; regenerate the report to refresh them.

| Item | Count | Notes |
| --- | ---: | --- |
| Hallucination probes | 10 | fabricated facts, citations, APIs, package names, quotes |
| Instruction-following probes | 10 | negative constraints, format, length and ordering |
| Context-retrieval probes | 10 | needle-in-haystack, lost-in-the-middle, distractors |
| Reasoning-consistency probes | 10 | arithmetic and date edge cases, paraphrase stability |
| Sycophancy probes | 10 | stance flips under social pressure, false user premises |
| Structured-output probes | 10 | JSON-schema conformance, tool-call argument shapes |
| Multilingual probes | 10 | cross-lingual degradation, code-switching, scripts |
| Safety-consistency probes | 10 | over-refusal on harmless prompts, inconsistent boundaries |
| Agentic-reliability probes | 10 | loops, over-eager tool use, failure to stop or recover |
| Determinism and calibration probes | 10 | temperature-0 variance, counting and abstention edge cases |
| **Total probes** | **100** | ten classes, ten probes each; severity mix 5 critical / 34 high / 43 medium / 18 low |
| **Evidence records in the atlas** | **110** | cited public reports across all ten classes, each with a real source URL |
| **Committed demo run (`mock` provider)** | **100** | 64 pass, 34 fail, 2 error; a pipeline demo, not a measurement of any model |

The demo's two `error` entries are simulated provider failures. Per the contract,
provider and transport errors are recorded separately and are never counted as
model failures.

What the runner provides (all verifiable in the code):

- **Concurrency and retries.** Probes run in a thread pool (`--concurrency`,
  default 4); the OpenAI-compatible provider retries transient failures
  (timeouts, transport errors and HTTP 408/409/429/5xx) with bounded backoff
  (`--retries`, default 2).
- **Auditable artifacts.** `results.json` plus `raw.jsonl` are written
  atomically; recorded requests contain no credentials and the API key is never
  logged or stored.
- **Replay and audit.** `python -m failbench replay --results <run>` re-scores
  the recorded responses offline, so a run can be re-checked without network or
  an API key; add `--out DIR` to write `replay-results.json` outside the recorded
  run directory.
- **Static dashboard and report.** `report` renders a single `index.html` with
  inline CSS, JS and data; it loads no external scripts, fonts or images and
  needs no server.
- **CI regression gate.** `gate` compares a baseline run to a current run.
- **Offline validation.** `validate` checks every probe and evidence record
  against the contract schema.

## Run it against your own OpenAI-compatible endpoint

Any endpoint that speaks the OpenAI Chat Completions wire format works. The API
key is read from the environment variable you name with `--api-key-env`; the key
value is never read or printed by the CLI itself.

```shell
python -m failbench run --provider openai \
  --base-url https://api.openai.com/v1 \
  --api-key-env OPENAI_API_KEY \
  --model gpt-4o-mini \
  --out results/run1
```

Set the variable first: PowerShell
`$env:OPENAI_API_KEY = "sk-your-key"`, bash
`export OPENAI_API_KEY=sk-your-key`. For DeepSeek, Ollama, vLLM, LiteLLM and
other endpoints, see the endpoint table and environment-variable examples in
[docs/QUICKSTART.md](docs/QUICKSTART.md). Use `--class CLASS` and `--limit N` to
run a subset while you are validating an integration.

## Use it as a GitHub Action

Run the suite against any OpenAI-compatible endpoint in a workflow, optionally gate
on regressions against a committed baseline, and upload the report:

```yaml
      - uses: Qin-Z-x/llm-failbench@v0.2.0
        with:
          base-url: ${{ secrets.LLM_BASE_URL }}
          model: ${{ vars.LLM_MODEL }}
          baseline: baselines/prod/results.json
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

Full inputs, outputs, caveats and cost notes are documented in
[docs/GITHUB_ACTION.md](docs/GITHUB_ACTION.md).

## CI gate

`gate` compares a baseline `results.json` with a current one. It exits `0` when
there are no regressions, `1` when a previously passing probe now fails or
errors (or a probe disappeared from the current run), and `2` on usage or
configuration errors such as a missing file.

The committed demo run makes the gate testable in CI without any API key. A
minimal workflow that re-runs the deterministic demo and gates it against the
committed baseline:

```yaml
name: failbench
on: [pull_request]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Fresh deterministic demo run
        run: python -m failbench run --provider mock --demo --out results/ci
      - name: Regression gate against the committed baseline
        run: >-
          python -m failbench gate
          --baseline results/demo/results.json
          --current results/ci/results.json
```

For a real endpoint, commit a baseline run produced by that endpoint and model
(the same way `results/demo/` is committed here), then gate each candidate run
against it. The repository's own CI workflow lives at
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Evidence atlas

The atlas is a machine-readable, per-class corpus of publicly reported LLM
failure modes in `data/evidence/`, one JSONL file per failure class. Each record
is one JSON object describing a single source: a stable evidence id, the failure
class, a title and neutral summary, the source type and a **real, public source
URL**, the publisher and date where known, and optional short verbatim quotation.
Records default to `status: "cited"`; the contract forbids marking a record
`tested` without a real live run. The atlas is linked to the probe corpus by
failure class, not by per-probe citation.

Popularity signals are recorded where the source exposes them: Hacker News points
and comments, and GitHub reactions and comments. The contract's metric vocabulary
also allows Reddit counts, citation counts and repository stars; this build does
not use those. The recorded numbers measure attention, not severity or
prevalence.

To browse the atlas with the current run, generate the site and open the file:

```shell
python -m failbench report --results results/demo --out site
start site\index.html     # Windows; macOS: open site/index.html; Linux: xdg-open site/index.html
```

The generated `index.html` is self-contained: open it directly from disk, no web
server and no network connection required. The committed
[`site/index.html`](site/index.html) was generated from the demo run and the
atlas.

## Methodology

Probes are static, single-turn prompts. Each carries a fixed scoring rule from a
small mechanical vocabulary: required substrings, forbidden substrings, exact
match, regular expression, numeric tolerance, a minimal JSON-schema subset, or a
conjunction of those. Responses are whitespace-normalized before matching; a
probe with multiple repeats passes only if every repeat passes. Provider and
transport failures become `error` records, never `fail` records. Every failure
reports the concrete mismatch (what was expected versus what was recorded) rather
than a subjective score. The full rationale, including how to add probes without
introducing ambiguity, is documented in `docs/METHODOLOGY.md` alongside this
README.

## Limitations and threats to validity

- **Mechanical scoring is brittle by design.** A semantically correct answer
  phrased outside the expected surface forms can fail a probe. Every probe
  documents its pass condition, and scoring brittleness is fixed by changing the
  probe and re-running the gates, not by silently loosening the scorer.
- **The committed demo is not a measurement.** It exercises the pipeline with a
  deterministic mock provider. It says nothing about the quality of any model.
- **Per-class sample size is small.** At v0.2.0 each class has 10 probes, so a
  single probe moves that class's pass rate by 10 percentage points. Treat class
  rates as diagnostics for regressions, not as precise capability estimates.
- **No statistical confidence claims.** FailBench is a regression and smoke-test
  kit, not a leaderboard. No confidence intervals, significance tests or
  population estimates are made.
- **Static prompts only.** The suite covers single-turn, statically prompted
  behaviours; it does not measure tool use in a live environment, multi-turn
  dialogues or retrieval pipelines.
- **Public corpus, overfitting risk.** Probes and their sources are public, so a
  model or vendor could overfit to them. Use private additions as a holdout
  where that matters.
- **Evidence popularity is not prevalence.** Atlas metrics measure public
  attention, not how often a failure occurs in the wild or how severe it is.

## Related tools

- [llm-json-doctor](https://github.com/Qin-Z-x/llm-json-doctor) - deterministic
  repair and JSON Schema validation for malformed LLM structured output; the
  companion mitigation tool for the `structured_output` failure class. It logs
  every repair action and never invents missing values.
- [yixin-go](https://github.com/Qin-Z-x/yixin-go) - local-first Windows Go (weiqi/baduk) sparring partner built on KataGo + Human SL.
- [llm-invisible-guard](https://github.com/Qin-Z-x/llm-invisible-guard) - detect and sanitize invisible-Unicode prompt injection (zero-width, bidi, Unicode-Tag smuggling).
- [llm-exfil-guard](https://github.com/Qin-Z-x/llm-exfil-guard) - detect data exfiltration through rendered LLM output: image beacons, hidden content, remote loads.
- [slopsquat-guard](https://github.com/Qin-Z-x/slopsquat-guard) - flag hallucinated / typosquatted PyPI and npm dependency names before you install them.
- [regex-redos-guard](https://github.com/Qin-Z-x/regex-redos-guard) - ReDoS (catastrophic backtracking) risk detection for LLM-generated regexes, static + timed probes.

## Community

- **Discussions:** questions, probe requests, and "share your results" posts are
  welcome in [GitHub Discussions](https://github.com/Qin-Z-x/llm-failbench/discussions).
- **Evidence and probes:** submit a real public report or a deterministic probe via
  the issue templates; see [CONTRIBUTING.md](CONTRIBUTING.md).
- **Dashboard:** <https://qin-z-x.github.io/llm-failbench/>

## Citation, license and contributing

If you use FailBench, cite it as described in [CITATION.cff](CITATION.cff).
A generic reference:

```bibtex
@misc{failbench2026,
  title        = {FailBench: the evidence-backed, judge-free failure probe kit for LLMs},
  author       = {{llm-failbench contributors}},
  year         = {2026},
  version      = {0.2.0},
  note         = {Open-source software; citation metadata in CITATION.cff}
}
```

- **Code:** MIT. See [LICENSE](LICENSE).
- **Data** (probe corpus and evidence atlas): CC-BY-4.0, per
  [docs/CONTRACT.md](docs/CONTRACT.md). External sources stay under their own
  licenses; the atlas links to them and stores only short quotations and neutral
  summaries.

Contributions are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) first. For security issues in the tool
itself, see [SECURITY.md](SECURITY.md).

## Learn more

- [docs/QUICKSTART.md](docs/QUICKSTART.md) - install-free local demo and
  endpoint setup for OpenAI, DeepSeek, Ollama, vLLM and LiteLLM.
- [docs/RESULTS.md](docs/RESULTS.md) - generated report for the committed demo
  run, with per-class tables.
- [docs/TAXONOMY.md](docs/TAXONOMY.md) - definitions of the ten failure classes.
- [docs/ATLAS.md](docs/ATLAS.md) - what the evidence atlas contains and how it
  is curated.
- [docs/ROADMAP.md](docs/ROADMAP.md) - planned work for future releases.
- [docs/FAQ.md](docs/FAQ.md) - direct answers, including how FailBench differs
  from other LLM evaluation and red-teaming tools.
- [CHANGELOG.md](CHANGELOG.md) - release history.
- [docs/CONTRACT.md](docs/CONTRACT.md) - the build contract: schemas, scoring
  rules, CLI contract and quality bar.

FailBench is not affiliated with any model vendor.
