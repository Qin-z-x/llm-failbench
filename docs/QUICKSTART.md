# FailBench quickstart

This guide takes you from a fresh checkout to a completed offline run, then shows
how to run the same suite against your own OpenAI-compatible endpoint. All
commands run from the repository root with plain `python`; the local demo needs
no install, no API key and no network.

## Prerequisites

- **Python 3.9 or newer.** `pyproject.toml` declares `requires-python >= 3.9`;
  CI exercises 3.11 and 3.13.
- **No third-party dependencies.** The package and CLI use only the standard
  library.
- **Run from the repository root.** Commands are `python -m failbench ...`; paths
  such as `probes/`, `data/evidence/` and `results/` resolve from the current
  directory.
- **Optional install.** `pip install -e .` gives a `failbench` console command; it
  is not required for anything in this guide.

## 5-minute local demo

### 1. Check the CLI

```shell
python -m failbench --help
```

The commands are `list`, `validate`, `run`, `replay`, `report` and `gate`. Exit
codes printed by `--help`: `0` success, `1` failure/regressions, `2` usage or
configuration error, `3` internal error, `130` interrupted.

### 2. List the probe corpus

```shell
python -m failbench list
python -m failbench list --class hallucination
```

The summary line at the v0.1.0 build snapshot was
`100 probe(s) in 10 class(es)`. The class names are `hallucination`,
`instruction_following`, `context_retrieval`, `reasoning_consistency`,
`sycophancy`, `structured_output`, `multilingual`, `safety_consistency`,
`agentic_reliability` and `determinism_calibration`.

> Windows note: the CLI writes Unicode-safe output, so a legacy console code page
> (for example GBK) does not crash `list`. If your terminal still shows garbled
> characters or a `UnicodeEncodeError`, set `$env:PYTHONIOENCODING = "utf-8"`
> before running.

### 3. Validate the corpus

```shell
python -m failbench validate
```

Every probe and evidence record is checked against the schema in
[CONTRACT.md](CONTRACT.md). At the v0.1.0 build snapshot the output ended with
`OK: 100 probes, 110 evidence records, 0 errors`. Use `--strict` to treat
warnings as errors and `--json` for the raw report.

### 4. Run the offline demo

```shell
python -m failbench run --provider mock --demo --out results/demo
```

`--demo` forces the deterministic `mock` provider: no network, no API key. The
command prints one progress line per probe and a summary, then writes:

- `results/demo/results.json` - contract-shaped results: counts, per-class
  aggregates, per-probe status and reason.
- `results/demo/raw.jsonl` - one line per attempt with the recorded request,
  response, error, latency and timestamp, for auditing and replay.

The committed run in this repository was produced by this exact command. Its
numbers exercise the pipeline; they are not measurements of any model.

### 5. Generate the static dashboard

```shell
python -m failbench report --results results/demo --out site
```

This writes `site/index.html` (a single self-contained file with inline CSS, JS
and data) and regenerates the Markdown report at `docs/RESULTS.md`. Open the
dashboard directly; no server is needed:

```powershell
start site\index.html          # Windows
```

```bash
open site/index.html           # macOS
xdg-open site/index.html       # Linux
```

The page loads no external scripts, fonts or images, so it works offline. Pass
`--results-md PATH` to regenerate the Markdown report elsewhere.

### 6. Replay the recorded run offline

```shell
python -m failbench replay --results results/demo --out results/replay
```

Replay re-scores the responses stored in `raw.jsonl` using the current probe
corpus and scoring rules, with no network and no API key. By default it writes
`replay-results.json` next to the recorded run; `--out DIR` writes it elsewhere,
which keeps the committed `results/demo/` directory untouched. Status changes are
reported as findings rather than crashes. Use it to audit how a scorer or corpus
change would affect an old run without re-querying the endpoint.

## Run against your own OpenAI-compatible endpoint

The `openai` provider talks to any endpoint implementing the OpenAI Chat
Completions API. It reads the API key from an environment variable whose **name**
you pass with `--api-key-env`; the CLI never reads or prints the key value.

| Option | Meaning |
| --- | --- |
| `--base-url URL` | Endpoint base URL (required). `/chat/completions` is appended unless the URL already ends with it. |
| `--api-key-env VAR` | Name of the environment variable holding the key. Defaults to `OPENAI_API_KEY`. |
| `--model MODEL` | Model to request. Defaults to the provider default; set it explicitly. |

Optional: `--concurrency N` (default 4), `--timeout SECONDS` (default 30),
`--retries N` (default 2), `--class CLASS`, `--limit N`, `--out DIR`.

### Endpoint examples

These are common defaults; confirm them against your deployment. Model names are
endpoint-specific examples.

| Endpoint | `--base-url` | Example `--model` | Key variable |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| DeepSeek | `https://api.deepseek.com/v1` (docs also document `https://api.deepseek.com`) | `deepseek-flash` | `DEEPSEEK_API_KEY` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.1` | `OLLAMA_API_KEY`, any non-empty value |
| vLLM (local) | `http://localhost:8000/v1` | the served model, e.g. `Qwen/Qwen2.5-7B-Instruct` | `VLLM_API_KEY`, any non-empty value |
| LiteLLM proxy | `http://localhost:4000/v1` | your proxy model alias, e.g. `gpt-4o-mini` | `LITELLM_API_KEY` |

References: [OpenAI Python library](https://github.com/openai/openai-python),
[DeepSeek API docs](https://api-docs.deepseek.com/),
[Ollama](https://github.com/ollama/ollama),
[vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/),
[LiteLLM OpenAI-compatible endpoints](https://docs.litellm.ai/docs/providers/openai_compatible).
Ollama and vLLM often run without key validation, but the provider requires the
named variable to be non-empty, so set a placeholder unless you configure one.
Never put a real key in a committed file.

### Set the key and run

PowerShell, against the OpenAI API:

```powershell
$env:OPENAI_API_KEY = "sk-your-key"
python -m failbench run --provider openai `
  --base-url https://api.openai.com/v1 `
  --api-key-env OPENAI_API_KEY `
  --model gpt-4o-mini `
  --out results/openai-run1
```

Bash, against DeepSeek:

```bash
export DEEPSEEK_API_KEY=sk-your-deepseek-key
python -m failbench run --provider openai \
  --base-url https://api.deepseek.com/v1 \
  --api-key-env DEEPSEEK_API_KEY \
  --model deepseek-flash \
  --out results/deepseek-run1
```

Bash, against a local Ollama server:

```bash
export OLLAMA_API_KEY=ollama
python -m failbench run --provider openai \
  --base-url http://localhost:11434/v1 \
  --api-key-env OLLAMA_API_KEY \
  --model llama3.1 \
  --out results/ollama-run1
```

The same pattern works for vLLM and a LiteLLM proxy, and for any other
OpenAI-compatible server; substitute the base URL, key variable and model name:

```powershell
# vLLM serving on localhost:8000
$env:VLLM_API_KEY = "local-placeholder"
python -m failbench run --provider openai `
  --base-url http://localhost:8000/v1 `
  --api-key-env VLLM_API_KEY `
  --model Qwen/Qwen2.5-7B-Instruct `
  --out results/vllm-run1

# LiteLLM proxy on localhost:4000
$env:LITELLM_API_KEY = "sk-your-proxy-key"
python -m failbench run --provider openai `
  --base-url http://localhost:4000/v1 `
  --api-key-env LITELLM_API_KEY `
  --model my-proxy-alias `
  --out results/litellm-run1
```

Use placeholder values only; never put a real key in a committed file or a
`results/` artifact. Smoke-test an integration with one probe first:

```shell
python -m failbench run --provider openai --base-url https://api.openai.com/v1 \
  --api-key-env OPENAI_API_KEY --model gpt-4o-mini \
  --class hallucination --limit 1 --out results/smoke
```

A run exits `0` when the suite completed, regardless of how many probes passed:
probe failures are the measurement, not a CLI error. Configuration problems
(unknown provider or class, missing base URL, empty key variable, bad `--limit`)
exit `2` before any probe is attempted.

## Choosing probes

`--class CLASS` restricts the run to one failure class; `--limit N` runs at most N
probes after the corpus is sorted by class and id; `--repeats N` overrides each
probe's repeat count (most probes run once, determinism and calibration probes
repeat three times by default); `--quiet` suppresses per-probe progress lines.

## Interpreting results

Each attempt has one status: `pass` (satisfied the mechanical scoring rule),
`fail` (recorded and did not satisfy it), or `error` (the provider, transport or
scoring could not produce a verdict). Errors are never model failures; a run
whose probes all error can still exit `0`, so check `counts.error`.

`results.json` is the contract-shaped summary: `schema`, `run_id`, `provider`,
`model`, `base_url`, `suite_version`, `started_at`, `finished_at`,
`environment`, `config`, `counts` (`probes`, `pass`, `fail`, `error`),
`by_class` (per-class `total`, `pass`, `fail`, `error`, `pass_rate`), and
`probes` (per-probe `status`, `reason`, `latency_ms`, token counts,
`response_sha256`, `response_excerpt`, `attempts`). API keys are never stored.

`raw.jsonl` is the audit trail: one JSON line per attempt with `probe_id`,
`attempt`, the recorded `request` and `response`, any `error`, `latency_ms` and
`timestamp`. Keep it with `results.json`; replay and forensic review use it.

## Gate in CI

`gate` compares a baseline `results.json` with a current one: exit `0` when clean,
`1` when a previously passing probe now fails or errors (or a probe is missing
from the current results), `2` for usage or configuration errors.

The committed deterministic demo makes the gate testable without an API key:

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

A clean comparison during the build ended with the real line
`GATE PASS: no regressions (100 probes compared).` For a real endpoint, produce a
baseline run with that endpoint and model, commit it (the way `results/demo/` is
committed here), and gate every candidate run against it. The repository's own
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) shows a fuller offline
pipeline. GitHub Actions documentation:
<https://docs.github.com/en/actions>.

## Troubleshooting

**A `UnicodeEncodeError` or `internal error: 'gbk' codec ...` is printed.** Set
`$env:PYTHONIOENCODING = "utf-8"` (PowerShell) or `export PYTHONIOENCODING=utf-8`
(bash) before running FailBench.

**Every probe is `error`, or exit status `2` mentions provider configuration.**
Check that `--base-url` starts with `http://` or `https://`, that the variable
named by `--api-key-env` exists and is non-empty, and that `--model` matches a
model your endpoint serves. For local Ollama or vLLM, set the key variable to a
non-empty placeholder.

**HTTP 401 or 403.** Authentication or permission failure. Verify the key value
and that the key may call the model. These statuses are not retried; affected
probes are recorded as `error`.

**Timeouts.** Raise `--timeout` (seconds, provider default 30) and/or lower
`--concurrency`. Timeouts and transport failures are retried up to `--retries`
times (default 2) with bounded backoff.

**HTTP 429 or transient 5xx errors.** Retryable. Lower `--concurrency` (for
example `--concurrency 1`) and raise `--retries` if the endpoint is rate limited.

**Cost.** FailBench makes one completion request per probe attempt; token counts
are recorded under `tokens` in `results.json`, and each probe caps completion
length with `params.max_tokens`. Cost depends entirely on your endpoint's
pricing, so this project does not estimate a dollar amount. Start with
`--limit 10` or a single `--class` to bound a trial run.

**Replay reports mismatches.** That is a finding, not a crash: the recorded
responses no longer score the same under the current corpus or scoring rules.
Inspect the reported probe ids and the recorded `raw.jsonl` responses.

**The gate exits `1` unexpectedly.** Read its report: it lists every regression
(`pass` -> `fail`/`error`, `fail` -> `error`) and any probe missing from the
current run. New probes are informational and never fail the gate.

## Where to go next

- [../README.md](../README.md) - project overview, suite table, limitations.
- [CONTRACT.md](CONTRACT.md) - schemas, scoring semantics, CLI contract.
- [METHODOLOGY.md](METHODOLOGY.md) - scoring rationale, statistics and threats
  to validity.
- [RESULTS.md](RESULTS.md) - generated report for the committed demo.
- [FAQ.md](FAQ.md) - direct answers, including comparison with other tools.
- [ROADMAP.md](ROADMAP.md) - planned work, and what is not planned.
- [../CONTRIBUTING.md](../CONTRIBUTING.md) - propose probes and evidence records.
- [../SECURITY.md](../SECURITY.md) - responsible disclosure for issues in the
  tool.
