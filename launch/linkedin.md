<!--
DRAFT (not posted). Venue: LinkedIn. Before posting: repo must be public, {{REPO_URL}} substituted,
and docs/DISTRIBUTION.md §11 platform rules re-read on the day of posting. Word count: 292 (body
below, including the hashtag line and command lines, excluding this comment). Counted 2026-11-24.
-->

Most LLM evaluations end with a model grading another model. That works, but judges are expensive, sensitive to prompt wording, and hard to reproduce: change the judge or the rubric and the score moves.

FailBench takes a different route. It is an open-source failure probe kit for LLMs: 100 deterministic, judge-free probes across ten failure classes, from hallucination to agentic reliability.

Each probe is a static record with one fixed prompt and one mechanical pass condition: a required substring, an exact match, a regex, a JSON-schema subset, a numeric tolerance, or an all-of combination. Same response, same verdict, every time: no judge model, no grading API spend, no hidden rubric. Every failure states the concrete mismatch (expected vs. found), and the 110-record evidence atlas links each failure mode to a public source.

For example, a context-retrieval probe hides a unique code mid-context and passes only if the reply contains it.

To try it (Python 3.9+, stdlib only):

python -m failbench run --provider mock --demo --out results/demo
python -m failbench run --provider openai --base-url <YOUR_BASE_URL> --api-key-env FAILBENCH_API_KEY --model <MODEL> --out results/run1

The offline mock demo runs in seconds with no network; point the runner at any OpenAI-compatible endpoint for your own model's numbers, and use the CI gate to compare runs against a baseline. A full pass typically takes a minute or two against a hosted endpoint, depending on latency.

Status: v0.1.0 pre-release. The committed demo run covers all 100 probes — 64 pass, 34 fail, 2 error — from the deterministic mock provider, not measurements of any real model; no live model endpoint was available during the build. Run it on your own endpoint for real numbers.

Repository: {{REPO_URL}}

Feedback on probe design, scoring and missing evidence is welcome via issues/PRs.

#OpenSource #LLM #MachineLearning
