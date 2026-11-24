# Changelog

All notable changes to this project are documented here. The format follows
Keep a Changelog, and the project uses semantic versioning: while the project is
pre-1.0, minor releases may include changes that are not backward compatible.
Data artifacts (the evidence atlas and the probe corpus) change with the package
version.

## [Unreleased]

No changes yet.

## [0.2.0] - 2026-11-24

### Added

- Composite GitHub Action (`action.yml`) to run a probe suite against any
  OpenAI-compatible endpoint in CI, optionally gate on regressions against a
  committed baseline, and upload the report. Documented in
  [`docs/GITHUB_ACTION.md`](docs/GITHUB_ACTION.md).
- README status badges (CI, release, license, live dashboard, Discussions) and a
  Community section pointing at Discussions, issue templates and the dashboard.
- Community seed content: GitHub Discussions ("Share your FailBench results",
  "Probe requests and evidence submissions") and `good first issue` tasks under
  the repository's issue templates.

### Changed

- Documentation and generated artifacts bumped to 0.2.0.

## [0.1.1] - 2026-11-24

### Fixed

- Generated `docs/RESULTS.md` no longer repeats the honesty sentence twice
  (report generator de-duplicated); `site/index.html` regenerated.
- `scripts/validate/check_links.py` now sends an honest, correct User-Agent
  pointing at the real repository, and the checker version is 0.1.1.
- `docs/ATLAS.md` references the verification tables by section number
  (`section 10`, `10.3`) instead of an ambiguous "at the end of this file".
- Version string bumped to 0.1.1 in package metadata, `CITATION.cff` and tests.

### Added

- Committed the QA and audit reports under `docs/reviews/`
  (`QA_REPORT.md`, `CLAIMS_AUDIT.md`, `SAFETY_REVIEW.md`) for the v0.1.0
  publishing candidate reviewed by the QA and audit workstreams.
- Enabled GitHub Actions CI (green) and GitHub Pages deployment of the
  self-contained dashboard at https://qin-z-x.github.io/llm-failbench/.

## [0.1.0] - 2026-11-24

### Added

- The `failbench` package: a standard-library-only Python toolkit (Python 3.9+,
  no third-party runtime dependencies) for running deterministic, judge-free
  failure probes against LLM endpoints.
- Probe schema loading and validation in `failbench/schema.py`, covering the ten
  failure classes, probe and evidence record rules, and the eight scoring
  types.
- A probe corpus of 100 probes, ten in each of the ten failure classes
  (`hallucination`, `instruction_following`, `context_retrieval`,
  `reasoning_consistency`, `sycophancy`, `structured_output`, `multilingual`,
  `safety_consistency`, `agentic_reliability`, `determinism_calibration`).
- Mechanical, judge-free scorers in `failbench/scoring.py`: `contains_all`,
  `contains_any`, `not_contains_any`, `exact_match`, `regex`, `json_schema`,
  `numeric`, and `all_of`, with concrete failure details for mismatches.
- Providers: a deterministic offline mock provider, an OpenAI-compatible
  provider built on `urllib` (no third-party HTTP client), and a replay
  provider that re-scores recorded responses without network access.
- A runner that writes `results.json` and an auditable `raw.jsonl` per run,
  including per-attempt statuses, response hashes, latency, and token counts.
- A regression gate that compares a current run against a baseline run and
  reports status changes.
- An offline report generator that emits a self-contained static site
  (`site/index.html`), with no remote scripts, stylesheets, or telemetry.
- A deterministic demo run included under `results/demo/`, produced by the mock
  provider; the committed numbers exercise the pipeline and are not live-model
  measurements.
- A cited evidence atlas across the ten failure classes, stored as one JSONL
  file per class under `data/evidence/`, with source URLs, short quotes,
  popularity signals, and honest status labels.
- The `python -m failbench` command-line interface with `list`, `validate`,
  `run`, `replay`, `report`, and `gate` subcommands, matching the CLI contract
  in `docs/CONTRACT.md`.
- Template files under `docs/templates/` for probe and evidence records.
- Documentation covering the build contract, failure-class taxonomy, evidence
  atlas, mitigations, publishing notes, security policy, and contribution and
  community guidelines.
- An offline validation toolchain under `scripts/validate/` (contract gate,
  link checker, and an end-to-end validation runner) and a CI workflow that
  runs schema validation, the contract gate, unit tests, CLI validation, two
  mock demo runs with a determinism comparison, site sanity checks, and the
  full offline suite on Python 3.11 and 3.13.
- A standard-library `unittest` suite under `tests/` covering the validators,
  scorers, providers, runner, gate, and CLI.

### Changed

- Nothing: this is the first release of the project.

### Known Limitations

- No live-model measurements are committed. The demo run and the CI checks use
  the deterministic mock provider; real numbers require running the kit against
  an endpoint you configure.
- Judge-free scoring is narrower than free-form judging: it checks mechanical
  constraints only, so failure modes that require human or LLM judgement are
  out of scope by design.
- Class coverage is balanced in probe count (ten per class) but uneven in
  depth: some classes have more mature probe designs and more linked evidence
  than others.
- Results are descriptive, not inferential. A probe passes only if every repeat
  passes, and no statistical significance is claimed for a single run or across
  models.
- Evidence atlas metrics are popularity signals (Hacker News points, citations,
  stars), not validation of the underlying claim; a highly upvoted source is
  not a verified finding.
- The evidence atlas is English-centric and skews toward public English-language
  discussion, so non-English failure reports are underrepresented.
