# FailBench Probe Corpus

This directory is the deterministic, judge-free regression suite promised by
`docs/CONTRACT.md`: **ten failure classes**, one JSON file per probe, every probe scored by a
mechanical rule from `failbench/scoring.py`. There are no LLM judges, no network calls during
scoring, and no dependency on model identity or vendor.

Every probe is a static, self-contained prompt (`params.temperature: 0`) with exactly one
defensible pass condition. Running the corpus yields per-class pass rates plus the exact reason
for every failure. Wall-clock runtime depends on the endpoint and model and was not measured
against a live endpoint in this build; the shipped demo run uses the deterministic offline mock
provider.

## Corpus map

```
probes/
├─ README.md                 # this file
├─ DESIGN_CHECKLIST.md       # authoring rules + per-class design coverage + worker gates
├─ _index.json               # machine-readable counts (by class, by severity)
├─ hallucination/            # hal_*    fabricated facts, citations, APIs, packages, quotes
├─ instruction_following/    # if_*     negative constraints, format/length/order constraints
├─ context_retrieval/        # ctx_*    needle-in-haystack, lost-in-the-middle, distractors
├─ reasoning_consistency/    # rea_*    arithmetic/date/unit edge cases, paraphrase stability
├─ sycophancy/               # syc_*    stance flip under social pressure
├─ structured_output/        # str_*    JSON schema conformance, tool-call arguments
├─ multilingual/             # ml_*     cross-lingual degradation, code-switching, scripts
├─ safety_consistency/       # saf_*    over-refusal on harmless prompts, boundary consistency
├─ agentic_reliability/      # agt_*    loops, over-eager tool use, failure to stop/recover
└─ determinism_calibration/  # det_*    counting/tokenization edge cases, abstention calibration
```

Counts per class and severity are kept in `_index.json` and summarized here:

| class | abbr | probes | critical | high | medium | low |
|---|---|---|---|---|---|---|
| hallucination | hal | 10 | 1 | 5 | 3 | 1 |
| instruction_following | if | 10 | 0 | 2 | 6 | 2 |
| context_retrieval | ctx | 10 | 0 | 5 | 4 | 1 |
| reasoning_consistency | rea | 10 | 0 | 2 | 6 | 2 |
| sycophancy | syc | 10 | 2 | 3 | 3 | 2 |
| structured_output | str | 10 | 0 | 3 | 5 | 2 |
| multilingual | ml | 10 | 0 | 3 | 5 | 2 |
| safety_consistency | saf | 10 | 1 | 3 | 4 | 2 |
| agentic_reliability | agt | 10 | 1 | 5 | 3 | 1 |
| determinism_calibration | det | 10 | 0 | 3 | 4 | 3 |
| **total** | | **100** | **5** | **34** | **43** | **18** |

> The table above is generated from the files; `_index.json` is the authoritative snapshot and
> the table is updated whenever probes are added or removed.

Probe ids follow `<abbr>_<slug>_<2 digits>` (e.g. `ctx_needle_middle_01`). The file name is the
probe id. `_index.json` is underscore-prefixed on purpose: `failbench.schema.load_probes`
treats every non-underscore `*.json` file under `probes/` as a probe, so a plain
`index.json` here would itself be loaded and fail probe validation.

## Design principles

1. **Determinism.** Static prompt text, no templating, no retrieval, `temperature: 0`.
   `repeats` is `1` for all classes except `determinism_calibration`, which uses `3`; a probe
   passes only if every repeat passes, so flaky probes are visible instead of averaged away.
2. **One defensible answer.** Every probe has a single mechanically checkable correct
   behaviour. Ambiguous questions (disputed trivia, underspecified requests) are only used
   where the correct behaviour is to say "I cannot determine that".
3. **Positive and negative units together.** A `not_contains_any` check alone would pass on an
   empty or off-topic response, so every negative constraint is paired with a positive check
   in an `all_of` unit.
4. **No judges.** Scoring uses only the eight mechanical types in `docs/CONTRACT.md` §6:
   `contains_all`, `contains_any`, `not_contains_any`, `exact_match`, `regex`, `json_schema`,
   `numeric`, `all_of`. Each failure reports the concrete mismatch (expected vs found).
5. **Synthetic content only.** Long contexts are generated synthetic prose; invented papers,
   packages, people, places and products keep the hallucination traps unambiguous. No PII, no
   private data, no copied source text, no harmful payloads.
6. **Severity means impact.** `critical` is reserved for failures that cause unsafe or
   trust-destroying action (fabricated citation, medically relevant sycophancy, refusal of a
   harmless request for help, an agent looping or failing to stop). Cosmetic format breakage is
   `medium`/`low`.
7. **Abstention is a pass where honesty is the requirement.** Hallucination and calibration
   probes pass on explicit uncertainty with no fabricated identifier — never on a confident
   guess. The corresponding failure is a fabricated DOI, package, quote, statistic or API.
8. **Brittleness is documented, not hidden.** Every probe's `notes` records why it is
   deterministic and where a correct-looking answer could still fail (e.g. quoting a
   fabricated DOI while disclaiming it). Regressions that turn out to be scoring brittleness
   should be fixed by changing the probe and re-running the gates, not by loosening the scorer
   silently.

## Scoring semantics (short version)

- `contains_*` match on a normalized, whitespace-collapsed, lowercased response.
- `regex` runs on the raw response with `re.DOTALL | re.MULTILINE`; anchor whole-response
  constraints with `\A...\Z`.
- `numeric` reads the **first** number in the response (commas stripped) and applies
  `tolerance`; prompts that need a number say "answer with the number only".
- `json_schema` accepts a bare JSON value or one ```json fence and supports only the minimal
  subset `type`, `properties`, `required`, `additionalProperties`, `items`, `enum`.
- `all_of` requires every unit to pass.
- Provider/network errors are run errors, never probe failures.

## How to add a probe

1. Read `docs/CONTRACT.md` §5-§6 and `probes/DESIGN_CHECKLIST.md` (§2 record shape, §3 limits,
   §5 scoring gotchas, §7 per-class designs).
2. Pick the class directory and the next free two-digit suffix; use the class abbr.
3. Write `probes/<class>/<abbr>_<slug>_<NN>.json` with: title (5-120 chars), severity,
   rationale (10-400 chars, why the failure matters), a static prompt, `params.temperature: 0`,
   a sensible `max_tokens`, `repeats: 1` (or `3` only for calibration probes), one scoring
   spec, `tags`, and `notes` covering determinism + brittleness. Leave `evidence_ids` at `[]`
   unless the ids exist in `data/evidence/` — never invent evidence ids.
4. Prove the scorer is unambiguous: a good answer must pass and a plausible bad answer must
   fail. Run Gate 2 from `DESIGN_CHECKLIST.md` §9 with a real `(good, bad)` sample pair.
5. Validate the file and the whole corpus from the repo root:

   ```
   python -m failbench.schema
   ```

   Expected: `errors=0`. Warnings about a class having no evidence records are created by
   workstreams outside `probes/` and do not indicate a probe defect.

6. Update `_index.json` (counts regenerate trivially via `failbench.schema.load_probes`) and
   the table above.

## License

The probe corpus is data, licensed CC-BY-4.0 as stated in `docs/CONTRACT.md`. The `failbench`
code is MIT.
