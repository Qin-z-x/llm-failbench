# FailBench Distribution Plan

**Status:** planning document + ready-to-use drafts. **Nothing in this repository is auto-posted.**
The repository owner (a human) publishes every item manually from their own accounts. The drafts in
`launch/` are inputs for that human, not executable marketing automation.

**Project state this plan assumes (verify at post time):** FailBench v0.2.0 pre-release, MIT code,
CC-BY-4.0 data, no users/stars/testimonials yet. The committed demo results were produced by the
deterministic **mock** provider — they are *not* measurements of any real model; no live model
endpoint was available during the build. Any public copy that mentions results must say this
plainly (see §10). Nothing here claims a benchmark measurement that the repository does not contain.

---

## 1. Ground rules

1. **One human owner is the publisher.** Every post, reply, PR, and form submission with the
   project's name is made by the owner from their own account. No fake accounts, no delegation of
   posting to automation, no purchasing engagement.
2. **Drafts, not broadcasts.** Files in `launch/` are tailored to one venue each. Do not paste the
   same text into multiple venues; adapt it. Do not cross-post the same body on the same day.
3. **Substance first.** The only durable distribution is a useful artifact: probes that reproduce,
   an evidence base people can check, and fast, honest responses. If a channel produces no
   substantive feedback, that channel is not working — change the artifact, not the volume.
4. **Rules before posting.** Re-read the current rules of each venue on the day of posting (links in
   §11). Rules change; this document can go stale.
5. **Disclose AI assistance** where the venue asks for it and where a reasonable reader could be
   misled otherwise (§10).

---

## 2. Pre-launch gate (Day 0 — owner actions)

Do not start the calendar until all of these are true:

- [ ] Repository is public with a final URL; substitute `https://github.com/Qin-z-x/llm-failbench` in every `launch/*.md` draft.
- [ ] `LICENSE` (MIT), `CITATION.cff`, `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
      `SECURITY.md` are present and reviewed.
- [ ] CI is green on the publish commit; `python -m failbench validate --strict`, the offline
      `unittest` suite, the mock demo run, report generation, and the determinism re-run all pass.
- [ ] `site/index.html` renders offline from the published tree (no network requests) and shows the
      mock-demo honesty banner.
- [ ] Issues are enabled with the evidence-submission / probe-request / bug templates; Discussions
      enabled only if the owner intends to answer them (otherwise leave it off — an empty forum is a
      bad signal).
- [ ] Labels created: `evidence-submission`, `probe-request`, `correction`, `bug`, `question`,
      `good-first-issue`, `release`.
- [ ] Release `v0.2.0` is tagged with release notes that repeat the mock-demo disclaimer.
- [ ] Optional: a GitHub Pages deployment of `site/` — only if it is regenerated on release; a stale
      dashboard is worse than none.
- [ ] **Baseline metrics snapshot** recorded (see §6), so day-14 deltas are real rather than guessed.
- [ ] The owner has read `launch/show_hn.md` §"Tough questions" and `docs/FAQ.md`; they should be able
      to answer methodology questions without improvising claims.
- [ ] Confirm: the demo on the published tree is still the mock run and the disclaimer has not
      drifted. If a real model run was added, label it as such (provider, model, date, settings) —
      never present mock output as a model measurement.

---

## 3. Launch asset map

| File | Venue | Notes |
|---|---|---|
| `launch/show_hn.md` | Hacker News (Show HN) | Title, body/link comment, first comment, tough-questions Q&A, rules note |
| `launch/x_thread.md` | X / Twitter | 6–8 tweet thread, ≤280 chars each |
| `launch/devto_article.md` | dev.to | 700–1000 word technical article, front-matter |
| `launch/linkedin.md` | LinkedIn | 200–300 word professional post |
| `launch/reddit.md` | r/MachineLearning, r/LocalLLaMA, r/LLMDevs | One tailored draft + rules notes per sub |
| `launch/hf_discussion.md` | Hugging Face community / forum | Community-tone discussion draft |
| `launch/awesome_lists.md` | Awesome lists / community indexes | Verified lists, contribution rules, exact PR snippets |
| `launch/outreach.md` | Newsletters / podcasts / communities | Pitches only where submissions are welcome |
| `launch/verification.md` | — | URL verification ledger for this workstream |
| `assets/banner.svg`, `assets/logo.svg` | Repo, posts, site | Self-made SVG, no external fonts/images |
| `CITATION.cff` | Repo | CFF 1.2.0, contributors-only authorship, no fabricated identities |

Internal drafting conventions live in `launch/README.md` (tokens and substitution checklist).

---

## 4. 14-day calendar

Day 1 = first public day. One or two channels per day maximum. Times are guidance, not guarantees:
weekday late-morning/early-afternoon US Eastern (roughly 14:00–17:00 UTC) is a commonly used window
for developer-audience posts; the owner should check the venue's current norms rather than treat this
as fact.

| Day | Channel | Owner action | Primary success signal (see §6) |
|---|---|---|---|
| 0 | Repo / release | Complete §2 gate; publish `v0.2.0`; record baseline metrics | CI green, release live, baseline recorded |
| 1 | Hacker News (Show HN) | Post using `launch/show_hn.md`; stay in the thread; answer every substantive question honestly within 48h. Do **not** ask for votes or share the link to solicit upvotes | Substantive methodological discussion; ≥1 reproducible bug/method critique |
| 2 | X / Twitter | Post `launch/x_thread.md` thread; reply to questions; no engagement-bait follow-ups | Questions from practitioners; no fake amplification |
| 3 | dev.to | Publish `launch/devto_article.md`; respond to comments | Substantive comments; corrections accepted |
| 4 | LinkedIn | Post `launch/linkedin.md` | Practitioner questions or issue reports |
| 5 | r/MachineLearning | Post the `[P]` draft from `launch/reddit.md` **only after** re-reading current sub rules and mod guidance; use the correct flair | Methodology critique; ≥1 evidence/probe suggestion |
| 6 | Hugging Face | Post `launch/hf_discussion.md` in the appropriate forum/discussion venue; begin 1–2 awesome-list PRs (one at a time, tailored) | Community response; PR accepted or useful review comment |
| 7 | — (review only) | **Weekly review #1:** metrics snapshot, triage all inbound, small fixes, update `CHANGELOG.md`; no new channels | 48h response SLA met; open issues triaged |
| 8 | r/LocalLLaMA | Post the LocalLLaMA draft from `launch/reddit.md`; check rules first | People actually running the kit locally; result reports |
| 9 | r/LLMDevs | Post the LLMDevs draft from `launch/reddit.md`; check rules first | CI-gate / eval-workflow questions |
| 10 | Newsletters / podcasts | Send pitches from `launch/outreach.md` — only to venues whose submission policy welcomes unsolicited pitches; max 3 on this day; one follow-up total, ever | A reply (even a "no") or an accepted submission |
| 11 | Patch release | Cut `v0.1.1` for confirmed bugs/corrections; add a real (clearly labeled) provider-run example if the owner ran one; respond to open PRs | Corrections shipped; contributor PRs reviewed |
| 12 | Awesome lists round 2 | 1–2 more PRs from `launch/awesome_lists.md`, each tailored to that list's format | PRs accepted; maintainer feedback |
| 13 | Follow-up content | Only if there is a real update: a short dev.to/X post about corrections made or probes added. No "engagement roundup" posts | Corrected claims visible; nothing deleted quietly |
| 14 | Retrospective | Metrics delta vs. baseline; list what produced substance and what did not; write v0.2 priorities (with W6/root) and decide whether to stop | A written go/no-go and a backlog, not more posting |

**If a post underperforms:** do not repost it, do not ask others to upvote it, do not delete it and
retry. Fix the artifact (docs, error messages, demo), then let the next scheduled channel carry the
improved version. HN in particular has strict Show HN rules and hostile reactions to vote
solicitation; one submission per launch, one repost only if the owner has a genuinely new milestone
and checks current rules first.

---

## 5. Sequencing and anti-spam rules

- Maximum **two public channels per day** and **one subreddit on any given day**.
- Space the three subreddit posts by at least **3 days** (this calendar uses days 5, 8, 9 — consider
  moving day 9 to 11 if day 5 drew mod attention; adapt, don't argue).
- Never paste identical text into two subreddits; each draft in `launch/reddit.md` is different for a
  reason.
- Do not post the same link in a subreddit where it has been posted before; check the sub's search
  first.
- One follow-up per person/venue, ever. If no reply, drop it.
- Weekend posting is not scheduled; reply within SLA, nothing else.
- If any venue removes a post for self-promotion rules, **do not** repost it elsewhere with the same
  framing; fix the framing or skip the channel.

---

## 6. Success metrics

Track **substance**, not vanity. Stars are a lagging side effect; do not optimize for them.

Baseline on Day 0 and then snapshot on Days 7 and 14. Sources are GitHub-native; record the raw
numbers and the date, never estimate from memory.

| Metric | Source | Why it matters |
|---|---|---|
| Repository views / unique visitors | GitHub Insights → Traffic | Did the channel actually send people? |
| Top referrers | GitHub Insights → Traffic → Referrers | Which channel worked; which didn't |
| Clones | GitHub Insights → Traffic → Clones | Do people actually try it? |
| Stars / forks / watchers | GitHub repo page | Weak signal, but forks predict contributions |
| Issues opened, by label | GitHub Issues with the templates/labels from §2 | The real output: reproducible reports |
| Evidence submissions / corrections | `evidence-submission`, `correction` labels | Atlas quality — the project's core promise |
| Probe PRs | PRs touching `probes/` | Community contribution to the corpus |
| External contributors | GitHub contributor graph | ≥1 non-owner code/data contribution is a win |
| Response time | Issue/PR thread timestamps | 48h SLA (§7) and one concrete target: median first response < 24h |
| Release downloads / PyPI (if published) | PyPI stats | Adoption proxy |
| Site visits (if Pages) | Analytics provider *only if disclosed*, otherwise skip | Optional; do not add tracking silently |

**Goals for the 14 days** (process goals chosen by the owner, not claims of achieved results):
≥3 substantive evidence/correction submissions; ≥1 external probe or code PR; all inbound triaged
within 48h; zero rules-violations removals; a written retrospective. If those are missed, the
retrospective says so plainly — it does not reframe vanity metrics as success.

---

## 7. Response SLA and triage

**SLA: first human response within 48 hours** to every issue, PR, and substantive comment that
mentions the project, during the 14-day window (and best-effort afterwards). A triage reply such as
"thanks — I can reproduce; scheduled for v0.1.1" counts; silence does not.

Triage buckets (use the labels from §2):

1. **Bug / incorrect claim** → verify, reproduce, fix, credit the reporter in `CHANGELOG.md` unless
   they ask not to be named. If a factual claim is wrong, publish the correction rather than quietly
   editing.
2. **Evidence submission** → check the source URL is real and reachable, the quote is verbatim and
   ≤200 chars, `status` stays `cited` unless a real test exists; merge with credit.
3. **Probe request / probe PR** → run the validation CLI, check the scoring is mechanical and
   unambiguous, merge or request changes.
4. **Methodology critique** → answer with the concrete scoring rule and evidence record; if the
   critique holds, open an issue and change the prose. "Good point, fixed" is better than defending
   a claim the repo cannot support.
5. **Usage/help question** → link the relevant doc; if the doc was unclear, fix the doc (that is a
   product bug too).

---

## 8. Iteration loop (feedback → release)

Weekly, during the launch window:

1. Collect all inbound feedback, issues, and PRs into one list.
2. Classify: bug / claim correction / missing evidence / probe gap / docs gap / usage question /
   feature request. Ignore engagement metrics in this step.
3. Fix the highest-frequency, lowest-cost items immediately; batch the rest into a patch release.
4. Update `CHANGELOG.md` with every behavior change, and regenerate `docs/RESULTS.md` + `site/` if
   results or counts changed.
5. If the demo run changes, keep the mock/real distinction explicit; never overwrite "mock" labels.
6. Announce only real changes, with links to the issue/PR. No "engagement recap" posts.
7. At day 14: stop the calendar, write the retrospective, and decide v0.2 scope from evidence —
   which probes people actually asked for, which evidence classes were challenged, which docs were
   read. Do not continue posting just because the calendar says so.

---

## 9. "DO NOT" list (non-negotiable)

- **No fake accounts, sockpuppets, or personas.** Ever.
- **No astroturfing** — no staged "users", no friends-in-the-comments theater, no manufactured
  testimonials, no fabricated quotes or endorsements.
- **No vote rings / upvote solicitation** — nothing like "upvote if you agree", no sharing links in
  chat groups asking for HN/Reddit votes, no link-swapping rings.
- **No paid stars, bots, engagement pods, or purchased "promotion"** that hides who paid.
- **No spamming unrelated threads** — do not drop the link into unrelated discussions, issue
  threads, PRs, mailing lists, or DMs.
- **No mass DMs or mass emails** — no scraped-contact blasts; one tailored pitch per venue, official
  submission forms first.
- **No impersonation** — of researchers, maintainers, HN/Reddit users, or organizations; no invented
  affiliations or credentials.
- **No fabricated data** — no invented benchmark numbers, user counts, stars, quotes, dates, or
  sources; the mock demo is never presented as a model measurement.
- **No silent edits** — do not quietly rewrite a claim after criticism; publish the correction
  (CHANGELOG/issue) and say what changed.
- **No deleting critical comments** or blocking good-faith critics; answer them.
- **No AI-scaled fake community activity** — automated replies, generated "user" voices, or bot
  accounts are out, even if they would look organic.
- **No bypassing rules** — if a venue prohibits self-promotion, the project is posted only where
  permitted; a removed post is not retried elsewhere with the same framing.

---

## 10. Transparency and authorship policy

FailBench's public claim is that every claim is sourced and every number reproducible. The same
standard applies to the project's own story:

- **Authorship is never misrepresented.** The project is published by its human owner, with
  contributions credited by contribution (code, evidence, probes, reviews), not by invented
  identities. `CITATION.cff` credits "llm-failbench contributors" because there is no single named
  academic author; individual names are added only with permission.
- **The project was built with AI assistance.** Parts of the code, documentation, and launch copy
  were developed with AI agents under human direction and review. This is disclosed to any person
  who asks how the project was built, and is disclosed up front wherever the venue's rules or norms
  require it (for example, platforms with AI-content or authorship-disclosure rules). We do not
  claim human-only authorship, and we do not present AI-generated engagement or content as
  human-authored.
- **Venue text rules win over convenience.** Some venues prohibit AI-generated or AI-edited post
  text outright. Hacker News is the strictest case: its guidelines say "Please don't put generated
  text in HN posts. Write your text yourself," and HN moderator "dang"'s tips thread (2026-03-28
  edit, linked from the Show HN guidelines) adds "Write your text by hand. Don't use an LLM to
  generate any of it (not even a tiny bit, including to edit or spruce it up)." Accordingly,
  `launch/show_hn.md` is explicitly background notes: the owner writes the HN submission and any HN
  comments personally, from scratch, and nothing is automated or pasted. For other venues, the
  owner follows each platform's current disclosure rules and states AI assistance plainly where it
  is expected.
- **The owner is accountable.** A human reviews and takes responsibility for every claim published
  under the project's name, including AI-assisted text. If something is wrong, the correction is
  public.
- **Demos are labeled.** Mock-provider demo output is labeled as mock everywhere it appears. Real
  model runs, when they exist, are labeled with provider, model, date, and settings, and are never
  blended into the demo.
- **Sources are real.** Cited reports are linked and were checked when collected; the
  `scripts/validate/check_links.py` check is run before release. A dead source link is a bug, not a
  rounding error.

---

## 11. Platform rules quick reference (verified 2026-11-24)

Re-read rules at post time; these links were reachable when this document was written.

| Venue | Rules / policy URL | What the owner must check |
|---|---|---|
| Hacker News — Show HN | https://news.ycombinator.com/showhn.html | Show HN is for things people can try; original work; no vote solicitation |
| Hacker News — guidelines | https://news.ycombinator.com/newsguidelines.html | No generated or AI-edited text in posts/comments; no self-promo spam; no asking for votes |
| Hacker News — moderator tips | https://news.ycombinator.com/item?id=22336638 | Linked from the Show HN page as "tips about how to present your work"; 2026-03-28 edit requires text written by hand, no LLM generation or editing |
| Hacker News — FAQ | https://news.ycombinator.com/newsfaq.html | Reposting rules, what counts as a Show HN |
| Reddit — r/MachineLearning | https://www.reddit.com/r/MachineLearning/ | `[P]` tag for projects, self-promotion limits; read rules in a browser (rules JSON blocked automated fetch) |
| Reddit — r/LocalLLaMA | https://www.reddit.com/r/LocalLLaMA/ | Self-promotion and link rules; read rules in a browser |
| Reddit — r/LLMDevs | https://www.reddit.com/r/LLMDevs/ | Self-promotion rules; read rules in a browser |
| Reddit — site rules | https://redditinc.com/policies/reddit-rules | No vote manipulation, no spam, no ban evasion |
| Hugging Face — code of conduct | https://huggingface.co/code-of-conduct | Community conduct; no spam/self-promo abuse |
| Hugging Face — Hub discussions docs | https://huggingface.co/docs/hub/repositories-pull-requests-discussions | Where discussions belong (Hub repo discussions vs. forum) |
| dev.to — code of conduct | https://dev.to/code-of-conduct | Original content, no spam, disclosure of sponsored/AI content per current policy |
| LinkedIn — professional community policies | https://www.linkedin.com/legal/professional-community-policies | No spam, no fake profiles, no misleading content |
| GitHub — issue templates docs | https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository | Template configuration used by the repo |
| GitHub — topics docs | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics | Discoverability (topics, not spam) |
| GitHub — traffic insights | https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-traffic-to-a-repository | Metric source for §6 |

The full per-URL verification ledger for the launch kit is in `launch/verification.md`.

---

## 12. Verification of this document

- All policy/guideline URLs above were fetched with an HTTP client on 2026-11-24; statuses are
  recorded in `launch/verification.md`. Reddit rules JSON endpoints return HTTP 403 to automated
  clients even though the subreddit pages load, so the plan explicitly requires reading sub rules in
  a browser at post time instead of relying on cached copies.
- This document makes no claim of achieved users, stars, downloads, or model measurements. Every
  project claim refers to files in this repository or to the documented v0.2.0 scope; anything about
  future results is labeled as such.
