---
title: "Judge-free LLM evaluation: inside FailBench's deterministic failure probes"
published: false
description: "How FailBench scores LLM failures with deterministic, judge-free rules: probe schema, mechanical scorers, evidence atlas, runner, CI gate and honest limits."
tags: ai, opensource, python, llm
ai_disclosure_level: some_ai
---

Most LLM evaluations end with a model grading another model. Judges are convenient, but they add cost and variance, and a rubric edit can move scores without the model changing. Public claims often arrive without a source or a rerunnable command. FailBench, a pre-release open-source project, takes a narrower route: write the pass condition down, make the check mechanical, and source every failure mode.

## The problem with judge-based evaluation

LLM-as-judge has genuine uses, but as a regression test it is expensive, variable, and opaque: a disputed verdict has no rule to inspect, and a judge upgrade can silently change historical scores. A testable claim like "models miss information in the middle of long context" is citable; a bare score usually is not. A 2023 paper, "Lost in the Middle: How Language Models Use Long Contexts" (Liu et al., TACL; https://arxiv.org/abs/2307.03172), found that retrieval accuracy is highest when relevant information is at the start or end of the input and degrades in the middle. That is the shape of claim a deterministic probe can encode: put a unique synthetic code mid-context and check whether the reply contains it.

## Why judge-free, deterministic scoring

A response should get the same verdict every time, and anyone should be able to recompute it offline. FailBench scores only with written-down mechanical rules: the same recorded response re-scored later produces the same result with no network and no API key. Failures report expected versus found rather than a bare boolean, and provider exceptions are errors, never failures, so infrastructure problems cannot lower a pass rate.

The evidence atlas backs its 110 failure-mode records with a real source URL, optional popularity metrics, a short exact quote when verifiable, and a status of `cited`; `tested` requires a real model run. Probes and evidence records share the same ten-class vocabulary, so a reader can move from a probe to its class's public reports; per-probe evidence ids are not populated in v0.1.0.

## Design

**Probes** are one JSON file each under `probes/<class>/<probe_id>.json`; the corpus is 100 probes across 10 failure classes. Each record carries its class, severity, rationale, a static prompt, sampling parameters, a repeat count, and exactly one scoring rule. Prompts are self-contained with no templating and default to temperature 0. Ordinary probes run once; determinism and calibration probes repeat, and every repeat must pass, so flakiness is visible.

**Scorers** live in `failbench/scoring.py`: `contains_all`, `contains_any`, `not_contains_any`, `exact_match`, `regex`, `json_schema` (a minimal subset), `numeric` with optional tolerance, and `all_of`. Normalization collapses whitespace and non-breaking spaces, matching is case-insensitive unless stated, JSON may be bare or fenced, and numeric scoring reads the first number. A negative check alone would pass on an empty response, so negative constraints pair with a positive check inside `all_of`.

**Evidence, runner, report, gate.** Providers: a deterministic offline `mock`; `openai` for any OpenAI-compatible `/chat/completions` endpoint, standard library only, with timeouts, retries, and no key logging; and `replay`, which re-scores recorded responses from `raw.jsonl` offline. A run writes `results.json` plus the raw log, a static report renders the dashboard, and a gate command exits nonzero on regressions, so it works in CI.

## Walkthrough: one probe, end to end

`probes/reasoning_consistency/rea_arithmetic_01.json` is a real probe: class `reasoning_consistency`, severity `high`, basic arithmetic. The system message says "You are a precise arithmetic assistant. Answer with the number only."; the user message says "Compute (17 * 23) - 119." Sampling is temperature 0 with `max_tokens` 64, one repeat, and the scoring rule is `{"type": "numeric", "value": 272}` with zero tolerance.

The scorer reads the first number in the response after removing thousands separators, and passes only when it is within tolerance of 272. Verified against the actual scorer: `272` passes, `The answer is 272.` passes, and `391 - 119 = 272` fails with "expected 272 (tolerance 0.0) but found 391.0", because the first number is 391. A word-only answer such as "two hundred seventy-two" fails with "no number found in response". That brittleness is documented: a chatty reply whose first number is not the result fails even when the result appears later, which is why the system message forbids explanation.

## How to run it

Plain Python (3.9+), from the repository root, no virtual environment or install:

```bash
python -m failbench validate
python -m failbench run --provider mock --demo --out results/demo
python -m failbench run --provider openai --base-url "$FAILBENCH_BASE_URL" --api-key-env FAILBENCH_API_KEY --model your-model --out results/run1
python -m failbench replay --results results/run1
python -m failbench gate --baseline results/baseline/results.json --current results/run1/results.json
```

The mock demo is offline and deterministic; point `openai` at your endpoint for real numbers.

## Honest limitations

- The committed demo run covers all 100 probes: 64 pass, 34 fail, 2 error, from the deterministic mock provider, not from measurements of any real model. No live model endpoint was available during the build; real numbers require running the kit on your own endpoint.
- The probe corpus is small and still growing.
- Keyword-style scoring has known limits: paraphrases and formatting changes can fail correct answers, and a substring can pass without semantic correctness. The schema subset is minimal and regex probes are only as good as their patterns.
- There is no public leaderboard yet.
- Evidence collection was done by one team; independent verification and corrections are valuable.

Mechanical scoring is a filter, not a substitute for careful human review.

## Contributing evidence and probes

Evidence contributions need a real source URL from a search or API result, an exact quote of at most 200 characters when verifiable, and status `cited`; `tested` requires a real run. Probes need a static prompt, one defensible pass condition, a mechanical rule, and a rationale. Tests must run offline without an API key; new probes should pass `python -m failbench validate`. Code is MIT; evidence and probe data are CC-BY-4.0. The repository is at https://github.com/Qin-z-x/llm-failbench.

*Disclosure: this article and the project were developed with AI assistance under human direction and review; the `ai_disclosure_level: some_ai` front-matter field records that. The human maintainer is accountable for the claims here, and corrections are welcome.*
