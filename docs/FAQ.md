# FailBench FAQ

These answers describe FailBench version 0.2.0 as shipped in this repository. For the
measurement definitions behind them, see [`METHODOLOGY.md`](METHODOLOGY.md); for the
normative schemas and scoring semantics, see [`CONTRACT.md`](CONTRACT.md).

## Is FailBench another leaderboard?

No. FailBench reports per-probe pass/fail results and descriptive per-class pass rates
for one endpoint at a time; it does not rank models, compute an aggregate quality score,
or publish a public leaderboard. Its intended use is a fast regression gate ("did this
deployment change break a behaviour that used to work?") plus an evidence atlas of
publicly reported failures. Cross-model or cross-run comparisons are descriptive only and
carry no significance claim at v0.2.0.

## Why deterministic scoring instead of an LLM judge?

Because a measurement instrument should not change without the input changing. A
mechanical rule returns the same verdict for the same recorded response forever, can be
audited by reading the response and the probe file, and costs nothing beyond the model
call being measured. An LLM judge's verdict depends on the judge model, its version, its
prompt, and its decoding parameters, and judges have documented tendencies such as
self-preference, position bias, and verbosity bias. The tradeoff is acknowledged:
deterministic rules cover less, and classes that cannot be checked mechanically are
excluded rather than delegated to a judge.

## Isn't keyword or string scoring too brittle?

It is brittle in known ways, and [`METHODOLOGY.md`](METHODOLOGY.md) section 10 lists them
rather than hiding them. Substring matching misses correct paraphrases and can be gamed
by echoing the expected string; regex can over-match; `numeric` uses the first number in
the response, so an intermediate step can be scored instead of the final answer; and
`exact_match` fails on any unanticipated formatting. Probes are designed so that a
defensibly correct response contains the checked token, structure, or number, but this
design choice means a probe failure is a concrete witness, not proof that the model
"fails the class". Open-ended qualities are out of scope.

## Why is the demo run against a mock provider, and what do the demo numbers mean?

No live model endpoint was available during the build, so the committed demo was produced
by the deterministic, offline `mock` provider to exercise the full pipeline end to end.
The provider synthesizes responses from each probe's own scoring rules and deterministically
mixes pass, fail, and simulated transport-error outcomes, which is why the demo exercises
all three status paths. The committed demo numbers are therefore a pipeline demonstration:
they are not measurements of any model, and they must not be compared with other tools,
leaderboards, or real model runs. To obtain real numbers, run the kit against any
OpenAI-compatible endpoint as shown in [`QUICKSTART.md`](QUICKSTART.md) and regenerate the
report for that run.

## Does FailBench test safety, jailbreaks, or prompt injection?

No. FailBench ships no attack payloads and does not measure jailbreak capability, harmful
content generation, or prompt-injection attacks against third-party systems. The
`safety_consistency` class measures the opposite direction: over-refusal on harmless
prompts and inconsistent refusal boundaries across near-duplicate harmless prompts. The
repository's non-negotiables prohibit harmful or exploit content, and security-oriented
adversarial tooling (garak, PyRIT) is the appropriate category for attack measurement. See
[`TAXONOMY.md`](TAXONOMY.md) section 3 for the deliberate scope exclusions.

## What do "pass", "fail", and "error" mean, and why must every repeat pass?

`pass` means the response met the probe's mechanical condition on every attempt; `fail`
means the condition was not met on at least one attempt; `error` means the attempt could
not be scored because the provider or runtime failed (network error, timeout, malformed
scoring specification), and it is never counted as a model failure. A probe passes only
if all of its repeats pass, because a behaviour that is present on one identical call and
absent on the next is not reliable enough to call a pass. Repeats are used mainly for the
`determinism_calibration` probes, whose subject is stability across identical calls.
Per-attempt history is preserved in `results.json`, and errors remain visible in the
report rather than being folded into failures.

## Can I use FailBench commercially?

Yes, subject to the licenses: the code is MIT and the data (probe corpus and evidence
atlas) is CC-BY-4.0, which requires attribution when you redistribute or adapt the data.
The package declares no third-party runtime dependencies, so there is no dependency
license chain to audit, and external sources quoted in the atlas remain under their
authors' licenses. The software is provided "as is" with no warranty, and the project
offers no commercial support or security-response SLA. Review [`../LICENSE`](../LICENSE)
and [`../SECURITY.md`](../SECURITY.md) for your own compliance assessment; this answer is
not legal advice.

## How do I cite FailBench?

Use the metadata in [`../CITATION.cff`](../CITATION.cff). A suitable prose form is:
"FailBench contributors. FailBench (Version 0.2.0) [Computer software]. 2026." The
citation file intentionally omits a repository URL until the project's public location is
fixed, and no DOI is assigned yet; if you need a stable identifier, archive the version
you used (for example a release tarball or Zenodo-style archive you control) and cite
that alongside the version number.

## How can I contribute probes or evidence?

Read [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and start from the templates:
[`templates/probe.template.json`](templates/probe.template.json) and
[`templates/evidence.template.jsonl`](templates/evidence.template.jsonl). Probes go under
`probes/<class>/<id>.json` and must be static, self-contained, mechanically scored, and
have exactly one defensible pass condition; evidence goes into
`data/evidence/<class>.jsonl` and must have a real reachable URL, verbatim quotes (or
`""`), real metrics or omitted metrics, and an honest status label. Run
`python -m failbench validate --strict` and the unit tests before opening a pull request;
CI is offline and does not call paid endpoints. Probes and evidence are contributed under
CC-BY-4.0 and code under MIT.

## Why ten failure classes? Why not more?

The ten classes passed three filters documented in [`TAXONOMY.md`](TAXONOMY.md) section 2:
each failure is user-visible, each has at least eight independent public reports behind it,
and each can be checked mechanically with one defensible pass condition. Ten classes at
roughly ten probes each keeps the suite small enough to run as a fast regression gate,
while still covering the common observable failure surface of text chat APIs. The
taxonomy is explicitly not exhaustive, and its deliberate exclusions (tone, helpfulness,
multimodal behaviour, training-time issues, attack capability) are listed in
[`TAXONOMY.md`](TAXONOMY.md) section 3. More classes would mean more judgement-laden
criteria that fail the deterministic-measurement filter, not better coverage.

## How is FailBench different from garak, PyRIT, promptfoo, lm-evaluation-harness, and HELM?

They are different instruments, and FailBench is much smaller in scope. The short version:
the security tools scan for vulnerabilities and adversarial weaknesses, the benchmark
frameworks measure capability on academic tasks or holistic scenario suites, and FailBench
is a fixed deterministic failure-probe suite with an evidence atlas and a CI regression
gate. Links below were checked when this FAQ was written (2026-11-24).

| Project | What it is | How FailBench differs |
|---|---|---|
| [garak](https://github.com/NVIDIA/garak) | NVIDIA's LLM vulnerability scanner: security probes, detectors, harnesses, and automatic red teaming. | FailBench is not a scanner and ships no attack payloads or detector models; it is a small fixed judge-free regression suite plus a cited evidence atlas. |
| [PyRIT](https://github.com/microsoft/PyRIT) | Microsoft's Python Risk Identification Tool: an open framework for security professionals and engineers to identify risks in generative AI systems, including automated scans and adaptive multi-turn attacks. | FailBench is not a red-teaming framework: single-turn static probes only, no orchestration, no attack generation, deterministic scoring. |
| [promptfoo](https://github.com/promptfoo/promptfoo) | Open-source CLI and library for evaluating and red-teaming LLM apps, with declarative configs, assertions (including model-graded ones), and CI integration. | FailBench has no app-specific configuration, no model-graded assertions, and no Node/runtime dependencies; it is a fixed corpus in stdlib-only Python. |
| [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | EleutherAI's unified framework for evaluating language models on a large collection of academic benchmarks, with multiple model backends. | FailBench does not measure academic accuracy and does not load models or need GPUs; it probes specific failure behaviours through a chat-completions API. |
| [HELM](https://crfm.stanford.edu/helm/) | Stanford CRFM's Holistic Evaluation of Language Models: broad multi-scenario evaluation with public reports and leaderboards. | FailBench publishes no leaderboard, no broad capability ranking, and no cross-model aggregation; its per-run pass rates are descriptive and endpoint-specific. |

These projects are mature and broader in scope than FailBench; the difference is not a
claim of superiority. A team that needs adversarial security testing should use garak or
PyRIT, a full capability benchmark should use lm-evaluation-harness or HELM, and an
application-specific eval harness should use promptfoo.

## Does FailBench cover non-English models?

Only partially. The `multilingual` class has ten probes covering Arabic, Chinese
(Simplified), French, Hindi (Devanagari), Japanese, and Spanish, including script
handling, code-switching, and translation cases, but this is a small convenience sample,
not a systematic multilingual benchmark. Most probes are English-language, and the
evidence atlas skews towards English-language, technical sources (see
[`ATLAS.md`](ATLAS.md) section 5). Treat non-English behaviour as largely unmeasured and
use a dedicated multilingual benchmark when that is the question.

## Will it work with my fine-tuned model or a local model?

Yes, if the model is served behind an OpenAI-compatible `/chat/completions` endpoint.
Use the `openai` provider with `--base-url`, `--api-key-env`, and `--model`; the key value
is read from the named environment variable and never written to results or logs. Local
servers such as vLLM or Ollama can be used the same way, with a dummy key if the server
ignores authentication. There is no native Hugging Face `transformers` loader: if your
model cannot be exposed through an OpenAI-compatible server, FailBench cannot call it
directly. Some servers silently ignore `temperature`, `max_tokens`, or system messages,
which can change results; confirm the server honours the parameters before trusting
comparisons.

## How long does a run take, and what will it cost?

No fixed figures are claimed. At v0.2.0 a full run makes about 120 model calls: 90
single-repeat probes plus ten three-repeat probes, before any configured retries, plus one
call per retry for retryable provider errors. Cost is the sum over those calls of input
tokens times the endpoint's input price plus completion tokens times its output price;
`max_tokens` bounds each completion but prompt sizes vary by probe. Wall-clock time is
dominated by endpoint latency, rate limits, and the default concurrency of 4; the offline
mock demo needs no network and completes almost instantly. Use your provider's current
price list for an estimate, and expect retries or rate limiting to add calls.

## Can I trust the evidence atlas?

The atlas is a curated set of real, linked public reports, not an independent
verification. Each record must have a reachable source URL, a short neutral summary, and
verbatim quotes only where exact text was verified; popularity metrics (Hacker News
points and comments, and GitHub reactions and comments) are attention signals, not
quality, severity, or prevalence. In v0.2.0 every record has `status: "cited"`, because no live model runs were
available to reproduce the reports; `tested` is reserved for records backed by a real
run reference. Reports are self-reported and can misdiagnose a cause, so treat the atlas
as evidence that someone publicly reported a phenomenon, and check the linked sources.
Corrections are welcome through the contribution process.

## How do I report a bug or a security issue?

For ordinary bugs, open a GitHub issue using the repository's issue template and include
the version, the command or probe involved, and a minimal reproduction. For security
problems in the tool itself, do not open a public issue: use the repository's private
security advisory flow as described in [`../SECURITY.md`](../SECURITY.md), and include the
affected version, component, impact, and a minimal reproduction. Model-failure findings
discovered with the probes should be reproduced deterministically and reported to the
model vendor privately before publication, per the policy in
[`../SECURITY.md`](../SECURITY.md). The project is volunteer-maintained with no bug bounty
and no security-response SLA.

## What is the release status, and are the formats stable?

Version 0.2.0 (2026-11-24) is a pre-1.0 release. While the project is pre-1.0, minor
releases may include changes that are not backward compatible, and the data artifacts
(the probe corpus and evidence atlas) change with the package version. This release
contains no live-model measurements: the committed demo uses the mock provider, and the
evidence atlas is report-level evidence. Pin a version or commit for reproducible
comparisons; [`../CHANGELOG.md`](../CHANGELOG.md) and [`ROADMAP.md`](ROADMAP.md) track
what changed and what is planned.

## What Python versions are supported?

The declared requirement is Python 3.9 or newer ([`../pyproject.toml`](../pyproject.toml)),
and the package uses only the standard library with no third-party runtime dependencies.
The committed demo artifacts were produced with CPython 3.13.15 on Windows, and CI
examples in the documentation use Python 3.13. You do not need to install the package or
create a virtual environment: run `python -m failbench` from the repository root, though
an editable install is optional for tooling.

## Does it need network access or an API key for the demo and the tests?

No. The mock demo, `validate`, `report`, `replay`, the gate, and the unit tests all run
offline and require no API key. Only two paths use the network: the `openai` provider,
which sends probe prompts to the endpoint you configure, and the evidence collectors
under `scripts/evidence/` (which are not needed to use the kit). The `mock` provider does
not contact any model and performs no inference, which is why it can run in CI without
cost or credentials.

## What about data privacy and secrets?

Probe prompts are synthetic and the corpus contains no real user data or PII by design,
and the project ships no telemetry, analytics, or external CDN loads in its static report.
API keys are passed by naming an environment variable (`--api-key-env`); the CLI only ever
handles the variable's name and does not read or print the key value, and the documented
posture is that key values are never written to artifacts or logs. However, `results/**` does contain
prompt text and model responses, so treat produced artifacts as potentially sensitive,
keep non-demo results out of version control, and avoid putting real user data into custom
probes. When you use the `openai` provider, prompts and responses leave your machine for
the endpoint you choose, and that provider's data-handling terms apply; see
[`../SECURITY.md`](../SECURITY.md) for the full posture.
