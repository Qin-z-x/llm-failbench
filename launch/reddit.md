# Reddit launch drafts — r/MachineLearning, r/LocalLLaMA, r/LLMDevs

> **Drafts only. Owner posts manually from their own account, one sub at a time, days apart. No crosspost spam.**
> Read each subreddit's current rules in a browser before posting: the official Reddit rules pages could not be read by
> the build machine's fetch tools (see §4. Rules-verification notes). Every rule detail quoted below comes from
> third-party rule trackers fetched on 2026-11-24, not from Reddit directly, so treat it as a strong prior and the
> live sidebar as the authority.

**State this file assumes (from `docs/CONTRACT.md`):** FailBench v0.1.0 pre-release; code MIT, data CC-BY-4.0;
the committed demo results come from the deterministic **mock** provider and are **not** measurements of any real model;
no live model endpoint existed during the build; no users, stars, testimonials, downloads, or adoption claims exist.
Nothing here is auto-posted. `https://github.com/Qin-z-x/llm-failbench` is the only substitution token — substitute it after the repository is public
(convention from `launch/README.md`); do **not** invent a GitHub URL now.

**Cadence (from `docs/DISTRIBUTION.md` §4–§5):** one subreddit per day, at least three days apart — plan is
r/MachineLearning (Day 5), r/LocalLLaMA (Day 8), r/LLMDevs (Day 9). If a sub removes the post, do not repost the same
text elsewhere that day; fix the framing or skip the channel. The three bodies below are deliberately different;
do not paste one into two subs.

---

## 0. Pre-flight checklist (do before the first Reddit post)

- [ ] `https://github.com/Qin-z-x/llm-failbench` substituted in the draft being posted (exactly one per body); repository public and reachable.
- [ ] On a clean machine with plain Python 3.9+ (no venv, no install), the offline demo actually runs:
      `python -m failbench run --provider mock --demo --out results/demo`, and the `report` and `gate` commands below
      exist and work on the published tree. If a command changed, edit the draft to match the README.
- [ ] The published README / `docs/RESULTS.md` / dashboard still label the demo as mock-provider output; the honest-status
      paragraph in the draft must not drift from it.
- [ ] The counts are frozen for v0.1.0 and already appear in the drafts: 100 probes (10 per class) and 110 cited evidence records (54 HN, 46 arXiv, 10 GitHub issues); the committed demo is 100 probes: 64 pass / 34 fail / 2 error, mock provider only. If `README.md`'s count table differs at posting time, update the numbers before posting.
- [ ] Re-read the official sub rules in a browser (URLs in each draft's rules block and in §4). Rules change.
- [ ] Search the sub before posting: no earlier FailBench post, no duplicate link.
- [ ] Owner is available to answer in the thread for several hours, and will correct any wrong claim publicly.
- [ ] If asked how it was built: the project was built with substantial AI assistance under human direction and review;
      never claim human-only authorship. Disclose up front where the venue asks for it.
- [ ] The account is the owner's own, has some genuine participation history, and is not a new or shared/purchased
      account. No vote requests anywhere, on or off Reddit.

**Safe-claims sheet (applies to all three drafts):** say "open-source, non-commercial, no signup, no paid tier";
say "deterministic, judge-free, mechanically scored"; say "every evidence record links to a public source". Do **not** say
"first", "only", "best", "state-of-the-art", "leaderboard", "X% better", "used by N teams", or anything implying real-model
measurements. The mock demo is the only shipped result and it is always labeled mock.

---

## 1. r/MachineLearning — `[P]` project draft

**Suggested tag/flair:** `[P]` project tag in the title (r/MachineLearning's project tag; the fetched flair-usage data for
the sub shows Project `[P]` / Discussion `[D]` / Research `[R]` / News `[N]` in use). Post as a **text post** with the repo
link in the body — not a bare link post. Verify the current tag/flair convention on the live page before submitting.

**Title (primary, 123 characters):**

```
[P] FailBench v0.1.0: deterministic, judge-free probes for 10 LLM failure classes, with an evidence atlas of public sources
```

**Alternative titles (both under 300 characters; re-count after editing):**

```
[P] FailBench: a judge-free LLM failure-probe suite with a sourced evidence atlas (v0.1.0 pre-release, code + data open)
```

```
[P] FailBench v0.1.0 - mechanical failure probes for LLM endpoints, every evidence record backed by a public source
```

**Body — copy between the markers (450 words as drafted, within the 250–450 cap; recount if you edit):**

<!-- BODY:START rml -->
I've been building FailBench, an open benchmark plus evidence atlas for LLM failure modes. It's v0.1.0, a pre-release, and I'm posting it here mainly to get the methodology picked apart.

**What it is.** The benchmark half is a corpus of 100 deterministic probes across ten failure classes (10 per class): hallucination, instruction following, context retrieval, reasoning consistency, sycophancy, structured output, multilingual, safety consistency, agentic reliability, and determinism/calibration. Each probe is a static prompt with exactly one mechanical pass condition: a substring or regex match, JSON-schema validation, a numeric comparison within tolerance, or an all-of combination. There are no LLM judges in the scoring path, no model-written rubric, and no human grading. The atlas half catalogues 110 publicly reported failure modes (54 HN threads, 46 arXiv papers, 10 GitHub issues), and every record links to the public source it came from. Records are marked `cited` unless a real model run produced them.

**Why judge-free.** Judge-based evals drift when the judge model or judge prompt changes, and are expensive to reproduce. Here a pass or fail is decidable by reading the scoring rule and the stored response, and a run can be re-scored offline from its raw responses. The repository also includes a CI regression gate that compares a new run against a baseline, a self-contained static dashboard, and a runner for any OpenAI-compatible `/chat/completions` endpoint. The Python is stdlib-only. An offline deterministic mock provider exercises the whole pipeline with no API key and no network: `python -m failbench run --provider mock --demo --out results/demo`.

**Honest status of the results.** The committed demo run covers all 100 probes: 64 pass, 34 fail, 2 error, and came from that deterministic mock provider. They are not measurements of any real model. No live model endpoint was available while I was building this, so the release contains no real-model benchmark numbers. For real numbers, run the kit against your own endpoint; do not read the demo pass rates as model results.

**What I'm asking for.** Methodology critique first: are any probes ambiguous or trivially gameable; does a substring-style check measure the failure class it claims to measure; where is coverage thin? Mechanical scoring is a deliberate trade-off: a model can pass by emitting the expected string, and the public corpus can be overfitted to. I treat the score as a single-endpoint regression signal, not a capability ranking. Second, evidence and probe contributions: dead links, misattributed sources, better probe designs are welcome. Code is MIT, data is CC-BY-4.0, and there is no paid tier or signup behind it. Repository: https://github.com/Qin-z-x/llm-failbench

I'll answer questions in the thread. The project was built with substantial AI assistance under my direction and review; I'm the human accountable for what's published.
<!-- BODY:END rml -->

**Sub rules notes — read these before posting (r/MachineLearning):**

- **Known relevant rules to verify in the browser before posting:** use the `[P]` project tag for a project post; no
  low-effort self-promotion or marketing framing; disclose affiliations (here: sole maintainer, no company or paid product
  behind it); link the code; posts are expected to carry technical detail. These are r/MachineLearning's well-known
  project-post expectations; they are consistent with what the fetched third-party summaries say about self-promotion
  and the `[P]` tag, but they were **not** read from Reddit directly
  in this session — confirm each against the live rules page and wiki.
- **Official rules / moderation URLs — unverified in session (must be opened by the owner in a browser):**
  `https://www.reddit.com/r/MachineLearning/about/rules` and the sub wiki `https://www.reddit.com/r/MachineLearning/wiki/index`
  (both blocked for the build machine; see §4).
- **Observed tag evidence:** the fetched GummySearch page for the sub (HTTP 200, last updated 2026-11-22) lists
  Project `[P]`, Discussion `[D]`, Research `[R]`, and News `[N]` among flairs in active use —
  https://gummysearch.com/r/MachineLearning/
- **Practical precautions:** one post only; no crossposting; answer every substantive critique; if a mod removes it, read the
  removal reason and do not repost the same framing elsewhere the same day. r/MachineLearning is a strict sub for
  promotion — the post must read as a request for methodological critique and contribution, not as a launch advertisement.

---

## 2. r/LocalLLaMA — practitioner draft

**Suggested flair/flair name:** **Resources** (the sub's rules, as summarized by the fetched tracker, say an owner's own
project must be flaired Resources and **never News**; the sub also uses an "I Built A Thing" flair in practice — Resources
is the safer choice for a tool announcement). Do not flair it as News or Discussion.

**Title (primary, 126 characters):**

```
FailBench v0.1.0: a judge-free failure-probe kit for local models - offline mock demo first, then any OpenAI-compatible server
```

**Alternative titles (both under 300 characters):**

```
I built FailBench: deterministic, judge-free LLM failure probes you can run against Ollama, vLLM, LM Studio or llama.cpp
```

```
FailBench: run a judge-free LLM failure suite offline, then point it at your own local OpenAI-compatible endpoint
```

**Body — copy between the markers (450 words as drafted, within the 250–450 cap; recount if you edit):**

<!-- BODY:START localllama -->
I built FailBench v0.1.0, an open, judge-free failure-probe kit for LLMs, and this sub is the right place to ask what it gets wrong on local setups.

The idea is simple: a benchmark plus an evidence atlas. The benchmark is 100 deterministic probes across ten failure classes, 10 per class (hallucination, instruction following, context retrieval, reasoning consistency, sycophancy, structured output, multilingual, safety consistency, agentic reliability, determinism/calibration). Every probe is a static prompt plus one mechanical pass condition — substring, regex, JSON schema, or numeric tolerance — so there is no LLM judge in the loop and no judge cost per run. All 110 evidence records link to a public source: 54 HN threads, 46 arXiv papers, 10 GitHub issues. Code is MIT, data is CC-BY-4.0, and the Python is stdlib-only: no install, no third-party packages.

Try the whole thing offline first. The mock provider is deterministic and needs no API key and no network:

```
python -m failbench run --provider mock --demo --out results/demo
python -m failbench report --results results/demo --out site
```

That exercises the runner and the static report offline, no API key. For your own hardware it talks to any OpenAI-compatible `/chat/completions` server, so Ollama, vLLM, LM Studio, or llama.cpp's server all work — point `--base-url` at the server's `/v1` endpoint and `--model` at whatever you loaded. The local use I care about is comparison: the same suite against a model at different quants, or across an engine upgrade. The gate compares a new run to a saved baseline, so you see which classes moved rather than one aggregate number. Worth saying plainly: the corpus is public and mechanically scored, so it can be gamed and it can fail an output for the wrong reason (a formatting miss rather than an understanding miss). Open the stored response in the dashboard and judge the failure yourself. Treat it as a regression signal for one endpoint over time, not as a leaderboard.

Honest status: the committed demo run covers all 100 probes — 64 pass, 34 fail, 2 error — and comes from the deterministic mock provider. They are not measurements of any real model. No live endpoint was available during the build, so there are no real-model numbers in this release — run it yourself for those.

What I want: reports from people running it against local models, with hardware, model, quant, and engine settings. Probe ideas for failures that show up specifically in local deployments (long context, tool-call formatting, multilingual). And pushback: which checks are too brittle to be useful in practice? Repo: https://github.com/Qin-z-x/llm-failbench

I'm the maintainer; the project was built with AI assistance under my review, and I don't claim otherwise. Questions welcome in the thread.
<!-- BODY:END localllama -->

**Sub rules notes — read these before posting (r/LocalLLaMA):**

- **Rules content read from a third-party tracker** (not Reddit): https://spacestationlabs.ai/subreddits/localllama
  (fetched HTTP 200 on 2026-11-24; page says its rule text is "as archived in January 2025" and its data is as of
  2026-10-04). It reproduces five current-looking rules: search before asking; off-topic posts; low-effort posts;
  **Limit Self-Promotion** (1/10 guideline, no sensationalized titles, no affiliate links, link directly to the source such
  as GitHub or Hugging Face, and **do not flair your own project as News — use Resources**); follow Reddit's content policy.
- **Karma gate:** the same tracker reports that r/LocalLLaMA requires **5 karma earned inside the subreddit** before a post
  survives AutoModerator ("gain the minimum of 5 karma and then re-post"), and that post flair is effectively required.
  If the owner's account lacks subreddit karma, the post will be removed automatically — comment genuinely first, or gain the
  karma, and do not ask anyone for votes.
- **Official sub rules URL — unverified in session (open it in a browser):** `https://www.reddit.com/r/LocalLLaMA/`
  (and `https://www.reddit.com/r/LocalLLaMA/about/rules`). Both were blocked for the build machine; see §4.
- **Culture notes from the same fetched page:** posts pair claims with numbers and state hardware/quant/engine; owners who
  disclose their own project and lead with limitations are received better; repeated posts of the same project are removed.
  The draft does this deliberately — keep it that way if editing.

---

## 3. r/LLMDevs — developer / eval-engineering draft

**Suggested flair:** **Tools** (flair in active use for project/tool posts; ~21% of posts on the fetched tracker's sample,
alongside Discussion, Resource, Help Wanted, News). A text post with context, not a bare link post.

**Title (primary, 141 characters):**

```
FailBench: judge-free LLM failure probes plus a CI regression gate for any OpenAI-compatible endpoint (looking for eval-engineering feedback)
```

**Alternative titles (both under 300 characters):**

```
A judge-free eval suite with an exit-code CI gate - would this fit your LLM regression pipeline? (FailBench v0.1.0 preview)
```

```
FailBench: deterministic LLM failure probes you can run as a CI regression gate, with no LLM judge in the loop
```

**Body — copy between the markers (423 words as drafted, within the 250–450 cap; recount if you edit):**

<!-- BODY:START llmdevs -->
I'm building FailBench v0.1.0, a judge-free failure-probe suite for LLM endpoints, and I'd rather have eval-engineering feedback than attention: does this fit a CI pipeline you would actually run?

The shape: 100 deterministic probes across ten failure classes, 10 per class (hallucination, instruction following, context retrieval, reasoning consistency, sycophancy, structured output, multilingual, safety consistency, agentic reliability, determinism/calibration). Each probe is a static prompt plus one mechanical scorer — substring, regex, JSON-schema validation, or numeric tolerance — declared in a JSON file. No LLM judge anywhere means no judge prompt to version, no judge cost per run, and no judge-model drift between runs. A pass or fail is auditable from the scorer rule plus the stored response, and raw responses are kept so a run can be re-scored or replayed offline.

The workflow I care about is regression detection. Run the suite against an endpoint, keep the results file, then after a model swap or prompt change run it again and compare:

```
python -m failbench gate --baseline results/base/results.json --current results/run1/results.json
```

The gate compares the two runs and is meant to fail the check when the run regresses, which is the piece that makes it usable as a CI check. There is also a static dashboard build (`report --results ... --out site`) and a runner for any OpenAI-compatible `/chat/completions` endpoint; the Python is stdlib-only. Adding a probe is editing one JSON file with a prompt and a scorer, then running the validation command.

Honest status: the committed demo run covers all 100 probes — 64 pass, 34 fail, 2 error — and was produced by the deterministic mock provider. They are not measurements of any real model. No live model endpoint was available during the build, so the release has no real-model numbers. Run it on your endpoint for those; do not read the demo pass rates as model results.

Useful feedback for me: whether the exit-code gate matches how you would wire a regression check; whether the probe format is reasonable to contribute to, or too rigid; coverage gaps around tool-calling, structured output, and agent loops; and where mechanical scoring will be too brittle in practice. It is deliberately not a leaderboard — the corpus is public and mechanical, so it can be gamed — and I would rather it be a cheap per-endpoint regression gate than a ranking. Corrections to the 110 evidence records are equally welcome.

Repo: https://github.com/Qin-z-x/llm-failbench

Built with substantial AI assistance under human direction and review; MIT code, CC-BY-4.0 data; I'll be in the thread to answer questions.
<!-- BODY:END llmdevs -->

**Sub rules notes — read these before posting (r/LLMDevs):**

- **Rules content read from a third-party tracker** (not Reddit): https://spacestationlabs.ai/subreddits/llmdevs
  (fetched HTTP 200 on 2026-11-24; rule text marked "as archived in January 2025", data as of 2026-10-04). It reproduces
  nine rules, including: **Rule 5 — no self-promotion / excessive promotion of personal or commercial projects**;
  Rule 7 — provide sources and references, and label AI-generated content with context and attribution; Rule 3 — accuracy
  and no misleading claims; Rule 6 — no low-effort posts or spam; Rule 4 — stay on LLM/NLP topic.
- **Cross-check fetched:** https://www.replyhey.com/subreddits/llmdevs (HTTP 200, "rules last read 2026-08-25") classifies
  r/LLMDevs self-promotion as **restricted**. The same tracker's page for r/MachineLearning was fetched HTTP 200 with
  "rules last read 2026-11-08" and also classifies self-promotion as restricted:
  https://www.replyhey.com/subreddits/machinelearning
- **Official sub rules URL — unverified in session (open it in a browser):** `https://www.reddit.com/r/LLMDevs/`
  and `https://www.reddit.com/r/LLMDevs/about/rules`. Both were blocked for the build machine; see §4.
- **Culture notes from the fetched tracker:** open-source show-and-tell with code and numbers is the norm and does well;
  a signup link or launch dressed up as discussion is what gets removed. This draft is written as a feedback request with the
  open-source repo linked; keep that framing.

---

## 4. Rules-verification notes (what was fetched, what resolved, what did not)

**Date:** 2026-11-24 (Asia/Shanghai session date). **Method:** the session's `web_fetch` tool was used for every external
URL below. Reddit domains could not be reached by `web_fetch` at all — every attempt returned
`Error: web_fetch failed: TypeError: fetch failed`. As a supplemental check from the same machine, a direct Python 3.13
`urllib` request (browser User-Agent) and a PowerShell request were tried; results are recorded separately below. **No
Reddit rules text was successfully read in this session.** The rule details in §1–§3 come from third-party trackers that
*did* resolve; they are secondary sources and may be stale, so the owner must read the official rules in a browser before
posting.

The W7 lead re-checked every URL in this section at the end of the build. Final statuses are recorded in
`launch/verification.md` §D and can differ slightly from the worker-time notes below (third-party mirrors and
proxies are flaky: `r.jina.ai`, `leadsrover.io`, `replyhey.com/subreddits/localllama` and
`subredditmarketing.com` resolved on retry, while `archive.ph` and one `web.archive.org` snapshot still
failed). The official Reddit rules URLs now resolve to HTTP 200 JavaScript shells (or redirect to
`/mod/<sub>/rules/`) but still expose no readable rule text to an automated client, so the
"unverified in session" conclusion below stands.

### 4.1 Third-party pages that resolved (used for the rules notes above)

| URL | Fetch result (2026-11-24) | What was observed |
|---|---|---|
| https://spacestationlabs.ai/subreddits/localllama | HTTP 200 | r/LocalLLaMA guide: 5 named rules incl. Limit Self-Promotion; 1/10 guideline; no sensational titles; no affiliate links; direct source links; own project → Resources, never News; 5 subreddit-karma AutoModerator gate; flair requirement. Rule text marked "as archived in January 2025"; site data "as of October 4, 2026". |
| https://spacestationlabs.ai/subreddits/llmdevs | HTTP 200 | r/LLMDevs guide: 9 named rules incl. no self-promotion (Rule 5), sources/AI-content attribution (Rule 7), accuracy (Rule 3), low-effort (Rule 6), on-topic (Rule 4), surveys disclosure (Rule 2); flair usage (Discussion 50%, Tools 21%, Resource 10%); rules marked "as archived in January 2025". |
| https://spacestationlabs.ai/subreddits | HTTP 200 | Index of the tracker's guides. Confirmed it has **no** r/MachineLearning guide, so no RML rules substitute was available there. |
| https://spacestationlabs.ai/subreddits/machinelearning | HTTP 404 | No page at that path — no RML data from this source. |
| https://www.replyhey.com/subreddits/llmdevs | HTTP 200 | r/LLMDevs classified "self-promotion restricted"; "rules last read 2026-08-25"; page links to the official Reddit rules page (which I could not fetch). |
| https://www.replyhey.com/subreddits/machinelearning | HTTP 200 | r/MachineLearning classified "self-promotion restricted"; "rules last read 2026-11-08"; links to the official rules page. |
| https://www.replyhey.com/subreddits/localllama | timeout (30 s) | No content returned — not used. |
| https://gummysearch.com/r/MachineLearning/ | HTTP 200 | r/MachineLearning flair/post data: Project `[P]`, Discussion `[D]`, Research `[R]`, News `[N]` all in active use; last updated 2026-11-22. Used only as evidence that the `[P]` tag is the sub's project tag — no rule text. |
| https://reddifier.com/free-subreddit-analysis-tool/r/MachineLearning | HTTP 200 | Page loaded but its subreddit analysis is client-side generated and returned no r/MachineLearning rules text — not used. |
| https://www.subredditmarketing.com/subreddits/machinelearning | errors: `fetch failed` on first attempt, timeout on retry; the `/machine-learning` variant returned HTTP 404 | No usable content — not used. |
| https://leadsrover.io/subreddits/r/llmdevs | timeout (30 s) | Not used. |

### 4.2 Official Reddit URLs — **unverified in session**

Every official Reddit rules/moderation URL tried is listed here with what actually happened. **Do not treat these as
verified facts**; they are the URLs the owner should open in a browser before posting.

| URL | What happened (2026-11-24) |
|---|---|
| https://www.reddit.com/r/MachineLearning/ | `web_fetch`: TypeError fetch failed. Supplemental `urllib`: HTTP 200 but an 8,415-byte JavaScript shell (page title only "Reddit", no subreddit content). |
| https://www.reddit.com/r/LocalLLaMA/ | `web_fetch`: TypeError fetch failed. |
| https://www.reddit.com/r/LLMDevs/ | `web_fetch`: TypeError fetch failed. |
| https://www.reddit.com/r/MachineLearning/about/rules | `web_fetch`: TypeError fetch failed. Supplemental `urllib`: HTTP 200, an 8,423-byte JS shell with no rule text. |
| https://www.reddit.com/r/MachineLearning/about/rules.json | `web_fetch`: TypeError fetch failed. Supplemental `urllib`: **HTTP 403 "Blocked"**; PowerShell: HTTP 403; `curl.exe`: connection failure (HTTP 000). |
| https://www.reddit.com/r/LocalLLaMA/about/rules.json | `urllib`: HTTP 403 "Blocked". |
| https://www.reddit.com/r/LLMDevs/about/rules.json | `urllib`: HTTP 403 "Blocked". |
| https://old.reddit.com/r/MachineLearning/ | `web_fetch`: TypeError fetch failed. Supplemental `urllib`: HTTP 200 but a 342 KB "Welcome to Reddit" shell with no rule text. |
| https://old.reddit.com/r/MachineLearning/about/rules | `urllib`: HTTP 200, same generic shell (no rule text). |
| https://old.reddit.com/r/LocalLLaMA/about/rules | `urllib`: HTTP 200, same generic shell (no rule text). |
| https://old.reddit.com/r/LLMDevs/about/rules | `urllib`: HTTP 200, same generic shell (no rule text). |
| https://www.reddit.com/r/MachineLearning/wiki/index | `web_fetch`: TypeError fetch failed. Not re-tried by `urllib`. |
| https://api.reddit.com/r/MachineLearning/about/rules ; https://sh.reddit.com/r/MachineLearning/ ; https://reddit.com/r/MachineLearning/ | `web_fetch`: TypeError fetch failed. |
| https://web.archive.org/web/2026/https://www.reddit.com/r/MachineLearning/about/rules ; https://web.archive.org/web/2025/https://www.reddit.com/r/LocalLLaMA/about/rules | `web_fetch`: TypeError fetch failed (archive also unreachable from this session). |
| https://archive.ph/newest/https://www.reddit.com/r/MachineLearning/about/rules | `web_fetch`: TypeError fetch failed. |
| https://r.jina.ai/https://www.reddit.com/r/MachineLearning/about/rules | `web_fetch`: TypeError fetch failed. |
| https://redlib.catsarch.com/r/MachineLearning | `urllib`: HTTP 429 Too Many Requests. |
| https://safereddit.com/r/MachineLearning | `urllib`: HTTP 200 but a "Verifying your browser" challenge page, no content. |
| https://redlib.perennialte.ch/r/MachineLearning | `urllib`: HTTP 410 Gone. |
| https://l.opnxng.com/r/MachineLearning | `urllib`: HTTP 429 Too Many Requests. |
| https://api.allorigins.win/raw?url=https%3A%2F%2Fwww.reddit.com%2Fr%2FMachineLearning%2Fabout%2Frules.json | HTTP 522 (upstream timeout). |
| https://corsproxy.io/?url=https%3A%2F%2Fwww.reddit.com%2Fr%2FLocalLLaMA%2Fabout%2Frules.json | HTTP 401 (API key required). |
| https://api.codetabs.com/v1/proxy?quest=https://www.reddit.com/r/LLMDevs/about/rules.json | HTTP 522 (upstream timeout). |

**Also attempted, for completeness:** https://www.redditinc.com/ (redirect not followed; the site's own
`redditinc.com` was not fetched — the site-wide policy URL is listed in `docs/DISTRIBUTION.md` §11 for the owner to check
when posting). A `web_search` was used only to locate candidate sources; result snippets were **not** treated as
verification, and search-sourced pages that could not be fetched (e.g. raw.githubusercontent.com playbooks) are not cited
in this file.

**Net conclusion for the owner:** Reddit blocks this build machine's automated clients (403 on the JSON rules endpoints,
JS-only shells or challenge pages on the HTML), so the official rule text is **unverified in session**. The rules notes in
§1–§3 are drawn from third-party trackers that were readable, and those trackers themselves say their rule snapshots are
from January 2025 and from August / November 2026. Before each post, open the sub's sidebar/about/rules page in a logged-in
browser, read it, and adjust the draft if anything disagrees.

---

## 5. "Do not" list (binding for every Reddit action)

- **No vote solicitation.** No "upvote if…", no "if this is useful please upvote", nothing that asks for votes, and no
  asking anyone off-Reddit to vote or comment on the post.
- **No "please star".** Do not ask for GitHub stars, watches, follows, or shares — not in the post, not in comments, not
  in reply to praise. Stars are not a goal of this launch.
- **No fake accounts or astroturfing.** No sockpuppets, no friends/colleagues planted in the comments, no fake user
  quotes, no manufactured testimonials, no purchased accounts or karma, no vote rings, no engagement pods.
- **No identical text across subs.** Each sub gets its own draft; do not crosspost, and do not post the same body twice.
  One subreddit on any given day, at least three days apart.
- **No mass DMs or unsolicited outreach.** No bulk messages to users who discussed LLM evaluation, no cold DMs to
  maintainers, no scraping commenters from a thread.
- **No engagement bait.** No "what do you think?", "hot take", "unpopular opinion", "tag someone", or rage-bait framing;
  no A/B voting posts; no "daily" or "answer in comments" gimmicks.
- **No claimed real-model results.** Never present the mock-provider demo as a model measurement, never invent numbers,
  users, quotes, downloads, or adoption. The honest-status paragraph must stay in every post that mentions results.
- **No "first / only / best / state-of-the-art" claims**, no leaderboard claims, no implication of benchmarking any named
  model or vendor.
- **No human-only authorship claim and no impersonation.** Disclose AI assistance when asked (and up front where venue
  rules require it); never claim credentials, affiliations, or identities the owner does not have.
- **No arguing with moderators, no ban evasion, no reposting removed content.** If a post is removed for self-promotion,
  read the reason, do not repost it elsewhere with the same framing, and do not create another account to get around a
  ban or a karma gate. A removal is a rules signal, not a marketing problem.
- **No silent deletion of criticism.** Answer good-faith critique; if a claim was wrong, correct it publicly (issue /
  CHANGELOG) and say so in the thread.
