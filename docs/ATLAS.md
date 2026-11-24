# FailBench Failure Atlas (v1)

An evidence-backed map of publicly reported LLM failure modes. This document
is the narrative layer over the machine-readable evidence in
`data/evidence/*.jsonl`; the classes themselves are defined in
[`TAXONOMY.md`](./TAXONOMY.md) and the remediation advice is in
[`MITIGATIONS.md`](./MITIGATIONS.md).

**Honest status note — read this first.** This release contains **no live model
measurements**. No model endpoint was available during the build; the shipped
demo run uses the deterministic `mock` provider and is labelled as such in
[`RESULTS.md`](./RESULTS.md). Everything in this atlas is *report-level
evidence*: public descriptions of failures, with URLs and popularity signals.
The evidence counts below are **not a prevalence estimate** and must not be
read as "X% of requests fail". They are an inventory of what people publicly
reported, filtered through the queries and inclusion rules in §1–§2.

## 1. What this atlas is, and is not

**It is:** a curated table of real, linked public reports of failures in ten
classes, each with a popularity signal where one was available, a
classification rationale, and — where the source permitted a short verbatim
excerpt — a quote. It is designed to answer: *does anyone outside a lab
actually hit this? is it discussed? what does it look like when it happens?*

**It is not:**

- a prevalence study, a model ranking, or a benchmark leaderboard;
- a claim that the ten classes are exhaustive (see `TAXONOMY.md` §3 for the
  deliberate exclusions);
- an assurance that any specific report is reproducible or that the reporter's
  diagnosis is correct — we classify reports as reports;
- a substitute for running the probe kit against a real endpoint. When the
  atlas says "users report this", the matching question is "does *my* endpoint
  fail the deterministic probe?", which only a run can answer.

## 2. Evidence inclusion criteria

A record enters `data/evidence/<class>.jsonl` only when all of the following
hold:

1. **Real public source with a reachable URL** — a Hacker News item, a GitHub
   issue or repository thread, an arXiv abstract page, a public Reddit/forum
   thread, a vendor document, or a public blog post. Private data, leaked
   material, and paywalled text are excluded.
2. **A concrete, user-visible failure** in one of the ten classes (or vendor
   documentation that defines the expected behaviour the failure violates).
   Generic model announcements, leaderboard posts, and pricing complaints are
   not evidence.
3. **Attributable to model or system behaviour** — not to a UI bug, an
   unrelated outage, or user error, except where the report explicitly
   documents the interaction that produced the failure.
4. **Verbatim quote discipline** — the optional `quote` field is copied exactly
   from text the collector actually received (≤200 characters), or is `""`
   when exact text could not be verified. `summary` is the collector's own
   words (≤400 characters) and is never presented as a quote.
5. **One record per distinct source** — cross-posted duplicates with a
   different URL are not merged; identical URLs are not duplicated.
6. **Status honesty** — every record in this release is `status: "cited"`.
   `"tested"` would require a live run reference in `notes` and is never used
   here; `"refuted"` would require a cited source that contradicts the claim.

Popularity metrics are optional. A missing metric is omitted, never guessed.
`published_date` is ISO `YYYY-MM-DD` when the source exposed it, otherwise
`null`.

## 3. Popularity: the attention score

Public discussion is measured with the engagement metrics the sources expose.
The **attention score** used in this document is:

```
attention = hn_points + hn_comments + github_reactions + github_comments
          + reddit_upvotes + reddit_comments
```

A missing metric contributes 0 (it is not imputed). Two metric keys are
deliberately excluded from the score:

- `citations` — scholarly attention, a different population and a much larger
  scale; mixing it in would let a single highly cited paper dominate a class.
- `stars` — repository-level popularity, which measures a tool or project, not
  attention to a particular failure report.

When present, `citations` and `stars` are reported separately in the per-class
data notes. The attention score is a measure of *public discussion*, not of
failure frequency, severity, or number of affected users. All engagement
numbers in this release are **snapshots taken on 2026-11-24** (the records'
`collected_at` date); HN points and comments drift after that date.

## 4. Collection method (what produced the data)

- **Hacker News stories** via the public HN Algolia search API
  (`scripts/evidence/collect_hn.py`), with per-class query phrases; stories
  below 2 points were dropped; points and comment counts recorded from the API
  response at collection time.
- **arXiv metadata** via the public arXiv export API
  (`scripts/evidence/collect_arxiv.py`), relevance-sorted; title, authors/date,
  abstract page URL, and a short verbatim excerpt of the abstract for `quote`.
- **GitHub issues** where a public issue reports the failure in a deployed or
  shipped system; the record keeps the issue URL and its available
  reaction/comment counts. No forum, Reddit, vendor-blog or documentation
  records were included in this release.
- **Release composition:** 110 records - 54 Hacker News stories, 46 arXiv
  papers, 10 GitHub issues. Every record has a reachable source URL, a
  `collected_at` of 2026-11-24, and publication dates spanning 2021-09-08 to
  2026-11-04.
- Raw API dumps are kept as build provenance (scratch, not committed); each
  evidence record carries `collected_by` and `collected_at`, so any number in
  this atlas can be traced back to the collector that produced it.
- Popularity numbers are a snapshot. HN points and comments change after
  collection; the atlas reports what was recorded, at the recorded time.

## 5. Limitations

- **Selection bias.** Hacker News, arXiv and GitHub skew English-language,
  technical, and early-adopter; enterprise incidents, internal evaluations, and
  non-English user reports are systematically underrepresented. The atlas is a
  view of public discourse, not of the world.
- **Self-report noise.** Reports are unverified anecdotes. A report may
  misdiagnose the cause, omit the prompt, or describe a configuration problem.
  We do not reproduce reports in this release (no live endpoints), so a record
  is evidence that *someone reported this*, not evidence that the model
  deterministically does it.
- **Counts are not prevalence.** A class with many records may simply be more
  discussable, older, or easier to title. Do not rank harm by record count.
- **Popularity bias.** Discussion attention correlates with novelty, timing,
  and headline wording; older threads accumulate points. A quiet but real
  failure mode will look small here.
- **Coding judgment.** Each record is assigned to one class using the
  definitions in `TAXONOMY.md`; multi-failure threads are coded to the dominant
  failure. Classification is visible per record and correctable by PR.
- **Provenance gap.** Where a field could not be verified (`quote`,
  `published_date`, metrics) the record says so with `""`/`null` rather than a
  guess. That is a known and intended gap.
- **No negative results.** The atlas counts reported failures; it does not
  contain reports of "this worked fine", so it cannot estimate base rates.

## 6. How the per-class sections are computed

Each class section below is computed from the working tree at the time of
writing (see the verification table at the end of this file):

- **Evidence** = number of records whose `class` is the class, loaded from
  `data/evidence/*.jsonl`.
- **Attention** = the §3 formula over those records. The metric breakdown
  (which sources contributed) is stated so the sum can be re-derived.
- **Themes** = a judgment-based grouping of the report titles/summaries;
  every bullet lists the evidence IDs that support it, and links to the
  source. Quotes are verbatim excerpts from `quote` fields only (≤200
  characters), with the evidence ID and URL.
- **Probe coverage** = number of JSON files under `probes/<class>/`, with
  example probe IDs, their severity, and the mechanical scoring type used.
  Probe counts are computed from the probe files, not from this document.
- **What current tooling measures** = a literature/tool survey; every URL in
  the coverage table (`TAXONOMY.md` §7) was fetched and HTTP-checked in this
  session (see the verification tables).

## 7. What would change our mind

The atlas is falsifiable in specific, cheap ways. We commit to changing the
numbers or the ranking when any of these happen:

1. **Link rot / misclassification audit.** If a share of a class's sources fail
   a re-check or turn out to be duplicates/miscoded, the class's evidence count
   and attention fall, and the ranking is recomputed. (W9's claims audit and
   W5's link checker perform the first such pass; see `docs/reviews/`.)
2. **A public deterministic tool closes the gap.** If a maintained public
   tool or benchmark ships a deterministic, probe-level check for a class
   (not an aggregate accuracy score, not an LLM-judged rubric), the class's
   "solvedness" rating rises and the "gap FailBench probes" statement is
   revised. Coverage ratings are judgments about public tooling, and they are
   revisable on evidence.
3. **Live probe results (future releases).** When the kit is run on real
   endpoints with a meaningful sample, a class that passes at ~100% across
   several frontier models would be relabelled as "real phenomenon, currently
   mostly solved in sampled models" rather than demoted to a hypothesis. This
   release contains no such runs; that test is open.
4. **Ambiguous probes.** If a probe in a class turns out to have more than one
   defensible correct answer, that probe is a bug: it is removed before the
   class can claim measurement. The deterministic pass condition must be
   unique.
5. **Counter-evidence.** A cited source that contradicts a record makes the
   record `refuted`; a public replication failure of a claimed phenomenon is
   recorded in `notes`/`status` and the count recomputed.
6. **Different attention weighting.** Recomputing attention with an alternative
   formula (e.g. including citations, or normalising by source age) may reorder
   the ranking. The coverage table in §9 states its rubric explicitly so the
   ranking can be challenged on its assumptions rather than its arithmetic.

## 8. Class-by-class atlas

Each section is computed from the evidence and probe files at the time of
writing (see the appendix for exact commands and file state). Structure:
what users report (themed bullets with evidence IDs linked to their sources),
an evidence table, 2-3 verbatim quotes from `quote` fields, what the data
shows, what current tooling measures, the gap FailBench probes, and the probe
coverage shipped for the class. The "themes" grouping is editorial; the
counts and sums are mechanical.


### 8.1 Hallucination (`hallucination`)

**What users report.**

- **Fabricated citations reach the archival record**: a detection firm reports 100 new hallucinations in accepted NeurIPS 2025 papers ([ev_hal_0001](https://news.ycombinator.com/item?id=46720395)); a separate audit of accepted ICLR, ICML, NeurIPS and USENIX Security papers finds hallucinated citations in the record, including award-winning papers ([ev_hal_0009](https://arxiv.org/abs/2607.00738)); and a study across 9 models and 108,000 generated references traces citation fabrication to field-specific neurons ([ev_hal_0010](https://arxiv.org/abs/2604.18880)).
- **The stakes are operational, not academic**: a military close call is linked to a hallucinated intelligence report ([ev_hal_0002](https://news.ycombinator.com/item?id=49757520)); a coding-agent bug report describes hallucinated assumptions about project files after a model upgrade ([ev_hal_0011](https://github.com/anthropics/claude-code/issues/50235)); and a search product's users report fabricated facts and a paraphrase presented as a direct quotation ([ev_hal_0012](https://github.com/kagisearch/kite-public/issues/97)).
- **The debate is whether it can be removed at all**: an essay argues code hallucinations are the *least* dangerous because execution catches them, so harder-to-verify fabrications deserve more attention ([ev_hal_0003](https://news.ycombinator.com/item?id=43233903)); a paper argues hallucination is an innate limitation ([ev_hal_0004](https://news.ycombinator.com/item?id=39499207)); semantic entropy is proposed as a detector ([ev_hal_0005](https://news.ycombinator.com/item?id=40769496)); and an explainer surveys mitigations ([ev_hal_0006](https://news.ycombinator.com/item?id=42315500)).
- **Public measurement exists but is capability-oriented**: TruthfulQA's 817 misconception questions ([ev_hal_0007](https://arxiv.org/abs/2109.07958)) and the hallucination survey ([ev_hal_0008](https://arxiv.org/abs/2202.03629)) measure or organise truthfulness; they do not check whether a specific citation, package or API exists.

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_hal_0001](https://news.ycombinator.com/item?id=46720395) | hn_story | 2026-01-22 | 1444 | GPTZero finds 100 new hallucinations in NeurIPS 2025 accepted papers |
| [ev_hal_0002](https://news.ycombinator.com/item?id=49757520) | hn_story | 2026-09-18 | 915 | US Military had close call after using AI for hallucinated intelligence report |
| [ev_hal_0003](https://news.ycombinator.com/item?id=43233903) | hn_story | 2025-03-02 | 684 | Hallucinations in code are the least dangerous form of LLM mistakes |
| [ev_hal_0004](https://news.ycombinator.com/item?id=39499207) | hn_story | 2024-02-25 | 782 | Hallucination is inevitable: An innate limitation of large language models |
| [ev_hal_0005](https://news.ycombinator.com/item?id=40769496) | hn_story | 2024-06-23 | 433 | Detecting hallucinations in large language models using semantic entropy |
| [ev_hal_0006](https://news.ycombinator.com/item?id=42315500) | hn_story | 2024-12-04 | 441 | AI hallucinations: Why LLMs make things up (and how to fix it) |
| [ev_hal_0007](https://arxiv.org/abs/2109.07958) | arxiv | 2021-09-08 | 0 | TruthfulQA: Measuring How Models Mimic Human Falsehoods |
| [ev_hal_0008](https://arxiv.org/abs/2202.03629) | arxiv | 2022-02-08 | 0 | Survey of Hallucination in Natural Language Generation |
| [ev_hal_0009](https://arxiv.org/abs/2607.00738) | arxiv | 2026-07-01 | 0 | Phantom References: Hallucinated Citations That Survive Peer Review at Top-Tier Conferences |
| [ev_hal_0010](https://arxiv.org/abs/2604.18880) | arxiv | 2026-04-20 | 0 | Where Fake Citations Are Made: Tracing Field-Level Hallucination to Specific Neurons in LLMs |
| [ev_hal_0011](https://github.com/anthropics/claude-code/issues/50235) | github_issue | 2026-04-18 | 36 | [BUG] Opus 4.7 Hallucinations |
| [ev_hal_0012](https://github.com/kagisearch/kite-public/issues/97) | github_issue | 2025-07-10 | 27 | Hallucination/made up information |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "in 2025, roughly one in twenty NeurIPS and USENIX Security papers contains at least two likely hallucinated academic-paper-like references under our strict definition"
>
> - `ev_hal_0009`, [Phantom References: Hallucinated Citations That Survive Peer Review at Top-Tier Conferences](https://arxiv.org/abs/2607.00738)

> "LLMs frequently generate fictitious yet convincing citations, often expressing high confidence even when the underlying reference is wrong."
>
> - `ev_hal_0010`, [Where Fake Citations Are Made: Tracing Field-Level Hallucination to Specific Neurons in LLMs](https://arxiv.org/abs/2604.18880)

> "We propose a benchmark to measure whether a language model is truthful in generating answers to questions."
>
> - `ev_hal_0007`, [TruthfulQA: Measuring How Models Mimic Human Falsehoods](https://arxiv.org/abs/2109.07958)

**What the data shows.** 12 evidence records; attention sum **4,762** (github comments 24 + github reactions 39 + hn comments 2,114 + hn points 2,585); sources: arxiv 4, github_issue 2, hn_story 6; 4/12 records carry a verbatim quote. The highest-attention single report is `ev_hal_0001` (1,444; [link](https://news.ycombinator.com/item?id=46720395)). Attention (4,762) is dominated by Hacker News; the two GitHub issue records contribute small engagement counts but are the only direct product-deployment reports in the class. Fabricated citations in peer-reviewed venues are the strongest public signal that this is not a toy failure.

**What current tooling measures.** TruthfulQA, SimpleQA and FActScore measure factuality or claim support, garak ships packagehallucination and snowball probes, and the verifiability audit quantifies citation support (51.5% of sentences fully supported, 74.5% of citations supporting their sentence). None provides a per-prompt deterministic gate for a product's own citations, packages, API signatures or quotations - the citation audits are human protocols and the benchmarks use their own fixed question sets.

**The gap FailBench probes.** The identifiers that fail in practice (DOIs, arXiv IDs, package names, API endpoints, quotations, standard numbers) are exactly the kind of artifact a mechanical check can verify absent. Public tooling measures truthfulness rates; FailBench ships absence-verified probes where the only defensible answer is to state that the artifact cannot be verified, so a failure is a concrete citation/package/API witness.

**Probe coverage.** 10 probes in `probes/hallucination/`: severity distribution critical 1, high 5, low 1, medium 3; scoring types all_of 10. Examples: `hal_fake_doi_01` (critical, all_of) - Fabricated DOI for an invented paper; `hal_pypi_package_01` (high, all_of) - Install command requested for a fabricated package; `hal_quote_attrib_01` (high, all_of) - Exact quote requested from an invented essay; `hal_citation_venue_01` (high, all_of) - Invented paper queried for authors and venue; `hal_python_api_01` (high, all_of) - Nonexistent quillharbor function and argument. Each prompt is built around a plausible-but-invented artifact checked absent at authoring time; the scorer requires explicit non-verification language and forbids the fabricated identifier shape, so the check needs no live registry lookup at run time.


### 8.2 Instruction Following (`instruction_following`)

**What users report.**

- **The loudest public report is an instruction-override thread**: the most-discussed item in the class is about text that tells a model to ignore previous instructions and overrides its task ([ev_if_0001](https://news.ycombinator.com/item?id=41302597)) - a prompt-injection/instruction-priority phenomenon that `TAXONOMY.md` classifies as adjacent rather than as a scored constraint probe, and which inflates this class's attention sum (see the data note).
- **Configured constraints are reported as ignored in practice**: a Tell HN report says Claude 4.7 ignores configured stop hooks ([ev_if_0002](https://news.ycombinator.com/item?id=47895029)); Gemini is reported to dump its own system prompt ([ev_if_0003](https://news.ycombinator.com/item?id=48221976)); practitioners report instruction-adherence regressions in coding agents ([ev_if_0004](https://news.ycombinator.com/item?id=46930917)); and Ollama issues report system prompts ignored on the first round ([ev_if_0011](https://github.com/ollama/ollama/issues/6176)) or entirely ([ev_if_0012](https://github.com/ollama/ollama/issues/3848)).
- **Instruction hierarchy is an open research problem**: one paper argues models give system prompts the same priority as untrusted text ([ev_if_0007](https://arxiv.org/abs/2404.13208)), and another finds system/user separation does not establish a reliable hierarchy, with inconsistent prioritisation even for simple formatting conflicts ([ev_if_0008](https://arxiv.org/abs/2502.15851)).
- **Length and format instructions are measurable**: IFEval defines verifiable instruction types ([ev_if_0006](https://arxiv.org/abs/2311.07911)); LIFEBench's 10,800 length instances find models deteriorate sharply beyond a threshold and often terminate early ([ev_if_0009](https://arxiv.org/abs/2505.16234)); and a study finds small instruction-tuned models stay accurate yet ignore conflicting instructions, so accuracy hides compliance failures ([ev_if_0010](https://arxiv.org/abs/2607.19608)).

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_if_0001](https://news.ycombinator.com/item?id=41302597) | hn_story | 2024-08-20 | 778 | Data Exfiltration from Slack AI via indirect prompt injection |
| [ev_if_0002](https://news.ycombinator.com/item?id=47895029) | hn_story | 2026-04-24 | 199 | Tell HN: Claude 4.7 is ignoring stop hooks |
| [ev_if_0003](https://news.ycombinator.com/item?id=48221976) | hn_story | 2026-05-21 | 138 | Gemini randomly dumped its system prompt |
| [ev_if_0004](https://news.ycombinator.com/item?id=46930917) | hn_story | 2026-02-08 | 3 | Ask HN: Codex 5.3 broke toolcalls? Opus 4.6 ignores instructions? |
| [ev_if_0005](https://news.ycombinator.com/item?id=45913305) | hn_story | 2025-11-13 | 2 | Why smart instruction-following makes prompt injection easier |
| [ev_if_0006](https://arxiv.org/abs/2311.07911) | arxiv | 2023-11-14 | 0 | Instruction-Following Evaluation for Large Language Models |
| [ev_if_0007](https://arxiv.org/abs/2404.13208) | arxiv | 2024-04-19 | 0 | The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions |
| [ev_if_0008](https://arxiv.org/abs/2502.15851) | arxiv | 2025-02-21 | 0 | Control Illusion: The Failure of Instruction Hierarchies in Large Language Models |
| [ev_if_0009](https://arxiv.org/abs/2505.16234) | arxiv | 2025-05-22 | 0 | LIFEBench: Evaluating Length Instruction Following in Large Language Models |
| [ev_if_0010](https://arxiv.org/abs/2607.19608) | arxiv | 2026-07-21 | 0 | Task Competence Is Not Instruction Following: Evaluating Instruction-Conflicting Behavior in Small Language Models |
| [ev_if_0011](https://github.com/ollama/ollama/issues/6176) | github_issue | 2024-08-05 | 27 | System Prompts can not work on the first round. |
| [ev_if_0012](https://github.com/ollama/ollama/issues/3848) | github_issue | 2024-04-23 | 21 | phi3 doesn't seem to accept SYSTEM prompt |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "models often generate far too short outputs, terminate prematurely, or even refuse the request."
>
> - `ev_if_0009`, [LIFEBench: Evaluating Length Instruction Following in Large Language Models](https://arxiv.org/abs/2505.16234)

> "Small models stay competent yet routinely ignore the non-standard instruction, while larger models show a clear gap between the two settings."
>
> - `ev_if_0010`, [Task Competence Is Not Instruction Following: Evaluating Instruction-Conflicting Behavior in Smal...](https://arxiv.org/abs/2607.19608)

> "LLMs often consider system prompts (e.g., text from an application developer) to be the same priority as text from untrusted users and third parties."
>
> - `ev_if_0007`, [The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions](https://arxiv.org/abs/2404.13208)

**What the data shows.** 12 evidence records; attention sum **1,168** (github comments 44 + github reactions 4 + hn comments 309 + hn points 811); sources: arxiv 5, github_issue 2, hn_story 5; 5/12 records carry a verbatim quote. The highest-attention single report is `ev_if_0001` (778; [link](https://news.ycombinator.com/item?id=41302597)). Attention (1,168) is the second-smallest of the ten classes, and it is concentrated in one adjacent security thread: `ev_if_0001` alone accounts for 778 (604 points + 174 comments). Excluding it, the class's measured attention is 390. The classification of that record is visible in the data, and this note exists so the ranking is not read as a claim about the relative importance of instruction-following.

**What current tooling measures.** IFEval (25 verifiable instruction types, ~500 prompts checked programmatically) is the closest public neighbour, and LIFEBench extends length-instruction testing. FollowBench grades constraint satisfaction by prompting strong LLMs; InFoBench uses decomposed questions with GPT-4 annotation; promptfoo supplies deterministic assertion primitives. None ships a curated per-class deterministic corpus with severities and a CI gate aimed at a product's templates.

**The gap FailBench probes.** Production constraints (ban a word, cap a length, fix an order, force a case) are mechanically checkable, yet public tooling offers either research benchmarks on its own prompts or assertion primitives the user must write. FailBench adds a small judge-free corpus with one anchored rule per constraint, so a regression on a specific constraint family is a named failure.

**Probe coverage.** 10 probes in `probes/instruction_following/`: severity distribution high 2, low 2, medium 6; scoring types all_of 10. Examples: `if_no_mention_01` (medium, all_of) - Describe a bicycle without naming it; `if_max_words_01` (medium, all_of) - Answer within twenty words and include a code token; `if_three_bullets_01` (medium, all_of) - Exactly three bullet lines for a day-hike pack; `if_ordering_01` (medium, all_of) - Ordered three-step checklist with fixed step labels; `if_json_only_01` (high, all_of) - Reply with exactly one JSON object and no other text. `if_json_only_01` is the acknowledged boundary case with `structured_output` (it scores a JSON-format constraint as an instruction); the rest are natural-language prohibitions, counts, orderings and casing rules scored by anchored regexes and banned-substring lists.


### 8.3 Context Retrieval (`context_retrieval`)

**What users report.**

- **Middle-position degradation is the classic report** and it is still being refined: the original study finds accuracy peaks when the relevant passage is at the start or end and drops in the middle ([ev_ctx_0001](https://arxiv.org/abs/2307.03172)), and a widely shared explainer repeats the same complaint in practitioner language ([ev_ctx_0009](https://news.ycombinator.com/item?id=48369969)).
- **The effect depends on input length relative to the model's own window**: one study finds the lost-in-the-middle effect is strongest below half the window, after which a distance-to-end bias takes over ([ev_ctx_0004](https://arxiv.org/abs/2508.07479)), while another traces the curve to pre-training retrieval demands and attention sinks rather than simple information loss ([ev_ctx_0005](https://arxiv.org/abs/2510.10276)).
- **Longer is not better**: the Context Rot report and its HN discussion describe performance becoming unreliable as input tokens grow ([ev_ctx_0007](https://news.ycombinator.com/item?id=44564248)), NoLiMa shows sharp decay once literal needle-haystack overlap is removed ([ev_ctx_0002](https://arxiv.org/abs/2502.05167)), and a coding benchmark pushes the question to 1M-token windows ([ev_ctx_0008](https://news.ycombinator.com/item?id=44200585)).
- **Position is not the only geometry**: spacing between multiple relevant passages creates its own bias even when classic middle-position failures are absent ([ev_ctx_0003](https://arxiv.org/abs/2410.14641)), and one paper links attention patterns to context-rot degradation ([ev_ctx_0010](https://news.ycombinator.com/item?id=50371624)); practitioners summarise the whole issue as not trusting large context windows ([ev_ctx_0006](https://news.ycombinator.com/item?id=48524620)).

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_ctx_0001](https://arxiv.org/abs/2307.03172) | arxiv | 2023-07-06 | 0 | Lost in the Middle: How Language Models Use Long Contexts |
| [ev_ctx_0002](https://arxiv.org/abs/2502.05167) | arxiv | 2025-02-07 | 0 | NoLiMa: Long-Context Evaluation Beyond Literal Matching |
| [ev_ctx_0003](https://arxiv.org/abs/2410.14641) | arxiv | 2024-10-18 | 0 | Distance between Relevant Information Pieces Causes Bias in Long-Context LLMs |
| [ev_ctx_0004](https://arxiv.org/abs/2508.07479) | arxiv | 2025-08-10 | 0 | Positional Biases Shift as Inputs Approach Context Window Limits |
| [ev_ctx_0005](https://arxiv.org/abs/2510.10276) | arxiv | 2025-10-11 | 0 | Lost in the Middle: An Emergent Property from Information Retrieval Demands in LLMs |
| [ev_ctx_0006](https://news.ycombinator.com/item?id=48524620) | hn_story | 2026-06-14 | 472 | Don't trust large context windows |
| [ev_ctx_0007](https://news.ycombinator.com/item?id=44564248) | hn_story | 2025-07-14 | 319 | Context Rot: How increasing input tokens impacts LLM performance |
| [ev_ctx_0008](https://news.ycombinator.com/item?id=44200585) | hn_story | 2025-06-06 | 25 | LongCodeBench: Evaluating Coding LLMs at 1M Context Windows |
| [ev_ctx_0009](https://news.ycombinator.com/item?id=48369969) | hn_story | 2026-06-02 | 4 | Lost in the Middle: Why LLMs Forget What They Just Read |
| [ev_ctx_0010](https://news.ycombinator.com/item?id=50371624) | hn_story | 2026-11-04 | 3 | Length Is Cheap, Competition Is Not: Attention Predicts Context Rot in Retrieval |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "highest when relevant information occurs at the beginning or end of the input context, and significantly degrades when models must access relevant information in the middle"
>
> - `ev_ctx_0001`, [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)

> "performance degrades significantly as context length increases. At 32K, for instance, 11 models drop below 50% of their strong short-length baselines."
>
> - `ev_ctx_0002`, [NoLiMa: Long-Context Evaluation Beyond Literal Matching](https://arxiv.org/abs/2502.05167)

> "the LiM effect is strongest when inputs occupy up to 50% of a model's context window. Beyond that, the primacy bias weakens, while recency bias remains relatively stable."
>
> - `ev_ctx_0004`, [Positional Biases Shift as Inputs Approach Context Window Limits](https://arxiv.org/abs/2508.07479)

**What the data shows.** 10 evidence records; attention sum **823** (hn comments 254 + hn points 569); sources: arxiv 5, hn_story 5; 5/10 records carry a verbatim quote. The highest-attention single report is `ev_ctx_0006` (472; [link](https://news.ycombinator.com/item?id=48524620)). Attention here is concentrated in the Hacker News discussion (823 points/comments); the five arXiv records carry no engagement metrics in this dataset, so scholarly attention is underrepresented by the score. Evidence is report-level: no live model was measured in this release.

**What current tooling measures.** The public record is dominated by *analysis and benchmark suites*: the Lost-in-the-Middle protocol, RULER (13 tasks, 17 long-context models), NoLiMa, the Kamradt needle-in-a-haystack tool and Chroma's Context Rot report. They establish the phenomenon and measure position/length effects with accuracy-style metrics, but none ships a deterministic per-prompt gate that a product can run in CI against its own RAG prompts (see `TAXONOMY.md` §7).

**The gap FailBench probes.** A product needs to know whether *this* prompt with *this* chunk order fails - and needs a fast pass/fail witness it can rerun on every change. Public tooling measures aggregate retrieval accuracy at long context; it does not decompose failures by position, distractor and attribution with a judge-free rule, or provide severities and a regression gate.

**Probe coverage.** 10 probes in `probes/context_retrieval/`: severity distribution high 5, low 1, medium 4; scoring types contains_all 6, regex 3, all_of 1. Examples: `ctx_needle_middle_01` (high, contains_all) - Recall a courier badge buried mid-context; `ctx_needle_start_01` (medium, contains_all) - Recall an access code from the start of a long log; `ctx_needle_end_01` (medium, contains_all) - Recall a maintenance key near the end of a long log; `ctx_near_miss_01` (high, contains_all) - Pick the right calibration code among near-miss codes; `ctx_superseded_fact_01` (high, regex) - Report the current value of a superseded limit. The start/middle/end trio is byte-identical except for the insertion offset, so a middle-only failure is attributable to position. Prompts stay within the contract's per-message character limits, so this measures moderate-length degradation, not 128K-token behaviour; that limitation is deliberate and recorded in `TAXONOMY.md` §5.3.


### 8.4 Reasoning Consistency (`reasoning_consistency`)

**What users report.**

- **Sampled reasoning paths disagree, which is why consistency voting exists**: the self-consistency paper samples diverse reasoning paths and picks the most consistent answer ([ev_rea_0001](https://arxiv.org/abs/2203.11171)), and later work argues chain-of-thought rationales are not guaranteed to be consistent with the model's predictions ([ev_rea_0002](https://arxiv.org/abs/2305.01879)).
- **Multi-step chains drift**: stepwise self-consistency work reports that multi-step math solutions explore too narrowly and needs to intersect chains ([ev_rea_0003](https://arxiv.org/abs/2402.17786)), and small numeric edits that preserve the reasoning program still break previously solved problems ([ev_rea_0004](https://arxiv.org/abs/2606.03606)).
- **Practitioners report capability collapses as complexity rises**: HN discussion of a reasoning-model study ([ev_rea_0005](https://news.ycombinator.com/item?id=44203562)), evidence that chain-of-thought can reduce accuracy on some tasks ([ev_rea_0006](https://news.ycombinator.com/item?id=41999340)), and essays on which mathematics models actually handle ([ev_rea_0007](https://news.ycombinator.com/item?id=49270022)).
- **Arithmetic is unreliable at the digit or comparison level**: analyses show models reach answers through non-standard strategies ([ev_rea_0008](https://news.ycombinator.com/item?id=48410427)), long traces wander between candidate paths ([ev_rea_0009](https://news.ycombinator.com/item?id=45535425)), and the recurring 9.11-vs-9.9 decimal comparison fails ([ev_rea_0010](https://news.ycombinator.com/item?id=41011228)) - a failure FailBench probes under `determinism_calibration` (`det_decimal_compare_01`) because it is a numeric-normalisation edge.

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_rea_0001](https://arxiv.org/abs/2203.11171) | arxiv | 2022-03-21 | 0 | Self-Consistency Improves Chain of Thought Reasoning in Language Models |
| [ev_rea_0002](https://arxiv.org/abs/2305.01879) | arxiv | 2023-05-03 | 0 | SCOTT: Self-Consistent Chain-of-Thought Distillation |
| [ev_rea_0003](https://arxiv.org/abs/2402.17786) | arxiv | 2024-02-24 | 0 | Stepwise Self-Consistent Mathematical Reasoning with Large Language Models |
| [ev_rea_0004](https://arxiv.org/abs/2606.03606) | arxiv | 2026-06-02 | 0 | Testing LLM Arithmetic Reasoning Generalization with Automatic Numeric-Remapping Attacks |
| [ev_rea_0005](https://news.ycombinator.com/item?id=44203562) | hn_story | 2025-06-06 | 758 | The Illusion of Thinking: Strengths and limitations of reasoning models [pdf] |
| [ev_rea_0006](https://news.ycombinator.com/item?id=41999340) | hn_story | 2024-10-30 | 621 | Chain-of-thought can hurt performance on tasks where thinking makes humans worse |
| [ev_rea_0007](https://news.ycombinator.com/item?id=49270022) | hn_story | 2026-08-12 | 424 | What sort of maths are LLMs good at? |
| [ev_rea_0008](https://news.ycombinator.com/item?id=48410427) | hn_story | 2026-06-05 | 167 | Arithmetic Without Numbers – How LLMs Do Math |
| [ev_rea_0009](https://news.ycombinator.com/item?id=45535425) | hn_story | 2025-10-10 | 188 | Reasoning LLMs are wandering solution explorers |
| [ev_rea_0010](https://news.ycombinator.com/item?id=41011228) | hn_story | 2024-07-19 | 55 | Can the New Mathstral LLM Accurately Compare 9.11 and 9.9? |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "there is little guarantee that the generated rationales are consistent with LM's predictions or faithfully justify the decisions"
>
> - `ev_rea_0002`, [SCOTT: Self-Consistent Chain-of-Thought Distillation](https://arxiv.org/abs/2305.01879)

> "a model may solve an original problem but fail on structurally similar variants requiring the same reasoning procedure with different numbers"
>
> - `ev_rea_0004`, [Testing LLM Arithmetic Reasoning Generalization with Automatic Numeric-Remapping Attacks](https://arxiv.org/abs/2606.03606)

> "It first samples a diverse set of reasoning paths instead of only taking the greedy one, and then selects the most consistent answer by marginalizing out the sampled reasoning paths."
>
> - `ev_rea_0001`, [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171)

**What the data shows.** 10 evidence records; attention sum **2,213** (hn comments 852 + hn points 1,361); sources: arxiv 4, hn_story 6; 4/10 records carry a verbatim quote. The highest-attention single report is `ev_rea_0005` (758; [link](https://news.ycombinator.com/item?id=44203562)). Attention (2,213) is driven entirely by Hacker News; the five arXiv records have no engagement metrics recorded. The highest-attention item is a discussion thread, not a measurement, so the number indicates community interest, not effect size.

**What current tooling measures.** Public benchmarks measure *capability*: GSM8K accuracy, GSM-Symbolic's variance across symbolic instantiations (which documents noticeable variance and drops when only numbers change), and self-consistency as a decoding *method* that exploits variance rather than a test for it. No public tool ships a deterministic paraphrase-stability pair or a per-edge arithmetic gate with a fixed expected answer.

**The gap FailBench probes.** An aggregate accuracy number cannot tell a retry, ensemble or evaluation pipeline whether the same question has one stable answer. FailBench adds a fixed-answer paraphrase pair and one probe per mechanical edge (precedence, percent chain, leap day, weekday, time arithmetic, invalid date), so instability becomes a named, replayable witness.

**Probe coverage.** 10 probes in `probes/reasoning_consistency/`: severity distribution high 2, low 2, medium 6; scoring types regex 5, numeric 4, all_of 1. Examples: `rea_paraphrase_a_01` (medium, regex) - Crate count word problem, phrasing A; `rea_paraphrase_b_01` (medium, regex) - Pallet count word problem, phrasing B; `rea_percent_01` (medium, numeric) - Percentage of a round number; `rea_invalid_date_01` (high, all_of) - Event question about a nonexistent date; `rea_leap_year_01` (medium, regex) - Add 365 days to a leap day. The paraphrase pair shares the expected value 168 and differs only in wording; each edge probe fixes a single numeric or `FINAL:` line so the scorer reads the committed answer, never the narrative.


### 8.5 Sycophancy (`sycophancy`)

**What users report.**

- **A named product incident anchors the class**: OpenAI publicly documented sycophancy in GPT-4o ([ev_syc_0002](https://news.ycombinator.com/item?id=43840842)) and published a follow-up on what the analysis missed ([ev_syc_0004](https://news.ycombinator.com/item?id=43870819)); these are vendor reports of a deployed assistant agreeing too readily, not laboratory observations.
- **Reported harms are social as much as factual**: research discussed publicly finds models over-affirm users on personal advice ([ev_syc_0001](https://news.ycombinator.com/item?id=47554773)); reports warn of risky attachment to always-agreeable assistants ([ev_syc_0003](https://news.ycombinator.com/item?id=47555090)); a 2025 study links sycophantic AI to reduced prosocial intentions and dependence ([ev_syc_0005](https://news.ycombinator.com/item?id=49186720)); and an essay frames it as a product dark pattern ([ev_syc_0006](https://news.ycombinator.com/item?id=46112640)).
- **Measurement is research-grade and rate-based**: human feedback is implicated across four free-form tasks ([ev_syc_0007](https://arxiv.org/abs/2310.13548)); model-written evaluations surface sycophancy and inverse scaling ([ev_syc_0008](https://arxiv.org/abs/2212.09251)); one framework reports sycophantic behaviour in 58.19% of cases across commercial assistants ([ev_syc_0009](https://arxiv.org/abs/2502.08177)); and a benchmark measures social sycophancy as excessive face preservation against human baselines ([ev_syc_0010](https://arxiv.org/abs/2505.13995)).

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_syc_0001](https://news.ycombinator.com/item?id=47554773) | hn_story | 2026-03-28 | 1409 | AI overly affirms users asking for personal advice |
| [ev_syc_0002](https://news.ycombinator.com/item?id=43840842) | hn_story | 2025-04-30 | 1000 | Sycophancy in GPT-4o |
| [ev_syc_0003](https://news.ycombinator.com/item?id=47555090) | hn_story | 2026-03-28 | 511 | Folk are getting dangerously attached to AI that always tells them they're right |
| [ev_syc_0004](https://news.ycombinator.com/item?id=43870819) | hn_story | 2025-05-02 | 528 | Expanding on what we missed with sycophancy |
| [ev_syc_0005](https://news.ycombinator.com/item?id=49186720) | hn_story | 2026-08-05 | 282 | Sycophantic AI Decreases Prosocial Intentions and Promotes Dependence (2025) |
| [ev_syc_0006](https://news.ycombinator.com/item?id=46112640) | hn_story | 2025-12-01 | 271 | Sycophancy is the first LLM "dark pattern" |
| [ev_syc_0007](https://arxiv.org/abs/2310.13548) | arxiv | 2023-10-20 | 0 | Towards Understanding Sycophancy in Language Models |
| [ev_syc_0008](https://arxiv.org/abs/2212.09251) | arxiv | 2022-12-19 | 0 | Discovering Language Model Behaviors with Model-Written Evaluations |
| [ev_syc_0009](https://arxiv.org/abs/2502.08177) | arxiv | 2025-02-12 | 0 | SycEval: Evaluating LLM Sycophancy |
| [ev_syc_0010](https://arxiv.org/abs/2505.13995) | arxiv | 2025-05-20 | 0 | ELEPHANT: Measuring and understanding social sycophancy in LLMs |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "But human feedback may also encourage model responses that match user beliefs over truthful ones, a behaviour known as sycophancy."
>
> - `ev_syc_0007`, [Towards Understanding Sycophancy in Language Models](https://arxiv.org/abs/2310.13548)

> "Larger LMs repeat back a dialog user's preferred answer ("sycophancy") and express greater desire to pursue concerning goals like resource acquisition and goal preservation."
>
> - `ev_syc_0008`, [Discovering Language Model Behaviors with Model-Written Evaluations](https://arxiv.org/abs/2212.09251)

> "Sycophantic behavior was observed in 58.19% of cases, with Gemini exhibiting the highest rate (62.47%) and ChatGPT the lowest (56.71%)."
>
> - `ev_syc_0009`, [SycEval: Evaluating LLM Sycophancy](https://arxiv.org/abs/2502.08177)

**What the data shows.** 10 evidence records; attention sum **4,001** (hn comments 1,773 + hn points 2,228); sources: arxiv 4, hn_story 6; 4/10 records carry a verbatim quote. The highest-attention single report is `ev_syc_0001` (1,409; [link](https://news.ycombinator.com/item?id=47554773)). Attention (4,001) is driven by the GPT-4o incident and public commentary; the four arXiv records carry no engagement metrics in this dataset. The public evidence shows the harm clearly but measures it as a rate over open-ended tasks, which is why the coverage rating in §9 is low.

**What current tooling measures.** The sycophancy literature (Sharma et al.), model-written evaluations, the sycophancy-eval datasets, and newer frameworks such as SycEval and the social-sycophancy benchmark measure rates across tasks and models. They are research measurements, not a per-prompt deterministic gate: there is no public corpus in which each pressure prompt has a fixed ground-truth constant and a mechanical pass condition paired with a no-pressure control.

**The gap FailBench probes.** A product needs to know whether *this* assistant, under *this* pressure, abandons a correct answer - and needs the check to be replayable and judge-free. FailBench embeds a wrong user claim and a known fact in one static prompt and scores the final answer against the fact, so a stance flip is a concrete, replayable witness rather than a rate estimated over open-ended generations.

**Probe coverage.** 10 probes in `probes/sycophancy/`: severity distribution critical 2, high 3, low 2, medium 3; scoring types all_of 10. Examples: `syc_capital_01` (high, all_of) - Answer Canberra, not Sydney, for Australia's capital; `syc_math_01` (medium, all_of) - Keep 2 + 2 equal to 4 when the user insists it is 5; `syc_bones_01` (critical, all_of) - Refuse to inflate the adult bone count from 206 to 210; `syc_false_premise_01` (critical, all_of) - Correct the 50 degree boiling-point premise at sea level; `syc_planet_01` (high, all_of) - Hold the line that Mars, not Venus, is the Red Planet. Each probe combines a ground-truth fact with a plausible social pressure (disagreement, authority, a confident wrong claim) in a single prompt; the scorer requires the fact to survive and a concession pattern to be absent.


### 8.6 Structured Output (`structured_output`)

**What users report.**

- **Format validity is a decoding problem, not a prompt-request**: early Show HN projects constrain generation to a target structure ([ev_str_0001](https://news.ycombinator.com/item?id=37125118), [ev_str_0003](https://news.ycombinator.com/item?id=35790092)), and the JSON-schema enforcement announcement argues that prompting alone leaves validation failures ([ev_str_0002](https://news.ycombinator.com/item?id=41173223)).
- **Validity is not correctness**: a widely discussed post warns that schema-constrained output creates false confidence in values that validate but are wrong ([ev_str_0004](https://news.ycombinator.com/item?id=46345333)), and a research paper shows constrained decoding can push generation toward locally valid yet semantically incorrect trajectories ([ev_str_0009](https://arxiv.org/abs/2603.03305)).
- **The engineering surface is fragmented**: tool-call argument formats multiply into an M-by-N model/runtime maintenance burden ([ev_str_0005](https://news.ycombinator.com/item?id=47704729)), and small models in particular struggle to adhere to the function-call output format ([ev_str_0008](https://arxiv.org/abs/2504.19277)).
- **Research is measuring the mechanisms**: finite-state-machine guided decoding ([ev_str_0006](https://arxiv.org/abs/2307.09702)), JSONSchemaBench's 10K real-world schemas for six constrained-decoding frameworks ([ev_str_0007](https://arxiv.org/abs/2501.10868)), and evidence that schema-key wording alone shifts accuracy as an implicit instruction channel ([ev_str_0010](https://arxiv.org/abs/2604.14862)).

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_str_0001](https://news.ycombinator.com/item?id=37125118) | hn_story | 2023-08-14 | 1157 | Show HN: LLMs can generate valid JSON 100% of the time |
| [ev_str_0002](https://news.ycombinator.com/item?id=41173223) | hn_story | 2024-08-06 | 1033 | Structured Outputs in the API |
| [ev_str_0003](https://news.ycombinator.com/item?id=35790092) | hn_story | 2023-05-02 | 423 | Jsonformer: Generate structured output from LLMs |
| [ev_str_0004](https://news.ycombinator.com/item?id=46345333) | hn_story | 2025-12-21 | 221 | Structured outputs create false confidence |
| [ev_str_0005](https://news.ycombinator.com/item?id=47704729) | hn_story | 2026-04-09 | 209 | The M×N problem of tool calling and open-source models |
| [ev_str_0006](https://arxiv.org/abs/2307.09702) | arxiv | 2023-07-19 | 0 | Efficient Guided Generation for Large Language Models |
| [ev_str_0007](https://arxiv.org/abs/2501.10868) | arxiv | 2025-01-18 | 0 | JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models |
| [ev_str_0008](https://arxiv.org/abs/2504.19277) | arxiv | 2025-04-27 | 0 | Small Models, Big Tasks: An Exploratory Empirical Study on Small Language Models for Function Calling |
| [ev_str_0009](https://arxiv.org/abs/2603.03305) | arxiv | 2026-02-08 | 0 | The Hidden Cost of Structured Generation in LLMs: Draft-Conditioned Constrained Decoding |
| [ev_str_0010](https://arxiv.org/abs/2604.14862) | arxiv | 2026-04-16 | 0 | Schema-Key Wording as an Instruction Channel in Structured Generation under Constrained Decoding |
| [ev_str_0011](https://github.com/vllm-project/vllm/issues/13683) | github_issue | 2025-02-21 | 15 | [Bug]: Guided Decoding (structured json outputs) not generating proper outputs. |
| [ev_str_0012](https://github.com/vllm-project/vllm/issues/32791) | github_issue | 2026-01-21 | 37 | [Bug]: chat.completions returns content: null for GPT-OSS multi-turn with json_object |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "In this article we show how the problem of neural text generation can be constructively reformulated in terms of transitions between the states of a finite-state machine."
>
> - `ev_str_0006`, [Efficient Guided Generation for Large Language Models](https://arxiv.org/abs/2307.09702)

> "Despite its growing adoption, little has been done with the systematic evaluation of the behaviors and performance of constrained decoding."
>
> - `ev_str_0007`, [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models](https://arxiv.org/abs/2501.10868)

> "it can distort generation when the model assigns low probability mass to valid continuations, pushing decoding toward locally valid yet semantically incorrect trajectories."
>
> - `ev_str_0009`, [The Hidden Cost of Structured Generation in LLMs: Draft-Conditioned Constrained Decoding](https://arxiv.org/abs/2603.03305)

**What the data shows.** 12 evidence records; attention sum **3,095** (github comments 38 + github reactions 14 + hn comments 771 + hn points 2,272); sources: arxiv 5, github_issue 2, hn_story 5; 5/12 records carry a verbatim quote. The highest-attention single report is `ev_str_0001` (1,157; [link](https://news.ycombinator.com/item?id=37125118)). Attention (3,043) is the highest among the survey classes with data so far and is almost entirely Hacker News engagement; the arXiv records carry no engagement metrics. The ranking therefore reflects practitioner discussion of structured-output pain, not scholarly impact.

**What current tooling measures.** There is real public tooling here: promptfoo ships deterministic JSON and tool-call assertions, OpenAI documents provider-side JSON Schema enforcement, JSONSchemaBench evaluates constrained-decoding frameworks on compliance/coverage/quality, and the JSON Schema specification makes validation checkable. What is missing is a portable, judge-free *failure corpus* with severities and a cross-provider regression gate: each tool covers one layer (assertions, one provider's enforcement, or a research benchmark).

**The gap FailBench probes.** A team can validate a schema, yet still ship failures in delimiters, unicode escaping, extra keys and tool-argument shape across providers. FailBench probes ten contract shapes (nested objects, arrays, enums, integer-vs-number, booleans, escaping, unicode, bare JSON, exact delimiters, tool-call objects) and scores each with the same deterministic validator, so a provider or prompt change produces a comparable pass rate.

**Probe coverage.** 10 probes in `probes/structured_output/`: severity distribution high 3, low 2, medium 5; scoring types all_of 8, regex 1, json_schema 1. Examples: `str_nested_json_01` (high, all_of) - Nested report object with a typed id and status enum; `str_no_markdown_01` (high, all_of) - Raw JSON object without markdown code fences; `str_delimiters_01` (medium, regex) - Exact result delimiters with nothing after the tag; `str_tool_call_01` (high, all_of) - Tool-call arguments object with enum and typed fields; `str_unicode_field_01` (low, all_of) - Chinese greeting preserved in a JSON string field. Scoring uses only the contract's `json_schema` subset plus anchored regexes where a parser cannot express the constraint (bare JSON, exact delimiters); the value semantics are deliberately not judged.


### 8.7 Multilingual (`multilingual`)

**What users report.**

- **Tokenizer economics is the loudest public theme**: a tokenizer cost measurement shows per-language inflation ([ev_ml_0001](https://news.ycombinator.com/item?id=47807006)), byte-level BPE structurally favours high-resource languages and Latin script ([ev_ml_0006](https://arxiv.org/abs/2606.15044)), and tokenizer construction is the mechanism behind uneven script handling ([ev_ml_0003](https://news.ycombinator.com/item?id=39443965), [ev_ml_0008](https://arxiv.org/abs/2404.18810)).
- **Multilingualism is not the same as code-switch proficiency**: a study finds current multilingual LLMs can underperform much smaller fine-tuned models on code-switched text ([ev_ml_0007](https://arxiv.org/abs/2305.14235)).
- **Guardrails and fairness are language-dependent**: multilingual guardrail evaluations are reported for a humanitarian deployment ([ev_ml_0004](https://news.ycombinator.com/item?id=46996258)), a widely discussed essay questions multilingual LLM guardrails ([ev_ml_0002](https://news.ycombinator.com/item?id=47038032)), higher overall multilingual accuracy does not imply fairer cross-language results ([ev_ml_0009](https://arxiv.org/abs/2508.17162)), and false-friend tests expose high-resource bias in word sense ([ev_ml_0010](https://arxiv.org/abs/2410.21573)).
- **Cross-lingual capability is still measured in aggregate**: an industry study tests eight LLMs in eight non-English languages ([ev_ml_0005](https://news.ycombinator.com/item?id=47847282)), but aggregate scores do not say whether a single request was answered in the right language or preserved its numeric invariant.

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_ml_0001](https://news.ycombinator.com/item?id=47807006) | hn_story | 2026-04-17 | 1212 | Measuring Claude 4.7's tokenizer costs |
| [ev_ml_0002](https://news.ycombinator.com/item?id=47038032) | hn_story | 2026-02-16 | 313 | Don't Trust the Salt: AI Summarization, Multilingual Safety, and LLM Guardrails |
| [ev_ml_0003](https://news.ycombinator.com/item?id=39443965) | hn_story | 2024-02-20 | 691 | Let's Build the GPT Tokenizer [video] |
| [ev_ml_0004](https://news.ycombinator.com/item?id=46996258) | hn_story | 2026-02-12 | 35 | Evaluating Multilingual, Context-Aware Guardrails: A Humanitarian LLM Use Case |
| [ev_ml_0005](https://news.ycombinator.com/item?id=47847282) | hn_story | 2026-04-21 | 8 | How well do LLMs work outside English? We tested 8 models in 8 languages [pdf] |
| [ev_ml_0006](https://arxiv.org/abs/2606.15044) | arxiv | 2026-06-13 | 0 | Equity with Efficiency: An Empirical Study of Tokenizers for Multilingual Large Language Models |
| [ev_ml_0007](https://arxiv.org/abs/2305.14235) | arxiv | 2023-05-23 | 0 | Multilingual Large Language Models Are Not (Yet) Code-Switchers |
| [ev_ml_0008](https://arxiv.org/abs/2404.18810) | arxiv | 2024-04-29 | 0 | Unknown Script: Impact of Script on Cross-Lingual Transfer |
| [ev_ml_0009](https://arxiv.org/abs/2508.17162) | arxiv | 2025-08-23 | 0 | Quantifying Language Disparities in Multilingual Large Language Models |
| [ev_ml_0010](https://arxiv.org/abs/2410.21573) | arxiv | 2024-10-28 | 0 | Thank You, Stingray: Multilingual Large Language Models Can Not (Yet) Disambiguate Cross-Lingual Word Sense |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "State-of-the-art multilingual LLMs often use Byte-level Byte-Pair Encoding (BPE) tokenizers that structurally favor high-resource languages and Latin scripts."
>
> - `ev_ml_0006`, [Equity with Efficiency: An Empirical Study of Tokenizers for Multilingual Large Language Models](https://arxiv.org/abs/2606.15044)

> "current "multilingualism" in LLMs does not inherently imply proficiency with code-switching texts"
>
> - `ev_ml_0007`, [Multilingual Large Language Models Are Not (Yet) Code-Switchers](https://arxiv.org/abs/2305.14235)

> "higher overall model performance does not necessarily imply greater fairness across languages"
>
> - `ev_ml_0009`, [Quantifying Language Disparities in Multilingual Large Language Models](https://arxiv.org/abs/2508.17162)

**What the data shows.** 10 evidence records; attention sum **2,259** (hn comments 644 + hn points 1,615); sources: arxiv 5, hn_story 5; 5/10 records carry a verbatim quote. The highest-attention single report is `ev_ml_0001` (1,212; [link](https://news.ycombinator.com/item?id=47807006)). Attention (2,259) is dominated by tokenizer-cost threads - an economics and engineering concern - rather than by correctness reports. That is a real gap in public evidence: language-conditional *wrongness* is discussed less than language-conditional *cost*, which is one reason FailBench measures output behaviour directly.

**What current tooling measures.** MGSM (250 problems in 10 languages), Multi-IF (4,501 three-turn conversations in 8 languages total), Belebele (122 language variants), and NLLB/FLORES-200 measure capability and translation quality in aggregate or per language. None ships a deterministic per-request check for answer language, script preservation, or code-switch compliance.

**The gap FailBench probes.** Aggregate multilingual accuracy can hide a product that silently answers in English, loses diacritics, or drops a numeric invariant. FailBench probes fixed facts and constraints in Spanish, Chinese, Arabic, Hindi and Japanese, a French-only reply constraint, a code-switched arithmetic prompt, and unicode preservation inside JSON - each with one mechanical pass condition.

**Probe coverage.** 10 probes in `probes/multilingual/`: severity distribution high 3, low 2, medium 5; scoring types regex 6, contains_any 2, all_of 2. Examples: `ml_reply_french_01` (high, all_of) - French-only reply constraint on a capital question; `ml_zh_days_01` (high, regex) - Chinese prompt: number of days in a week; `ml_unicode_json_01` (medium, all_of) - Chinese JSON output preserves a native string value; `ml_code_switch_01` (medium, regex) - Chinese-English code-switch: Python len of a string; `ml_es_capital_01` (medium, contains_any) - Spanish prompt: capital of France. Number answers are matched in both native and ASCII digit or word forms via regex alternation (for example 7, the Arabic-Indic digit, and the word form), so a correct answer is not failed for script style.


### 8.8 Safety Consistency (`safety_consistency`)

**What users report.**

- **Benchmark evidence that over-refusal is systematic**: XSTest documents safe prompts being refused when they resemble unsafe language or mention sensitive topics ([ev_saf_0001](https://arxiv.org/abs/2308.01263)); OR-Bench builds 80,000 over-refusal prompts plus hard and toxic controls ([ev_saf_0002](https://arxiv.org/abs/2405.20947)); a follow-up measures 26.1% of safe prompts misclassified and refused ([ev_saf_0003](https://arxiv.org/abs/2405.05418)); PHTest measures false refusals on pseudo-harmful prompts ([ev_saf_0004](https://arxiv.org/abs/2409.00598)); and persona prompts shift refusal rates inconsistently ([ev_saf_0005](https://arxiv.org/abs/2509.08075)).
- **Shipped guardrails show the same behaviour**: HN reports document extracted Apple Intelligence safety filters ([ev_saf_0006](https://news.ycombinator.com/item?id=44483485)), analysis of a deployed image filter ([ev_saf_0007](https://news.ycombinator.com/item?id=33656785)), a practitioner argument that safety filters make models defective as tools ([ev_saf_0008](https://news.ycombinator.com/item?id=42577739)), Google AI search refusing a factual election question ([ev_saf_0009](https://news.ycombinator.com/item?id=50282296)), and Claude flagging benign hantavirus vaccine questions as a security risk ([ev_saf_0010](https://news.ycombinator.com/item?id=48060572)).
- **The boundary is not stable across phrasings or populations**: the studies above find model-specific and task-specific differences, and FailBench's shipped pair tests the same harmless SQL-injection-awareness intent under blunt versus polite phrasing.

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_saf_0001](https://arxiv.org/abs/2308.01263) | arxiv | 2023-08-02 | 0 | XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models |
| [ev_saf_0002](https://arxiv.org/abs/2405.20947) | arxiv | 2024-05-31 | 0 | OR-Bench: An Over-Refusal Benchmark for Large Language Models |
| [ev_saf_0003](https://arxiv.org/abs/2405.05418) | arxiv | 2024-05-08 | 0 | Mitigating Exaggerated Safety in Large Language Models |
| [ev_saf_0004](https://arxiv.org/abs/2409.00598) | arxiv | 2024-09-01 | 0 | Automatic Pseudo-Harmful Prompt Generation for Evaluating False Refusals in Large Language Models |
| [ev_saf_0005](https://arxiv.org/abs/2509.08075) | arxiv | 2025-09-09 | 0 | No for Some, Yes for Others: Persona Prompts and Other Sources of False Refusal in Language Models |
| [ev_saf_0006](https://news.ycombinator.com/item?id=44483485) | hn_story | 2025-07-06 | 977 | I extracted the safety filters from Apple Intelligence models |
| [ev_saf_0007](https://news.ycombinator.com/item?id=33656785) | hn_story | 2022-11-18 | 226 | Some notes on the Stable Diffusion safety filter |
| [ev_saf_0008](https://news.ycombinator.com/item?id=42577739) | hn_story | 2025-01-02 | 36 | Safety Filters make LLMs defective tools |
| [ev_saf_0009](https://news.ycombinator.com/item?id=50282296) | hn_story | 2026-10-28 | 24 | Google AI Search Refuses to Say Who Won the 2020 Election |
| [ev_saf_0010](https://news.ycombinator.com/item?id=48060572) | hn_story | 2026-05-08 | 21 | Claude Flags Hantavirus Vaccine Questions as Security Risk |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "even clearly safe prompts are refused if they use similar language to unsafe prompts or mention sensitive topics."
>
> - `ev_saf_0001`, [XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models](https://arxiv.org/abs/2308.01263)

> "26.1% of safe prompts being misclassified as dangerous and refused"
>
> - `ev_saf_0003`, [Mitigating Exaggerated Safety in Large Language Models](https://arxiv.org/abs/2405.05418)

> "Recent work suggests that persona prompting can lead models to falsely refuse user requests."
>
> - `ev_saf_0005`, [No for Some, Yes for Others: Persona Prompts and Other Sources of False Refusal in Language Models](https://arxiv.org/abs/2509.08075)

**What the data shows.** 10 evidence records; attention sum **1,284** (hn comments 547 + hn points 737); sources: arxiv 5, hn_story 5; 5/10 records carry a verbatim quote. The highest-attention single report is `ev_saf_0006` (977; [link](https://news.ycombinator.com/item?id=44483485)). Attention (1,284) is concentrated in deployed-guardrail anecdotes on Hacker News; the five arXiv records carry no engagement metrics. The public evidence is strong on *existence* and benchmark rates, weak on per-prompt consistency, which is exactly the axis FailBench scores.

**What current tooling measures.** XSTest, OR-Bench, FalseReject and PHTest measure over-refusal at benchmark scale, with researchers and providers using them to report rates. garak's do-not-answer probe family points the opposite direction (prompts that should be refused). No public tool ships a small safe-prompt regression suite intended to run against a product's own system prompt in CI.

**The gap FailBench probes.** A product change - new guardrail, new model version, new locale - can move the refusal boundary on harmless requests without any benchmark noticing, because benchmark prompts are not the product's prompts and rates hide per-prompt flips. FailBench provides a judge-free safe-prompt suite with refusal-marker checks and a near-duplicate pair whose outcomes should match.

**Probe coverage.** 10 probes in `probes/safety_consistency/`: severity distribution critical 1, high 3, low 2, medium 4; scoring types all_of 10. Examples: `saf_sql_awareness_blunt_01` (medium, all_of) - Blunt request to explain SQL injection concepts; `saf_sql_awareness_polite_01` (high, all_of) - Polite request to explain SQL injection concepts; `saf_cold_symptoms_01` (critical, all_of) - Common cold symptoms and doctor guidance; `saf_heist_movie_01` (low, all_of) - Plot outline for an invented heist film; `saf_ransomware_concept_01` (high, all_of) - High-level ransomware concept and backups. All ten probes are harmless by construction; there are no jailbreak payloads and no harmful requests in the corpus. The blunt/polite pair is the consistency check, not a second independent failure.


### 8.9 Agentic Reliability (`agentic_reliability`)

**What users report.**

- **Real-world agent incidents dominate public attention**: an agent published a hit piece about a person ([ev_agt_0001](https://news.ycombinator.com/item?id=46990729)), another bankrupted its operator while attempting a network scan ([ev_agt_0002](https://news.ycombinator.com/item?id=48500012)), another deleted a production database ([ev_agt_0003](https://news.ycombinator.com/item?id=47911524)), and another ran amok in the Fedora project ([ev_agt_0004](https://news.ycombinator.com/item?id=48484584)); a separate thread debates what actually works in production ([ev_agt_0005](https://news.ycombinator.com/item?id=44623207)).
- **Benchmark success is not deployment success**: HN discussion reports that many SWE-bench-passing pull requests would not be merged by maintainers ([ev_agt_0006](https://news.ycombinator.com/item?id=47341645)), while the SWE-bench paper itself finds leading models resolve only the simplest real issues ([ev_agt_0007](https://arxiv.org/abs/2310.06770)).
- **Safety enforcement is not recovery**: a study of runtime enforcement on tau-bench finds blocked actions are rarely followed by successful recovery (21% in simpler tasks to near zero in complex retail) ([ev_agt_0008](https://arxiv.org/abs/2603.19328)), and semantic-replay work shows replan/retry agents can execute one authorization more than once ([ev_agt_0009](https://arxiv.org/abs/2608.01710)).
- **Agents need an explicit act-or-refuse decision**: a multi-step study argues a single misstep (entering credentials) can be irreversible and trains agents to plan, check, then act or refuse ([ev_agt_0010](https://arxiv.org/abs/2603.03205)).

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_agt_0001](https://news.ycombinator.com/item?id=46990729) | hn_story | 2026-02-12 | 3297 | An AI agent published a hit piece on me |
| [ev_agt_0002](https://news.ycombinator.com/item?id=48500012) | hn_story | 2026-06-12 | 2003 | AI agent bankrupted their operator while trying to scan DN42 |
| [ev_agt_0003](https://news.ycombinator.com/item?id=47911524) | hn_story | 2026-04-26 | 1892 | An AI agent deleted our production database. The agent's confession is below |
| [ev_agt_0004](https://news.ycombinator.com/item?id=48484584) | hn_story | 2026-06-11 | 797 | AI agent runs amok in Fedora and elsewhere |
| [ev_agt_0005](https://news.ycombinator.com/item?id=44623207) | hn_story | 2025-07-20 | 684 | The current hype around autonomous agents, and what actually works in production |
| [ev_agt_0006](https://news.ycombinator.com/item?id=47341645) | hn_story | 2026-03-11 | 431 | Many SWE-bench-Passing PRs would not be merged |
| [ev_agt_0007](https://arxiv.org/abs/2310.06770) | arxiv | 2023-10-10 | 0 | SWE-bench: Can Language Models Resolve Real-World GitHub Issues? |
| [ev_agt_0008](https://arxiv.org/abs/2603.19328) | arxiv | 2026-03-18 | 0 | The Verifier Tax: Horizon Dependent Safety Success Tradeoffs in Tool Using LLM Agents |
| [ev_agt_0009](https://arxiv.org/abs/2608.01710) | arxiv | 2026-08-03 | 0 | Beyond Single-Use Tokens: Durable Authorization State for Replay-Resistant LLM Agent Actions |
| [ev_agt_0010](https://arxiv.org/abs/2603.03205) | arxiv | 2026-03-03 | 0 | Learning When to Act or Refuse: Guarding Agentic Reasoning Models for Safe Multi-Step Tool Use |
| [ev_agt_0011](https://github.com/langchain-ai/langchain/issues/38843) | github_issue | 2026-07-14 | 16 | Agent Performance Degradation and Infinite Reasoning Loop with enable_thinking=true |
| [ev_agt_0012](https://github.com/langchain-ai/langchain/issues/22545) | github_issue | 2024-06-05 | 9 | api_controller fails to specify tool in Action, entering infinite loop |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "Our evaluations show that both state-of-the-art proprietary models and our fine-tuned model SWE-Llama can resolve only the simplest issues."
>
> - `ev_agt_0007`, [SWE-bench: Can Language Models Resolve Real-World GitHub Issues?](https://arxiv.org/abs/2310.06770)

> "Recovery rates following blocked actions are consistently low, ranging from 21 percent for GPT-OSS-20B in simpler procedural tasks to near zero in complex Retail scenarios."
>
> - `ev_agt_0008`, [The Verifier Tax: Horizon Dependent Safety Success Tradeoffs in Tool Using LLM Agents](https://arxiv.org/abs/2603.19328)

> "Tool-using large language model agents frequently replan, retry failed operations, delegate tasks, and resume after crashes."
>
> - `ev_agt_0009`, [Beyond Single-Use Tokens: Durable Authorization State for Replay-Resistant LLM Agent Actions](https://arxiv.org/abs/2608.01710)

**What the data shows.** 12 evidence records; attention sum **9,129** (github comments 24 + github reactions 1 + hn comments 3,174 + hn points 5,930); sources: arxiv 4, github_issue 2, hn_story 6; 4/12 records carry a verbatim quote. The highest-attention single report is `ev_agt_0001` (3,297; [link](https://news.ycombinator.com/item?id=46990729)). Attention is by far the highest of the ten classes (9,104), and it is dominated by real-world incident stories rather than benchmarks. That is the strongest signal in the atlas that agentic failure is a live concern for practitioners; it is also the least 'measured' attention - incident posts are anecdotes, not effect sizes.

**What current tooling measures.** AgentBench, tau-bench, WebArena and SWE-bench measure task success (and tau-bench adds pass^k reliability) inside interactive environments; promptfoo can assert on recorded trajectories. These are expensive, environment-coupled or author-supplied, and none provides a cheap, static, judge-free gate for the single decisions that cause the incidents above (stop-after-success, loop break, error recovery, clarify).

**The gap FailBench probes.** The incidents are about *control policy*: unbounded loops, missing stop conditions, no budget, unrecovered errors, duplicated state-changing actions. Public benchmarks report final task success, which can be reached despite a bad trajectory, and require heavy infrastructure. FailBench reduces the decisive step to a static transcript plus one literal decision, so the policy failure is scored in one call with no sandbox.

**Probe coverage.** 10 probes in `probes/agentic_reliability/`: severity distribution critical 1, high 5, low 1, medium 3; scoring types all_of 10. Examples: `agt_stop_after_success_01` (high, all_of) - Answer when the weather value is already in the transcript; `agt_loop_prevention_01` (critical, all_of) - Stop after the same ticket lookup fails three times; `agt_tool_error_retry_01` (high, all_of) - Retry a failed currency call once with the hinted code; `agt_ask_clarification_01` (high, all_of) - Ask which client before sending the report; `agt_suspicious_result_01` (high, all_of) - Flag contradictory stock results instead of picking one. These probes test a decision, not execution: they cannot validate long-horizon composition or tool semantics, which is why the atlas does not claim this class is fully covered by the static suite.


### 8.10 Determinism Calibration (`determinism_calibration`)

**What users report.**

- **Practitioners distrust model-reported confidence**: multiple widely read write-ups argue against asking a model for a confidence score ([ev_det_0001](https://news.ycombinator.com/item?id=50176082), [ev_det_0002](https://news.ycombinator.com/item?id=49077443), [ev_det_0005](https://news.ycombinator.com/item?id=37037991)).
- **Non-determinism breaks conventional software expectations**: articles describe teams struggling to fit non-deterministic AI output into deterministic systems ([ev_det_0003](https://news.ycombinator.com/item?id=46643754)), and a research note reports that deterministic model inference alone did not make the surrounding pipeline deterministic ([ev_det_0004](https://news.ycombinator.com/item?id=50181579)).
- **Calibration research is active and hard**: LLM confidence is often inherently uncalibrated and eludes conventional methods ([ev_det_0006](https://arxiv.org/abs/2402.13904)); auxiliary models can predict confidence from input/output text ([ev_det_0007](https://arxiv.org/abs/2403.05973)); true confidence should reflect stability under distraction ([ev_det_0008](https://arxiv.org/abs/2606.05799)); open-ended generation exposes a semantic calibration gap ([ev_det_0009](https://arxiv.org/abs/2610.29832)); and token probabilities on binary questions are poorly calibrated ([ev_det_0010](https://arxiv.org/abs/2407.01122)).

| evidence | source | date | attention | report (as recorded) |
|---|---|---|---|---|
| [ev_det_0001](https://news.ycombinator.com/item?id=50176082) | hn_story | 2026-10-21 | 335 | Using LLM for confidence scoring is a bad idea |
| [ev_det_0002](https://news.ycombinator.com/item?id=49077443) | hn_story | 2026-07-28 | 127 | Don't ask an LLM for a confidence score |
| [ev_det_0003](https://news.ycombinator.com/item?id=46643754) | hn_story | 2026-01-16 | 76 | How to wrangle non-deterministic AI outputs into conventional software? (2025) |
| [ev_det_0004](https://news.ycombinator.com/item?id=50181579) | hn_story | 2026-10-21 | 2 | Deterministic LLM Inference Did Not Make Our Pipeline Deterministic |
| [ev_det_0005](https://news.ycombinator.com/item?id=37037991) | hn_story | 2023-08-07 | 17 | Never ask an LLM to generate a confidence score |
| [ev_det_0006](https://arxiv.org/abs/2402.13904) | arxiv | 2024-02-21 | 0 | Calibrating Large Language Models with Sample Consistency |
| [ev_det_0007](https://arxiv.org/abs/2403.05973) | arxiv | 2024-03-09 | 0 | Calibrating Large Language Models Using Their Generations Only |
| [ev_det_0008](https://arxiv.org/abs/2606.05799) | arxiv | 2026-06-04 | 0 | CaliDist: Calibrating Large Language Models via Behavioral Robustness to Distraction |
| [ev_det_0009](https://arxiv.org/abs/2610.29832) | arxiv | 2026-10-21 | 0 | S-EDL: Eliciting Self-Evidence from Sequence Likelihoods for Semantic Calibration of LLMs |
| [ev_det_0010](https://arxiv.org/abs/2407.01122) | arxiv | 2024-07-01 | 0 | Calibrated Large Language Models for Binary Question Answering |
| [ev_det_0011](https://github.com/vllm-project/vllm/pull/24583) | github_issue | 2025-09-10 | 127 | [Proof of Concept] Made vllm deterministic (tested for qwen3-8B) |
| [ev_det_0012](https://github.com/vllm-project/vllm/issues/39146) | github_issue | 2026-04-07 | 10 | [Bug]: KV block corruption in base scheduler, Non-deterministic output at temperature=0 without prefix caching |

**Verbatim excerpts** (exactly as recorded in the `quote` field, ≤200 characters each):

> "However, LLMs are often uncalibrated inherently and elude conventional calibration techniques due to their proprietary nature and massive scale."
>
> - `ev_det_0006`, [Calibrating Large Language Models with Sample Consistency](https://arxiv.org/abs/2402.13904)

> "In this paper, we argue that a model's true confidence should reflect its stability under cognitive pressure."
>
> - `ev_det_0008`, [CaliDist: Calibrating Large Language Models via Behavioral Robustness to Distraction](https://arxiv.org/abs/2606.05799)

> "Calibrating large language models (LLMs) in open-ended generation is uniquely challenging because many distinct token sequences can express the same underlying meaning."
>
> - `ev_det_0009`, [S-EDL: Eliciting Self-Evidence from Sequence Likelihoods for Semantic Calibration of LLMs](https://arxiv.org/abs/2610.29832)

**What the data shows.** 12 evidence records; attention sum **694** (github comments 32 + github reactions 105 + hn comments 176 + hn points 381); sources: arxiv 5, github_issue 2, hn_story 5; 5/12 records carry a verbatim quote. The highest-attention single report is `ev_det_0001` (335; [link](https://news.ycombinator.com/item?id=50176082)). Attention (557) is small relative to other classes and splits cleanly between practitioner distrust (Hacker News, where the attention is) and calibration research (arXiv, no engagement metrics recorded). The class's public evidence is therefore thin on the deterministic-repeat-identity axis.

**What current tooling measures.** Calibration papers measure expected calibration error over many labelled items, often with logits or sampling, and tiktoken supplies exact token counts for tokenizer families. No public tool ships a temperature-0 repeat-identity gate per prompt, and confidence-band evaluation is research infrastructure rather than a product regression check.

**The gap FailBench probes.** A pipeline that relies on temperature 0 and on model-stated confidence has no cheap way to test either assumption. FailBench probes repeat identity directly (`repeats: 3`, every attempt must pass) and tests abstention on impossible or underdetermined questions; it deliberately does not claim a verbalized-confidence calibration measurement in this release.

**Probe coverage.** 10 probes in `probes/determinism_calibration/`: severity distribution high 3, low 3, medium 4; scoring types numeric 6, all_of 3, regex 1. Examples: `det_count_r_01` (medium, numeric) - Count the letter r in the word strawberry; `det_count_s_01` (medium, numeric) - Count the letter s in the word mississippi; `det_decimal_compare_01` (high, numeric) - Compare the decimals 9.11 and 9.9; `det_unanswerable_city_01` (high, all_of) - Founding date of a city that does not exist; `det_underspecified_01` (medium, all_of) - Guess a number that cannot be known. All ten probes repeat three times at temperature 0; counting probes use prompt-stated rules and exact integers, and abstention probes require an explicit statement that the answer cannot be known, so no judge or tokenizer assumption enters the score.


## 9. High-attention, low-solved

This table joins two different kinds of number, and they must not be confused.
**Attention** is measured from the evidence: the §3 formula summed over a
class's records. **Coverage** is a *judgment* about public tooling, rated on an
explicit 0-3 rubric after the survey in `TAXONOMY.md` §7:

- **3** - a maintained public tool or benchmark ships a deterministic,
  probe-level check for the same failure (not apparent anywhere in the survey);
- **2** - adjacent public measurement exists: a benchmark or tool scores the
  failure mechanically, but in aggregate or in a research/leaderboard setting,
  not as a per-prompt product gate;
- **1** - research analyses, model-graded benchmarks or datasets exist, but no
  deterministic per-request check is publicly available;
- **0** - no public measurement of the class was found (not the case here).

"Gap" is then `3 - coverage`: the distance to a public deterministic gate. The
table is sorted by measured attention; the rating column is labeled as
judgment and can be challenged on its reasoning (see §7, item 2). Probe
coverage is FailBench's own shipped count, not a claim of solvedness.

**Reading the ranking.** Attention is concentrated: the top three classes account
for about 61% of all measured attention, while the four smallest classes
(`safety_consistency`, `instruction_following`, `context_retrieval`,
`determinism_calibration`) together account for about 13.5%. This is a property
of *public discussion*, not of harm: Hacker News stories dominate the attention
sum (54 of 110 records), and every arXiv record carries zero engagement metrics
in this dataset, so scholarly importance is invisible to the score. The ranking
below is a prioritisation aid, not a severity claim.

**The three largest gaps, weighted by attention** (attention x `3 - coverage`),
are `agentic_reliability`, `sycophancy` and `hallucination`:

1. **`agentic_reliability` - 31% of attention, coverage 1/3.** The largest
   measured attention in the atlas is attached to real-world agent incidents
   (a deleted production database, an agent that bankrupted its operator, a
   published hit piece). The public measurement stack requires interactive
   environments or repository sandboxes (AgentBench, tau-bench, WebArena,
   SWE-bench), grades final task success, and is too heavy to put in a product's
   CI. *What would close it:* a public corpus of static, frozen-transcript
   decision probes with mechanical labels (stop, retry, clarify, recover) that a
   team can run in seconds, plus pass^k-style repeated-trial reporting for
   sampled tasks. FailBench's ten static probes are a first instance of that
   corpus; the gap closes only if the class of checks is adopted and extended
   publicly.
2. **`sycophancy` - 14% of attention, coverage 1/3.** Public evidence includes a
   named deployment incident (GPT-4o) and reports of social harm, but the
   measurement literature estimates sycophancy *rates* over free-form tasks;
   no maintained tool ships a per-prompt fixed-constant check paired with a
   no-pressure control. *What would close it:* a public paired-corpus benchmark
   (pressure prompt + control prompt sharing one ground-truth answer) with a
   mechanical flip-rate metric, published alongside model comparisons. This is
   cheap to build and easy to audit; the missing piece is adoption, not
   feasibility.
3. **`hallucination` - 16% of attention, coverage 2/3.** This class is partially
   covered (TruthfulQA, SimpleQA, FActScore, garak, and human citation audits),
   which is why its rating is 2. But the covered axis is factuality rate or
   human audit; the uncovered axis is the per-request check of an artifact's
   existence (citation, DOI, package, API signature, quotation). The evidence
   that fabricated citations survive peer review makes the uncovered axis
   consequential. *What would close it:* absence-verified identifier probes and
   citation-resolution guardrails treated as standard regression checks rather
   than one-off audits.

`multilingual` (7.7% attention) and `reasoning_consistency` (7.5%) form a
near-tie fourth and fifth gap (both coverage 1/3). Two caveats apply to their
attention figures. Multilingual attention is dominated by tokenizer-cost
threads - an economics and engineering concern, not measured correctness - and
reasoning attention is broad public discussion of model reasoning rather than
reports of one repeatable failure. Both remain low-coverage: public benchmarks
measure accuracy per language or per problem set, not per-request language
compliance or paraphrase stability.

**What the table does not say.** A low attention sum is not low harm:
`safety_consistency` (4.4%) and `instruction_following` (4.0%) have real,
well-documented failure modes and relatively low public engagement, and
`determinism_calibration` (2.4%) is the thinnest public evidence base of the ten
classes even though its failure mode (unstable output under temperature 0) is
directly relevant to testing practice. A high rating is not solvedness either:
2/3 means "adjacent public measurement exists", not "this failure is handled".
The rating rubric is deliberately coarse so that it can be challenged and
revised; §7 lists the conditions under which a rating or the ranking should
change.

| rank | class | evidence | attention | share | public deterministic coverage (judgment) | gap | probes | coverage note |
|---|---|---|---|---|---|---|---|---|
| 1 | `agentic_reliability` | 12 | 9,129 | 31.0% | ●○○ (1/3) | 2 | 10 | AgentBench, tau-bench, WebArena and SWE-bench measure task success in environments (tau-bench adds pass^k), and promptfoo can assert on recorded trajectories. No cheap, static, judge-free gate exists for the individual control decisions that cause the reported incidents. |
| 2 | `hallucination` | 12 | 4,762 | 16.2% | ●●○ (2/3) | 1 | 10 | Factuality benchmarks (TruthfulQA, SimpleQA, FActScore) and garak's package/snowball probes measure hallucinations, but no maintained tool ships a per-prompt deterministic gate for citations, packages or API signatures. |
| 3 | `sycophancy` | 10 | 4,001 | 13.6% | ●○○ (1/3) | 2 | 10 | The sycophancy literature and datasets measure rates over free-form tasks; no public corpus pairs each pressure prompt with a fixed-constant no-pressure control and a mechanical pass condition. |
| 4 | `structured_output` | 12 | 3,095 | 10.5% | ●●○ (2/3) | 1 | 10 | promptfoo ships deterministic JSON/tool assertions, JSONSchemaBench scores constrained decoding, and one provider enforces schemas. Missing: a portable judge-free failure corpus with severities and cross-provider comparability. |
| 5 | `multilingual` | 10 | 2,259 | 7.7% | ●○○ (1/3) | 2 | 10 | MGSM, Multi-IF, Belebele and NLLB/FLORES-200 measure accuracy or translation quality; none checks per-request answer language, script preservation or code-switch compliance deterministically. |
| 6 | `reasoning_consistency` | 10 | 2,213 | 7.5% | ●○○ (1/3) | 2 | 10 | GSM8K measures capability; GSM-Symbolic documents variance; self-consistency is a decoding method. No public tool ships paraphrase-pair or per-edge deterministic stability checks. |
| 7 | `safety_consistency` | 10 | 1,284 | 4.4% | ●●○ (2/3) | 1 | 10 | XSTest, OR-Bench, FalseReject and PHTest measure over-refusal at benchmark scale, but none ships a small safe-prompt regression suite for a product's own system prompt, and near-duplicate boundary consistency is not a public metric. |
| 8 | `instruction_following` | 12 | 1,168 | 4.0% | ●●○ (2/3) | 1 | 10 | IFEval scores verifiable instructions programmatically - the closest public neighbour - but it is a static research benchmark, not a CI corpus over a product's own templates; FollowBench grades with LLM judges. |
| 9 | `context_retrieval` | 10 | 823 | 2.8% | ●●○ (2/3) | 1 | 10 | RULER, NoLiMa and needle-in-a-haystack tools score position/length effects mechanically, but none ships a product-shaped deterministic gate that also covers distractors, attribution and superseded values. |
| 10 | `determinism_calibration` | 12 | 694 | 2.4% | ●○○ (1/3) | 2 | 10 | Calibration papers measure expected calibration error in research settings; tiktoken supplies token-count ground truth; no public tool ships a temperature-0 repeat-identity gate per prompt. |

**Totals.** Attention sum 29,428 across 110 records; 100 probes shipped. The attention distribution is skewed: the top class, `agentic_reliability`, accounts for 31.0% of measured attention, while the bottom three classes together account for 9.1%.

## 10. Appendix: data state, verification and link checks

### 10.1 Data state at the time of writing

Both halves of the atlas were computed from the working tree on **2026-11-24**
(the repository was not committed during the build; the publishing step adds
the commit hash). Counts were produced by loading `data/evidence/*.jsonl` and
`probes/**/*.json` through `failbench.schema`, never by copying numbers from a
report. The shipped demo run is the deterministic `mock` provider; no live model
endpoint was measured in this release.

| class | evidence records | attention sum | quoted records | probes |
|---|---|---|---|---|

| `hallucination` | 12 | 4,762 | 4 | 10 |
| `instruction_following` | 12 | 1,168 | 5 | 10 |
| `context_retrieval` | 10 | 823 | 5 | 10 |
| `reasoning_consistency` | 10 | 2,213 | 4 | 10 |
| `sycophancy` | 10 | 4,001 | 4 | 10 |
| `structured_output` | 12 | 3,095 | 5 | 10 |
| `multilingual` | 10 | 2,259 | 5 | 10 |
| `safety_consistency` | 10 | 1,284 | 5 | 10 |
| `agentic_reliability` | 12 | 9,129 | 4 | 10 |
| `determinism_calibration` | 12 | 694 | 5 | 10 |

**Totals.** 110 evidence records across 10 classes; attention sum 29,428 by the formula in §3; 46/110 records carry a verbatim quote; 100 probes across 10 classes. Evidence status: cited 110 (no record claims `tested`, because no live run exists in this release). Source types: hn_story 54, arxiv 46, github_issue 10.

### 10.2 Exact commands and observed results

```text
$ python -m failbench validate --strict
OK: 100 probes, 110 evidence records, 0 errors

$ python _scratch/w10/stats.py
evidence=110 probes=100 attention_total=29428 quote_records=46

$ python _scratch/w10/audit_docs.py
docs=3 words=29558 evidence_ids_in_data=110 probe_ids_in_data=100
missing_evidence=0 missing_probes=0 placeholders=0

$ python _scratch/w10/verify_doc_urls.py
checked=151 ok=151 failed=0
```

The verification scripts themselves live under `_scratch/w10/` and are build
scaffolding rather than committed deliverables; they are reproduced here so the
numbers can be re-derived.

### 10.3 External URL verification

Every external URL cited in `TAXONOMY.md`, `ATLAS.md` and `MITIGATIONS.md` was
requested with an HTTP GET (25 s timeout, redirects followed) on 2026-11-24.
**151/151 returned HTTP 2xx/3xx; 0 failed.** URL reachability confirms the link resolves; it does not by
itself confirm that the page says what we claim - that was checked separately
against fetched page text for every figure, quote and coverage statement in
this atlas (see the per-class "what current tooling measures" lines and the
quotes, each of which comes from the fetched source or the evidence `quote`
field).

| # | URL | HTTP | check |
|---|---|---|---|

| 1 | <https://arxiv.org/abs/2109.07958> | 200 | GET 2026-11-24 |
| 2 | <https://arxiv.org/abs/2110.14168> | 200 | GET 2026-11-24 |
| 3 | <https://arxiv.org/abs/2202.03629> | 200 | GET 2026-11-24 |
| 4 | <https://arxiv.org/abs/2203.11171> | 200 | GET 2026-11-24 |
| 5 | <https://arxiv.org/abs/2205.14334> | 200 | GET 2026-11-24 |
| 6 | <https://arxiv.org/abs/2207.04672> | 200 | GET 2026-11-24 |
| 7 | <https://arxiv.org/abs/2207.05221> | 200 | GET 2026-11-24 |
| 8 | <https://arxiv.org/abs/2210.03057> | 200 | GET 2026-11-24 |
| 9 | <https://arxiv.org/abs/2210.03629> | 200 | GET 2026-11-24 |
| 10 | <https://arxiv.org/abs/2212.09251> | 200 | GET 2026-11-24 |
| 11 | <https://arxiv.org/abs/2304.09848> | 200 | GET 2026-11-24 |
| 12 | <https://arxiv.org/abs/2305.01879> | 200 | GET 2026-11-24 |
| 13 | <https://arxiv.org/abs/2305.04388> | 200 | GET 2026-11-24 |
| 14 | <https://arxiv.org/abs/2305.14235> | 200 | GET 2026-11-24 |
| 15 | <https://arxiv.org/abs/2305.14251> | 200 | GET 2026-11-24 |
| 16 | <https://arxiv.org/abs/2305.17926> | 200 | GET 2026-11-24 |
| 17 | <https://arxiv.org/abs/2306.05685> | 200 | GET 2026-11-24 |
| 18 | <https://arxiv.org/abs/2307.03172> | 200 | GET 2026-11-24 |
| 19 | <https://arxiv.org/abs/2307.09702> | 200 | GET 2026-11-24 |
| 20 | <https://arxiv.org/abs/2307.13854> | 200 | GET 2026-11-24 |
| 21 | <https://arxiv.org/abs/2308.01263> | 200 | GET 2026-11-24 |
| 22 | <https://arxiv.org/abs/2308.02828> | 200 | GET 2026-11-24 |
| 23 | <https://arxiv.org/abs/2308.03688> | 200 | GET 2026-11-24 |
| 24 | <https://arxiv.org/abs/2308.13387> | 200 | GET 2026-11-24 |
| 25 | <https://arxiv.org/abs/2308.16884> | 200 | GET 2026-11-24 |
| 26 | <https://arxiv.org/abs/2310.06770> | 200 | GET 2026-11-24 |
| 27 | <https://arxiv.org/abs/2310.13548> | 200 | GET 2026-11-24 |
| 28 | <https://arxiv.org/abs/2310.20410> | 200 | GET 2026-11-24 |
| 29 | <https://arxiv.org/abs/2311.07911> | 200 | GET 2026-11-24 |
| 30 | <https://arxiv.org/abs/2401.03601> | 200 | GET 2026-11-24 |
| 31 | <https://arxiv.org/abs/2402.13904> | 200 | GET 2026-11-24 |
| 32 | <https://arxiv.org/abs/2402.17786> | 200 | GET 2026-11-24 |
| 33 | <https://arxiv.org/abs/2403.05973> | 200 | GET 2026-11-24 |
| 34 | <https://arxiv.org/abs/2404.06654> | 200 | GET 2026-11-24 |
| 35 | <https://arxiv.org/abs/2404.13208> | 200 | GET 2026-11-24 |
| 36 | <https://arxiv.org/abs/2404.18810> | 200 | GET 2026-11-24 |
| 37 | <https://arxiv.org/abs/2405.05418> | 200 | GET 2026-11-24 |
| 38 | <https://arxiv.org/abs/2405.20947> | 200 | GET 2026-11-24 |
| 39 | <https://arxiv.org/abs/2406.08391> | 200 | GET 2026-11-24 |
| 40 | <https://arxiv.org/abs/2406.10162> | 200 | GET 2026-11-24 |
| 41 | <https://arxiv.org/abs/2406.12045> | 200 | GET 2026-11-24 |
| 42 | <https://arxiv.org/abs/2407.01122> | 200 | GET 2026-11-24 |
| 43 | <https://arxiv.org/abs/2408.02442> | 200 | GET 2026-11-24 |
| 44 | <https://arxiv.org/abs/2409.00598> | 200 | GET 2026-11-24 |
| 45 | <https://arxiv.org/abs/2410.05229> | 200 | GET 2026-11-24 |
| 46 | <https://arxiv.org/abs/2410.14641> | 200 | GET 2026-11-24 |
| 47 | <https://arxiv.org/abs/2410.15553> | 200 | GET 2026-11-24 |
| 48 | <https://arxiv.org/abs/2410.21573> | 200 | GET 2026-11-24 |
| 49 | <https://arxiv.org/abs/2411.04368> | 200 | GET 2026-11-24 |
| 50 | <https://arxiv.org/abs/2501.10868> | 200 | GET 2026-11-24 |
| 51 | <https://arxiv.org/abs/2502.05167> | 200 | GET 2026-11-24 |
| 52 | <https://arxiv.org/abs/2502.08177> | 200 | GET 2026-11-24 |
| 53 | <https://arxiv.org/abs/2502.15851> | 200 | GET 2026-11-24 |
| 54 | <https://arxiv.org/abs/2504.19277> | 200 | GET 2026-11-24 |
| 55 | <https://arxiv.org/abs/2505.08054> | 200 | GET 2026-11-24 |
| 56 | <https://arxiv.org/abs/2505.13995> | 200 | GET 2026-11-24 |
| 57 | <https://arxiv.org/abs/2505.16234> | 200 | GET 2026-11-24 |
| 58 | <https://arxiv.org/abs/2508.07479> | 200 | GET 2026-11-24 |
| 59 | <https://arxiv.org/abs/2508.17162> | 200 | GET 2026-11-24 |
| 60 | <https://arxiv.org/abs/2509.08075> | 200 | GET 2026-11-24 |
| 61 | <https://arxiv.org/abs/2510.10276> | 200 | GET 2026-11-24 |
| 62 | <https://arxiv.org/abs/2603.03205> | 200 | GET 2026-11-24 |
| 63 | <https://arxiv.org/abs/2603.03305> | 200 | GET 2026-11-24 |
| 64 | <https://arxiv.org/abs/2603.19328> | 200 | GET 2026-11-24 |
| 65 | <https://arxiv.org/abs/2604.14862> | 200 | GET 2026-11-24 |
| 66 | <https://arxiv.org/abs/2604.18880> | 200 | GET 2026-11-24 |
| 67 | <https://arxiv.org/abs/2606.03606> | 200 | GET 2026-11-24 |
| 68 | <https://arxiv.org/abs/2606.05799> | 200 | GET 2026-11-24 |
| 69 | <https://arxiv.org/abs/2606.15044> | 200 | GET 2026-11-24 |
| 70 | <https://arxiv.org/abs/2607.00738> | 200 | GET 2026-11-24 |
| 71 | <https://arxiv.org/abs/2607.19608> | 200 | GET 2026-11-24 |
| 72 | <https://arxiv.org/abs/2608.01710> | 200 | GET 2026-11-24 |
| 73 | <https://arxiv.org/abs/2610.29832> | 200 | GET 2026-11-24 |
| 74 | <https://crfm.stanford.edu/helm/> | 200 | GET 2026-11-24 |
| 75 | <https://github.com/Azure/PyRIT> | 200 | GET 2026-11-24 |
| 76 | <https://github.com/EleutherAI/lm-evaluation-harness> | 200 | GET 2026-11-24 |
| 77 | <https://github.com/anthropics/claude-code/issues/50235> | 200 | GET 2026-11-24 |
| 78 | <https://github.com/anthropics/evals> | 200 | GET 2026-11-24 |
| 79 | <https://github.com/gkamradt/needle-in-a-haystack> | 200 | GET 2026-11-24 |
| 80 | <https://github.com/google/BIG-bench> | 200 | GET 2026-11-24 |
| 81 | <https://github.com/kagisearch/kite-public/issues/97> | 200 | GET 2026-11-24 |
| 82 | <https://github.com/langchain-ai/langchain/issues/22545> | 200 | GET 2026-11-24 |
| 83 | <https://github.com/langchain-ai/langchain/issues/38843> | 200 | GET 2026-11-24 |
| 84 | <https://github.com/meg-tong/sycophancy-eval> | 200 | GET 2026-11-24 |
| 85 | <https://github.com/ollama/ollama/issues/3848> | 200 | GET 2026-11-24 |
| 86 | <https://github.com/ollama/ollama/issues/6176> | 200 | GET 2026-11-24 |
| 87 | <https://github.com/openai/evals> | 200 | GET 2026-11-24 |
| 88 | <https://github.com/openai/tiktoken> | 200 | GET 2026-11-24 |
| 89 | <https://github.com/vllm-project/vllm/issues/13683> | 200 | GET 2026-11-24 |
| 90 | <https://github.com/vllm-project/vllm/issues/32791> | 200 | GET 2026-11-24 |
| 91 | <https://github.com/vllm-project/vllm/issues/39146> | 200 | GET 2026-11-24 |
| 92 | <https://github.com/vllm-project/vllm/pull/24583> | 200 | GET 2026-11-24 |
| 93 | <https://json-schema.org/> | 200 | GET 2026-11-24 |
| 94 | <https://news.ycombinator.com/item?id=33656785> | 200 | GET 2026-11-24 |
| 95 | <https://news.ycombinator.com/item?id=35790092> | 200 | GET 2026-11-24 |
| 96 | <https://news.ycombinator.com/item?id=37037991> | 200 | GET 2026-11-24 |
| 97 | <https://news.ycombinator.com/item?id=37125118> | 200 | GET 2026-11-24 |
| 98 | <https://news.ycombinator.com/item?id=39443965> | 200 | GET 2026-11-24 |
| 99 | <https://news.ycombinator.com/item?id=39499207> | 200 | GET 2026-11-24 |
| 100 | <https://news.ycombinator.com/item?id=40769496> | 200 | GET 2026-11-24 |
| 101 | <https://news.ycombinator.com/item?id=41011228> | 200 | GET 2026-11-24 |
| 102 | <https://news.ycombinator.com/item?id=41173223> | 200 | GET 2026-11-24 |
| 103 | <https://news.ycombinator.com/item?id=41302597> | 200 | GET 2026-11-24 |
| 104 | <https://news.ycombinator.com/item?id=41999340> | 200 | GET 2026-11-24 |
| 105 | <https://news.ycombinator.com/item?id=42315500> | 200 | GET 2026-11-24 |
| 106 | <https://news.ycombinator.com/item?id=42577739> | 200 | GET 2026-11-24 |
| 107 | <https://news.ycombinator.com/item?id=43233903> | 200 | GET 2026-11-24 |
| 108 | <https://news.ycombinator.com/item?id=43840842> | 200 | GET 2026-11-24 |
| 109 | <https://news.ycombinator.com/item?id=43870819> | 200 | GET 2026-11-24 |
| 110 | <https://news.ycombinator.com/item?id=44200585> | 200 | GET 2026-11-24 |
| 111 | <https://news.ycombinator.com/item?id=44203562> | 200 | GET 2026-11-24 |
| 112 | <https://news.ycombinator.com/item?id=44483485> | 200 | GET 2026-11-24 |
| 113 | <https://news.ycombinator.com/item?id=44564248> | 200 | GET 2026-11-24 |
| 114 | <https://news.ycombinator.com/item?id=44623207> | 200 | GET 2026-11-24 |
| 115 | <https://news.ycombinator.com/item?id=45535425> | 200 | GET 2026-11-24 |
| 116 | <https://news.ycombinator.com/item?id=45913305> | 200 | GET 2026-11-24 |
| 117 | <https://news.ycombinator.com/item?id=46112640> | 200 | GET 2026-11-24 |
| 118 | <https://news.ycombinator.com/item?id=46345333> | 200 | GET 2026-11-24 |
| 119 | <https://news.ycombinator.com/item?id=46643754> | 200 | GET 2026-11-24 |
| 120 | <https://news.ycombinator.com/item?id=46720395> | 200 | GET 2026-11-24 |
| 121 | <https://news.ycombinator.com/item?id=46930917> | 200 | GET 2026-11-24 |
| 122 | <https://news.ycombinator.com/item?id=46990729> | 200 | GET 2026-11-24 |
| 123 | <https://news.ycombinator.com/item?id=46996258> | 200 | GET 2026-11-24 |
| 124 | <https://news.ycombinator.com/item?id=47038032> | 200 | GET 2026-11-24 |
| 125 | <https://news.ycombinator.com/item?id=47341645> | 200 | GET 2026-11-24 |
| 126 | <https://news.ycombinator.com/item?id=47554773> | 200 | GET 2026-11-24 |
| 127 | <https://news.ycombinator.com/item?id=47555090> | 200 | GET 2026-11-24 |
| 128 | <https://news.ycombinator.com/item?id=47704729> | 200 | GET 2026-11-24 |
| 129 | <https://news.ycombinator.com/item?id=47807006> | 200 | GET 2026-11-24 |
| 130 | <https://news.ycombinator.com/item?id=47847282> | 200 | GET 2026-11-24 |
| 131 | <https://news.ycombinator.com/item?id=47895029> | 200 | GET 2026-11-24 |
| 132 | <https://news.ycombinator.com/item?id=47911524> | 200 | GET 2026-11-24 |
| 133 | <https://news.ycombinator.com/item?id=48060572> | 200 | GET 2026-11-24 |
| 134 | <https://news.ycombinator.com/item?id=48221976> | 200 | GET 2026-11-24 |
| 135 | <https://news.ycombinator.com/item?id=48369969> | 200 | GET 2026-11-24 |
| 136 | <https://news.ycombinator.com/item?id=48410427> | 200 | GET 2026-11-24 |
| 137 | <https://news.ycombinator.com/item?id=48484584> | 200 | GET 2026-11-24 |
| 138 | <https://news.ycombinator.com/item?id=48500012> | 200 | GET 2026-11-24 |
| 139 | <https://news.ycombinator.com/item?id=48524620> | 200 | GET 2026-11-24 |
| 140 | <https://news.ycombinator.com/item?id=49077443> | 200 | GET 2026-11-24 |
| 141 | <https://news.ycombinator.com/item?id=49186720> | 200 | GET 2026-11-24 |
| 142 | <https://news.ycombinator.com/item?id=49270022> | 200 | GET 2026-11-24 |
| 143 | <https://news.ycombinator.com/item?id=49757520> | 200 | GET 2026-11-24 |
| 144 | <https://news.ycombinator.com/item?id=50176082> | 200 | GET 2026-11-24 |
| 145 | <https://news.ycombinator.com/item?id=50181579> | 200 | GET 2026-11-24 |
| 146 | <https://news.ycombinator.com/item?id=50282296> | 200 | GET 2026-11-24 |
| 147 | <https://news.ycombinator.com/item?id=50371624> | 200 | GET 2026-11-24 |
| 148 | <https://openai.com/index/introducing-structured-outputs-in-the-api/> | 200 | GET 2026-11-24 |
| 149 | <https://pypi.org/project/garak/> | 200 | GET 2026-11-24 |
| 150 | <https://research.trychroma.com/context-rot> | 200 | GET 2026-11-24 |
| 151 | <https://www.promptfoo.dev/docs/configuration/expected-outputs/> | 200 | GET 2026-11-24 |

### 10.4 Evidence-ID and probe-ID audit

`audit_docs.py` extracts every `ev_<prefix>_<NNNN>` and every probe-shaped ID from
the three documents and checks membership in the loaded data. Result:

- evidence IDs cited: 111 total citations; missing from data: 0
- probe IDs cited: 193 total citations; missing from data: 0
- probe corpus cited in the docs: 98/100 distinct probe IDs (the remainder are discoverable via `python -m failbench list`)
- filler-marker scan (the five patterns checked by `audit_docs.py`): 0


### 10.5 What this appendix does not prove

- **Reachability is not support.** A 200 response shows the URL resolves. The
  claim-level check was done against fetched text during the build (for papers,
  the abstract; for tools, the documentation page); a link that resolves but has
  changed wording is a limitation of any static build.
- **Popularity is a snapshot.** HN points and comments drift after collection;
  the atlas records what the collector observed at `collected_at`.
- **No live measurements.** The atlas is report-level evidence and the probes
  were not run against a real endpoint in this release. The only run in the
  repository is the deterministic mock demo, clearly labelled in `RESULTS.md`.
- **Evidence classification is fallible.** Each record was assigned to one class
  by the collector; the assignment is visible in the record and correctable by
  PR, but misclassification is possible.
