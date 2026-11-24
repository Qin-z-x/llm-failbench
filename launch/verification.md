# Launch URL verification ledger

**Date of all checks:** 2026-11-24 (session local time, Asia/Shanghai).
**Finalized:** after the v0.1.0 launch-data freeze — the repository contains 100 probes (10 per class; severity
5 critical / 34 high / 43 medium / 18 low) and 110 cited evidence records across all 10 classes (54 Hacker News,
46 arXiv, 10 GitHub issues), and the committed demo run is against the deterministic mock provider only
(100 probes: 64 pass / 34 fail / 2 error). No URL status in this ledger changed after that freeze.

**Scope:** every external URL cited in `launch/**` and `docs/DISTRIBUTION.md` (plus the two URLs in
`CITATION.cff` — there are none by design). This ledger is the verification record for the W7 launch kit:
it lists each URL, the HTTP status observed from the build machine on that date, and what the URL is used
for in the deliverables.

**Method.** URLs were extracted mechanically from the launch files, de-duplicated, and requested with
direct HTTPS `GET` requests from the build machine (Python 3.13 `urllib`, browser `User-Agent`). The
session's `web_fetch` tool could not reach several hosts (Reddit, Hacker News, Hugging Face, GitHub HTML
from the worker sandboxes), so direct requests were the primary method and this limitation is disclosed
here and inside the affected drafts. Status codes are point-in-time; policy pages and third-party
mirrors change.

**Summary (unique URLs = 98 referenced across the launch materials; 4 are substitution templates and were not tested):**

| Result | Count | Notes |
|---|---|---|
| HTTP 200 on the sweep | 60 | Content also spot-checked where the draft quotes it (see §5) |
| HTTP 403 | 25 | 20 are GitHub API requests after the unauthenticated 60 req/h limit was exhausted (all returned 200 earlier in this session); 5 are Reddit endpoints that block automated clients and are recorded as negative results in `launch/reddit.md` |
| HTTP 5xx / transport errors | 4 | Third-party Reddit mirrors/proxies/archive (522 ×2, 503 ×1, ERR ×1) — all appear in the drafts as *recorded failures*, not as endorsed channels |
| HTTP 404 | 1 | `spacestationlabs.ai/subreddits/machinelearning` — cited as a negative result: no r/MachineLearning guide exists there |
| HTTP 401 / 410 / 429 | 4 | Third-party proxy/mirrors; statuses match the draft's own ledger (mirrors fluctuate) |
| Template URLs, not tested | 4 | Three `img.shields.io/.../OWNER/REPO` badge templates plus `https://project-url` inside a quoted list-format example; the owner fills these after publishing and they cannot resolve before the repo exists |

**No URL is fabricated.** Every 200 in tables A and B was also checked for the content the draft
attributes to it (§5). URLs with non-200 statuses are either (a) intentionally recorded failures used as
negative evidence, (b) rate-limit artifacts, or (c) flaky third-party mirrors — not unverified claims
presented as working channels.

**Templates excluded from testing (by design):** `https://github.com/Qin-z-x/llm-failbench` (the single owner substitution token used
across the drafts — not a URL and therefore not counted above), three
`https://img.shields.io/github/.../OWNER/REPO` badge templates inside the two table-format awesome-list
snippets, and one `https://project-url` inside a quoted description of a list's own entry format. These are
formatting templates, not live URLs.

This ledger also records a few verification-only references that do not appear in the copy itself (for
example the four dev.to tag pages whose existence was checked before choosing front-matter tags) and the
redirect targets of policy pages. Those are labelled as such in the tables.

---

## A. Venue, policy and reference URLs (all HTTP 200 unless noted)

| URL | Status (2026-11-24) | Role in the drafts |
|---|---|---|
| https://news.ycombinator.com/showhn.html | 200 | Show HN rules; content read and quoted |
| https://news.ycombinator.com/newsguidelines.html | 200 | HN guidelines (no generated/AI-edited text; no vote solicitation); content read and quoted |
| https://news.ycombinator.com/newsfaq.html | 200 | HN FAQ (reposting); cited in DISTRIBUTION.md |
| https://news.ycombinator.com/item?id=22336638 | 200 | HN moderator "tips about how to present your work", linked from Show HN page; 2026-03-28 edit read and quoted ("Write your text by hand...") |
| https://discuss.huggingface.co/ | 200 | HF forum home |
| https://discuss.huggingface.co/about | 200 | Forum about page |
| https://discuss.huggingface.co/faq | 200 → redirects to /guidelines | Forum guidelines; content read and quoted |
| https://discuss.huggingface.co/categories.json | 200 | Category IDs/names used in hf_discussion.md; verified (Show and Tell = 65, Research = 7, Hub = 23) |
| https://discuss.huggingface.co/c/show-and-tell/65 | 200 | Primary venue; category description matches the draft |
| https://discuss.huggingface.co/c/research/7 | 200 | Alternative venue; category description matches |
| https://discuss.huggingface.co/c/hub/23 | 200 | Marked "not suitable" in the draft; category description matches |
| https://huggingface.co/code-of-conduct | 200 | HF conduct policy |
| https://huggingface.co/content-policy | 200 | HF content policy; §5 spam restrictions read and quoted |
| https://huggingface.co/docs/hub/repositories-pull-requests-discussions | 200 | Hub discussions documentation |
| https://dev.to/code-of-conduct | 200 | dev.to conduct policy |
| https://dev.to/p/editor_guide | 200 | Front-matter reference: confirms `ai_disclosure_level` with values `not_disclosed / no_ai / some_ai / fully_autonomous`, max four tags |
| https://dev.to/t/ai · https://dev.to/t/opensource · https://dev.to/t/python · https://dev.to/t/llm | 200 (each) | Tag pages for the four tags used in the article front matter |
| https://www.linkedin.com/legal/professional-community-policies | 200 | LinkedIn professional community policies (no spam/fake profiles) |
| https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository | 200 | Issue-template reference in DISTRIBUTION.md |
| https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics | 200 | Topics reference |
| https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-traffic-to-a-repository | 200 | GitHub Insights traffic metric source used in DISTRIBUTION.md §6 |
| https://redditinc.com/policies/reddit-rules | 200 | Site-wide Reddit rules (no vote manipulation/spam) |
| https://www.redditinc.com/ | 200 → redirects to https://redditinc.com/ | Reddit corporate site; recorded in reddit.md §4 |
| https://arxiv.org/abs/2307.03172 | 200 | "Lost in the Middle: How Language Models Use Long Contexts" — used in devto_article.md; page metadata confirms title, submitted 2023-07-06, comment "Accepted for publication in TACL, 2023" |
| https://github.com/ | 200 | Generic GitHub reference in launch/README.md and awesome_lists.md |

## B. Awesome-list submission targets (verified via GitHub API / raw files)

All of the following returned HTTP 200 when first checked this session. The final sweep for the
`api.github.com` rows hit GitHub's unauthenticated rate limit (HTTP 403, 60 requests/hour, reset
11:23 local) — a rate-limit artifact, not a dead link; the same session had already fetched each
repository's metadata and raw README/CONTRIBUTING text.

| URL | Status | Role |
|---|---|---|
| https://api.github.com/repos/Vvkmnn/awesome-ai-eval | 200 earlier; final sweep 403 (rate limit) | List metadata: 127★, active, CC0-1.0, not archived |
| https://api.github.com/repos/Vvkmnn/awesome-ai-eval/readme | 200 earlier; final sweep 403 | README (30,357 B): sections and benchmark entries checked |
| https://api.github.com/repos/Vvkmnn/awesome-ai-eval/contents/CONTRIBUTING.md | 200 earlier; final sweep 403 | CONTRIBUTING rules checked (20-word cap, alphabetical, no badges, `pnpm lint`) |
| https://api.github.com/repos/danielrosehill/Awesome-AI-Evaluations-Tools | 200 earlier; final sweep 403 | Metadata: 29★, pushed 2026-11-23, no CONTRIBUTING.md |
| https://api.github.com/repos/danielrosehill/Awesome-AI-Evaluations-Tools/contents/ | 200 earlier; final sweep 403 | Root listing: README.md, data/, scripts/, .github/ (export-csv.yml) |
| https://api.github.com/repos/tensorchord/Awesome-LLMOps | 200 earlier; final sweep 403 | Metadata: active, CC0-1.0, `web_commit_signoff_required: true` |
| https://api.github.com/repos/tensorchord/Awesome-LLMOps/readme | 200 earlier; final sweep 403 | README (249,922 B): LLMOps table format checked |
| https://api.github.com/repos/tensorchord/Awesome-LLMOps/contents/contributing.md | 200 earlier; final sweep 403 | contributing.md rules checked (alphabetical, one PR per suggestion, scripts) |
| https://api.github.com/repos/benchflow-ai/awesome-evals | 200 earlier; final sweep 403 | Metadata: active, 1,049★ |
| https://api.github.com/repos/benchflow-ai/awesome-evals/readme | 200 earlier; final sweep 403 | README sections checked |
| https://api.github.com/repos/benchflow-ai/awesome-evals/contents/CONTRIBUTING.md | 200 earlier; final sweep 403 | CONTRIBUTING inclusion bar checked ("Tools need evidence someone else uses them" / "come back later") |
| https://api.github.com/repos/onejune2018/Awesome-LLM-Eval | 200 earlier; final sweep 403 | Metadata: 661★, last push 2025-11-24 (stale) |
| https://api.github.com/repos/onejune2018/Awesome-LLM-Eval/readme | 200 earlier; final sweep 403 | README table format checked |
| https://api.github.com/repos/onejune2018/Awesome-LLM-Eval/contents/CONTRIBUTING.md | **404** (recorded in draft) | No CONTRIBUTING.md — correctly recorded as absent |
| https://api.github.com/repos/alopatenko/LLMEvaluation | 200 earlier; final sweep 403 | Metadata: 208★, `has_discussions: true`, no CONTRIBUTING.md |
| https://api.github.com/repos/alopatenko/LLMEvaluation/contents/ | 200 earlier; final sweep 403 | Root listing checked (README.md only) |
| https://api.github.com/repos/brandonhimpfen/awesome-ai-benchmarks-evaluation | 200 earlier; final sweep 403 | Redirects to `awelist/awesome-ai-benchmarks-evaluation` (org, 14★, homepage is a link directory) — excluded |
| https://github.com/Vvkmnn/awesome-ai-eval · https://github.com/danielrosehill/Awesome-AI-Evaluations-Tools · https://github.com/tensorchord/Awesome-LLMOps · https://github.com/benchflow-ai/awesome-evals · https://github.com/onejune2018/Awesome-LLM-Eval | 200 (each) | Human-visible canonical repo pages for the five list targets |
| https://lnktr.net/awesome | 200 | Homepage of the excluded awelist org repo (link directory) |

## C. Outreach venues

| URL | Status | Role |
|---|---|---|
| https://thegradient.pub/ | 200 | The Gradient homepage |
| https://thegradient.pub/write/ | 200 | "Write" page; quotes checked ("filling out this short form", "If you seem like a good fit, an editor will reach out to you soon") |
| https://latent.space/ | 200 | Latent Space homepage |
| https://latent.space/about/ | 200 | About page; "For stories and tips: tips@latent.space" and business address checked |
| https://twimlai.com/ | 200 | TWIML AI Podcast homepage |
| https://twimlai.com/contact/ | 200 | Contact form; "Recommend a Guest" topic and form text checked |
| https://www.deeplearning.ai/the-batch/about | 200 | About page; listed under "do not pitch" (no editorial tip channel visible) |
| https://lastweekin.ai/about | 200 | About page; listed under "do not pitch" (sponsoring only) |
| https://ai.engineer/ | 200 | Watch list; homepage mentions CFPs but no open CFP form verified |

## D. Reddit official URLs and third-party trackers/mirrors (recorded as negative results)

The drafts state that Reddit blocks the build machine's automated clients; the sweep confirms it. These
URLs are listed in `launch/reddit.md` §4 so the owner knows exactly what could not be verified and must
read in a browser before posting. Statuses are recorded as observed, not as recommendations.

| URL | Status | What happened |
|---|---|---|
| https://www.reddit.com/r/MachineLearning/ | 200 (JS shell, no rule text) | Reachable but content not readable by automated client |
| https://www.reddit.com/r/MachineLearning/about/rules | 200 → redirects to /mod/MachineLearning/rules/; still a JS shell | Rule text not readable; owner must open in a browser |
| https://www.reddit.com/r/MachineLearning/about/rules.json | 403 | Blocked automated client |
| https://www.reddit.com/r/MachineLearning/wiki/index | 200 (JS shell) | Wiki not readable |
| https://www.reddit.com/r/LocalLLaMA/ | 200 (JS shell) | Reachable, rules not readable |
| https://www.reddit.com/r/LocalLLaMA/about/rules | 200 → /mod/LocalLLaMA/rules/ (JS shell) | Rules text not readable |
| https://www.reddit.com/r/LocalLLaMA/about/rules.json | 403 | Blocked |
| https://www.reddit.com/r/LLMDevs/ | 200 (JS shell) | Reachable, rules not readable |
| https://www.reddit.com/r/LLMDevs/about/rules | 200 → /mod/LLMDevs/rules/ (JS shell) | Rules text not readable |
| https://www.reddit.com/r/LLMDevs/about/rules.json | 403 | Blocked |
| https://old.reddit.com/r/MachineLearning/ | 403 | Blocked |
| https://old.reddit.com/r/MachineLearning/about/rules | 403 | Blocked |
| https://old.reddit.com/r/LocalLLaMA/about/rules | 403 | Blocked |
| https://old.reddit.com/r/LLMDevs/about/rules | 403 | Blocked |
| https://api.reddit.com/r/MachineLearning/about/rules | 403 | Blocked |
| https://sh.reddit.com/r/MachineLearning/ | 200 → redirects to www (JS shell) | No rule text |
| https://reddit.com/r/MachineLearning/ | 200 → redirects to www (JS shell) | No rule text |
| https://www.replyhey.com/subreddits/machinelearning | 200 | Third-party tracker: self-promotion "restricted", rules last read 2026-11-08 |
| https://www.replyhey.com/subreddits/llmdevs | 200 | Third-party tracker: self-promotion "restricted", rules last read 2026-08-25 |
| https://www.replyhey.com/subreddits/localllama | 200 (the draft records an earlier timeout; mirrors fluctuate) | Third-party tracker |
| https://spacestationlabs.ai/subreddits/localllama | 200 | Third-party tracker: r/LocalLLaMA rules incl. Limit Self-Promotion, Resources-not-News, 5-karma AutoMod gate; text marked "as archived in January 2025" |
| https://spacestationlabs.ai/subreddits/llmdevs | 200 | Third-party tracker: r/LLMDevs rules incl. no self-promotion (rule 5), source/AI-content attribution |
| https://spacestationlabs.ai/subreddits | 200 | Tracker index; confirms no r/MachineLearning guide exists there |
| https://spacestationlabs.ai/subreddits/machinelearning | 404 | Correctly recorded in the draft as a negative result |
| https://gummysearch.com/r/MachineLearning/ | 200 | Flair data (Project `[P]`, Discussion `[D]`, Research `[R]`, News `[N]`) |
| https://reddifier.com/free-subreddit-analysis-tool/r/MachineLearning | 200 | Loaded but client-side; recorded as not usable |
| https://www.subredditmarketing.com/subreddits/machinelearning | 200 (draft records earlier errors; fluctuates) | Not used for rules |
| https://leadsrover.io/subreddits/r/llmdevs | 200 (draft records an earlier timeout; fluctuates) | Not used |
| https://redlib.catsarch.com/r/MachineLearning | 429 | Mirror rate-limited |
| https://l.opnxng.com/r/MachineLearning | 429 | Mirror rate-limited |
| https://redlib.perennialte.ch/r/MachineLearning | 410 | Mirror gone |
| https://safereddit.com/r/MachineLearning | 200 (browser challenge page) | No content |
| https://r.jina.ai/https://www.reddit.com/r/MachineLearning/about/rules | 200 (draft records an earlier failure; fluctuates) | Proxy; no verified rule text captured |
| https://api.allorigins.win/raw?url=... | 522 | Proxy upstream timeout (matches draft ledger) |
| https://corsproxy.io/?url=... | 401 | Proxy requires API key (matches draft ledger) |
| https://api.codetabs.com/v1/proxy?quest=... | 522 | Proxy upstream timeout (matches draft ledger) |
| https://web.archive.org/web/2026/https://www.reddit.com/r/MachineLearning/about/rules | 200 → redirects to a 2025 Reddit login page | Archive snapshot is a login wall, no rule text |
| https://web.archive.org/web/2025/https://www.reddit.com/r/LocalLLaMA/about/rules | 503 | Archive unavailable |
| https://archive.ph/newest/https://www.reddit.com/r/MachineLearning/about/rules | transport error (TLS handshake timeout) | Archive unavailable |

**Net Reddit conclusion (unchanged from the drafts):** the official rule text could not be read in this
session. The launch kit therefore (a) tells the owner to open each sub's rules page in a browser on the
day of posting, and (b) labels every rule detail as coming from third-party trackers whose snapshots are
secondary sources. The URLs above are real and are the ones to open.

## E. What was verified in content, not just by status

- **HN rules text**: exact quotes from `showhn.html`, `newsguidelines.html` and the moderator tips item
  were read on 2026-11-24 and are quoted in `launch/show_hn.md` §4/§7; the tips item's 2026-03-28 edit
  ("Write your text by hand. Don't use an LLM to generate any of it...") is quoted verbatim.
- **HF venue facts**: category IDs and descriptions from `categories.json` (Show and Tell 65, Research 7,
  Hub 23) match the draft; content-policy §5 spam wording and forum-guideline wording were read and
  are quoted in `launch/hf_discussion.md`.
- **dev.to front matter**: `https://dev.to/p/editor_guide` documents `ai_disclosure_level`
  (`not_disclosed`, `no_ai`, `some_ai`, `fully_autonomous`) and a four-tag limit; the article's four tag
  pages all return 200.
- **arXiv**: the devto_article's "Lost in the Middle" citation matches the arXiv metadata (title,
  submission date 2023-07-06, TACL 2023 acceptance note).
- **Awesome-list rules**: the CONTRIBUTING text quoted for Vvkmnn (20-word cap, alphabetical, no
  badges, `pnpm lint`), tensorchord (alphabetical, one PR per suggestion, helper scripts), benchflow
  (external-use bar, disclose affiliation), onejune (no CONTRIBUTING.md; README welcomes PRs), and
  danielrosehill (PRs welcome, no CONTRIBUTING.md) was read from the repositories in this session.
- **Outreach policies**: The Gradient's write-form invitation, Latent Space's tips address, TWIML's
  "Recommend a Guest" form, The Batch's subscribe-only page, Last Week in AI's sponsoring-only page and
  AI Engineer's CFP mention were all read and are reflected in `launch/outreach.md`.
- **Probe walkthrough**: `launch/devto_article.md` cites `probes/reasoning_consistency/rea_arithmetic_01.json`
  (numeric scorer, expected 272); the scorer's actual behavior was executed this session — `272` PASS,
  `The answer is 272.` PASS, `391 - 119 = 272` FAIL with "expected 272 (tolerance 0.0) but found 391.0",
  and a word-only answer FAILs with "no number found in response" — exactly as the article states.

## F. Limitations

- Statuses are point-in-time. Policy pages and third-party trackers drift; the launch plan (§11 of
  `docs/DISTRIBUTION.md`) requires re-reading every venue's current rules on the day of posting.
- Third-party subreddit trackers are secondary sources. No official Reddit rule text was read
  successfully; the drafts say so explicitly and defer to the live sidebar.
- GitHub API rows were verified before the unauthenticated hourly limit was exhausted; re-checking after
  the reset is recommended but is not required for the launch, since the human-visible `github.com`
  pages for all six lists return 200.
- The three badge/badge-like URLs that contain `OWNER/REPO` placeholders are formatting templates, not
  live URLs, and cannot be tested until the repository owner publishes and fills them in.
- `https://github.com/Qin-z-x/llm-failbench` tokens are intentional and documented in `launch/README.md`; they are not broken links.
  They must be substituted before posting, and `launch/README.md` is the single substitution checklist.
