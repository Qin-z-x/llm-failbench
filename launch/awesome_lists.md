# Awesome-list submissions (draft, not posted)

**Project:** FailBench v0.2.0 (pre-release) — *The evidence-backed, judge-free failure probe kit for LLMs.*
**Prepared:** 2026-11-24 · **Owner:** repo owner (W7 draft; nothing here has been posted or emailed)
**Scope:** 5 real awesome lists / community indexes where a judge-free LLM failure-probe benchmark can
legitimately be submitted. Vvkmnn, danielrosehill and tensorchord are currently active; benchflow-ai is
active but its inclusion bar means the submission should wait; onejune2018 is stale and optional.

> **Single substitution:** every suggested line below uses the token `https://github.com/Qin-z-x/llm-failbench`. The owner replaces
> `https://github.com/Qin-z-x/llm-failbench` with the final public repo URL after publishing. That is the only substitution needed for
> the simple one-line lists; on the two table lists (items 2 and 3) the same URL path also has to fill the
> two shields.io badge cells, as noted there. No live GitHub URL is invented in this file, and the project
> is **not** claimed to be listed anywhere yet.

## Hard rules for these submissions

- Submit only **after** the public repo exists (a PR with a dead `https://github.com/Qin-z-x/llm-failbench` will be closed).
- **One PR per list**, in that list's own format, from the owner's own account. Do not ask anyone to
  upvote/star/comment; no fake accounts, no vote rings.
- **Disclose self-authorship** in the PR body (required by some lists, good practice everywhere).
- **Badges are list format, not star requests.** Two suggested rows use the target lists' own star/status badge cells; that is the lists' table format, not a request for stars, and the owner must never promote them as one.
- **State pre-release status honestly** where a description allows it; never claim users, stars,
  benchmarks, or real-model measurements. The committed demo results come from the deterministic mock
  provider, so the description must not imply measured model quality.
- Do not submit to SEO link-farms, "star if you like it" lists, template-generated list orgs, or paid
  directories. Do not re-submit after rejection; one polite follow-up at most.
- Match the surrounding style; do not reformat existing entries or reorder tables.

## Verification table (verified in-session from the build machine, 2026-11-24)

The session's `web_fetch` tool could not reach `raw.githubusercontent.com` or GitHub HTML pages from this
sandbox (connection errors), so every row below was verified with direct HTTPS requests to the GitHub API
and raw file endpoints from the build machine, and README/CONTRIBUTING text quoted in this file was read
from those same raw files in this session. Canonical `https://github.com/<owner>/<repo>` URLs are given for
each entry because that is the address a PR must target; their HTML pages were not fetchable from this
sandbox, so repo identity/activity is evidenced by the `api.github.com/repos/…` rows below.

| URL (verified in-session) | HTTP status | Date | What I observed |
|---|---|---|---|
| https://api.github.com/repos/Vvkmnn/awesome-ai-eval | 200 | 2026-11-24 | Real repo, 127★, 65 forks, default branch `main`, pushed 2026-11-01, license CC0-1.0, `archived: false`, topics include `llm-evaluation`, `benchmarks`. |
| https://api.github.com/repos/Vvkmnn/awesome-ai-eval/readme | 200 | 2026-11-24 | `README.md`, 30,357 bytes; sections: Benchmarks (Agents / General / Long-Context / Multimodal / Safety / Specialized), Leaderboards, Platforms, Resources, Tools. |
| https://api.github.com/repos/Vvkmnn/awesome-ai-eval/contents/CONTRIBUTING.md | 200 | 2026-11-24 | `CONTRIBUTING.md`, 1,408 bytes; Scope / Placement / Format / Pull requests sections (quoted below). |
| https://api.github.com/repos/danielrosehill/Awesome-AI-Evaluations-Tools | 200 | 2026-11-24 | Real repo, 29★, 27 forks, default branch `master`, pushed 2026-11-23, `archived: false`; license metadata `null` (README itself claims CC0). |
| https://api.github.com/repos/danielrosehill/Awesome-AI-Evaluations-Tools/contents/ | 200 | 2026-11-24 | Root: `README.md` (41,215 B), `data/` (weekly CSV), `scripts/`, `.github/`; **no CONTRIBUTING.md**. |
| https://api.github.com/repos/tensorchord/Awesome-LLMOps | 200 | 2026-11-24 | Real repo, 5,982★, 1,395 forks, default `main`, pushed 2026-11-16, CC0-1.0, `archived: false`, `web_commit_signoff_required: true`. |
| https://api.github.com/repos/tensorchord/Awesome-LLMOps/readme | 200 | 2026-11-24 | `README.md`, 249,922 bytes; table-based categories incl. `LLMOps` with eval/CI tools. |
| https://api.github.com/repos/tensorchord/Awesome-LLMOps/contents/contributing.md | 200 | 2026-11-24 | `contributing.md`, 824 bytes; contribution guidelines (quoted below). |
| https://api.github.com/repos/benchflow-ai/awesome-evals | 200 | 2026-11-24 | Real canonical repo, 1,049★, 159 forks, default `main`, pushed 2026-11-04, 94 open issues, `archived: false`. |
| https://api.github.com/repos/benchflow-ai/awesome-evals/readme | 200 | 2026-11-24 | `README.md`, 150,466 bytes; "Awesome Agent Evals", 12 numbered sections incl. §5a frameworks and §6 benchmark-vs-eval. |
| https://api.github.com/repos/benchflow-ai/awesome-evals/contents/CONTRIBUTING.md | 200 | 2026-11-24 | `CONTRIBUTING.md`, 2,532 bytes; what-belongs / bar-for-inclusion / format / how sections (quoted below). |
| https://api.github.com/repos/onejune2018/Awesome-LLM-Eval | 200 | 2026-11-24 | Real repo, 661★, 122 forks, default `main`, pushed **2025-11-24** (one year stale), 84 open issues, MIT, `archived: false`. |
| https://api.github.com/repos/onejune2018/Awesome-LLM-Eval/readme | 200 | 2026-11-24 | `README.md`, 225,146 bytes; sections incl. `Datasets or Benchmarks > General` table and `Tools`. |
| https://api.github.com/repos/onejune2018/Awesome-LLM-Eval/contents/CONTRIBUTING.md | **404** | 2026-11-24 | No `CONTRIBUTING.md` file in the repo. |
| https://api.github.com/repos/alopatenko/LLMEvaluation | 200 | 2026-11-24 | Real repo, 208★, pushed 2026-11-14, discussions enabled — considered, not recommended yet. |
| https://api.github.com/repos/alopatenko/LLMEvaluation/contents/ | 200 | 2026-11-24 | Root has `README.md` (155,444 B); **no CONTRIBUTING.md**. |
| https://api.github.com/repos/brandonhimpfen/awesome-ai-benchmarks-evaluation | 200 | 2026-11-24 | Redirects to organization-owned `awelist/awesome-ai-benchmarks-evaluation` (org `awelist`, created 2025-11-29, 14★, homepage `https://lnktr.net/awesome` which is a link directory) — excluded as a link-farm-style list, not a community-curated one with a review bar. |

---

## 1. Vvkmnn/awesome-ai-eval — **recommended first submission**

- **Name / canonical URL:** Awesome AI Eval — https://github.com/Vvkmnn/awesome-ai-eval
- **Verified:** repo API 200 (127★, 65 forks, pushed 2026-11-01, CC0-1.0, not archived); README via API 200
  (30,357 B); CONTRIBUTING.md via API 200 (1,408 B). List is real and active; contribution instructions are
  explicit.
- **Relevance:** target section **Benchmarks → General** (the section currently lists AGIEval, ARC-AGI-2/3,
  CommonGen-Eval, DyVal, GDPval, GPQA, IFEval, LiveBench, StructEval, …). The list's own scope sentence
  (CONTRIBUTING.md): *"The list covers the evaluation of AI systems: language models, RAG pipelines, and
  agents. Frameworks, benchmarks, datasets, leaderboards, platforms, papers, and guides are in scope."*
  FailBench is a benchmark, so it is squarely in scope.
- **Contribution rules (verified CONTRIBUTING.md):** entry format is
  ``- [Name](project-url) - What it is and what it does.``; one line, **20 words or fewer**, capital
  start, period end; **no badges/images/bold/emoji**; state what it does and leave out "best/powerful/simple"
  and changing counts; HTTPS link, no tracking params; **alphabetical order inside one section**; one entry
  per PR titled `Add Name`; change only the file the entry belongs in; check it is not already in
  `README.md` or `archive.md`; run `pnpm install` and `pnpm lint` before opening the PR. PRs are accepted.
- **Exact suggested line** (alphabetically between `DyVal` and `GDPval`):
  ```markdown
  - [FailBench](https://github.com/Qin-z-x/llm-failbench) - Deterministic, judge-free failure probes across 10 LLM failure classes with mechanical scoring.
  ```
  (12 words after the dash — under the 20-word cap. No badge, no emoji, no changing metric.)
- **Suggested PR body (one paragraph):**
  > Hi — I maintain FailBench (https://github.com/Qin-z-x/llm-failbench), a small MIT-licensed, stdlib-only Python project that packages deterministic, judge-free failure probes across 10 LLM failure classes with fully mechanical scoring, plus a runner, static dashboard, and CI regression gate. It is v0.2.0 pre-release and self-submitted; the shipped demo run uses a deterministic mock provider, not real model measurements. I added one entry under Benchmarks → General in alphabetical order and followed CONTRIBUTING.md. Happy to adjust the wording or move it to a different section if you prefer.
- **Status:** **Accept PRs** (verified).
- **Caveat:** CC0 list; a 12-word annotation with no ranking claims is the safe shape. No known blockers.

## 2. danielrosehill/Awesome-AI-Evaluations-Tools — **good fit, table format**

- **Name / canonical URL:** Awesome AI Evaluations & Benchmarks — https://github.com/danielrosehill/Awesome-AI-Evaluations-Tools
- **Verified:** repo API 200 (29★, pushed 2026-11-23, default `master`, not archived; license metadata null
  while the README claims CC0); contents API 200 shows README.md 41,215 B, `data/` and `scripts/` and
  `.github/`, **no CONTRIBUTING.md**. README contribution line: *"Contributions, corrections, and PRs
  welcome."*
- **Relevance:** target the **`## Benchmarks`** table (Project | Description | Stars | Updated). Scope line
  in README: *"A list of **open source tools, frameworks, and benchmarks for evaluating AI systems** — LLMs,
  RAG pipelines, agents, multimodal models, and AI applications."* Its In-Scope list explicitly includes
  "Benchmark suites and benchmark datasets" and "Grounding, hallucination, bias, sycophancy, refusal/safety
  evaluation" — which maps to FailBench's failure classes.
- **Contribution rules (verified):** no `CONTRIBUTING.md`; README says contributions/PRs welcome; edit
  `README.md` directly and keep the 4-column table shape. The repo's `data/repos.csv` is described in the
  README as generated weekly via GitHub Actions — **do not hand-edit `data/repos.csv`**. Row order is not
  alphabetical, so add the row near the top of the `Benchmarks` table (or where the maintainer asks).
- **Exact suggested row** (replace `OWNER/REPO` with the same path taken from the published `https://github.com/Qin-z-x/llm-failbench`;
  badges cannot resolve before the repo is public):
  ```markdown
  | [FailBench](https://github.com/Qin-z-x/llm-failbench) | Judge-free, deterministic failure probes across 10 LLM failure classes; mechanical scoring, offline mock demo, CI regression gate. | ![](https://img.shields.io/github/stars/OWNER/REPO?style=social) | ![](https://img.shields.io/github/last-commit/OWNER/REPO) |
  ```
- **Suggested PR body (one paragraph):**
  > Hi Daniel — I maintain FailBench (https://github.com/Qin-z-x/llm-failbench), an MIT-licensed, stdlib-only Python benchmark of deterministic, judge-free failure probes across 10 LLM failure classes (mechanical scoring, no LLM judge), with an offline mock-provider demo and a CI regression gate. It is v0.2.0 pre-release and this is a self-submission; no real-model results are claimed. I added one row to the Benchmarks table in the existing column format and left data/repos.csv to your weekly Action. Happy to tweak the description or move the entry.
- **Status:** **Accept PRs** (README statement; no formal CONTRIBUTING file, so it is a smaller, informal list).
- **Caveat:** small audience (29★) and no written review criteria — a "nice to have", not a priority. The
  repo has no license metadata even though the README says CC0; no action needed from us.

## 3. tensorchord/Awesome-LLMOps — **accepts PRs, medium fit, follow format exactly**

- **Name / canonical URL:** Awesome LLMOps — https://github.com/tensorchord/Awesome-LLMOps
- **Verified:** repo API 200 (5,982★, 1,395 forks, pushed 2026-11-16, CC0-1.0,
  `web_commit_signoff_required: true`); README via API 200 (249,922 B); `contributing.md` via API 200
  (824 B). List is real, large, and active.
- **Relevance:** the **`## LLMOps`** category (3-column table: Project | Details | Repository). The category
  already carries code-first eval/CI tools — e.g. an entry for OpenGATE mentions a "no LLM judge" mode plus
  "CI regression gates" — so a judge-free probe kit with a CI gate fits the category's grain. The list's own
  description is *"An awesome & curated list of the best LLMOps tools for developers."*; this is a **medium**
  fit (LLMOps tooling list, not an eval-only list), so treat it as third priority.
- **Contribution rules (verified `contributing.md`):** "New categories or improvements to the existing
  categorization are welcome"; search for duplicates first; **an individual pull request for each
  suggestion**; run `./scripts/generate-star-badges.py` if needed, `./scripts/github-markdown-toc ./README.md`
  if needed, and `./scripts/check-activity.py` (needs `GITHUB_TOKEN`) to check activity; **order link titles
  alphabetically within each category**; mark archived repos *(Archived)*; remove 404 repos. Repo setting
  requires **commit sign-off (DCO)**, so use `git commit -s`.
- **Exact suggested row** (alphabetically by project title inside `## LLMOps`; replace `OWNER/REPO` with the
  published repo path after the repo is public):
  ```markdown
  | [FailBench](https://github.com/Qin-z-x/llm-failbench) | Deterministic, judge-free failure probes across 10 LLM failure classes; mechanical scoring, CI regression gate, offline mock demo. | ![GitHub Badge](https://img.shields.io/github/stars/OWNER/REPO.svg?style=flat-square) |
  ```
- **Suggested PR body (one paragraph):**
  > Hi — I maintain FailBench (https://github.com/Qin-z-x/llm-failbench), a small MIT-licensed, stdlib-only Python project that runs deterministic, judge-free failure probes (mechanical scoring, no LLM judge) across 10 LLM failure classes, with an offline mock-provider demo and a CI regression gate for OpenAI-compatible endpoints. It is v0.2.0 pre-release and self-submitted; the shipped demo results are from the mock provider, not real models. I added one alphabetically placed row to the LLMOps table, ran the star-badge/ToC/activity scripts, and signed off the commit. Happy to adjust or move it.
- **Status:** **Accept PRs** (verified contributing.md; DCO sign-off required).
- **Caveat:** this is a broad LLMOps list with a very large table and some self-submitted entries; a PR can
  take time. The star badge will show 0★ until the project has any — that is normal on this list but the
  owner should be comfortable with it.

## 4. benchflow-ai/awesome-evals — **best topical fit, but wait for the list's own inclusion bar**

- **Name / canonical URL:** Awesome Agent Evals — https://github.com/benchflow-ai/awesome-evals
  (maintained by BenchFlow; the similar-looking `tonydzi/awesome-evals` is a **fork**, do not submit there)
- **Verified:** repo API 200 (1,049★, 159 forks, pushed 2026-11-04, 94 open issues, not archived); README via
  API 200 (150,466 B); CONTRIBUTING.md via API 200 (2,532 B).
- **Relevance:** either **§5a "Eval frameworks & harnesses (code-first test-runners)"** (FailBench ships a
  runner + CI gate) or **§6 "Benchmark vs. eval (and benchmark integrity …)"** (FailBench is a small,
  deterministic benchmark). The list's own scope line: *"Resources for **building and evaluating AI
  agents**: papers, blog posts, talks/podcasts, courses, tools/frameworks, and benchmarks — that a
  practitioner at the Eugene-Yan / Han-Chung-Lee bar would actually send a colleague."* FailBench is
  LLM-general (with an agentic-reliability class), so this is a **partial / agent-evals** fit.
- **Contribution rules (verified CONTRIBUTING.md):** one-line annotation explaining what it is + why it
  belongs; canonical URL, note caveats; right section; **"Tools need evidence someone else uses them. Stars,
  external issues/PRs, or a third-party write-up. … a brand-new repo with no users outside the authoring org
  is a 'come back later,' not a listing."**; **disclose affiliation in the PR body** (self-submissions are
  welcome); format: `- **[Title](<project-url>)** — Author/Org — <https://project-url> · *type* — one-line note. 🆕 (if
  2025–2026)`; open a PR editing `README.md` (or `MENTIONS.md`), one change per PR.
- **Exact suggested line** (§5a shape, which often drops `· *type*`):
  ```markdown
  - **[FailBench](https://github.com/Qin-z-x/llm-failbench)** — <https://github.com/Qin-z-x/llm-failbench> — judge-free, deterministic failure probes across 10 LLM failure classes; mechanical scoring, offline mock demo, and a CI regression gate. 🆕
  ```
- **Suggested PR body (one paragraph):**
  > Hi — I maintain FailBench (https://github.com/Qin-z-x/llm-failbench), an MIT-licensed, stdlib-only Python benchmark of deterministic, judge-free failure probes across 10 LLM failure classes (mechanical scoring, no LLM judge), with a runner for any OpenAI-compatible endpoint, an offline mock-provider demo, and a CI regression gate. This is a self-submission and the project is v0.2.0 pre-release; the committed demo results come from the deterministic mock provider, not real model measurements. I added one entry to §5a (happy to move it to §6 if you think that fits better). I understand the list asks for evidence of external use, so if that bar is not met yet I'm happy to come back later.
- **Status:** **Accept PRs, but the list's own inclusion bar means this is a "come back later" until there is
  an external issue/PR, a third-party write-up, or organic stars.** Do not open this PR on launch day in the
  hope the maintainer waives the bar.
- **Caveat:** explicitly agent-focused list; keep the entry's wording honest about LLM generality.

## 5. onejune2018/Awesome-LLM-Eval — **topical fit but stale; optional "maybe"**

- **Name / canonical URL:** Awesome LLM Eval — https://github.com/onejune2018/Awesome-LLM-Eval
- **Verified:** repo API 200 (661★, 122 forks, MIT, not archived, **pushed 2025-11-24** — one year before this
  session; 84 open issues); README via API 200 (225,146 B); **CONTRIBUTING.md: HTTP 404** (no file).
- **Relevance:** section **"Datasets or Benchmarks → General"** table (columns: Name | Organization | Website
  | Description; rows include MMLU-Pro, TrustLLM, DyVal, RewardBench, LV-Eval …). List self-description:
  *"Awesome-LLM-Eval: a curated list of tools, datasets/benchmark, demos, leaderboard, papers, docs and
  models, mainly for Evaluation on Large Language Models and exploring the boundaries and limits of
  Generative AI."* FailBench is in scope topically.
- **Contribution rules (verified):** no CONTRIBUTING.md and no written format rules. The README says:
  *"We also welcome any pull request or issues to help us improve this work. Your contributions will be
  acknowledged in acknowledgements."* So contributions are invited, but there is no documented review
  process; copy the existing table shape exactly and append the date in the Description cell like the
  existing rows. Check whether the repo's English/Chinese README variants also carry the table and mirror
  the row if so (verify before editing).
- **Exact suggested row** (append to the `Datasets or Benchmarks → General` table):
  ```markdown
  | FailBench | (owner handle / org) | [FailBench](https://github.com/Qin-z-x/llm-failbench) | Judge-free, deterministic failure probes across 10 LLM failure classes with mechanical scoring, an offline mock demo, and a CI regression gate. (2026-11-24) |
  ```
- **Suggested PR body (one paragraph):**
  > Hi — I maintain FailBench (https://github.com/Qin-z-x/llm-failbench), an MIT-licensed, stdlib-only Python benchmark of deterministic, judge-free failure probes across 10 LLM failure classes with mechanical scoring, a runner for OpenAI-compatible endpoints, an offline mock-provider demo, and a CI regression gate. This is v0.2.0 pre-release and a self-submission; the demo results are from the deterministic mock provider, not real model measurements. I added one row to Datasets or Benchmarks → General in the existing table format with the date appended. Happy to adjust wording or placement.
- **Status:** **Accepts PRs/issues per README (no CONTRIBUTING.md, no documented format) — treat as "maybe /
  optional".** The list has not been pushed to in a year and has a large open-issue backlog, so a PR may
  simply sit there.
- **Caveat:** do this one last, or skip it; it is listed for completeness because it is the most on-topic
  table, not because it is healthy.

---

## Considered and not recommended (yet)

- **alopatenko/LLMEvaluation — "Awesome LLM Evaluation"** (208★, pushed 2026-11-14; README.md 155,444 B via
  contents API; **no CONTRIBUTING.md**). It is a comprehensive compendium (surveys, leaderboards, evaluation
  software, benchmarks) and a project could fit its "Evaluation Software" section, but there is no
  documented contribution process. If the owner wants it, open a polite issue first asking whether/where an
  entry is welcome; do not cold-PR a 155 KB curated compendium. *(repo + contents URLs verified, see table.)*
- **awelist/awesome-ai-benchmarks-evaluation** (reached by redirect from `brandonhimpfen/awesome-ai-benchmarks-evaluation`) — excluded: organization-run repo created 2025-11-29 with 14★ whose homepage is a link directory (`https://lnktr.net/awesome`); it reads as a link-farm-style list rather than a community-curated list with a review bar. No submission planned.
- **Template-generated list farms / "star if you like it" lists / paid directories** — do not submit; they
  add no legitimate distribution and can look like spam.

## Suggested order & timing

1. **Vvkmnn/awesome-ai-eval** — first, once the repo is public and CI is green.
2. **danielrosehill/Awesome-AI-Evaluations-Tools** — same week; low risk.
3. **tensorchord/Awesome-LLMOps** — after the first two, signed-off commit; medium fit.
4. **benchflow-ai/awesome-evals** — only after there is external evidence of use (an outside issue/PR, a
   write-up, or a release announcement someone else shares). Re-read CONTRIBUTING before opening.
5. **onejune2018/Awesome-LLM-Eval** — optional/last.

Between any two submissions, leave at least a couple of days and re-read the target list's contributing file:
formats change. Never submit the same PR to multiple lists in one batch, never ask for stars/votes, and treat
a rejection as final (one polite follow-up maximum).
