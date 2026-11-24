# Security Policy

FailBench is a small, dependency-free Python toolkit (an evidence atlas and a set
of deterministic model-failure probes) plus a static report. This document says
how to report problems in **the tool itself**, how we handle findings about
**model behaviour**, and what the project does and does not claim to secure.

Version: applies to the `0.1.x` line (`failbench` 0.1.0 is the current release).
The project is pre-1.0; security fixes are applied to the latest released version
only, and older snapshots are not maintained.

## Scope

### In scope — vulnerabilities in FailBench itself

Please report issues that could harm someone who installs or runs this project:

- **Code execution / injection** triggered by untrusted input data — a malicious
  `probes/**/*.json` or `data/evidence/**/*.jsonl` file that causes the validator,
  runner, report generator or CLI to execute code, import arbitrary modules, or
  write outside the intended output directory.
- **Prompt data handling** — cases where the runner or provider writes API keys,
  environment secrets or unexpected sensitive content into `results/**` artifacts
  (`results.json`, `raw.jsonl`), logs, or the generated site.
- **Secret leakage** — API keys printed to stdout/stderr, committed to files,
  exposed through error messages, or passed on a command line in a way the README
  recommends (for example a `--api-key` style flag). The intended pattern is an
  environment variable read at runtime and never logged.
- **Network posture violations** — code paths that make network requests where
  the project claims to be offline: unit tests, `--provider mock`, `replay`, the
  `validate` command, the `report` command, or the generated `site/index.html`
  when opened from disk. Only `scripts/evidence/**` collectors and the
  `openai` provider are supposed to use the network.
- **Dependency-free / stdlib-only posture** — any accidental non-stdlib import,
  build-time fetch, or embedded third-party executable that would change the
  supply-chain footprint. The package declares no runtime dependencies.
- **Telemetry / tracking** — any analytics, beacon, external font/CDN load,
  update ping or "phone home" behaviour, including in the static site. The
  project intends to ship none.
- **Cross-site scripting or HTML injection** in the generated
  `site/index.html` (evidence titles, quotes, probe text or model responses are
  rendered into a static HTML file and must not be able to inject script).
- **Path traversal / unsafe file writes** in CLI output options (e.g. `--out`),
  report generation, or the publishing scripts.
- **Credential handling in publishing scripts** — token leakage, unsafe logging,
  or non-dry-run defaults in `scripts/publish/**`.

### Out of scope — model behaviour and attack content

FailBench describes publicly reported model failures and runs harmless
over-refusal probes; it is **not** an attack toolkit and does not host working
payloads. The following are out of scope for this repository's security policy:

- Model jailbreaks, prompt-injection payloads against third-party systems,
  exploit chains, malware, or social-engineering scripts. We will not add,
  review, or host such material.
- Reports that a particular model can be made to produce harmful content.
  That is a finding about a model or vendor, not about this repository — see
  "Model-failure findings" below.
- Missing safety guardrails in a third-party API or endpoint.
- Issues that require the victim to run a modified, already-compromised copy of
  the project, or that rely on a hostile local environment.
- Denial-of-service through deliberately enormous self-authored test data.
- "Findings" produced only by a vendor's marketing benchmark, or claims that a
  model fails a probe with no reproducible transcript.

## Reporting a vulnerability in FailBench

Please **do not open a public issue** for a security problem. Instead, open a
**private security advisory on the repository** (GitHub's "Report a
vulnerability" / "Security advisories" flow under the repository's Security
tab). That gives us a private thread and, if appropriate, a coordinated
advisory later. No public bug-bounty program exists and no monetary reward is
promised.

If private advisories are unavailable to you for any reason, open a minimal
public issue that says only that you have a security report and asks the
maintainers to enable a private channel. Do not include exploit details,
secrets, or steps to reproduce in that public issue.

Please include where you can:

1. The affected version (output of `python -m failbench --version` or the
   `failbench/__init__.py` `__version__`) and the commit/tag.
2. Which component is affected: CLI, runner/providers, schema validator,
   report generator, static site, evidence collectors, publish scripts, docs.
3. A minimal reproduction: the smallest probe/evidence/results file or command
   that triggers the issue.
4. Impact: what an attacker could read, write, execute or exfiltrate, and the
   preconditions (for example "requires running a third-party probe file").
5. Whether any secret or personal data was exposed, and if so, which.
6. Any suggested fix.

Do not test against systems, accounts, or endpoints you do not own or have
permission to test.

## What to expect

This is a volunteer OSS project with no support contract and no security
response SLA. The following are **best-effort targets, not guarantees**:

- Acknowledgment of a private report within about 10 business days.
- An initial assessment (valid / invalid / needs info) within about 30 days.
- A fix or mitigation for confirmed in-scope vulnerabilities, and public credit
  in the release notes if you want it.
- Coordinated disclosure: we will agree a publication date with you, typically
  after a fix is available. If we cannot reach agreement, we will not stand in
  the way of disclosure after 90 days have passed, provided you made a
  reasonable effort to contact us.

We will not pursue or support legal action against good-faith security
researchers who follow this policy. This safe-harbour statement is a
best-effort statement of intent, not legal advice, and it does not bind third
parties or guarantee any legal outcome. Consult your own counsel if in doubt.

## Model-failure findings discovered with FailBench probes

FailBench's whole purpose is to reveal model failures, so serious findings are
expected. When a probe reveals something with real-world harm potential (for
example a reliable way to make a widely deployed model emit secrets, follow
injected instructions from untrusted content, or produce dangerous advice), we
ask contributors and users to treat it as a security-disclosure problem, not a
content opportunity:

1. **Reproduce it deterministically.** Record the model identifier, endpoint
   type, parameters, prompt, seed/temperature, and at least two independent
   runs. A single flaky sample is not a finding.
2. **Do not publish exploit details.** Do not post working payloads, minimal
   jailbreak prompts, or step-by-step exploitation instructions in issues,
   pull requests, the atlas, the site, or launch material. Publish the
   *phenomenon* and the measurement, not the weapon.
3. **Notify the vendor privately first.** Use that vendor's security contact or
   private advisory route, and give them a reasonable window to respond before
   public documentation — 90 days is the default, shorter only by mutual
   agreement or if there is evidence of active exploitation.
4. **Then document narrowly.** After the window, add a short, neutral
   description to the atlas (`data/evidence/**`) with the source URL, the
   measured behaviour and the date, plus a `reproducible: true`-style note in
   your own record. Keep harmful prompt content out of the repository: describe
   the trigger class, not a copy-paste payload. Evidence records follow the
   project's existing rule: quoted text is short, attributed, and never a
   working attack.
5. **Respect the licence and the law.** Do not include confidential vendor
   material, leaked data, or personal data in a record. Do not run probes
   against systems you are not authorised to test.

The project will not merge probes whose purpose is to teach harmful capability,
evade safety systems, or produce attack tooling; safety-class probes measure
over-refusal and refusal inconsistency on harmless prompts only.

## Security-relevant design posture

These properties are intended and are worth checking, reporting if broken:

- **Dependencies:** runtime dependencies are `[]`; the package is stdlib-only.
  Network access in the library is limited to the `openai` provider
  (`urllib`), which sends the prompt you give it to the endpoint you name.
- **Secrets:** the documented pattern is `--api-key-env VAR`; keys are read
  from the environment at runtime and are not written to `results/**` or logs.
- **Prompts and results are data:** running the `openai` provider sends probe
  prompts and (if you supply them) your own data to the third-party endpoint
  you configured. `results/**` includes prompt text and model responses; treat
  produced files as potentially sensitive, keep them out of version control
  (only `results/demo/` is intentionally committed), and do not include real
  user data in custom probes. The repository contains no telemetry and no
  analytics: the project does not learn who runs it.
- **Offline by default:** unit tests and `mock`/`replay` runs are offline and
  require no API key; only the evidence collectors (`scripts/evidence/**`) and
  the `openai` provider contact the network.
- **Static site:** `site/index.html` is self-contained and intended to make no
  network requests when opened locally; evidence links are plain external links
  that only load if you click them.
- **Third-party probe/evidence files:** probe JSON is treated as data, but the
  scoring specification supports `regex` patterns. A hostile scoring pattern
  supplied by a third party can cause a slow regex (ReDoS) in the validator or
  runner. Prefer running only probe files you trust; this is documented
  behaviour, not a guarantee of sandboxing.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (current) | Yes — fixes land on the latest release |
| < 0.1 | No |

## Credits

Confirmed in-scope vulnerabilities are credited in release notes unless the
reporter prefers to stay anonymous.
