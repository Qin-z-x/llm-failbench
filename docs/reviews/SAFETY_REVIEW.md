> Reviewed candidate: v0.1.0. This report is a review artefact of the v0.1.0 publishing candidate; v0.1.1 is a patch release limited to the items listed in CHANGELOG.md.

# FailBench Safety / Ethics / Licensing Review — FINAL (post-integration, publishing state)

**Reviewer:** W9 (independent of the builders).
**Status:** **FINAL PASS.** The root has frozen and is publishing the tree; findings below reflect the
final state. A PASS-1 review ran during the concurrent build and was re-run after integration.
**Snapshot:** 2026-11-24 ~10:52 Asia/Shanghai, repository root on the build machine.
**Method:** stdlib-only scans over the whole committed tree (100 probes, 110 evidence records, 9
launch drafts, `site/index.html`, all root/docs files, scripts); full manual read of the 10
`safety_consistency` probes; regex audits for harmful content / PII / secrets / fake social proof /
astroturfing; licence and attribution checks; 36-URL polite network sample (launch/channel/evidence,
40 requests total including W9 workers). **Not a legal review** — licence statements are checked for
consistency with the repository's own declarations.

## Overall risk assessment

**Overall: LOW.** **0 critical, 0 high, 0 medium.** 8 LOW findings remain; every one is cosmetic,
placeholder-hygiene, or a docs-completeness nit. No safety, ethics, privacy, licensing, or
promotion-integrity failure was found. The tree contains no jailbreak payloads, exploit code, malware,
harmful instructions, PII, copied long-form text, fake testimonials/metrics/identities, astroturfing
instructions, or credential leaks; the mock/offline status is disclosed in every results-bearing
artifact; the static site loads no external resources.

**Fixed by owners/root during the audit (re-verified):** (1) a labelled synthetic-fixture site with 18
evidence ids absent from the repo → regenerated from the committed mock demo (110/110 ids resolve,
`"is_mock":true`, `"is_fixture":false`); (2) RESULTS.md describing run 022734Z/33-pass while
`results/demo` held 022942Z/64-pass → regenerated and matching; (3) stale 70-record/"7 of 10" evidence
counts in README/RESULTS/site → now 110 records / 10 classes; (4) missing `docs/METHODOLOGY.md` and
`docs/FAQ.md` → written and reviewed; (5) incomplete `ATLAS.md` → §8 class-by-class and §9 ranked
attention table added (arithmetic re-verified exactly); (6) `CITATION.cff` "each traced" and README
popularity wording → reworded honestly; (7) all 60-/90-second time claims removed repo-wide (README
now "Quick-start demo"); (8) Python support statements unified (3.9+ / CI 3.11+3.13); (9)
`pyproject.toml` placeholder project URLs and stale `probes/README.md` severity table fixed.

## A. Issue table (final)

| ID | file:line | Severity | Description | Recommended fix |
|---|---|---|---|---|
| SAF-201 | `docs/ATLAS.md:142,157` | **LOW** | Dangling "see the verification table(s) … at the end of this file" — no verification table exists (file ends after §9 totals). | Add the table or redirect the sentence to `launch/verification.md` / `scripts/validate/check_links.py`. Owner: W10/root. |
| SAF-202 | `docs/RESULTS.md:7` vs `:9` | **LOW** | Generated honesty statement duplicated with near-identical wording. | Emit one honesty block in `failbench/report.py`; regenerate. Owner: W4/root. |
| SAF-203 | `docs/reviews/QA_REPORT.md` | **LOW** | W5 QA report still absent at publish time (contract layout completeness). | Publish before release if the QA stream completed. Owner: W5/root. |
| SAF-204 | `probes/context_retrieval/ctx_key_buried_01.json` (+ its excerpt in RESULTS/site) | **LOW** | Synthetic secrets use the Stripe live-key prefix (`sk_live_…`). Clearly invented (fabricated services, random hex) and harmless, but can trip secret scanners / read as leaked credentials. | Use unmistakably synthetic prefixes (`sk_synthetic_…`, `demo-key-…`) and regenerate. Owner: W2/root. |
| SAF-205 | probes/evidence corpora | **LOW** | Per-record probe↔evidence cross-links are empty (`evidence_ids`/`probe_ids` all `[]`). Docs now describe this honestly (class-level link; per-probe ids reserved for a future release); contract permits it. | Reconcile in a future release, not required for v0.1.0. Owner: root/W1/W2. |
| SAF-206 | `failbench/schema.py` evidence validator; `scripts/evidence/collect_hn.py` | **LOW** | `validate_evidence` does not reject unknown keys; the HN collector captures public `_author` handles in scratch-only candidate lines. Committed evidence has 0 non-schema keys today. | Reject unknown keys / strip `_`-prefixed keys; keep handles scratch-only. Owner: root/W1. |
| SAF-207 | `scripts/validate/check_links.py:31` | **LOW** | Link-checker User-Agent embeds a guessed repository URL (`https://github.com/llm-failbench/llm-failbench`) that does not exist yet. | Use a neutral UA without a guessed URL. Owner: W5/root. |
| SAF-208 | `launch/awesome_lists.md` | **LOW** | Suggested awesome-list rows contain `img.shields.io` stars badges with `OWNER/REPO` placeholders. Substitution is documented inline; unsubstituted it breaks the badge, and a stars badge can read as star-soliciting. | Keep the substitution instruction; optionally drop the stars badge. Owner: W7/root. |

## B. Required checks 1–9 (final)

**1) No jailbreak payloads / exploit code / malware / social-engineering scripts — PASS.**
All 100 probe prompts concatenated and scanned for override/jailbreak phrasing, weapon/bio/malware,
credential theft, phishing scripts. None. The 10 `safety_consistency` prompts were read in full: they
measure **over-refusal on harmless prompts** (school chemistry, general cold-symptom info, non-graphic
fiction, smoke detectors, kitchen-knife safety, phishing-awareness training, conceptual
ransomware/backups, concept-level SQL injection, blunt-vs-polite framing) and each explicitly forbids
payloads/steps. Evidence titles describe phenomena, not instructions. Launch material and SECURITY.md
explicitly forbid publishing payloads and route serious model findings to private vendor disclosure
first.

**2) No PII / private / leaked data — PASS (one residual low note).**
No private personal data in probes, evidence, site, docs or launch copy; committed evidence contains
only public HN/arXiv/GitHub metadata and **no HN usernames**. Remaining addresses are public
organisational contacts (`tips@latent.space`) and a GitHub `noreply` template. Residual note SAF-206.

**3) Copyright / quote discipline — PASS.**
No source text >100 chars copied into probes (synthetic filler; only a short title "Nineteen
Eighty-Four" named, unquoted). 46 evidence quotes, all ≤200 chars and attributed via
`source_url`/`source_title`/`publisher`; unverified quotes are `""`. LICENSE states quoted excerpts
remain the authors' property as short attributed quotations. No external fonts/images/CDN in site or
SVGs.

**4) No harmful medical / legal / financial advice presented as fact — PASS.**
MITIGATIONS is engineering remediation advice labelled `[EVIDENCE-BACKED]` / `[REASONED HYPOTHESIS]`;
no diagnosis, dosage, treatment, investment, tax or legal-advice assertions. `saf_cold_symptoms_01`
asks for general symptom info with an explicit "not medical advice" instruction (an over-refusal
probe, not advice). FAQ/METHODOLOGY reviewed: no advice presented as fact.

**5) No fake testimonials / metrics / identities / human-authorship claims — PASS.**
No testimonials, user quotes, star/adoption/usage claims, endorsements or invented persons.
`CITATION.cff` credits "llm-failbench contributors"; AI assistance is disclosed in launch copy,
DISTRIBUTION §10 and dev.to front-matter; no human-only authorship claim. External star/fork figures
in `launch/awesome_lists.md` concern *other* repositories and the four sampled were verified exactly
via the GitHub API. No fabricated FailBench metric exists; the demo is mock-labelled everywhere.

**6) No astroturfing / account-creation / vote-manipulation instructions — PASS.**
The launch kit contains explicit prohibitions: no fake accounts/sockpuppets, no vote rings/upvote
solicitation, no mass DMs/emails, no paid stars, no impersonation, no ban-evasion; one post per venue,
one subreddit per day, days apart. Nothing is auto-posted; every draft is published manually by the
human owner from the owner's own account. The karma-gate note advises genuine participation only.

**7) Promotion honesty / mock-demo disclosure / self-contained site — PASS.**
Mock-disclaimer present in README, CITATION, RESULTS, ATLAS, site (honesty banner + `"is_mock":true` +
title run id) and every results-bearing launch draft. `site/index.html` (633,132 B) is self-contained:
0 external script/link/img/fetch/XHR/analytics loads, inline CSS/JS/data, system fonts, 110/110
evidence ids resolve, plain `<a>` source links only. `publish.ps1` is plan-only by default (publish
requires `-Execute`), reads `GITHUB_TOKEN` from the environment only and masks it in output. All
60-/90-second duration claims removed by root.

**8) Licensing / attribution — PASS (one low nuance).**
Code MIT (`LICENSE`, `pyproject.toml`, `CITATION.cff`); data CC-BY-4.0 with an explicit data notice
naming `data/evidence/**` and `probes/**` (`LICENSE:23–28`), repeated in CONTRIBUTING, probes/README,
RESULTS and launch copy. Attribution complete (check 3). Assets are self-made SVG with accessible
`<title>/<desc>`, no external fonts/images. Nuance: `CITATION.cff` has a single `license: MIT` field
(CFF cannot express a separate data licence) — acceptable; CC-BY-4.0 is documented in LICENSE/docs.
`.env*`, `_scratch/`, logs and non-demo results are gitignored.

**9) Model-vendor fairness — PASS.**
No vendor rankings, leaderboards, bashing or unsupported vendor claims. TAXONOMY §7 and FAQ describe
public tools/benchmarks neutrally with explicit "not a claim of superiority"; model-specific numbers
are attributed to their papers. ATLAS/RESULTS disclaim ranking and affiliation.

**Model-failure findings policy — PASS.** `SECURITY.md` requires reproducible verification, no
publication of exploit details, private vendor notification first (default 90-day window), then narrow
documentation; SECURITY.md and MITIGATIONS both cover responsible disclosure, scope out harmful
payloads, and make no fake bounty/SLA promises.

## C. Launch / channel URLs and secret handling

- 8 launch/policy URLs re-verified 200 by the W9 safety worker (HN Show HN + guidelines, HF forum +
  FAQ, dev.to CoC, Reddit site rules, LinkedIn policies, The Gradient write page); 4 more channel URLs
  by the lead (all 200); 4 GitHub API repo URLs (all 200). `launch/verification.md` exists (97 cited
  URLs) and honestly records its own 403/5xx/Reddit-block negative results rather than presenting them
  as working channels. No fabricated channel URLs found.
- Whole-tree secret scan: no real credentials. `openai_compatible.py` keeps the key private, redacts
  it from messages/`repr`, and scrubs `sk-…` shapes; `raw.jsonl` contains no request headers/keys;
  `publish.ps1` masks the token and defaults to a plan. Tests use clearly synthetic fixtures. The only
  scanner-tripwire strings are the synthetic `sk_live_…` needles (SAF-204).

## D. What was NOT reviewed (explicit)

- `docs/reviews/QA_REPORT.md` (absent at publish time).
- The full final freeze is as of the files re-checked here; any post-audit edit by other owners is not
  covered.
- `failbench/report.py` / `cli.py` internals (behaviour verified via output; site HTML-escaping not
  pen-tested); `scripts/validate/**` and `tests/**` logic (secret/PII scan only); CI workflow read but
  not executed.
- `docs/PUBLISHING.md` commands and `scripts/publish/**` not executed (auditor must not run git);
  review limited to reading parameter/token handling.
- Full URL corpus (`launch/verification.md`, TAXONOMY §7 coverage, MITIGATIONS citations) — sampled
  (36 unique URLs); citation accuracy beyond the sampled evidence not independently verified.
- Model behaviour: no live model run exists in this release; probe safety reasoning is static, not
  empirical.
- `_scratch/**` (gitignored build scratch) except audit tooling.

## E. Verification commands (final, stdlib only, no project writes)

```
python _scratch/w9/corpus_scan.py probes      # per-probe danger/PII/copyright flags: all clean
python _scratch/w9/corpus_scan.py evidence    # 110 records: 0 PII; "jailbreak" term only as a
                                              # quoted phenomenon description, no instructions
python _scratch/w9/lead_safety_checks.py      # PII/email/phone, >100-char quoted text (none),
                                              # AI-free/fake-credential scan (none), sockpuppet
                                              # instructions (negations only), quote attribution and
                                              # length checks (clean), publish-token masking
python _scratch/w9/show_probes.py "probes/safety_consistency/*.json"   # full manual read
python -m failbench validate --strict         # OK: 100 probes, 110 evidence records, 0 errors
python -m unittest discover -s tests -t .     # Ran 103 tests ... OK (offline)
grep scans: jailbreak|ignore previous|malware|ransomware|phishing|exploit|payload|credential|
  sk-|ghp_|AKIA|PRIVATE KEY|email|phone over probes/**, data/evidence/**, docs/*.md, launch/**,
  site/index.html, README.md
```

**Bottom line (FINAL):** safety, privacy, copyright, medical/legal/financial advice, identity,
astroturfing, disclosure, licensing, secret-handling and vendor-fairness checks **PASS**.
**0 critical, 0 high, 0 medium; 8 low cosmetic/process items.** The release is safe to publish from an
ethics/safety/licensing standpoint; the two documentation nits worth fixing in the next patch are the
dangling ATLAS verification-table references and the duplicated RESULTS honesty sentence.
