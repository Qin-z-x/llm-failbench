# Hugging Face community discussion draft

**Status:** draft only, not posted. Publish only after the repository is public, `https://github.com/Qin-z-x/llm-failbench` is
substituted, and the rules below are re-read on the day of posting (see `docs/DISTRIBUTION.md`).

## Suggested venue

| choice | venue | URL | why |
|---|---|---|---|
| Primary | Hugging Face Forums, Show and Tell category (id 65) | https://discuss.huggingface.co/c/show-and-tell/65 | Official category description: "a dedicated space for sharing and discussing your exciting projects. Showcase your Spaces, new Models, Datasets, etc., gain feedback and connect with peers." (fetched 2026-11-24) |
| Alternative | Hugging Face Forums, Research category (id 7) | https://discuss.huggingface.co/c/research/7 | Category description: "Use this category for any research question or to coordinate on a project with other users." Use this only if the post is framed as an evaluation-methodology discussion, not a project announcement. |
| Later | Hub repository Discussions / Community tab | https://huggingface.co/docs/hub/repositories-pull-requests-discussions | Repo-level pull requests and discussions for model, dataset, and Space repos. Use after an HF-hosted artifact exists, to collect probe or dataset contributions. Not a substitute for the forum announcement. |
| Not suitable | Hub category (id 23) | https://discuss.huggingface.co/c/hub/23 | Category is for Hub questions (models, datasets, `huggingface_hub`), not project announcements. |

Post once, in one category. Do not cross-post the same body to several categories; the forum
guidelines ask users to "improve the discussion" and not to "post spam", and
`docs/DISTRIBUTION.md` forbids same-day cross-posting.

## Title options

1. `FailBench: an open, judge-free failure probe kit for LLMs (pre-release feedback wanted)`
2. `Deterministic, judge-free LLM failure probes: looking for feedback on FailBench v0.1.0`

## Category

Show and Tell

## Post body

Hi all,

I am sharing FailBench v0.1.0, a pre-release open-source project: an evidence-backed, judge-free failure probe kit for LLMs. The goal is to test failure modes with written-down mechanical rules instead of a second model's judgment, and to source every failure claim.

Why bother: LLM-as-judge evaluations are useful, but they add cost and variance, and a rubric change can move scores without the model changing. FailBench probes are static JSON records. Each has one fixed prompt and one mechanical pass condition (a required substring, exact match, regex, JSON-schema subset, numeric tolerance, or an all-of combination), so the same response always gets the same verdict. Every failure reports the concrete mismatch, expected versus found, and the 110-record evidence atlas links each failure mode to a public source (54 Hacker News threads, 46 arXiv papers, 10 GitHub issues; popularity counts are 2026-11-24 snapshots).

The kit ships 100 deterministic probes across ten failure classes — 10 per class, with a severity mix of 5 critical, 34 high, 43 medium and 18 low: hallucination, instruction following, context retrieval, reasoning consistency, sycophancy, structured output, multilingual behaviour, safety consistency, agentic reliability, and determinism/calibration. It includes a runner for any OpenAI-compatible `/chat/completions` endpoint, an offline deterministic mock demo that runs in seconds with no network, replayable raw logs, a static dashboard, and a CI regression gate. A full pass against a hosted endpoint typically takes a minute or two. Scoring is stdlib-only Python, with no LLM judge and no third-party dependencies; code is MIT and data is CC-BY-4.0.

Honest status: v0.1.0 is a pre-release. The committed demo run covers all 100 probes: 64 pass, 34 fail, 2 error, all from the deterministic mock provider. These are not measurements of any real model, and no live model endpoint was available during the build; users have to run the kit on their own endpoint for real numbers. There is no public leaderboard yet, the probe corpus is small and growing, and evidence collection has so far been done by one team, so independent verification and corrections are especially useful.

If you have an HF-hosted model behind an OpenAI-compatible endpoint, I would like to see what the probes report for it, including the failures. Corrections to scoring rules, evidence links, or probe prompts are welcome, and so are new probes with a defensible pass condition. Please share run configs when you report results so others can reproduce them.

Repository: https://github.com/Qin-z-x/llm-failbench

Thanks for reading, and I will answer questions in the thread.

## Venue and policy notes (fetched 2026-11-24)

- **Hugging Face Forums**: https://discuss.huggingface.co/ (HTTP 200). Community forum, Discourse
  hosted; category list fetched from https://discuss.huggingface.co/categories.json (HTTP 200).
- **Hugging Face Forums Guidelines**: https://discuss.huggingface.co/faq (HTTP 200). Civility and
  "improve the discussion" norms; "Don't post spam or otherwise vandalize the forum." Read in a
  browser at post time.
- **Hugging Face Content Policy**: https://huggingface.co/content-policy (HTTP 200; effective
  2025-04-10). Section 5, "Platform Abuse, Security Violations and Spam", includes "Spam (e.g.,
  advertising products/services, excessive bulk activity, or disrupting user experience)." The
  post must therefore read as project sharing plus a request for technical feedback, not as product
  advertising; post once, no bulk activity, and do not solicit votes or endorsement.
- **Hugging Face Code of Conduct**: https://huggingface.co/code-of-conduct (HTTP 200; Contributor
  Covenant, effective 2025-06-10). Applies to the discussion and to replies.
- **Hub discussions documentation**: https://huggingface.co/docs/hub/repositories-pull-requests-discussions
  (HTTP 200). Explains the Community tab and repo discussions for model, dataset, and Space repos.
- **Forum About page**: https://discuss.huggingface.co/about (HTTP 200). Lists admins and moderators.

### Disclosure requirements

As fetched on 2026-11-24, the Content Policy, Code of Conduct, and forum Guidelines do not state an
explicit AI-generated-content disclosure requirement for a forum post. This draft still discloses
AI assistance, to comply with the project's own authorship policy (`docs/DISTRIBUTION.md` §10):
the project and parts of this text were developed with AI agents under human direction and review.
Do not claim human-only authorship, HF endorsement, or maintainer approval. If a moderator asks how
the project was built, answer plainly and link this policy.

### Verification method and caveat

The session's `web_fetch` tool returned transport errors for Hugging Face hosts while remaining
able to reach other sites, so these URLs were verified with direct HTTP requests from this machine
on 2026-11-24; each returned HTTP 200 as noted. Policy pages change; re-check the linked pages on
the day of posting rather than trusting this table.
