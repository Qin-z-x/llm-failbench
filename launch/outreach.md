# Outreach targets (draft, not sent)

**Project:** FailBench v0.1.0 (pre-release) — *The evidence-backed, judge-free failure probe kit for LLMs.*
**Prepared:** 2026-11-24 · **Owner:** repo owner (W7 draft; nothing here has been sent)
**Scope:** 3 real venues — a publication, an AI-engineering publication/podcast, and an ML podcast — whose
official pages I verified this session. **Nothing here has been emailed, posted, or submitted.**

> **Single substitution:** pitches below use the token `https://github.com/Qin-z-x/llm-failbench`, which the owner replaces with the
> final public repo URL after publishing. That is the only substitution. No live GitHub URL is invented, the
> project is **not** claimed to be listed or covered anywhere yet, and no real-model results may be claimed:
> the committed demo run uses the deterministic **mock** provider.

## Hard rules (read first — non-negotiable)

1. **Only contact venues where unsolicited pitches/submissions are demonstrably welcome.** Use the official
   form/address listed for that venue; if a venue only has a subscribe or sponsor path, do not pitch it.
2. **Use the official submission form or the official tips address.** Do not guess personal emails, do not
   DM hosts/editors on X/LinkedIn, do not use contact-scraping lists.
3. **No mass DMs, no copy-paste blasts.** One venue per message, tailored; never BCC a list.
4. **No press-release spam.** These are short, personal pitches with one idea each — not "FOR IMMEDIATE
   RELEASE" announcements.
5. **Disclose pre-release status honestly.** Say v0.1.0 is pre-release, that the committed demo results come
   from the deterministic mock provider (not measurements of any real model), and that no live model endpoint
   was used during the build. Never imply users, traction, coverage, stars, or benchmark numbers.
6. **Owner sends from the owner's own address, under the owner's own identity.** No fake accounts, no
   impersonation, no paid "guaranteed placement".
7. **One follow-up maximum**, after 10–14 days; if there is no reply, mark it closed.
8. **Respect opt-outs immediately.** If a venue says no or asks not to be contacted, record it and do not
   re-approach; remove contacts on request.
9. **Do not ask for stars, votes, or coverage of the "project's launch";** offer substance (a method, a
   result-free-but-honest artifact, a perspective), and do not claim endorsement.

## Verification table (verified in-session from the build machine, 2026-11-24)

Every row below was checked with direct HTTPS requests from the build machine on 2026-11-24 (the session's
`web_fetch` tool also reached some of these hosts, but the ledger records what the lead re-verified).

| URL (verified in-session) | HTTP status | Date | What I observed |
|---|---|---|---|
| https://thegradient.pub/ | 200 | 2026-11-24 | The Gradient homepage: articles, newsletter, podcast, and a "Write" nav link. Real, active publication. |
| https://thegradient.pub/write/ | 200 | 2026-11-24 | "Write" page: open invitation to write with The Gradient, "fill out this short form" (Google Form link on the page), "If you seem like a good fit, an editor will reach out to you soon". |
| https://latent.space/ | 200 | 2026-11-24 | Latent Space homepage: articles, podcast, daily AI News, community, subscribe. Archive shows an evals episode, "The End of SWE-Bench Verified — Mia Glaese & Olivia Watkins, OpenAI Frontier Evals & Human Data". |
| https://latent.space/about/ | 200 | 2026-11-24 | About page: "For partnerships: business@latent.space"; **"For stories and tips: tips@latent.space"**; describes publication + podcast + community. |
| https://twimlai.com/ | 200 | 2026-11-24 | TWIML AI Podcast homepage ("The Voice of Machine Learning and Artificial Intelligence"): podcast, newsletter, community, blog. |
| https://twimlai.com/contact/ | 200 | 2026-11-24 | Official contact form: Name, Email, **Topic select includes "Recommend a Guest"** (also Sponsorship Inquiry, Partnership Opportunity, Other/General Inquiry), Message; "All fields are required except newsletter signup." |
| https://www.deeplearning.ai/the-batch/about | 200 | 2026-11-24 | The Batch about page: describes the newsletter; only subscribe navigation. No tip/pitch/guest channel visible — evidence for the DO-NOT list, not a venue. |
| https://lastweekin.ai/about | 200 | 2026-11-24 | Last Week in AI about page: who they are and a **"Sponsoring"** form only. No editorial tip/pitch channel visible — DO-NOT list. |
| https://ai.engineer/ | 200 | 2026-11-24 | AI Engineer conference site: flagship events, talk videos, and mention of "CFPs" in the newsletter signup block, but **no verified open CFP/pitch form** on the page. Watch list only, do not pitch now. |

---

## 1. The Gradient — written-pitch venue (best fit for an article idea)

- **Name / URL:** The Gradient — https://thegradient.pub/
- **Who it's for:** AI researchers, practitioners, and technically literate readers; a non-profit,
  volunteer-run publication with an article platform, newsletter, and podcast. It explicitly aims to be a
  platform for people who do not already have a large following.
- **Why it fits FailBench:** the project's distinguishing claim is methodological — deterministic,
  judge-free scoring with sourced evidence — which is exactly the kind of "accessible but technically
  informed overview" or "critical perspective" The Gradient publishes. The pitch should be an **article
  idea**, not a release announcement; the project appears only as the worked example.
- **Submission/contact policy verified:** the "Write" page (https://thegradient.pub/write/) states you can
  "Learn more about how you can write with The Gradient by filling out this short form" (official Google
  Form linked from that page) and "If you seem like a good fit, an editor will reach out to you soon".
  Unsolicited pitches are welcome through that official form; email address is not published, do not guess
  one. No deadlines; editors respond to fit.
- **One-paragraph pitch (≤120 words):**
  > Hi — I'd like to pitch a short perspective piece for The Gradient: "What a judge-free eval can actually
  > tell you." The argument is practical, not promotional: LLM-as-judge scores are useful but expensive and
  > contestable, so a deterministic probe suite with mechanical pass/fail rules is a complementary regression
  > tool, and its limits (it measures failures, not quality) are as interesting as its uses. I built a small
  > open-source artifact along these lines, FailBench (https://github.com/Qin-z-x/llm-failbench), now v0.1.0 pre-release; its committed
  > demo results come from a deterministic mock provider, not real model measurements, and I'd disclose that
  > in the piece. I'm happy to send an outline or full draft.
- **Status:** **Open to unsolicited pitches via the official form** (verified). This is a writing pitch, not
  a product-promotion channel — do not send a launch blurb.
- **Follow-up:** none needed; if an editor replies, answer with an outline and disclose the pre-release state
  again.

## 2. Latent Space — short tip to the AI-engineering audience

- **Name / URL:** Latent Space — https://latent.space/ (about: https://latent.space/about/)
- **Who it's for:** AI engineers building with models: practitioners who read the articles, listen to the
  podcast, and follow the daily AI News briefing; the publication is explicitly "by and for AI engineers".
- **Why it fits FailBench:** evals are a recurring Latent Space theme — the archive includes "The End of
  SWE-Bench Verified" with OpenAI's eval team — and a judge-free, mechanically scored probe kit is a
  concrete engineering object their audience can run against their own endpoints. The honest "no judges, no
  API keys needed for the demo" angle is a good tip shape.
- **Submission/contact policy verified:** the About page lists **"For stories and tips: tips@latent.space"**
  (and a separate business address for partnerships). There is **no formal guest-pitch form** on the public
  pages, so this is a **tips channel only**: send one short, factual tip; do not pitch a podcast guest and
  do not use the business address for editorial tips.
- **One-paragraph pitch (≤120 words):**
  > Hi — tip for the Latent Space team: I built an open-source probe kit, FailBench (https://github.com/Qin-z-x/llm-failbench), that runs
  > deterministic, judge-free failure probes across 10 LLM failure classes with fully mechanical scoring — no
  > LLM judge, no third-party Python dependencies, and an offline mock-provider demo so you can see the
  > outputs without an API key. It's v0.1.0 pre-release; the committed demo results are from the mock
  > provider, not real model measurements. Given your coverage of benchmark and eval problems, a "no judge,
  > no vibes: what deterministic probes can catch" item might fit. Happy to answer questions or share a
  > short walkthrough; no coverage expected.
- **Status:** **Tips welcome at the published tips address** (verified); no formal pitch/guest form.
  One short email, no attachments; treat silence as "not now".
- **Follow-up:** one only, after ~14 days, and only if the tip was time-sensitive; otherwise skip.

## 3. TWIML AI Podcast — recommend-a-guest form

- **Name / URL:** TWIML AI Podcast — https://twimlai.com/ (contact: https://twimlai.com/contact/)
- **Who it's for:** ML/AI practitioners, researchers, and technical leaders; a long-running podcast plus a
  newsletter and community covering machine learning and AI research/engineering.
- **Why it fits FailBench:** the show regularly covers model evaluation, reliability, and production ML.
  A conversation about *why mechanical, judge-free probing is a useful complement to LLM-as-judge* is a
  substantive topic, and the project is a concrete worked example rather than a product pitch. Only pitch
  the episode if the owner is prepared to speak on the record about the method's limitations and the
  mock-provider demo status.
- **Submission/contact policy verified:** the official contact form (https://twimlai.com/contact/) has a
  required **"Topic"** select that includes **"Recommend a Guest"**; the page says "Please use the form below
  to contact us and we'll be in touch shortly." This is the sanctioned channel for guest suggestions.
  Do not DM hosts or use private addresses.
- **One-paragraph pitch (≤120 words):**
  > Hi — using your contact form's "Recommend a Guest" option: I'd like to suggest a conversation about
  > judge-free evaluation: deterministic, mechanically scored probes as a regression tool for LLM failure
  > modes, where they help, and where LLM-as-judge is still needed. I'm happy to appear as maintainer, or to
  > suggest a different guest if that is a better fit; I maintain FailBench (https://github.com/Qin-z-x/llm-failbench), a v0.1.0
  > pre-release open-source probe kit covering 10 failure classes with no LLM judges and an offline mock
  > demo — its committed results are from the deterministic mock provider, not real model measurements. If
  > it's not a fit for the show, no problem at all; I appreciate the work you all do.
- **Status:** **Guest recommendations accepted via the official form** (verified). This is not a guarantee of
  an episode; do not follow up more than once.
- **Follow-up:** one, after ~14 days; if no response, close it.

---

## Watch list (verified, but do not pitch yet)

- **AI Engineer / AI Engineer conferences** — https://ai.engineer/ (homepage 200, 2026-11-24). Real
  conference/community for AI engineers, and a natural place for an eventual talk on judge-free evals, but
  the homepage only mentions "CFPs" in a newsletter signup block and **no open CFP or pitch form was
  verified**. Action: follow the newsletter and wait for an official CFP to open; submit only through that
  CFP, never by DM to organizers. This is not a place for a launch tip.

## DO NOT contact / not a fit

1. **Paid promotion and sponsor slots** (AI newsletters that sell placement, "featured project" packages,
   paid directories/link farms). Pay-to-play contradicts the project's honest-status and public-evidence
   framing, and it is not needed. Skip entirely.
2. **Mega AI news roundups with no verified editorial tip channel.** The Batch (verified about page shows
   only subscribe/business navigation) and Last Week in AI (verified about page shows only a "Sponsoring"
   form) are legitimate publications but offer no unsolicited-pitch route on their public pages. Do not
   cold-email editors or send a launch press release; they cover news, not pre-release OSS projects.
3. **Mass DMs, press-release blasts, and drive-by self-promo.** No bulk X/LinkedIn DMs, no posting the same
   text across Discord servers/Subreddits/HN, no asking anyone to "support the launch", no vote/star requests,
   no fake accounts. If a community's rules don't explicitly allow project sharing, don't post.

When in doubt: check the venue's own published policy page (the URLs above were checked on 2026-11-24),
re-read it at send time, and if there is no explicit welcome channel, do not contact.
