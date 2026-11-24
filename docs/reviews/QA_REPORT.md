> Reviewed candidate: v0.1.0. This report is a review artefact of the v0.1.0 publishing candidate; v0.1.1 is a patch release limited to the items listed in CHANGELOG.md.

# FailBench QA Report — W5 (QA & CI)

**Date:** 2026-11-24 (Asia/Shanghai, UTC+08:00), final gate run at ~10:45
**Environment:** Windows 11 host, `python` 3.13.15 (32-bit), PowerShell 7; no network for the offline
suite, no third-party Python packages, no `git` commands were run (root owns publishing).
**Scope:** the frozen publishing candidate of `llm-failbench` v0.1.0 — 100 probes (10/class),
110 evidence records (10–12/class), committed mock demo `results/demo/` (100 probes, 64 pass / 34
fail / 2 error), generated `site/index.html` and `docs/RESULTS.md`, 103 unit tests.

## Verdict: **PASS** (ship-ready, zero unresolved critical/high defects)

`python scripts/validate/run_all.py` → **PASS (9 passed, 0 failed, 0 skipped)**, exit 0.
`python scripts/validate/check_contract.py` (strict) → **PASS (0 failures, 1 informational warning)**,
exit 0. Three residual low-severity items are listed under "Open items" and are non-blocking.

## Deliverables verified in this report (W5 scope)

| File | Purpose |
|---|---|
| `scripts/validate/check_contract.py` | strict 10-check contract gate (C1–C10), `--strict` default, `--allow-incomplete` for early stage |
| `scripts/validate/run_all.py` | offline orchestrator: contract, unittest, CLI validate, mock demo ×2, determinism, report, site sanity, gate, root files |
| `scripts/validate/check_links.py` | separate network link checker for evidence `source_url`s (never run by CI) |
| `.github/workflows/ci.yml` | ubuntu-latest, Python 3.11 + 3.13 matrix, `permissions: contents: read`, offline steps |
| `docs/reviews/QA_REPORT.md` | this report |

All four are stdlib-only and run from the repo root on Windows PowerShell and on Linux CI.

## Method

1. Read `docs/CONTRACT.md` and `failbench/schema.py`; audited every deliverable against the contract.
2. Delegated independent workers for the three validation tools plus a baseline root-file audit; then
   personally reviewed, corrected and integrated their output (see "QA changes made during the build").
3. Ran the tools against the evolving tree, kept an independent adversarial audit (placeholders,
   secrets, cross-file numbers, broken relative links, YAML structure, probe/evidence cross-checks,
   artifact-vs-contract shape checks, site-vs-evidence-link reconciliation) in an OS temp directory
   (not committed), and re-ran everything on the frozen candidate.
4. Network checks: evidence links via `check_links.py` (polite, sequential, 0.2 s delay) plus a
   spot-check of external URLs cited by the W10 docs.

## Final gate results (actual observed output)

### check_contract.py (strict, default) — exit 0

```
PASS [C1] schema validation: 0 errors (probes=100, evidence=110)
PASS [C2] per-class counts: all 10 classes have >= 8 probes and >= 8 evidence records
PASS [C3] unique ids: 100 probe ids and 110 evidence ids are unique
PASS [C4] placeholder scan: no placeholder patterns in 166 text files (1 detector file(s) exempted)
PASS [C5] secret scan: no secret-like values in 182 text files
PASS [C6] demo results valid: provider=mock, probes=100 pass=64 fail=34 error=2
PASS [C7] site is self-contained and honest: site/index.html (633132 bytes, honesty markers present)
PASS [C8] docs/RESULTS.md: honesty sentence present and demo counts (probes=100 pass=64 fail=34 error=2) found as tokens; note: pass-rate/percentage present; derived values are display-only
PASS [C9] README explains the mock provider and lists runnable CLI commands
PASS [C10] parsed 100 probe JSON files and 110 evidence JSONL records without error
SUMMARY: checks=10, pass=10, warn=1, fail=0; probes=100, evidence=110
CONTRACT: PASS (0 failures, 1 warnings)
```

(The single warning is informational: the pass-rate percentage in `docs/RESULTS.md` is treated as a
display-derived value, not an independently recomputed token.)

### run_all.py — exit 0

```
+--------------------+--------+--------------------------------------------------------------------------------+
| STEP               | RESULT | DETAIL                                                                         |
+--------------------+--------+--------------------------------------------------------------------------------+
| CONTRACT           | PASS   | contract gate passed (strict, complete corpus)                                 |
| UNITTEST           | PASS   | unittest discover OK (7 test module(s))                                        |
| CLI_VALIDATE       | PASS   | validate --strict returned 0                                                   |
| DEMO_RUN           | PASS   | two mock demo runs exited 0 and wrote results.json                             |
| DETERMINISM        | PASS   | identical across 100 probes (pass=64, fail=34, error=2); results.json shape OK |
| REPORT             | PASS   | generated index.html (633187 bytes)                                            |
| SITE_SANITY        | PASS   | 633187 bytes; honesty markers present; no remote script/link/fetch/XHR         |
| GATE_DEMO_VS_RERUN | PASS   | gate reports no regressions between demo run A and re-run B                    |
| ROOT_FILES         | PASS   | all 5 required root files present                                              |
+--------------------+--------+--------------------------------------------------------------------------------+
RESULT: PASS (9 passed, 0 failed, 0 skipped)
```

Notes: determinism is checked the only sound way for this contract — two fresh mock runs normalized to
`{probe_id: (status, response_sha256)}` + `counts`; `run_id`, timestamps and latency are ignored
(byte-identical `results.json` is impossible by design because CONTRACT §7 requires real run ids and
timestamps). `run_all.py` renders its report and `RESULTS.md` into a temp directory, so it does not
mutate committed artifacts (verified: `site/index.html` and `docs/RESULTS.md` hashes unchanged across a
run). Committed `docs/RESULTS.md` is instead validated by C8.

### Independent checks (exact commands and observed results)

| Command | Observed |
|---|---|
| `python -m unittest discover -s tests -t . -v` | `Ran 103 tests in 8.848s` → `OK`, exit 0 |
| `python -m failbench validate --strict` | `OK: 100 probes, 110 evidence records, 0 errors`, exit 0 |
| `python -m failbench --version` | `python -m failbench 0.1.0`, exit 0 |
| `python -m failbench list` / `list --json` | 100 probes listed; valid JSON, exit 0 (cp936 console safe) |
| `python scripts/validate/check_links.py --limit 25 --timeout 12` | 25/25 HTTP 200, 0 dead, dead ratio 0.0%, `RESULT: PASS`, exit 0 (110 unique evidence URLs total) |
| W10 doc URL spot-check (12 sampled from 151 cited URLs in TAXONOMY/ATLAS/MITIGATIONS) | 12/12 reachable: 7×HEAD 200, 5 Hacker News HEAD 405 → GET 200; 0 dead |
| Artifact cross-check script | `results/demo/results.json` and `raw.jsonl` satisfy CONTRACT §7: provider=mock, base_url=null, 10 classes, counts 100/64/34/2 consistent with `probes[]` and `by_class`, 120 raw lines for 100 probes/120 attempts, no `api_key`/`sk-` material; all 110 site external `<a href>` links exactly equal the 110 evidence `source_url`s (0 extra, 0 missing), all anchors carry `rel="noopener noreferrer"` |
| README claim re-derivation | 100 probes/10 each, severity mix 5 critical / 34 high / 43 medium / 18 low, 110 evidence records, 64/34/2 demo, 2 demo errors are mock "synthetic transport failure" — all match files |
| `docs/RESULTS.md` cross-check | honesty sentence present; counts 100/64/34/2 present as standalone tokens; per-class rows match `results.json.by_class`; 64.0% overall and 64.6% severity-weighted both reproducible |
| Placeholder/secret scan (independent) | 0 real hits: `example.com`/`example.org`/`lorem ipsum` absent outside docs/templates; uppercase `PLACEHOLDER`/`TODO:`/`XXX` markers absent outside docs/tests; no `sk-…`, `ghp_…`, `github_pat_…`, `AKIA…`, no `.env`/private-key files |
| Absolute-path scan | `docs/CONTRACT.md` scrubbed by root; `docs/PUBLISHING.md` scrubbed by W8; remaining absolute paths are only in this review file's environment note |
| Assets | `assets/banner.svg`, `assets/logo.svg` are valid XML with no external references |
| `.github/workflows/ci.yml` | 184 lines; structural validation (no PyYAML available offline): required keys/steps present, `contents: read`, no `secrets.*`, no `check_links`; both embedded Python heredocs compile (`compile(..., "exec")` OK); matrix `["3.11","3.13"]` |
| Repo inventory | 194 files (excluding `_scratch/` and `__pycache__/`); `results/` contains only `results/demo/`; all contract §2 required deliverables present |

## Defects found and disposition

Severity: critical / high / medium / low. "Fixed" means re-tested and confirmed by the owner of the
file; W5 never edited files outside its scope.

| ID | File:line | Sev | Description | Recommended fix | Status |
|---|---|---|---|---|---|
| QA-01 | `failbench/scoring.py:141,169` | high | `exact_match` ignored `case_sensitive`: response was lowercased unconditionally, so `"ABC"` vs value `"ABC"` failed while `"abc"` passed. Reproduced, then root fixed. | normalize with the flag | **fixed** (root; re-verified both directions) |
| QA-02 | `failbench/scoring.py:213` | medium | `numeric` stripped all commas, so `1,234` matched value 1234 despite CONTRACT §6's first-number rule. | remove comma stripping | **fixed** (root; re-verified `1,234`→1) |
| QA-03 | `failbench/schema.py:158-162` | medium | date fields regex-only; `2026-13-45`, `2026-02-30` validated. | `datetime.date.fromisoformat` | **fixed** (root; re-verified) |
| QA-04 | `failbench/schema.py:68` | low | `PROBE_ID_RE` did not enforce `_<2 digits>` suffix from CONTRACT §3/§5. | enforce suffix | **fixed** (root; re-verified) |
| QA-05 | `failbench/scoring.py:183` | low | `bool("false") is True` made non-bool `negate` values truthy in unvalidated specs. | `is True` | **fixed** (root; re-verified) |
| QA-06 | `failbench/schema.py:83,124` | low | BOM-prefixed UTF-8 JSONL aborted validation. | `utf-8-sig` | **fixed** (root; re-verified with BOM fixture) |
| QA-07 | `pyproject.toml:27-28` | medium | placeholder project URLs `https://github.com/`. | real URLs or remove | **fixed** (root: `https://github.com/Qin-z-x/llm-failbench`; will 404 until the repo is pushed) |
| QA-08 | `docs/CONTRACT.md:3,91` | medium | public contract leaked local machine paths plus an unrelated project name. | generic paths | **fixed** (root) |
| QA-09 | `site/index.html` (fixture), `docs/RESULTS.md` (stale run) | high | early tree shipped a labeled fixture site and stale results (different run/counts). | regenerate from committed mock demo | **fixed** (W4; final hashes below; C7/C8 pass) |
| QA-10 | `tests/test_runner.py:1007` | medium | literal `sk-DUMMY…` fake API key in tests — trips secret scanners/push protection even though it is a fixture. | concatenate token parts | **fixed** (W3; C5 PASS) |
| QA-11 | `.github/workflows/ci.yml` site-sanity step | high | inline CI check forbade any `href="http`, which would fail on the contract-required external `<a href>` evidence links. | forbid only external *resource* loads | **fixed** (W5) |
| QA-12 | `scripts/validate/run_all.py:REPORT` | medium | `report` step regenerated committed `docs/RESULTS.md` as a side effect, so QA runs dirtied the tree. | render Markdown to temp, cross-check committed file in C8 | **fixed** (W5; verified hashes stable across run) |
| QA-13 | `scripts/validate/check_contract.py` (C4 initial) | high | case-insensitive placeholder scan produced 22 false positives (GitHub issue-form `placeholder:` keys, legitimate prose) — a green CI would be impossible. | uppercase-only marker matching; data patterns still case-insensitive; document tests/detector exemptions | **fixed** (W5; gate now PASS) |
| QA-14 | `docs/PUBLISHING.md:4,9,113,116,1296` | medium | hardcoded `C:\Users\28643\Downloads\llm-failbench` paths in a public publishing guide. | `<repo-root>` placeholder | **fixed** (W8) |
| QA-15 | `docs/ATLAS.md:142,157` | low | referenced a "verification table at the end of this file" that did not exist. | add appendix or fix pointer | **fixed** (W10 added §10 appendix with recomputed data/URL tables) |
| QA-16 | `docs/RESULTS.md:116` (template) | low | said "plain `python` 3.10+" while pyproject/QUICKSTART say 3.9+. | one canonical claim | **fixed** (W4: "Python 3.9 or newer; CI exercises 3.11 and 3.13") |
| QA-17 | `site/index.html` + README | low | "60-second demo" (site) vs "~90-second regression gate" (CONTRACT/TAXONOMY) — unmeasured time claims. | neutral wording, no time claim | **fixed** (W4 removed site time claims; W6 retitled README `## Quick-start demo`) |
| QA-18 | `CITATION.cff` abstract | medium | claimed probes are "each traced to a public report" while 0/100 probes carry `evidence_ids` (link is class-level only). | honest class-level wording | **fixed** (W7; claim re-checked) |
| QA-19 | `launch/*` drafts | low | same per-probe-citation overstatement in launch copy; `example.com` sample URL. | corrected wording / real URLs | **fixed** (W7) |
| QA-20 | `probes/README.md` severity table | low | early severity counts were stale. | regenerate from files | **fixed** (W2/W9; current 5/34/43/18 matches) |

No critical defects remain. All high/medium items above were confirmed fixed on the frozen tree.

## Open items (non-blocking, all low severity)

| ID | File:line | Description | Recommended action |
|---|---|---|---|
| OPEN-1 | evidence `probe_ids` / probe `evidence_ids` | Both are empty by design in v0.1.0 (README/CITATION now state this honestly). Not a defect, but reviewers should not expect per-probe grounding. | Future release: populate cross-links per CONTRACT §4/§5. |
| OPEN-2 | `pyproject.toml:11` vs `.github/workflows/ci.yml:23` | Metadata declares `requires-python = ">=3.9"`, but CI only exercises 3.11 and 3.13, and only 3.13 ran locally. 3.9/3.10 runtime compatibility is claimed but untested. | Add 3.10 (or 3.9) to the CI matrix, or raise the floor to `>=3.11` and align docs. This is a root decision; the W5 CI deliverable explicitly specifies the 3.11/3.13 matrix. |
| OPEN-3 | `pyproject.toml` `[project.urls]`, `CITATION.cff` `repository-code` | Root set the intended public URL `https://github.com/Qin-z-x/llm-failbench`; it 404s until the owner pushes, and CITATION.cff intentionally omits `repository-code`. Expected pre-release state; ensure the URL exists at publish time and then add `repository-code`. | Verify the target repo exists after push; add CFF `repository-code`. |

## QA changes made during the build (W5 scope only)

1. Refined `check_contract.py` C4: data placeholders (`example.com`, `example.org`, `lorem ipsum`) stay
   case-insensitive; unfinished-content markers (`PLACEHOLDER`, `TODO:`, `XXX`) match the uppercase
   literals from the gate spec, eliminating false positives on legitimate GitHub issue-form
   `placeholder:` keys, HTML input attributes and prose. Documented exemption: the placeholder-detector
   constants in `scripts/evidence/verify_provenance.py` (and the checker itself) are not unfinished
   content; `tests/` fixtures are exempt per CONTRACT §10.4 for both C4 and C5.
2. Fixed the CI site-sanity snippet to forbid only external resource loads (`<script src>`, `<link href>`,
   `fetch(`, `XMLHttpRequest`) and allow the required external `<a href>` evidence links; added a
   temp `--results-md` path so CI does not dirty the checkout.
3. Made `run_all.py`'s report step render Markdown into its temp dir (`--results-md`, with graceful
   fallback for older CLIs) and verified the committed artifacts' hashes are unchanged across a run.

## Coverage gaps / heuristic limits (honest limitations)

- **Heuristic checks, not proofs:** C4/C5 are regex scans with documented exemptions (case rules,
  `docs/` + `tests/` exemptions, two detector files). Cleverly obfuscated placeholders/secrets could
  evade them; GitHub secret scanning and human review remain the backstop. C8 checks count tokens +
  honesty sentence, not every table row of `docs/RESULTS.md` (per-class rows were cross-checked by an
  independent script for this report). C7 checks honesty markers, self-containment and size, not the
  semantic accuracy of every number rendered in the site (the embedded `fb-data` counts were
  reconciled against `results.json` for this report).
- **Determinism:** only `status` + `response_sha256` (+ counts) are cross-run compared, per CONTRACT
  intent; timestamps/run ids/latency vary by design and are ignored.
- **Network coverage:** `check_links.py` verified 25 of 110 evidence URLs (2xx, 0 dead) to respect
  source rate limits; the rest are unverified in this pass. W10's own appendix claims 151/151 cited
  URLs 2xx/3xx; I spot-checked 12 of those (12/12 reachable). Evidence **quotes** were not
  independently re-fetched/verified verbatim by W5 — that is W1's collector/verification scope
  (`scripts/evidence/verify_provenance.py`).
- **Live measurements:** none — by design. The demo is the deterministic `mock` provider; no live model
  endpoint was available, and every artifact says so.
- **CI execution:** the workflow was not run on GitHub Actions from this session (offline); it was
  validated structurally, its embedded Python snippets compiled, and all its underlying commands were
  executed locally on Windows/Python 3.13. The 3.11 leg and Linux-specific behavior rest on the
  stdlib/pathlib design.
- **Git state:** no `git` command was run (root owns publishing), so this report cannot certify which
  files are tracked vs ignored; `_scratch/`, `__pycache__/`, `.env*`, `results/*` except
  `results/demo/**` are covered by `.gitignore`.
- **Timing:** QA ran concurrently with authoring; this report is against the frozen candidate described
  by the hashes below. Any post-freeze edit requires re-running the gate.

## What a reviewer should re-run

From the repository root, with Python 3.11+ and no network:

```shell
python -m failbench.schema
python scripts/validate/check_contract.py --strict
python -m unittest discover -s tests -t . -v
python -m failbench validate --strict
python scripts/validate/run_all.py
```

Optional network check (politeness-capped; never part of CI):

```shell
python scripts/validate/check_links.py --limit 25 --timeout 12
```

The first five must all exit 0 and end with `CONTRACT: PASS`, `OK`, and
`RESULT: PASS (9 passed, 0 failed, 0 skipped)`. If anything changed after the freeze, expect the
placeholder/secret scan and C8 to flag any newly introduced placeholder text or results/doc mismatch.

## Frozen-candidate fingerprints (SHA-256, 2026-11-24 ~10:43)

| Artifact | SHA-256 |
|---|---|
| `results/demo/results.json` | `1D264A8349D48D33762121E6C495F8599163E0120BA41ACFA6595E6263AC7E77` |
| `results/demo/raw.jsonl` | `D5ADE544E684572DA54ADFB68439D5BE0388E6974DC0274914E1E4F81D98DB6A` |
| `site/index.html` (633,132 bytes, frozen by W4) | `D0B3215577E403CA63DA1E7C754149B3D70BFECE7907CE4C04F05470F6ABD85E` |
| `docs/RESULTS.md` (10,335 bytes, frozen by W4) | `2CE8465F139D33A4B2D909FA5DA0BF3A48A3B5C9F7BF1EACCD4B41320965EC43` |
| `README.md` | `53F60996D8287D5164A4FFA8A5DAF42E94E87B8E50360AAF695E76841BE35124` |
| `scripts/validate/check_contract.py` | `F226888D2A897F9262846732D0069E3864C016A28D7A2006ED36E319E3D7CE1A` |
| `scripts/validate/run_all.py` | `852E42F79049D79B616FA4F80B5175CA1EEDB3193673FC57D7D41843A5DB8B1B` |
| `scripts/validate/check_links.py` | `1F4A81ED02B966401916EEDBA0ECC44E520FC53C035F7DBB1DFDF62A2FD5F9AA` |
| `.github/workflows/ci.yml` | `6554F731832C35C6514787F5C9DCD7E482EC41B3F513C4454AB041591CEBDB47` |

## Reviewer sign-off

Frozen tree is **PASS** on all offline gates with zero unresolved critical/high defects. The three open
items are low-severity documentation/versioning choices for the repository owner. If the tree is edited
after this report, mark it `REQUIRES RE-RUN` and execute the commands in "What a reviewer should
re-run" before publishing.
