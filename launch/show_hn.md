# Show HN — preparation notes for the repository owner (not posted)

> **HN compliance — how to use this file**
>
> This file is **preparation notes, not copy-paste text**. HN's current guidelines are explicit: *"Please don't put generated text in HN posts. Write your text yourself — HN is for sharing between humans. For the same reason, please don't automate posting."* The owner must write the final submission text personally, in their own words, using these notes as source material.
>
> - **No automation.** Do not submit or comment programmatically, and do not schedule a bot. The owner posts from their own account.
> - **No generated text pasted into HN.** This applies to the title, body, and first comment below. If the owner cannot honestly say they wrote the submitted text, it is not ready to submit.
> - **Write it by hand.** HN moderator "dang"'s tips thread, linked from the Show HN guidelines as *tips about how to present your work*, states in its 2026-03-28 edit: *"Write your text by hand. Don't use an LLM to generate any of it (not even a tiny bit, including to edit or spruce it up)."* Treat every draft below as notes to rewrite from scratch in your own words — not as text to edit.
> - **Include backstory.** The tips ask for the backstory of how you came to work on the project and what is different about it. The sections below are source material; the owner should add their own genuine motivation and history.
> - **The owner must be present.** Show HN asks for a project the poster worked on personally and is around to discuss; the owner should stay in the thread to answer questions.
> - **The post must be tryable.** HN's Show HN guideline is *"Show HN is for something you've made that other people can play with."* The repository must be public, the demo runnable, and no signup or email barrier should be in the way. This is a post about a runnable artifact, not a blog post, landing page, newsletter, or launch announcement.
> - **No vote or comment solicitation.** Do not ask for upvotes, comments, or stars, and do not ask friends or colleagues to upvote or comment.
> - **Disclose AI assistance if asked** and never claim human-only authorship.
> - Replace every `https://github.com/Qin-z-x/llm-failbench` with the real public repository URL at posting time. Nothing in this file claims the project is already published.

---

## 1. Suggested HN title

Titles must begin with `Show HN: ` and stay under 80 characters (HN's submit form enforces a title limit; verify the current limit on the form before posting). The titles below are descriptive, not promotional: no "first", "best", "only", superlatives, or traction claims.

**Primary (70 characters, including spaces):**

```
Show HN: FailBench - deterministic, judge-free failure probes for LLMs
```

**Alternative 1 (69 characters):**

```
Show HN: FailBench - a judge-free failure-probe kit for LLM endpoints
```

**Alternative 2 (69 characters):**

```
Show HN: FailBench - mechanical LLM failure probes with cited sources
```

Character counts were checked against the exact strings above. Titles deliberately avoid: version numbers (HN's guidance says point-release/version posts generally are not substantive enough for Show HN), uppercase or exclamation marks, and any claim of popularity. If the owner edits a title, recount it.

**Show HN requires something people can try.** A repository alone is only acceptable if the thing runs without barriers: the offline demo should work with no signup, no API key, and no install beyond Python. State the try-it path in the body, and put the offline demo command early. If the only way to see anything is to read the README, HN's guidance says it is too early for a Show HN.

---

## 2. Posting body — draft for the "text" field

Use this for a text post whose subject is the runnable repository, not a launch announcement: the try-it command leads the body so a reader can already run something. If submitting `https://github.com/Qin-z-x/llm-failbench` as a link post instead, keep the same title and post the body below as the **first comment**, with the "Honest status" paragraph in the first few lines.

Rewrite it in your own words before submitting; per HN's current guidelines the final text must be written by the person posting. These are preparation notes, not text to paste.

```
FailBench: deterministic, judge-free failure probes for LLMs

Try it (offline demo: no API key, no install, stdlib only):

python -m failbench run --provider mock --demo --out results/demo

Against any OpenAI-compatible /chat/completions endpoint:

python -m failbench run --provider openai --base-url YOUR_URL --api-key-env YOUR_KEY_VAR --model YOUR_MODEL --out results/run1

A full pass typically takes a minute or two against a hosted endpoint; the offline mock demo is instant.

What it is

FailBench is an open benchmark and evidence atlas for LLM failure modes. The benchmark side is a corpus of 100 static probes across 10 failure classes (10 probes each; severity mix: 5 critical, 34 high, 43 medium, 18 low): hallucination, instruction following, context retrieval, reasoning consistency, sycophancy, structured output, multilingual, safety consistency, agentic reliability, and determinism/calibration. The atlas side catalogs 110 publicly reported failure modes — 54 Hacker News threads, 46 arXiv papers and 10 GitHub issues, with popularity counts as of 2026-11-24 — and gives every record a real public source URL.

Why judge-free and deterministic

Most benchmark numbers depend on an LLM judge or a model-applied rubric, so the score can move when the judge's prompt or version changes, and it is expensive to reproduce. Every FailBench probe has one mechanical pass condition instead: an exact substring or regex, a JSON-schema validation, a numeric comparison within tolerance, or a combination of those. Static prompt, temperature 0 by default, one defensible correct answer. A pass or fail can be audited by reading the rule and the stored response, and a run can be re-scored offline from its raw responses. There are no LLM judges anywhere in the scoring path.

Why evidence-backed

Each atlas record links to a public source (an HN thread, arXiv paper, GitHub issue, or blog post) and is marked "cited" unless a real model run produced it. Quotes are short and verbatim or left empty when the exact text is unavailable; the dataset rules forbid invented citations, metrics, and user quotes. Probes and atlas records share the same ten-class vocabulary, and the probe schema supports evidence ids, but in v0.1.0 the link between them is at class level, not per-probe citation.

One probe, described by its shape

Every probe has the same shape: one static prompt and one mechanical scorer. Consider a long-context retrieval probe. The prompt places a unique synthetic code near the middle of a long block of synthetic filler text, then asks for that code. The scorer is a case-sensitive substring check: the response must contain the code exactly. There is no rubric and no judge; when it fails, the scorer reports the concrete mismatch. Other classes follow the same pattern: structured-output probes validate JSON against a schema, numeric probes compare the first number in the response against an expected value within tolerance, and instruction-following probes check that a forbidden word or format constraint is respected. The value is that a passing or failing check is decidable by anyone reading the rule, and the full response is stored for inspection.

Two more commands are useful after a run: build the static dashboard, and compare two runs for regressions:

python -m failbench report --results results/run1 --out site
python -m failbench gate --baseline OLD/results.json --current NEW/results.json

Honest status of the committed results

The committed demo run covers all 100 probes: 64 pass, 34 fail, 2 error. It was produced by the deterministic mock provider, not a live model, and is not a measurement of any real model. No live model endpoint was available during the build, so this release contains no real-model benchmark numbers. Run the kit against your own endpoint to get real numbers. Do not read the demo pass rates as model results; they exist to exercise the pipeline, the report, and the CI gate.

Contributions and corrections

The evidence atlas is the part most likely to be wrong or incomplete, so corrections are welcome: dead links, misattributed sources, bad summaries, missing failure modes, probes with ambiguous pass conditions. Issues and pull requests: https://github.com/Qin-z-x/llm-failbench. Code is MIT; evidence and probe data are CC-BY-4.0.
```

Length note for the owner: HN allows long text, but a shorter post usually reads better. If you trim, keep the "Honest status" paragraph and the run commands; drop sentences, not honesty.

---

## 3. First top-level comment — draft

Post this (rewritten in your own voice) as the author's first comment, or use it to seed the discussion. Keep the tone plain and non-defensive.

```
Author here. Some context I'd rather state up front than have people dig for.

This is v0.1.0, a pre-release. The committed demo results come from a deterministic mock provider, not a live model. No model endpoint was available while I was building this, so there are no real-model numbers in the release. Run it on your own endpoint if you want a number that means anything.

The mechanical scoring is a deliberate trade. No judges means the result is auditable, cheap, and stable, but it also means a probe can be passed by emitting the expected string. A benchmark you can inspect is a benchmark you can game. I've treated it as a regression gate for a single endpoint over time, not as a leaderboard, and the results schema stores raw responses so failures can be re-scored and replayed offline.

The atlas is the half I care most about. Failure modes like "lost in the middle" or sycophantic stance flips circulate as anecdotes; each atlas record now carries a real public source link and a status. The schema is documented, and corrections to evidence records are genuinely wanted.

Useful feedback for me, in rough order: probe or scorer designs that are brittle or ambiguous, evidence records with wrong or dead sources, and whether the CI regression-gate workflow fits how you would actually use this.

I used AI assistance while building this, and I am not claiming otherwise.
```

The final line about AI assistance is optional and can be moved; it must not be dropped if the owner would otherwise imply the work was fully hand-made. Do not delete it and add a human-only authorship claim.

---

## 4. Tough questions — honest answers

Answer these factually and without defensiveness. If a commenter makes a correct criticism, say so and fix or file it.

**Q: Is this just known failure modes?**
Mostly, yes. The atlas deliberately collects publicly reported failure modes; nothing here claims to discover new classes of model failure. The contribution being attempted is operational: turning cited anecdotes into deterministic, re-runnable checks with a regression gate. If you already test these modes and don't need a citable record or a CI gate, the kit may not add much for you, and that is a fair reason not to use it. Do not counter with a novelty claim; there is no supported "first", "only", or "best" claim to make.

**Q: Are the probes keyword-brittle / gameable?**
Yes, and that is an accepted trade-off, not a hidden flaw. Mechanical scoring can be satisfied by a model that emits the expected string without understanding the task, and because the corpus is public it can be overfitted to. Treat a score as a regression signal for one endpoint over time, not a capability ranking or leaderboard. Mitigations in the design: failures report the exact mismatch, raw responses are stored for audit and offline replay, multiple scorer types are used, and adversarial probe contributions are wanted. Do not claim that a high pass rate means a model is robust.

**Q: Where are the real model results?**
There are none in this release. The committed demo results were produced by the deterministic mock provider; no live model endpoint was available during the build, and the docs and dashboard label the demo result as such. Users must run the kit against their own endpoint for real numbers. Never present demo pass rates as model measurements, and do not imply that real-model results are coming to a leaderboard.

**Q: Is this AI-generated content?**
Yes, in part: the project was built with AI assistance, and this file is AI-assisted preparation notes. The human repository owner is accountable for what is published. HN has become unusually strict here: the general guidelines say *"Please don't put generated text in HN posts. Write your text yourself,"* and HN moderator "dang"'s tips thread (2026-03-28 edit) goes further: *"Write your text by hand. Don't use an LLM to generate any of it (not even a tiny bit, including to edit or spruce it up)."* That is exactly why the owner must write the final HN submission and any HN comments personally, from scratch, using this file only as background notes — and must not paste or lightly edit any draft here, and must not use automation to submit or comment. If asked, disclose AI assistance plainly and never claim human-only authorship. The project's own rules require human verification of every citation and quote, so generated text is not treated as evidence.

**Q: Why should anyone trust the evidence records?**
Because each is checkable, not because the project asserts they are right. Records are constrained: a real, reachable source URL, a short verbatim quote or an empty quote if unverified, a status of "cited" unless a real run produced it, and no invented metrics. They can still be wrong or misattributed; the fix is a correction issue or PR, and reports of dead links, wrong titles, and bad summaries are wanted. Do not oversell data quality as editorial review by named humans.

---

## 5. Posting-time guidance (general guidance only — verify current practice)

There is no verified data behind any specific "best time" claim, including the usual advice. Treat the following as folklore-level guidance, and check current HN community discussions before posting.

- Weekdays are commonly suggested over weekends; many people avoid posting very late US hours.
- Two windows are often repeated in HN discussions: roughly 13:00-16:00 UTC (US morning) and roughly 18:00-21:00 UTC (US afternoon). These are conventions, not measured facts; verify against current discussion instead of trusting this file.
- Post when you can stay in the thread for a few hours. Show HN asks for a project you are "around to discuss", and answers are expected in the comments.
- Do not ask for votes or comments anywhere, do not coordinate upvotes, and do not tell friends to support the post. HN guidelines prohibit soliciting upvotes, comments, or submissions.
- Do not delete and repost if a submission does not gain traction; HN guidelines explicitly discourage delete-and-repost.

---

## 6. Pre-flight checklist before posting

- [ ] `https://github.com/Qin-z-x/llm-failbench` is substituted with the real public repository URL, and the repository is publicly reachable.
- [ ] On a clean machine with plain Python (3.9+, no extra packages), the offline demo runs: `python -m failbench run --provider mock --demo --out results/demo`.
- [ ] Committed demo results are labeled as mock-provider output, and `docs/RESULTS.md` / README / dashboard carry the honest-status paragraph.
- [ ] The data and code licences are stated (code MIT, data CC-BY-4.0).
- [ ] The numbers match the frozen v0.1.0 report table: 100 probes (10 per class; severity 5 critical / 34 high / 43 medium / 18 low), 110 cited evidence records (54 HN / 46 arXiv / 10 GitHub issues), and the committed mock demo run (100 probes: 64 pass / 34 fail / 2 error). Re-check `README.md` before posting if the repo changed.
- [ ] The title, body, and first comment are written by the owner personally, not pasted from this file, in line with HN's current guidance against generated text and automated posting.
- [ ] Every factual claim in the post is supported by the repository: no invented users, stars, testimonials, benchmark numbers, or adoption claims; no "first / only / best" language.
- [ ] No request for upvotes, comments, or stars appears anywhere in the post or in any channel around it.
- [ ] The owner has re-read the current rules (see source record below) and will be available in the thread.
- [ ] Nothing has been auto-posted; a human publishes from their own account.

---

## 7. Sources fetched for this draft (verification record)

Both pages were fetched **2026-11-24** from the build machine. HTTP responses were read with a direct HTTPS request (PowerShell `Invoke-WebRequest`, `User-Agent: Mozilla/5.0`). Note honestly: the session's `web_fetch` tool could not reach `news.ycombinator.com` — repeated attempts returned `TypeError: fetch failed` — so the page content was verified with the alternative HTTPS request from the same machine, which returned HTTP 200. The owner should re-open both pages before posting, since HN rules can change.

| URL | Observed result | Notes |
|---|---|---|
| https://news.ycombinator.com/showhn.html | HTTP 200, 2,682 bytes | Show HN guidelines, read 2026-11-24 |
| https://news.ycombinator.com/newsguidelines.html | HTTP 200, 5,864 bytes | HN general guidelines, read 2026-11-24 |
| https://news.ycombinator.com/item?id=22336638 | HTTP 200, 7,067 bytes | HN moderator tips thread linked from the Show HN guidelines; read 2026-11-24. Its 2026-03-28 edit says: *"Write your text by hand. Don't use an LLM to generate any of it (not even a tiny bit, including to edit or spruce it up)."* |

Verbatim excerpts observed on those pages on that date (short quotes, for the owner's reference; re-check before quoting publicly):

- Show HN: *"Show HN is for something you've made that other people can play with."*
- Show HN: *"If your work isn't ready for users to try out, please don't do a Show HN."*
- Show HN: *"Please don't ask friends to upvote or comment."*
- Guidelines: *"Please don't put generated text in HN posts. Write your text yourself — HN is for sharing between humans. For the same reason, please don't automate posting."*
- Guidelines: *"Don't solicit upvotes, comments, or submissions."*
- Guidelines: *"Please don't delete and repost."*
