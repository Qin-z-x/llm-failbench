## Summary

Spend two or three sentences on what this change does and why it belongs in FailBench. Link the evidence records, probes, or docs it touches. `docs/CONTRACT.md` is the source of truth for schemas, scoring semantics, and quality rules.

## Type of change

- [ ] New or updated probe(s) in `probes/<class>/`
- [ ] New or updated evidence record(s) in `data/evidence/`
- [ ] Scoring or runner change
- [ ] Documentation
- [ ] Site or report
- [ ] CI or validation
- [ ] Publishing or tooling
- [ ] Bug fix

## Verification (paste exact commands and results)

Run the offline checks from the repository root with plain `python`, with no third-party packages, no network, and no API key:

```shell
python -m unittest discover -s tests -t . -v
python -m failbench validate --strict
python -m failbench run --provider mock --demo --out results/demo
```

Paste the commands you actually ran and their observed output, including any error text. If a check could not run in your environment, say so instead of guessing.

## Checklist

- [ ] Probes and evidence records are schema-valid per `docs/CONTRACT.md` sections 4 and 5 and pass the repository validator (`python -m failbench validate --strict`).
- [ ] No fabricated URLs, dates, quotes, or metrics: every `source_url` was reached manually, and every `quote` is verbatim or empty.
- [ ] No harmful content: no jailbreak, exploit, or prompt-injection payloads, no PII or private data, and no long copyrighted text (a link plus a short quote only).
- [ ] Licenses are respected: code is MIT, evidence and probe data are CC-BY-4.0, and external sources are attributed with a link only.
- [ ] No secrets, API keys, or tokens appear in the diff, logs, or generated result files.
- [ ] Statuses are honest: evidence `status` stays `cited`; `tested` includes a real run reference in `notes`; the mock demo run is labeled as mock.
- [ ] The offline tests were run without network access and without an API key.
- [ ] `CHANGELOG.md` was updated when the change is user-visible.
- [ ] Documentation was updated when behavior changed.

## Related issues

Link related issues or discussions here. Write `Closes #123` when this pull request resolves an issue.

Maintainers may request changes before merging. Thanks for keeping FailBench deterministic, evidence-backed, and honest.
