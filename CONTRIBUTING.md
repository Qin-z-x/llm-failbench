# Contributing to FailBench

FailBench is two things in one repository: a small, curated **benchmark** of
deterministic LLM-failure probes, and an **evidence atlas** of publicly reported
failure modes with reachable sources. Contributions of probes, evidence records,
code, and documentation are welcome.

`docs/CONTRACT.md` is the source of truth for schemas, scoring semantics, file
layout, and quality rules. Read it before changing a schema, a scoring type, or
the layout of a committed artifact. If your change would require a schema
change, open an issue first so the contract and the validators can be updated
together.

## Ways to contribute

- **Evidence records** — add a public, real-world report of a failure mode to
  `data/evidence/<class>.jsonl`.
- **Probes** — add a deterministic, mechanically scored probe under
  `probes/<class>/<probe_id>.json`.
- **Code** — fix bugs or improve the validators, scorers, runner, providers,
  report generator, gate, and CLI in `failbench/`.
- **Documentation** — improve the docs, examples, and the static report.

## Ground rules

Keep every contribution honest and safe. In particular:

- **No fabricated data.** Never invent a URL, title, date, quote, metric, or
  citation. If a value is unknown, use `null` or omit the optional field.
- **No harmful content.** No working jailbreaks, exploit payloads,
  prompt-injection payloads aimed at third-party systems, malware, PII, or
  private/leaked data. Safety probes measure over-refusal and refusal
  inconsistency on harmless prompts only. Cite the phenomenon, never the payload.
- **Respect licenses.** Code is MIT; data (probes and evidence) is CC-BY-4.0.
  Do not copy large text from sources; link with a short quote only.

## Contributing evidence

Evidence records live in `data/evidence/<class>.jsonl`, one JSON object per
line, partitioned by the ten failure classes. Start from
`docs/templates/evidence.template.jsonl` and follow
`failbench/schema.py` for the exact field rules.

A record is acceptable only when:

- **The source is real and reachable.** `source_url` must be a public
  `http(s)` URL that you actually fetched or saw in a search/API result while
  collecting the record. Do not construct URLs from memory, and do not submit a
  URL you did not open.
- **The quote is exact.** `quote` must be copied verbatim from the fetched page
  or API result and is limited to 200 characters. If you cannot verify the
  exact text, use `""`.
- **The source type is from the fixed list.** `source_type` is one of
  `hn_story`, `github_issue`, `arxiv`, `blog`, `vendor_doc`,
  `reddit_thread`, `forum_thread`, or `docs`.
- **Metrics are real integers, or omitted.** Allowed metric keys are
  `hn_points`, `hn_comments`, `github_reactions`, `github_comments`,
  `reddit_upvotes`, `reddit_comments`, `citations`, and `stars`. They are
  popularity signals, not validation; unknown values are omitted rather than
  estimated.
- **The ID and provenance are present.** IDs use the form
  `ev_<abbr>_<4 digits>` (for example `ev_ctx_0001`), matching the class, and
  are unique across the corpus. `collected_by` and `collected_at` are required.
- **The status label is honest.** `status` stays `cited` by default.
  `tested` requires a real live model run; put the run reference in `notes`.
  `refuted` is used only when a cited source contradicts the claim.
- **The summary is yours.** `summary` is at most 400 characters, in your own
  words, without hype.

`probe_ids` may reference probes that do not exist yet; the corpus is
reconciled by class.

## Contributing probes

Each probe is one JSON file at `probes/<class>/<probe_id>.json`, using
`docs/templates/probe.template.json` as a starting point and
`failbench/schema.py` as the normative validator. Requirements:

- **Identity.** `id` matches `<abbr>_<slug>_<2 digits>` (for example
  `ctx_needle_01`) and uses the abbreviation of its class. `class` is one of
  `hallucination` (`hal`), `instruction_following` (`if`),
  `context_retrieval` (`ctx`), `reasoning_consistency` (`rea`), `sycophancy`
  (`syc`), `structured_output` (`str`), `multilingual` (`ml`),
  `safety_consistency` (`saf`), `agentic_reliability` (`agt`), or
  `determinism_calibration` (`det`).
- **Severity and rationale.** `severity` is one of `critical`, `high`,
  `medium`, `low`. `title` is 5–120 characters; `rationale` is 10–400
  characters and must state why the failure matters, not just "test the model".
- **Prompt.** `prompt` is a static, self-contained list of 1–20 messages with
  roles `system`, `user`, or `assistant`. Each message is 1–20000 characters
  and the total is at most 30000. No external files, no templating, and no
  copyrighted long text: more than 100 characters of source text is not allowed.
  Synthetic filler is encouraged.
- **Parameters.** `params.temperature` is 0–2 (default 0),
  `params.max_tokens` is 1–4096 (default 256), and optional `params.top_p` is in
  (0, 1].
- **Repeats.** `repeats` is 1–5. Use 3 only for determinism or calibration
  probes; a probe passes only if every repeat passes.
- **Scoring.** Exactly one mechanical scoring specification, of type
  `contains_all`, `contains_any`, `not_contains_any`, `exact_match`, `regex`,
  `json_schema`, `numeric`, or `all_of`, as implemented in
  `failbench/scoring.py`. No human or LLM judgement.
- **One defensible pass condition.** A probe must have a single, unambiguous
  correct answer or pass condition, with no partial grading. Check that a
  trivially correct response passes and a trivially wrong response fails before
  submitting.
- **Determinism.** Prefer static prompts and temperature 0. Provider or network
  failures are reported as errors, never as failures.

If a probe is grounded in an atlas entry, list the record IDs in
`evidence_ids`. An empty list is allowed.

## Verify before opening a pull request

Run the checks from the repository root:

```bash
python -m failbench validate --strict
python -m unittest discover -s tests -t . -v
```

Also run the end-to-end offline validation script, which chains the contract
gate, unit tests, CLI validation, mock demo runs, and report checks:

```bash
python scripts/validate/run_all.py
```

The mock demo is a fast, offline sanity check that the whole pipeline still
works:

```bash
python -m failbench run --provider mock --demo
```

All of these must remain offline and must not require an API key.

## Code contributions

- **Python 3.9+, standard library only.** The package declares no third-party
  runtime dependencies; do not add any. Build-time tooling in
  `pyproject.toml` is separate from runtime imports.
- **Run from the repository root** with `python -m failbench`. No virtualenv or
  installation is required; an editable install is optional for tooling only.
- **Offline safety.** Tests and the demo must not use the network. Only the
  evidence collectors under `scripts/evidence/` and the OpenAI-compatible
  provider are allowed to make network requests.
- **No secrets.** Never commit API keys, tokens, or credentials, and never log
  them. The documented pattern is to pass a key through an environment variable.
- **Determinism.** Committed artifacts and generated output should be
  deterministic: stable ordering, no wall-clock time in golden files, and no
  locale-dependent formatting.
- **Keep artifacts in sync.** If you change behavior, update the affected
  probes, evidence `probe_ids`, tests, and docs in the same pull request.
- **Add tests** for behavioral changes under `tests/`, using only the standard
  library's `unittest`. Keep tests fast and offline.

## Review process

- Send **small, focused pull requests**. One probe, or one evidence batch, per
  pull request is fine; unrelated changes belong in separate pull requests.
- Reviewers check schema validity, determinism, source reachability, the
  absence of fabricated metrics, honest status labels, and safety of the
  content. A pull request that cannot be checked mechanically is likely to be
  asked for a smaller, reproducible version.
- CI runs offline validation on every pull request. A red CI run needs to be
  fixed before review; CI does not call paid endpoints.
- Maintainers review on a best-effort basis. There is no auto-merge expectation
  and no promised review or release date is implied by opening a pull request.

Fill in the [pull request template](.github/PULL_REQUEST_TEMPLATE.md); it asks
for the same information a reviewer needs.

## License and attribution

- **Code** is released under the MIT License (`LICENSE`).
- **Data** — probe corpus (`probes/**`) and evidence atlas
  (`data/evidence/**`) — is released under CC-BY-4.0, as stated in `LICENSE`.
- By contributing, you confirm you have the right to share the material. Do not
  submit content that is confidential, leaked, personal, or incompatible with
  these licenses.
- Cite sources with a link and a short quote only. Quoted excerpts remain the
  property of their original authors.

## Security

Do not report security problems in public issues. Follow the responsible
disclosure process in [SECURITY.md](SECURITY.md); if that file is not available
in your checkout, contact the maintainers through the repository's issue
tracker without publishing exploit details. Do not test against endpoints or
accounts you do not own.

## Questions

Open a GitHub issue for questions about a probe, an evidence record, or a
workflow. For schema questions, quote the relevant section of
`docs/CONTRACT.md` so the discussion has a concrete reference.
