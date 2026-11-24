# FailBench Methodology

Version 0.1.0. This document describes how FailBench measures model behaviour, what
the measurements mean, and where they stop being trustworthy. The normative schemas
and scoring semantics live in [`CONTRACT.md`](CONTRACT.md); the class definitions live
in [`TAXONOMY.md`](TAXONOMY.md); this document is the explanatory layer.

FailBench has two halves: an **evidence atlas** of publicly reported LLM failure modes
(with real source links) and a **probe kit** of deterministic, judge-free checks. The
two are joined by a fixed ten-class vocabulary. Nothing in this document is derived
from a model's own judgement: every pass/fail decision comes from a mechanical rule.

## 1. Purpose and scope

### 1.1 What FailBench measures

FailBench measures, for a specific endpoint, model name and decoding configuration,
whether the model's output satisfies a set of **concrete, pre-specified conditions** on
a fixed corpus of static prompts. For each probe the outcome is binary (`pass`/`fail`)
and, separately, whether the attempt completed at all (`error`). Per-class pass rates
are descriptive summaries of those binary outcomes.

The unit of measurement is the probe: one static prompt, one pass condition, one
recorded response. This makes every failure a concrete, replayable witness ("this
endpoint produced this text for this prompt") rather than a score assigned by another
model.

### 1.2 What FailBench does not measure

- **General model quality or capability.** There is no aggregate quality score, no
  MMLU-style capability ranking, and no claim that a higher pass rate means a "better"
  model.
- **Safety, jailbreak resistance, or prompt-injection robustness.** The
  `safety_consistency` class measures the *opposite* direction: over-refusal on
  harmless prompts and inconsistent refusal boundaries across near-duplicate harmless
  prompts. No attack payloads are shipped and no probe asks for harmful output. See
  [`CONTRACT.md`](CONTRACT.md) section 1 and [`TAXONOMY.md`](TAXONOMY.md) section 3.
- **Leaderboard rankings, prevalence, or production failure rates.** Pass rates on a
  fixed public corpus are not estimates of how often a failure occurs in deployment.
- **Statistical inference.** No confidence intervals, significance tests, or
  model-comparison statistics are claimed at v0.1.0; see section 8.
- **Multimodal, training-time, or serving-infrastructure properties.** FailBench sends
  text to a chat-completions endpoint and observes text back.

### 1.3 Honest status of the shipped release

No live model endpoint was available during this build. In the words of the generated
report's required honesty sentence:

> No live model endpoint was available during this build, so the committed demo numbers
> exercise the pipeline rather than measure any model.

The committed demo under `results/demo/` was produced by the deterministic mock
provider (section 7). The atlas is report-level evidence: it records what people
publicly reported, not what this project reproduced.

## 2. Probe design principles

The probe schema is defined in [`CONTRACT.md`](CONTRACT.md) section 5 and validated by
`failbench/schema.py`. The design rules below are what make the resulting numbers
mechanically checkable.

### 2.1 One static, self-contained prompt

Each probe is a JSON file containing a complete message list (`system`/`user`/
`assistant`; 1-20 messages, at most 30,000 characters total). Prompts are static text:
no external files, no templating, no retrieval at run time, no tool calls. A probe must
be interpretable by a model that has seen nothing else. Synthetic filler text and
invented identifiers are encouraged; copying more than 100 characters of source text and
including PII are not allowed.

### 2.2 One unambiguous correct answer or pass condition

Every probe must have exactly one defensible pass condition. Partial credit is not
supported: a behaviour either meets the stated mechanical condition or it does not. If
two competent reviewers could disagree about whether a response "should" pass, the probe
is defective and must be fixed or removed. Probe authors are expected to verify that a
trivially correct response passes and a trivially wrong response fails before submitting
the probe.

### 2.3 Mechanical scoring only

Scoring is a pure function of the probe's scoring specification and the response text,
implemented in [`failbench/scoring.py`](../failbench/scoring.py). No human or model
judges any response at run time. Section 3 lists the eight supported scorer types and
their tradeoffs, and section 4 explains why an LLM judge is deliberately not used.

### 2.4 Severity labels

Every probe carries a `severity` label. The label is the probe author's judgement of
the **expected impact if this specific behaviour fails in a chat deployment**; it is not
a frequency estimate, not a measured harm score, and not a statement about prevalence.

| Label | Intended meaning |
|---|---|
| `critical` | A failure would plausibly cause material harm or a seriously wrong decision in a common deployment, and should be treated as blocking before deployment. |
| `high` | Clearly wrong or constraint-violating output on a core task; users would notice and trust would be lost. |
| `medium` | Failure under specific conditions; degrades reliability but is usually recoverable or noticeable. |
| `low` | Minor, cosmetic, formatting, or localization issue. |

Severity is used by the report generator (section 6) and in the corpus coverage tables.
It is a judgement made when the probe is written, and different authors may weigh
impact differently; the label is never inferred from a model's output.

### 2.5 Repeats (1-5)

`repeats` controls how many independent attempts are made for a probe. The allowed range
is 1-5. In the v0.1.0 corpus most probes use `repeats: 1`; the `determinism_calibration`
class uses `repeats: 3` because its subject is stability across identical calls. Repeats
are not used as a way to average away noise. A probe passes only if **every** repeat
passes (section 5).

### 2.6 Evidence grounding

A probe may reference evidence records through `evidence_ids`; evidence records may
reference probes through `probe_ids`. Both fields are optional in the schema. In the
v0.1.0 corpus the binding between the two halves is the shared class vocabulary, and the
explicit cross-reference lists shipped in the files are empty. They are validated when
present and are intended to become populated as the atlas matures.

### 2.7 Safety constraints

Probes must not contain working jailbreaks, exploit payloads, prompt-injection payloads
aimed at third-party systems, malware, PII, private data, or leaked material. Safety
probes are limited to harmless prompts that measure over-refusal and boundary
consistency. This is a repository non-negotiable in [`CONTRACT.md`](CONTRACT.md)
section 1 and is restated in [`../SECURITY.md`](../SECURITY.md).

## 3. Deterministic scoring

### 3.1 Normalization

Two normalizations are used, both implemented in `failbench/scoring.py`:

1. **Whitespace normalization** (`normalize`): every run of whitespace is collapsed to a
   single space, non-breaking spaces (U+00A0) are converted to ordinary spaces, and the
   result is trimmed. Case is then lowercased unless `case_sensitive: true`.
2. **No normalization for `regex` and `numeric`.** `regex` applies the pattern to the
   raw response text with `re.S | re.M`; `numeric` removes commas and reads the raw
   response. Only the `contains_*` and `exact_match` scorers use the normalized form.

Default case behavior: `case_sensitive` defaults to `false`, so contains-matching and
exact-match comparisons are case-insensitive unless the probe opts in. Regex matching is
case-sensitive unless the pattern itself uses flags or character classes.

`json_schema` extraction is separate from normalization: the scorer first tries fenced
code blocks, then the whole response, then the first parseable JSON value starting at
any `{` or `[`. The schema subset is `type`, `properties`, `required`,
`additionalProperties`, `items`, and `enum`; `integer` explicitly excludes booleans.

### 3.2 The eight scorer types

All scorers return `(passed: bool, detail: str)`. On failure the detail states the
concrete mismatch (expected versus found, truncated to 200 characters); it is surfaced
in `results.json` as the probe's `reason`.

| Type | Pass condition | Strength | Weakness |
|---|---|---|---|
| `contains_all` | Every string in `value` occurs in the normalized response. | Simple and robust to extra prose; suitable for multi-part answers with required tokens. | Misses paraphrases and equivalents; can be satisfied by echoing the expected strings. |
| `contains_any` | At least one string in `value` occurs in the normalized response. | Tolerates alternative correct spellings, notations, or translations. | A single permissive alternative can make a probe too easy; says nothing about the rest of the response. |
| `not_contains_any` | None of the strings in `value` occurs in the normalized response. | Expresses negative constraints and forbidden answers directly. | Substring false positives (a response that mentions the forbidden string while rejecting it fails) and no semantic matching. |
| `exact_match` | The normalized response equals the normalized `value`. | Strongest check for single-token or canonical answers; catches off-format output. | Brittle to any extra text or unanticipated formatting; only appropriate when exact output is itself the requirement. |
| `regex` | `re.search(pattern, response, re.S\|re.M)` matches (inverted when `negate: true`). | Flexible: codes, dates, full-width digits, alternative notations. | Patterns can over-match or match unintended text; complex patterns are hard to audit and a hostile pattern can be slow (ReDoS) when running untrusted probe files. |
| `json_schema` | Extract JSON from the response (one fence tolerated) and validate it against the minimal schema subset. | Checks structural conformance (types, required keys, no extra keys, array items) exactly. | "First parseable JSON" can pick an embedded example rather than the intended answer; the schema subset omits formats, ranges, and cross-field constraints. |
| `numeric` | The **first** number in the response (pattern `[-+]?\d+(?:\.\d+)?`, commas removed) is within `tolerance` of `value`. | Tolerant of units and explanation when the expected number is the first number; tolerance absorbs rounding. | A preamble or intermediate step containing a number is scored instead of the final answer; comma removal and sign/decimal edge cases can change what the first number is. |
| `all_of` | Every unit in `units` passes; used for multi-constraint probes. | Composes independent constraints (for example format plus content). | Strict conjunction raises false-fail risk and can be unsatisfiable if units conflict; only the first failing unit's detail is reported. |

The `all_of` scorer is the most common composition mechanism in the shipped corpus;
probes use it to combine a structural check with a content check. A probe uses one
`scoring` object; nesting is only through `all_of`.

### 3.3 Limits of mechanical scoring

Mechanical rules measure exactly what they are written to measure. A deterministic
scorer cannot judge whether an answer is useful, well-explained, or contextually
appropriate, and it cannot reliably recognise a correct paraphrase that avoids the
expected token. Probes are therefore designed so that a defensibly correct response
conventionally contains the checked token, structure, or number. When that design is
impossible, the phenomenon is out of scope for the probe kit (see
[`TAXONOMY.md`](TAXONOMY.md) section 3) rather than graded by a judge.

## 4. Why no LLM judge

FailBench deliberately does not use an LLM-as-judge, for five structural reasons:

1. **Reproducibility.** A judge's verdict depends on the judge model, its version, its
   system prompt, its decoding parameters, and the order of items. A scoring function
   that can change without any change to the probe or the response is not a measurement
   instrument.
2. **Known judge biases.** Judge models have documented tendencies such as preferring
   their own family's outputs, favouring earlier or later positions in a pairwise
   comparison, and favouring longer or more confident answers. These biases are not
   hypothetical edge cases; they make aggregate scores sensitive to prompt layout.
3. **Vendor dependence.** Using a hosted judge makes the benchmark's scores depend on a
   third-party endpoint's availability, pricing, and terms, and can create a conflict of
   interest when the judge and the judged model share a vendor.
4. **Cost and latency.** Every judged response is an additional model call; a suite that
   is cheap enough to run as a pre-deployment gate becomes materially more expensive and
   slower when a judge is added.
5. **Auditability.** "The judge marked it wrong" is not a reproducible failure report.
   A mechanical mismatch can be checked by a human with the response text and the probe
   file in seconds.

The cost of this choice is real: deterministic rules trade coverage for reproducibility.
They cannot score open-ended qualities, they are brittle to phrasing in ways judges are
not, and they can be gamed by output that contains the expected token. FailBench accepts
that trade because its purpose is a fast, auditable regression gate and citable failure
witnesses, not a general quality score. Classes that can only be recognised by a human
or a judge are excluded from the taxonomy rather than approximated with a model.

## 5. Repeats, the all-pass rule, and errors

`score_probe_scoring` in `failbench/scoring.py` scores every recorded response for a
probe and returns `passed = True` only if **all** repeats passed. The reasoning is
direct: a probe is a deterministic check of a specific behaviour. If a model meets the
condition on one call and not on an identical second call, the behaviour is not reliably
present, so reporting a pass would overstate it. A flaky result is a failure at the probe
level, and the per-attempt history is preserved so the flakiness is visible rather than
averaged away.

For example, the ten `determinism_calibration` probes run three times each; if two of
three attempts pass, the probe status is `fail`, and `attempts` in `results.json` shows
which attempt failed and why.

**Errors are not failures.** If the provider cannot produce a response (network error,
HTTP error, timeout after retries), the runner records `status: "error"` for that probe
and never routes the failure through the scorers. A malformed scoring specification or
an internal runner exception is also recorded as an error. The distinction matters: an
API outage says nothing about the model's behaviour, so counting it as a model failure
would bias every affected class. Errors are shown separately in the report and remain in
the pass-rate denominator (a probe that errored did not pass), but they are not counted
as model failures.

A run itself exits successfully when all probes completed, regardless of how many
failed: probe failures are the measurement, not a CLI error. The regression gate is what
turns status changes into a non-zero exit code.

## 6. Severity weighting: what is implemented

The report generator (`failbench/report.py`) computes a generic pass rate and a
**severity-weighted pass rate**:

```
weighted pass rate = sum(weight x passed) / sum(weight x attempted)
weights: critical = 4, high = 3, medium = 2, low = 1
```

An errored probe counts as not passed in this formula. The weights are a published,
fixed presentation choice so a reader can recompute the summary from the per-class
table; they are not a statistical estimate of importance. The report also shows severity
mix, filterable per-probe severity, and orders failure examples by severity, class, and
probe ID.

The regression **gate** (`failbench/gate.py`) is status-based, not severity-weighted. At
v0.1.0 it compares a baseline and a current results document and flags:

- a probe whose status got worse on the scale `pass` (best) < `fail` < `error` (worst);
- a probe that exists in the baseline and is missing from the current run;
- improvements and new probes are reported but do not fail the gate.

The gate exits non-zero when there is at least one regression; it does not apply a
numeric threshold, a severity cutoff, or a weighted-score cutoff. The authoritative
behaviour is in `failbench/gate.py`.

## 7. The mock provider and the demo run

The `mock` provider exists so that the full pipeline (runner, scoring, results
artifacts, report, gate, CI, committed demo) can be exercised with no network, no API
key, and no inference. Its behaviour is specified in
[`failbench/providers/mock.py`](../failbench/providers/mock.py):

- **Deterministic and offline.** Every decision is a pure function of
  `sha256("<probe_id>:<attempt>")`. There is no randomness, wall-clock time,
  environment dependence, or socket; repeated runs produce the same per-probe decisions
  and the same response text.
- **Synthetic mix of outcomes.** A digest-derived bucket decides intent: buckets 0-69
  intend a pass, 70-97 intend a fail, and 98-99 raise a simulated transport error
  (roughly 2% of attempts). For pass intent, responses are synthesized from the probe's
  own scoring specification and verified with the real scorer; for fail intent, a
  plausible evasive or wrong answer is chosen. Synthesis is best effort, so a
  pass-intended response can still fail a degenerate scoring specification.
- **Synthetic metadata.** Token counts are estimates derived from character counts
  (`len(text) // 4`), and latency is a hash-derived value between 1 and 40 ms per attempt
  (a probe with several repeats sums its attempts in `results.json`). They are not
  measurements of cost or timing.

**What the demo numbers mean.** The committed demo (`results/demo/results.json`,
provider `mock`, model name `failbench-mock-1`) exercises the pass, fail, and error
paths end to end. Its numbers are a pipeline demonstration, not a measurement of any
model, and they must not be compared with results from other tools or with real model
runs. The repo does not include a live-model run; users obtain real numbers only by
running the kit against their own endpoint.

**Determinism expectations.** Re-running the mock demo reproduces the same per-probe
statuses and response texts, so the pass/fail/error counts are stable. Run metadata is
not byte-identical across runs because `run_id`, `started_at`, and `finished_at` are
timestamps, and a regenerated report embeds a generation timestamp. Compare statuses,
not artifact hashes.

## 8. Statistics and reporting conventions

- **Pass rate** is `pass / attempted`, where attempted is the number of probes that ran
  (after any `--class`/`--limit` filtering). Errored probes stay in the denominator and
  are not passes.
- **Counts** (`counts.probes`, `counts.pass`, `counts.fail`, `counts.error`) partition
  the attempted probes. Per-class counts use the same definitions and are keyed by the
  fixed class names.
- **No significance testing and no confidence intervals are claimed at v0.1.0.** With
  roughly ten probes per class, a single probe moves a class pass rate by about ten
  percentage points. Ranking classes or models by these pass rates, or comparing runs
  across dates, is descriptive only and is not a statistical claim.
- **No aggregation across runs.** Each results document is a snapshot for one endpoint,
  model name, parameter set, corpus version, and date. The report does not pool runs,
  and the gate compares statuses per probe rather than aggregate scores.
- **Coverage is uneven by design.** Class pass rates are not comparable across classes:
  the probes test different behaviours, the per-class severity mix differs, and some
  classes are easier to check mechanically than others.

Table 1 is the single place where the volatile corpus counts for this release are
recorded. It was computed from `probes/**/*.json`, `data/evidence/*.jsonl`, and the
committed demo results at the time of writing (2026-11-24, v0.1.0). Numbers will change
as the corpus evolves.

**Table 1. Corpus composition and committed demo status (v0.1.0 snapshot).**

| Class | Probes | Critical | High | Medium | Low | Atlas records | Demo pass | Demo fail | Demo error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hallucination | 10 | 1 | 5 | 3 | 1 | 12 | 7 | 3 | 0 |
| instruction_following | 10 | 0 | 2 | 6 | 2 | 12 | 4 | 6 | 0 |
| context_retrieval | 10 | 0 | 5 | 4 | 1 | 10 | 6 | 4 | 0 |
| reasoning_consistency | 10 | 0 | 2 | 6 | 2 | 10 | 9 | 1 | 0 |
| sycophancy | 10 | 2 | 3 | 3 | 2 | 10 | 7 | 3 | 0 |
| structured_output | 10 | 0 | 3 | 5 | 2 | 12 | 6 | 4 | 0 |
| multilingual | 10 | 0 | 3 | 5 | 2 | 10 | 10 | 0 | 0 |
| safety_consistency | 10 | 1 | 3 | 4 | 2 | 10 | 10 | 0 | 0 |
| agentic_reliability | 10 | 1 | 5 | 3 | 1 | 12 | 4 | 5 | 1 |
| determinism_calibration | 10 | 0 | 3 | 4 | 3 | 12 | 1 | 8 | 1 |
| **Total** | **100** | **5** | **34** | **43** | **18** | **110** | **64** | **34** | **2** |

The demo columns are the mock provider's synthetic outcomes and carry no information
about any model. Atlas records are cited public reports, counted per class; they are not
a prevalence estimate.

## 9. Evidence atlas inclusion and ID conventions

The narrative atlas is [`ATLAS.md`](ATLAS.md); its inclusion criteria and collection
method are stated there. In summary, a record enters `data/evidence/<class>.jsonl` only
when all of the following hold:

- **Real, public, reachable source.** `source_url` starts with `http://` or `https://`
  and is a URL the collector actually received from a search or API call. The allowed
  `source_type` values are `hn_story`, `github_issue`, `arxiv`, `blog`, `vendor_doc`,
  `reddit_thread`, `forum_thread`, and `docs`. Private, leaked, and paywalled material is
  excluded.
- **A concrete, user-visible failure** attributable to model or system behaviour in one
  of the ten classes (or vendor documentation that defines the expected behaviour the
  failure violates). Generic announcements and pricing complaints are not evidence.
- **Verbatim quotes only.** The optional `quote` is copied exactly from text the
  collector received, at most 200 characters, or is `""` when exact text could not be
  verified. `summary` is the collector's own words, at most 400 characters, and is never
  presented as a quote. Fabricated URLs, titles, dates, metrics, and citations are
  prohibited.
- **Honest status.** `status` is `cited` by default. `tested` requires a real live run
  reference in `notes`; `refuted` requires a cited source that contradicts the claim.
  All records in the v0.1.0 atlas are `cited`, because no live model runs were available.
- **Optional popularity metrics only.** Allowed keys are `hn_points`, `hn_comments`,
  `github_reactions`, `github_comments`, `reddit_upvotes`, `reddit_comments`,
  `citations`, and `stars`, all non-negative integers. A missing metric is omitted, never
  guessed. Popularity is a discussion signal, not quality, severity, or prevalence. In
  the v0.1.0 atlas the recorded metrics are Hacker News points/comments and GitHub
  reactions/comments; the `citations` and `stars` keys are schema-permitted but not
  populated in this build.
- **Provenance.** `collected_by` and `collected_at` are required, so each record can be
  traced to the collector that produced it. `published_date` is ISO `YYYY-MM-DD` or
  `null`. One record per distinct source; identical URLs are not duplicated.

**ID conventions.** Evidence IDs are `ev_<abbr>_<4 digits>`, for example `ev_ctx_0001`,
partitioned by class file `<class>.jsonl`. Probe IDs are `<abbr>_<slug>_<2 digits>`, for
example `ctx_needle_01`, stored at `probes/<class>/<id>.json`. The schema validates that
the ID prefix matches the class and that the evidence filename matches the class.
Probe-to-evidence links are optional (`evidence_ids` on probes, `probe_ids` on evidence);
evidence `probe_ids` may reference probes that do not exist yet, and the corpus is
reconciled by class. The class vocabulary is the durable link between the two halves.

## 10. Threats to validity

These are the main reasons a FailBench result can be wrong, misleading, or
non-transferable. They are stated so readers can discount the numbers appropriately.

1. **Scorer brittleness.** String matching misses correct paraphrases and can be gamed
   by output that repeats the expected string. Regex patterns can over-match. `numeric`
   takes the first number in the response, so a preamble or intermediate step can be
   scored instead of the final answer. `exact_match` fails on any unanticipated
   formatting. `contains_any` probes may be too permissive. `not_contains_any` fails a
   response that mentions a forbidden term while rejecting it. `json_schema` can pick an
   embedded example rather than the intended answer.
2. **Prompt sensitivity.** Results depend on exact wording, system prompt, and the
   `max_tokens` budget: a truncated response is scored as truncated even if the model was
   on the right track, and a slightly reworded prompt can change behaviour. Probes are
   fixed prompts, so this sensitivity is a property of the measurement, not a bug that
   averaging removes.
3. **Sampling and decoding settings.** `temperature: 0` is not a guarantee of identical
   output across providers, batches, or time. Batching, hardware nondeterminism, mixture-
   of-experts routing, provider-side system prompts, and silent version updates can all
   change responses. A run is a snapshot of the endpoint as configured on that date.
4. **Contamination and overfitting.** The probe corpus and its prompts are public. They
   can appear in training data, and a model or vendor can tune against them. Overfitting
   to a public fixed corpus is possible; private or held-out probes are the mitigation,
   and FailBench does not claim resistance to deliberate tuning.
5. **Sampling bias in the evidence atlas.** Hacker News, arXiv, GitHub, and similar
   sources skew towards English-language, technical, early-adopter audiences. Enterprise
   incidents, non-English reports, and private evaluations are underrepresented. The
   atlas counts what was publicly reported, not what happens in deployment, and contains
   no negative results (no "this worked fine" reports), so it cannot estimate base rates.
6. **Atlas self-report noise and classification judgement.** Reports are unverified
   anecdotes: a reporter may misdiagnose the cause, omit the prompt, or describe a
   configuration problem. Assigning a report to one of ten classes involves judgement,
   and multi-failure reports are coded to the dominant failure. Popularity metrics
   reflect timing and headline wording more than importance.
7. **Uneven class coverage.** Each class has ten probes at v0.1.0, but the behaviours
   differ in difficulty and the severity mixes differ (5 critical versus 43 medium
   probes overall). Class pass rates are not comparable, and a single probe moves a class
   rate by about ten percentage points.
8. **Small samples and no inference.** There are no confidence intervals, no
   significance tests, and no multiplicity correction at v0.1.0. Comparisons between
   models, runs, or dates are descriptive only.
9. **Reproducibility only within a documented environment.** Artifacts record Python
   version, platform, run ID, timestamps, and configuration, and the mock demo is
   deterministic. Real-endpoint results additionally depend on the provider's current
   model version, serving stack, and policy filters, none of which FailBench controls.
10. **Model version drift.** An endpoint name is not a version pin. Vendors update
    models, safety layers, and serving infrastructure; a later run against the "same"
    model name may produce different results.
11. **Narrow surface.** FailBench measures single-turn text chat completions only. It
    does not measure agents over multiple turns, tool-use reliability in a real
    environment, retrieval pipelines, multimodal input, latency, cost, or training-time
    properties. Results should not be generalised to those surfaces.
12. **Judgement in authoring.** Probe prompts, rationales, severity labels, and atlas
    classifications are written by humans. They are reviewable and correctable, but they
    embed choices that the mechanics do not validate.

## 11. Responsible disclosure

The security policy is [`../SECURITY.md`](../SECURITY.md). In brief:

- For a vulnerability in the tool itself, use the repository's private security advisory
  flow rather than a public issue. Provide the version, affected component, a minimal
  reproduction, impact, and whether any secret or personal data was exposed. Do not
  publish exploit details in a public issue.
- For a model-failure finding produced with the probes, reproduce it deterministically
  (model identifier, endpoint type, parameters, transcript, at least two independent
  runs), notify the vendor privately first, and publish the phenomenon and measurement
  after a reasonable window (90 days is the documented default) rather than a working
  payload.
- FailBench will not accept probes whose purpose is to teach harmful capability or evade
  safety systems. Safety-class probes measure over-refusal on harmless prompts only.
- The project is volunteer-maintained with no bug bounty, support contract, or security
  response SLA; [`../SECURITY.md`](../SECURITY.md) states best-effort timelines.

## 12. Reproducing the shipped results

All commands run from the repository root with plain `python`; no virtual environment,
installation, network access, or API key is required for the mock demo. The declared
Python requirement is 3.9 or newer ([`../pyproject.toml`](../pyproject.toml)); the
committed demo artifacts were produced with CPython 3.13.15 on Windows.

```bash
# Validate the probe corpus and evidence atlas, treating warnings as errors.
python -m failbench validate --strict

# Run the deterministic offline demo (about 120 synthetic requests for 100 probes).
python -m failbench run --provider mock --demo --out results/demo

# Regenerate the static report and site from the demo results.
python -m failbench report --results results/demo --out site

# Re-score the recorded responses offline; no network is used. --out keeps the
# committed results/demo/ directory untouched.
python -m failbench replay --results results/demo --out results/replay

# Compare a baseline with a current run; exits non-zero on regressions.
python -m failbench gate \
  --baseline results/demo/results.json \
  --current results/demo/results.json
```

Expected behaviour:

- `validate --strict` prints an `OK` line with the probe and evidence counts and exits
  zero when the corpus is valid. The exact v0.1.0 counts are in Table 1.
- `run --demo` exits zero, writes `results/demo/results.json` and
  `results/demo/raw.jsonl`, and prints a summary. A completed run exits zero even when
  probes fail; probe failures are the measurement.
- `report` writes the self-contained `site/index.html` and the generated Markdown
  report (by default [`RESULTS.md`](RESULTS.md)). The generated page labels mock data as
  such.
- `replay` re-scores the recorded responses from `raw.jsonl` without contacting a model
  and reports any status mismatches against the original results. A mismatch is a
  finding: it means the current corpus or scoring rules no longer reproduce the
  recording.
- `gate` with the demo run as its own baseline prints `GATE PASS` and exits zero; two
  runs that differ in probe status produce a regression report and exit one.

**Determinism expectations.** Re-running the mock demo reproduces the per-probe statuses
and response texts, so the counts in Table 1 are stable for this corpus and provider.
Timestamps and run IDs differ between runs, and a regenerated report embeds a generation
timestamp, so artifacts are not byte-identical across regenerations. For real endpoints,
expect variation from sampling, provider versioning, and serving-stack changes; rerun
before treating a difference as a regression.

Useful companion commands: `python -m failbench list` lists the corpus;
`python -m failbench list --class hallucination --json` emits machine-readable probe
records; `python -m unittest discover -s tests -t . -v` runs the offline unit tests. See
[`QUICKSTART.md`](QUICKSTART.md) for a shorter walkthrough and
[`../README.md`](../README.md) for the project overview.

## 13. Adding probes and evidence

Contributions are governed by [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and the schemas
in [`CONTRACT.md`](CONTRACT.md). The short version:

- **Probes** start from [`templates/probe.template.json`](templates/probe.template.json)
  and live at `probes/<class>/<id>.json`. The probe must be static and self-contained,
  have one defensible pass condition, use one of the eight mechanical scorers, carry a
  title, rationale, severity, parameters, and repeat count, and contain no harmful
  content, PII, or unlicensed long text. IDs follow `<abbr>_<slug>_<2 digits>` and match
  the class prefix.
- **Evidence** starts from
  [`templates/evidence.template.jsonl`](templates/evidence.template.jsonl) and lives in
  `data/evidence/<class>.jsonl`, one JSON object per line. The source must be real and
  reachable, quotes verbatim (or `""`), metrics real integers or omitted, status honest,
  and provenance complete. Evidence is data, not a claim of independent verification.
- **Verify** with `python -m failbench validate --strict` and the unit tests, and run the
  offline demo (`python -m failbench run --provider mock --demo`) to confirm the pipeline
  still works. Reviewers check schema validity, determinism, source reachability, the
  absence of fabricated metrics or quotes, honest status labels, and content safety.
- **Licensing.** Code contributions are MIT. The probe corpus and evidence atlas are
  CC-BY-4.0; quoted excerpts remain the property of their original authors. See
  [`../LICENSE`](../LICENSE) and [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## 14. Versioning and change expectations

This document describes v0.1.0, a pre-1.0 release. Schemas, scoring rules, probe counts,
and counts in Table 1 can change in later releases, and the data artifacts change with
the package version. For changes, see [`../CHANGELOG.md`](../CHANGELOG.md); the release
roadmap is maintained as `ROADMAP.md` in the documentation directory. When comparing
results across time, record the suite version (`suite_version` in `results.json`) and the
corpus commit or release alongside the numbers.
