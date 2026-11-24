# X / Twitter thread — draft for the repository owner

Drafts only — owner posts manually from their own account.

- 8 tweets below, each within the 280-character limit. Character counts are drafting annotations, not part of the tweet text; they are exact for the text as written (including line breaks, counting `https://github.com/Qin-z-x/llm-failbench` as 12 characters).
- `https://github.com/Qin-z-x/llm-failbench` must be replaced with the real public repository URL at posting time. X wraps links to 23 characters, so a substituted URL shortens the effective count rather than growing it; tweet 8 stays under 280 even if the URL is counted literally.
- The thread describes the project as v0.2.0 pre-release. If the repository is not public yet, do not post; there is nothing to try.
- Do not claim human-only authorship. The project was built with AI assistance, and tweet 1 says so plainly; disclose it again if asked. Do not imply that committed demo results are real-model measurements.
- No engagement bait appears below: no requests to like, retweet, follow, star, or vote. Do not add any before posting.

---

## Tweet 1/8 — hook

```
Most LLM benchmarks hand you a score and nothing else. I wanted pass/fail rules I could read, re-run, and diff over time. So we built FailBench: deterministic failure probes for LLMs, no judge models, every atlas claim sourced. v0.2.0, pre-release. Built with AI assistance.
```

*Character count: 274 / 280*

---

## Tweet 2/8 — the problem

```
Two problems with failure-mode talk today:
1) Judge-based benchmarks tend to be slow, opaque, expensive, hard to reproduce.
2) Failure claims travel without sources.
Neither is auditable.
```

*Character count: 187 / 280*

---

## Tweet 3/8 — what we built

```
FailBench is an open benchmark plus an evidence atlas: 100 deterministic probes across 10 failure classes, and 110 cited public sources. Probes are static, scored by substring / regex / JSON-schema / numeric checks, no LLM judge. Code MIT, data CC-BY-4.0.
```

*Character count: 255 / 280*

---

## Tweet 4/8 — offline demo command

```
Try it offline, no install, no API key, stdlib only:
python -m failbench run --provider mock --demo --out results/demo
Deterministic mock only: 100 probes, 64 pass, 34 fail, 2 error. Not measurements of a real model; no live endpoint existed at build.
```

*Character count: 251 / 280*

---

## Tweet 5/8 — running against a real endpoint

```
Against your own model:
python -m failbench run --provider openai --base-url YOUR_URL --api-key-env YOUR_KEY_VAR --model YOUR_MODEL --out results/run1
Any OpenAI-compatible /chat/completions endpoint works. The numbers are yours to generate.
```

*Character count: 241 / 280*

---

## Tweet 6/8 — evidence atlas

```
The atlas is the other half: each publicly reported failure mode is one JSONL record with a real source URL, a summary, and a status. Status is "cited" unless a real run produced it. An evidence record has to be checkable, so a dead link is a bug.
```

*Character count: 247 / 280*

---

## Tweet 7/8 — CI regression gate

```
The part I care about most: a regression gate. Compare two runs and fail CI when a probe that used to pass starts failing:
python -m failbench gate --baseline BASE/results.json --current CURRENT/results.json
Mechanical, no judge, useful across model or prompt changes.
```

*Character count: 268 / 280*

---

## Tweet 8/8 — call for evidence and probe contributions

```
If you know a failure mode with a good public source, or want to propose a probe with one unambiguous pass condition, the issue and PR templates are open. Corrections to existing evidence records are especially welcome. https://github.com/Qin-z-x/llm-failbench
```

*Character count: 232 / 280 as written (12-char placeholder); lower once `https://github.com/Qin-z-x/llm-failbench` is substituted and X wraps the link.*

---

## Before posting — checklist

- [ ] `https://github.com/Qin-z-x/llm-failbench` is substituted with the real public repository URL (substitute it in tweet 8, and in tweets 4-5 only if you choose to add it there — do not add a link that does not work).
- [ ] Every command in tweets 4, 5, and 7 matches the current CLI in the repository at posting time.
- [ ] The committed demo results are still labeled as mock-provider output; no tweet implies they measure a real model.
- [ ] No request to like, retweet, follow, star, or vote has been added.
- [ ] The owner is available to answer replies for a few hours after posting.
- [ ] AI assistance will be disclosed if asked; no human-only authorship claim appears in the thread or replies.
- [ ] The account posting is the owner's own account; nothing is scheduled or automated.
