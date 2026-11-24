# Launch kit — read this first

**These files are drafts for the repository owner. Nothing here is posted automatically.**
Every public action (Show HN, Reddit, X, LinkedIn, dev.to, Hugging Face, awesome-list PRs, newsletter
pitches) is performed manually by the human owner from their own accounts after the repository is
published. No fake accounts, no vote solicitation, no engagement buying.

## Before posting — substitution checklist

The project does not have a final public URL at build time, so drafts use one explicit token:

- `https://github.com/Qin-z-x/llm-failbench` — replace with the final public repository URL after `v0.1.0` is published
  (e.g. `https://github.com/<owner>/<repo>`). This is the **only** substitution required. If a draft
  mentions a website/Pages URL, use `https://github.com/Qin-z-x/llm-failbench` plus the path, and only if that deployment exists.

After substitution, re-check every draft for claims that may have drifted:

1. **Demo honesty line** — the committed demo uses the deterministic mock provider; it is not a
   measurement of any model. This line must remain in every draft that shows results.
2. **Counts** — frozen v0.1.0 numbers are already in the drafts: 100 probes (10 per class; severity 5
   critical / 34 high / 43 medium / 18 low), 110 cited evidence records (54 Hacker News, 46 arXiv, 10 GitHub
   issues), and the committed demo run: 100 probes, 64 pass / 34 fail / 2 error, deterministic mock provider
   only. Re-check the README count table before posting if the repository changed.
3. **No fabricated social proof** — no users, stars, quotes, or endorsements.
4. **Links** — every URL in a post should resolve; `launch/verification.md` records what was verified
   at build time (2026-11-24). Re-check anything that may have moved.
5. **Venue rules** — re-read the current rules linked in the draft and in `../docs/DISTRIBUTION.md`
   §11 on the day of posting. Rules change; the plan can go stale.
6. **Disclosure** — if asked how the project was built, answer honestly: it was built with
   substantial AI assistance under human direction and review. Disclose AI assistance up front where
   the venue requires it. Never claim human-only authorship.

## File map

| File | Venue | Published by |
|---|---|---|
| `show_hn.md` | Hacker News (Show HN) | owner, own HN account |
| `x_thread.md` | X / Twitter | owner, own account |
| `devto_article.md` | dev.to | owner, own account |
| `linkedin.md` | LinkedIn | owner, own account |
| `reddit.md` | r/MachineLearning, r/LocalLLaMA, r/LLMDevs | owner, own account, one sub at a time |
| `hf_discussion.md` | Hugging Face community/forum | owner, own account |
| `awesome_lists.md` | Awesome lists / indexes | owner opens PRs (no auto-PR, no spam) |
| `outreach.md` | Newsletters / podcasts / communities | owner, only where submissions are welcome |
| `verification.md` | URL verification ledger for the launch kit | — |

Artwork: `../assets/banner.svg` (1280×320), `../assets/logo.svg` (256×256). Self-made SVG, no
external fonts/images, accessible `<title>`/`<desc>`.

## Posting order (from `../docs/DISTRIBUTION.md` §4)

Day 1 HN → Day 2 X → Day 3 dev.to → Day 4 LinkedIn → Day 5 r/MachineLearning → Day 6 Hugging Face
(+ first awesome-list PRs) → Day 8 r/LocalLLaMA → Day 9 r/LLMDevs → Day 10 newsletter pitches →
Day 11 patch release → Day 12 second round of awesome-list PRs → Day 14 retrospective. At most two
channels per day; at most one subreddit per day; no cross-posting identical text.

## Hard rules (short version)

- **Hacker News has an unusually strict AI-text rule.** Its guidelines say "Please don't put generated
  text in HN posts. Write your text yourself," and HN moderator "dang"'s tips thread (2026-03-28
  edit, linked from the Show HN guidelines) says "Write your text by hand. Don't use an LLM to
  generate any of it (not even a tiny bit, including to edit or spruce it up)." Therefore
  `show_hn.md` is **background notes only**: the owner must write the HN title/body/comment
  personally, from scratch. Do not paste or lightly edit any draft into HN, and never automate
  posting or commenting there.
- No asking for upvotes/stars/likes; no "please share"; no engagement bait.
- No fake accounts, astroturfing, vote rings, paid stars, engagement pods.
- No spamming unrelated threads, no mass DMs/emails, no impersonation.
- No invented benchmarks, users, quotes, or testimonials; mock demo is always labeled mock.
- Correct mistakes publicly (issue/CHANGELOG); do not silently rewrite claims.

Full detail: `../docs/DISTRIBUTION.md` §9–§10. Transparency policy: §10.

## Timeline reminder

v0.1.0 is a pre-release. The launch is an invitation to test, critique, and contribute evidence —
not a victory lap. If a channel underperforms, improve the artifact; do not repost or solicit votes.
