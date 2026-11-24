# Roadmap

This roadmap states direction, not commitments. There are no target dates and no
promises that an item ships in a particular release; items move when someone
does the work, when the schemas allow it, and when the result can be verified.
Version 0.1.0 is the current release.

## Near term

1. **Live-run results matrix.** The repository ships no live-model numbers at
   0.1.0: the demo run is produced by the deterministic mock provider. The next
   step is to document real runs that users and maintainers perform against one
   or more OpenAI-compatible endpoints, recording the endpoint type, model
   identifier, date, parameters, and provider, and labeling each cell as a
   single-run observation rather than a ranking. The runner, results schema, and
   report generator already support this; what is missing is collected runs and
   a review step.

2. **Probe corpus depth and class balance.** The corpus currently carries ten
   probes in each of the ten failure classes (100 probes), so counts are
   balanced by construction. The next step is depth rather than parity: more
   probes per class that target distinct sub-phenomena, plus a written note on
   which classes have linked evidence and which are currently probe-only. New
   probes must keep the same deterministic, mechanically scored rules as the
   existing corpus.

3. **pytest plugin and a reusable GitHub Action wrapper for `gate`.** Expose the
   suite to pytest users and CI users without shell glue: a pytest plugin that
   maps probes to test items, and a small reusable Action that wraps
   `python -m failbench gate`. Any such integration must remain optional so the
   core package keeps its standard-library-only runtime and offline-by-default
   behavior.

4. **Statistics across repeats.** Today a probe passes only if every repeat
   passes, which hides flakiness. Near-term work is to report per-repeat status,
   variance and flake rates in `results.json` and the report, so a repeated
   failure can be distinguished from a single unreliable sample. No statistical
   significance claims will be made until that reporting exists and is tested.

5. **Community evidence review process.** Document the inclusion criteria for
   the evidence atlas and a reviewer checklist covering source reachability,
   quote fidelity, status labels, metric provenance, and the no-PII/no-harmful-
   payload rules, plus a way to annotate disputed records. This should make
   review reproducible by someone who is not the original collector.

6. **Documentation translations (exploratory).** Translated documentation may be
   useful for non-English contributors, but it is exploratory: it happens only
   if maintainers with the relevant language skills volunteer, and no translated
   documentation ships at 0.1.0.

## Not planned

- **Vendor leaderboard rankings.** A single-run probe pass rate is not a model
  ranking, and ranked charts invite misuse that the project's evidence rules are
  designed to prevent.
- **LLM-as-judge scoring inside the tool.** Free-form judging would break the
  judge-free, deterministic, offline promise, so it belongs in separate tooling,
  not in the benchmark core.
- **Automated posting, promotion, or follower/star campaigns.** The project
  relies on honest, attributable distribution; automated promotion would
  misrepresent how it is used.
- **Fabricated or pay-to-list evidence.** Sponsored or invented records
  contradict the project's non-negotiables, so there will be no paid placement
  in the atlas.
- **Hosting third-party model endpoints.** The kit runs locally against
  endpoints the user configures; hosting inference infrastructure is out of
  scope.

## How this list changes

Roadmap changes arrive as pull requests and are discussed in an issue first. Add
an item only if it can be described without a date promise and without asserting
a result that has not been measured.
