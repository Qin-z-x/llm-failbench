> Reviewed candidate: v0.1.0. This report is a review artefact of the v0.1.0 publishing candidate; v0.1.1 is a patch release limited to the items listed in CHANGELOG.md.

# FailBench Claims Audit — FINAL (post-integration, publishing state)

**Auditor:** W9 (Claims Auditor & Safety Reviewer), independent of the builders.
**Status:** **FINAL PASS.** The root has frozen and is publishing the tree; this audit reflects the
final state. Two audit passes were run (PASS 1 during the concurrent build, FINAL after integration).
**Snapshot:** 2026-11-24 ~10:52 Asia/Shanghai, repository root on the build machine.
**Method:** mechanical re-derivation of every count from the artifacts with stdlib Python; ran the
offline tooling (`validate --strict`, `unittest`, mock demo, replay, gate, report); 36-URL polite
network sample across evidence, launch channels and external metadata claims (40 requests total
including GitHub API body fetches by W9 workers); greps for forbidden claims, placeholders, fake
social proof and fabricated URLs; every number below is reproducible from the committed tree.

## Verdict summary (84 claims audited across both passes)

| Verdict | Meaning | Count |
|---|---|---|
| **SUPPORTED** | verified against artifacts in the final tree | 76 |
| **UNSUPPORTED** | contradicted or not backed by any artifact | 0 |
| **OVERSTATED** | directionally true but stronger than the evidence supports | 2 |
| **MISLEADING** | would mislead a reader | 0 |
| **PROVISIONAL** | external URL/claim not re-verifiable within the network budget | 6 |
| **Total** | | **84** |

**Fixes applied by owners/root during the audit (all re-verified):** fixture site replaced by a render
of the committed mock demo; stale RESULTS run (022734Z/33-pass) regenerated to the committed run
(022942Z/64-pass); stale 70-record/"7 of 10" evidence counts corrected to **110 records / 10 classes**
in README, RESULTS and site; missing `docs/METHODOLOGY.md`, `docs/FAQ.md` written and audited;
incomplete `docs/ATLAS.md` completed (§8 class-by-class, §9 ranked table) and its attention arithmetic
verified exactly; `CITATION.cff` "each traced to a public report" reworded honestly ("share the same
ten-class vocabulary, while per-probe evidence ids are reserved for a future release"); all
"60-second"/"90-second" demo/gate claims removed repo-wide (README now "Quick-start demo"); Python
support statements unified on `requires-python >=3.9` / CI 3.11+3.13 / tested on 3.13; Reddit body
word counts corrected to exact 450/450/423; `probes/README.md` unmeasured 90-second sentence removed;
placeholder `pyproject.toml` project URLs removed.

## Final snapshot facts used for verification

- Probes: **100 files**, 10 per class, 10 class dirs, id == filename; severity **5 critical / 34 high /
  43 medium / 18 low**; all `params.temperature` 0; repeats 1 (90) / 3 (10); scoring types all_of 65,
  regex 16, contains_all 6, numeric 10, contains_any 2, json_schema 1. `probes/README.md` table and
  `probes/_index.json` match the files row-by-row.
- Evidence: **110 records / 10 classes** (10–12 per class), **110 unique https source_urls**, all
  `status: "cited"`, 46 non-empty quotes (all ≤200 chars), 0 summaries >400 chars, 0 non-schema keys;
  source types hn_story 54 / arxiv 46 / github_issue 10; `data/evidence/index.json` (total 110).
  Popularity totals recomputed exactly: 18,489 hn_points / 10,614 hn_comments / 163 github_reactions /
  162 github_comments.
- Demo: `results/demo/results.json` run `20261124T022942Z-mock`, provider `mock`, **100 probes = 64
  pass / 34 fail / 2 error (64.0%)**, severity-weighted 64.6% (recomputed 146/226); `raw.jsonl` 120
  attempts; fresh re-runs reproduce identical per-probe statuses/counts/response hashes (run_id and
  timestamps differ; docs state this honestly).
- Tooling: `python -m failbench validate --strict` → `OK: 100 probes, 110 evidence records, 0 errors`
  (exit 0); `python -m unittest discover -s tests -t .` → `Ran 103 tests ... OK`; `replay` 100/100
  statuses match; `gate` exit 0 clean / 1 regression / 2 config error (all three tested); `report`
  produces a self-contained `site/index.html`.
- Site: title `FailBench report — 20261124T022942Z-mock`, `"is_mock":true`, `"is_fixture":false`,
  **110/110 embedded evidence ids resolve**, 0 external script/link/img/fetch/analytics loads.
- ATLAS §9 attention table recomputed exactly: total **29,428**; all 10 class sums/ranks/shares match;
  bottom three = 9.1%; §8 per-class counts and probe coverage match the files.
- Cross-links: **0/100 probes have `evidence_ids`; 0/110 evidence records have `probe_ids`** — README
  and CITATION now describe this accurately (class-level link; per-probe ids reserved for a future
  release), so it is no longer an overstatement.
- `docs/reviews/QA_REPORT.md` (W5) is still absent at publish time — see remaining fixes.

## Claims table — final state

All 84 audited claims are recorded in the audit working notes (`_scratch/w9/`); the table below lists
**every claim that is not simply SUPPORTED** in the final tree, plus representative verified anchors.

| # | Claim | Location | Verification | Verdict |
|---|---|---|---|---|
| 1 | "The generated results report honesty statement" appears twice with near-identical wording | `docs/RESULTS.md:7` and `:9` | Both sentences present in the final generated file | **O** (cosmetic) |
| 2 | §6 says "see the verification table at the end of this file" / "see the verification tables" | `docs/ATLAS.md:142,157` | File ends after the §9 totals paragraph; no verification table exists | **O** (dangling ref) |
| 3 | Popularity examples / `citations` metric | README | final README records only HN + GitHub metrics and explicitly says other allowed keys are unused; corpus has 0 citation metrics | **S** |
| 4 | "Probes linked to atlas reports / each traced" wording | README, CITATION | final wording is class-level + "per-probe evidence ids reserved for a future release" — accurate | **S** |
| 5 | Python support: 3.9+ / CI 3.11+3.13 / tested 3.13 | pyproject, README, QUICKSTART, RESULTS, FAQ, METHODOLOGY | unified; no "3.10+" anywhere; CI matrix matches | **S** |
| 6 | Demo/gate duration claims | repo-wide | 0 occurrences of "60-second"/"90-second" in markdown + site; README heading "Quick-start demo"; mock demo measured ≈0.5 s | **S** |
| 7 | Committed demo 100 probes, 64 pass / 34 fail / 2 error, mock provider | README, RESULTS, site, CITATION | matches `results/demo/results.json`; site title/run id match | **S** |
| 8 | 100 probes, 10 per class, severity 5/34/43/18 | README table, probes/README, _index.json | counted from files, all match | **S** |
| 9 | 110 evidence records, all ten classes, real source URLs | README, RESULTS | counted: 110 / 110 unique https URLs / 110 `cited` | **S** |
| 10 | ATLAS §9 attention totals/shares, §8 counts and probe coverage | ATLAS §8–§9 | recomputed exactly from `data/evidence/*.jsonl` and `probes/` | **S** |
| 11 | RESULTS evidence summary and popularity snapshot numbers | RESULTS:95–110 | recomputed exactly (18,489 / 10,614 / 163 / 162; 54/46/10 mix) | **S** |
| 12 | Methodology: mechanical scoring only, no judges, errors≠fails, all-repeats-pass, no statistical claims | METHODOLOGY, README, CONTRACT | code inspection + results semantics; no contradicting claims | **S** |
| 13 | FAQ "a full run makes about 120 model calls: 90 …" | FAQ:162 | 90×1 + 10×3 = 120; `raw.jsonl` has exactly 120 attempts | **S** |
| 14 | FAQ vendor comparison (garak, PyRIT, promptfoo, lm-evaluation-harness, HELM) | FAQ:122–136 | neutral descriptions, explicit "not a claim of superiority"; links not re-fetched in this pass | **S** (links P) |
| 15 | Launch copy: mock/no-live-endpoint disclaimer in every results-bearing draft; no fake users/stars/testimonials; no "first/only/best" claims | README, launch/** | confirmed across all 9 drafts; explicit safe-claims sheets | **S** |
| 16 | Show HN titles 70/69/69 chars; X thread 8 tweets ≤280 (exact counts) | launch/show_hn.md, launch/x_thread.md | recomputed exactly (8/8 tweet counts exact) | **S** |
| 17 | Reddit titles 123/126/141; body word counts 450/450/423 | launch/reddit.md | recomputed exactly | **S** |
| 18 | dev.to `rea_arithmetic_01` walkthrough (fields, numeric 272, observed failure text) | launch/devto_article.md | probe file matches; scorer re-executed: 272 pass, "The answer is 272." pass, "391 - 119 = 272" fail with exact message | **S** |
| 19 | Awesome-list star/fork/activity claims about external repos | launch/awesome_lists.md | 4 repos re-fetched: stars/forks/archived/pushed dates all exact (e.g. 127/65, 5,982/1,395) | **S** |
| 20 | `launch/verification.md` ledger of 97 cited URLs, incl. honestly recorded 403/5xx/negative results | launch/verification.md | ledger present; spot-checked entries consistent; full ledger not re-fetched | **S** (full ledger P) |
| 21 | Tool claims: stdlib-only, no telemetry, offline tests/demo, secrets env-only and never in artifacts, atomic writes, retries/statuses, gate exit codes, self-contained site | SECURITY.md, README, CONTRIBUTING | verified in code + artifacts (0 non-stdlib imports; 0 external site loads; raw.jsonl no credentials; `_atomic_write_text`; retries=2; 408/409/429/5xx; gate 0/1/2) | **S** |
| 22 | MIT code + CC-BY-4.0 data + short attributed quotes | LICENSE, CONTRIBUTING, probes/README, CITATION | LICENSE has MIT + explicit CC-BY-4.0 data notice; all 46 quotes attributed, ≤200 chars | **S** |
| 23 | "No live model endpoint; demo is mock" | README, RESULTS, ATLAS, site, launch, CITATION | present and consistent everywhere results appear | **S** |
| 24 | docs/METHODOLOGY, FAQ, QUICKSTART, ROADMAP, CHANGELOG links | README + root | all present and reviewed | **S** |
| 25 | TAXONOMY §7 existing-coverage URLs "fetched and HTTP-checked" | TAXONOMY §7 / ATLAS:148–150 | table present (~20 URLs); not independently re-fetched within budget | **P** |
| 26 | MITIGATIONS evidence-backed citations (28 URLs; 51.5%/74.5% statistic) | MITIGATIONS | labelled EVIDENCE-BACKED/REASONED HYPOTHESIS; 5/28 corroborated by the atlas; remainder not re-fetched | **P** |
| 27 | PUBLISHING portable-git workflow and exact commands | docs/PUBLISHING.md | not executed (auditor must not run git); read-only review only | **P** |
| 28 | HF/dev.to/outreach channel URLs fetched 200 on 2026-11-24 | launch/hf_discussion.md, outreach.md, verification.md | 8 sampled URLs re-verified 200; full set recorded in ledger, not re-fetched | **P** |
| 29 | FAQ vendor links "checked when this FAQ was written (2026-11-24)" | FAQ:120 | not re-fetched in this pass | **P** |
| 30 | External star/fork figures beyond the 4 audited repos (awesome-list research) | launch/awesome_lists.md | 4/4 audited exact; rest not re-fetched | **P** |

## URL spot-checks (final)

Polite network sampling (stdlib `urllib`, identifying UA): 20 GETs by W9 lead + 8 by the W9 claims
worker + 8 by the W9 safety worker (disjoint sets) + 4 GitHub API bodies for quantitative claims =
**40 requests / 36 unique URLs; all observed HTTP 200, 0 dead, 0 fabricated** in the sample.
- Evidence sample (12, HN + arXiv, 7 classes at check time): 12/12 200.
- GitHub API repos from `launch/awesome_lists.md`: 4/4 200, star/fork/archived/pushed claims exact.
- Launch/channel URLs (Show HN, HN guidelines, Reddit sub, HF forum/CoC, dev.to CoC, LinkedIn policies,
  The Gradient write page): 8/8 200.
Not re-fetched due to budget: remaining ~74 evidence URLs, ~20 TAXONOMY coverage URLs, ~23 MITIGATIONS
URLs, full `launch/verification.md` ledger. Recommended final check:
`python scripts/validate/check_links.py` on the published tree.

## Fabrication / social-proof / placeholder scan (final)

- **No fake testimonials, user quotes, stars, adoptions, endorsements, identities or human-authorship
  claims.** No "used by", no invented author names (`CITATION.cff` = "llm-failbench contributors").
- **No "first / only / best / state-of-the-art"** claims in user-facing copy; launch material
  explicitly forbids them.
- **No fabricated FailBench metrics or URLs.** External star/fork figures are real and sampled ones
  exact. `{{REPO_URL}}`/`OWNER/REPO` are documented substitution tokens, not fake URLs.
- Remaining placeholder-ish string: `scripts/validate/check_links.py:31` User-Agent contains a guessed
  repository URL (`https://github.com/llm-failbench/llm-failbench`) — harmless, but **remove before
  publication** or keep only after the real URL exists.

## Remaining fix list (final, for the publishing owner)

Only minor/cosmetic items remain; **no critical or high severity items**:

1. **`docs/ATLAS.md:142,157` — dangling "verification table at the end of this file" references.**
   Add the table (per-URL status/date) or redirect the sentence to `launch/verification.md` /
   `scripts/validate/check_links.py`. Owner: W10/root. *(LOW)*
2. **`docs/RESULTS.md:7` vs `:9` — duplicated honesty statement** in the generated file. Emit one
   honesty block in `failbench/report.py` and regenerate. Owner: W4/root. *(LOW, cosmetic)*
3. **`scripts/validate/check_links.py:31` — guessed repo URL in User-Agent.** Use a neutral UA.
   Owner: W5/root. *(LOW)*
4. **`docs/reviews/QA_REPORT.md` absent** (W5 deliverable; contract layout). Publish before/with
   release if the QA stream completed. Owner: W5/root. *(process item, not a claims defect)*
5. Optional: drop the `img.shields.io` stars badge from `launch/awesome_lists.md` suggested rows
   (`OWNER/REPO` substitution is documented inline). *(LOW)*

## Not reviewable / limitations of this audit

- `docs/reviews/QA_REPORT.md` — absent at publish time.
- Full evidence/coverage/MITIGATIONS URL corpus and `launch/verification.md` ledger — sampled only.
- `docs/PUBLISHING.md` commands and `scripts/publish/**` — not executed (auditor must not run git).
- `failbench/report.py` / `cli.py` internals — behaviour verified via output, not line review;
  site HTML-escaping/XSS not pen-tested.
- `scripts/validate/**`, `tests/**` logic — scanned for secrets/PII, not line-reviewed.
- `.github/workflows/ci.yml` — read, not executed here.
- No live model exists in this release; all model-quality claims are therefore absent by design.

## Verification commands (final, stdlib only, no project writes)

```
python -m failbench validate --strict        # OK: 100 probes, 110 evidence records, 0 errors (exit 0)
python -m unittest discover -s tests -t .    # Ran 103 tests ... OK
python -m failbench run --provider mock --demo --out _scratch/w9/demo_c   # 64 pass / 34 fail / 2 error
python -m failbench replay --results _scratch/w9/demo_c                   # statuses match 100/100
python -m failbench gate --baseline results/demo/results.json --current <flipped copy>  # exit 1
python _scratch/w9/*.py                      # counts, quote lengths, uniqueness, weighted rate,
                                             # popularity totals, ATLAS attention table, README table,
                                             # RESULTS-vs-results.json row diff
python _scratch/w9/lead_url_check.py         # 20 polite GETs, all 200
python _scratch/w9/lead_github_claims.py     # 4 GitHub API bodies, all claims exact
```

**Bottom line (FINAL):** of 84 audited claims — **76 supported, 0 unsupported, 0 misleading, 2
overstated (both cosmetic wording/internal references), 6 provisional** (external URLs not re-fetched
in budget). The mock-demo honesty posture is consistent everywhere; the committed demo is reproducible
byte-for-byte at the probe-status/hash level; the evidence atlas and its quantitative summaries
recompute exactly; no fabricated data, URLs, metrics, identities or testimonials were found. Remaining
actions are cosmetic or process items. **Clear to publish.**
