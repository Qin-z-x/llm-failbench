# Use FailBench as a GitHub Action

The repository ships a composite GitHub Action at the root (`action.yml`). It runs a
deterministic, judge-free probe suite against any OpenAI-compatible
`/chat/completions` endpoint, optionally generates the static dashboard, and can
fail the job when a previously passing probe regresses.

The action has zero third-party Python dependencies: it runs the same
standard-library `failbench` package from this repository on the runner's Python 3.

## Minimal workflow

```yaml
name: failbench

on:
  pull_request:
  workflow_dispatch:

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run FailBench probes
        uses: Qin-Z-x/llm-failbench@v0.2.0
        with:
          base-url: ${{ secrets.LLM_BASE_URL }}
          model: ${{ vars.LLM_MODEL }}
          api-key-env: OPENAI_API_KEY
          out: failbench-results
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: failbench-report
          path: failbench-results/
```

Set the endpoint and model as repository variables/secrets, for example
`LLM_BASE_URL=https://api.deepseek.com/v1` and `LLM_MODEL=deepseek-chat`, with the
API key stored as a secret and exposed under the name given by `api-key-env`.

## Gate on regressions

Commit a baseline `results.json` produced by the same endpoint and model, then pass
its path. The action exits non-zero when a probe that passed in the baseline now
fails or errors, or when a baseline probe is missing from the current run.

```yaml
      - name: Run FailBench probes and gate on regressions
        uses: Qin-Z-x/llm-failbench@v0.2.0
        with:
          base-url: ${{ secrets.LLM_BASE_URL }}
          model: ${{ vars.LLM_MODEL }}
          baseline: baselines/llm-production/results.json
          out: failbench-results
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `base-url` | yes | | OpenAI-compatible API base URL |
| `model` | yes | | Model name to test |
| `api-key-env` | no | `OPENAI_API_KEY` | Name of the env var holding the key |
| `class` | no | | Restrict to one failure class |
| `limit` | no | | Restrict to the first N probes |
| `out` | no | `failbench-results` | Output directory relative to the workspace |
| `baseline` | no | | Baseline `results.json` for the regression gate |
| `report` | no | `true` | Generate the static dashboard |

## Outputs

| Output | Meaning |
| --- | --- |
| `results-path` | Path to `results.json` |
| `site-path` | Path to `site/index.html` when `report` is enabled |

## Notes and limits

- **Ubuntu only.** The action uses `bash`. On other runners, run the CLI directly.
- **The action measures your endpoint, not a vendor.** It sends the probe prompts to
  the endpoint you configure; review the probe corpus (`probes/`) and your provider's
  terms before pointing it at a paid or shared endpoint.
- **Costs.** A full 100-probe run is 100 chat completions; set `limit` or `class` to
  keep it small. The action itself has no fee.
- **Secrets.** Never commit API keys. The action reads the key from the environment
  variable you name (`api-key-env`); the CLI never logs the key.
- **No LLM judge.** Scoring is mechanical and offline; results are reproducible from
  the recorded `raw.jsonl` via `python -m failbench replay`.