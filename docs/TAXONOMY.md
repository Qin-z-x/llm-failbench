# FailBench Failure Taxonomy (v1)

Status: version 0.1.0. This document is the prose description of the fixed
ten-class vocabulary defined in [`docs/CONTRACT.md`](./CONTRACT.md) §3. The
class names and their two/three-letter prefixes are stable for the 0.1.x
series: probe IDs (`ctx_needle_middle_01`), evidence IDs (`ev_ctx_0001`) and result
buckets (`by_class["context_retrieval"]`) are all derived from them.

Related documents: [`ATLAS.md`](./ATLAS.md) (what the evidence says about each
class), [`MITIGATIONS.md`](./MITIGATIONS.md) (what to do about it), and
[`CONTRACT.md`](./CONTRACT.md) (the normative schema).

## 1. Why a failure-class taxonomy, not another leaderboard

A leaderboard answers *which model scores higher*. It does not answer *what
breaks, for whom, and how would I notice it breaking*. Aggregate scores hide
the failure mechanism: a model can gain three points on MMLU while getting
worse at refusing harmless requests, and a benchmark suite that reports one
number cannot tell you which of its own capabilities improved. Aggregates also
mix real regressions with sampling noise, and they are expensive to re-run
inside an application's CI.

A failure-class taxonomy is a different instrument:

- **It names the unit of failure once.** An issue report, a probe, a test and a
  dashboard metric can all refer to `hallucination` or `sycophancy` and mean the
  same thing.
- **It makes coverage visible.** A suite with no probe for a class cannot
  report on that class. The honest statement is the absence itself, which is
  why the "Existing coverage" table in §7 exists.
- **It forces a mechanical detection rule.** A class that can only be
  recognised by a human or an LLM judge is out of scope for FailBench's
  deterministic probes, however real the phenomenon is. In this repository every
  probe is scored by a fixed rule (substring, exact match, regex, JSON Schema,
  numeric, or a boolean composition of those); no judge model participates.

FailBench is therefore not another leaderboard: it is a small deterministic
regression gate plus an evidence atlas. The taxonomy is the interface between
the evidence half and the probe half of the project.

## 2. How the ten classes were chosen

Candidate classes had to pass three filters. All three were required.

1. **User-visible harm.** A user or operator can notice the failure in the
   model's output and it changes a decision: a wrong citation is trusted, a
   constraint is violated in production, a RAG answer omits the retrieved fact,
   an agent takes another irreversible action after success. White-box-only
   phenomena (specific attention-head behaviour, gradient-level instability) are
   excluded because they cannot be observed from the API surface.
2. **Existing public evidence.** At least eight independent public reports
   (Hacker News stories, GitHub issues, arXiv papers, vendor documentation) must
   attest that real users hit it. This filters out failure modes that exist only
   in adversarial laboratory settings. The counts are in
   [`ATLAS.md`](./ATLAS.md) and are recomputed from `data/evidence/`.
3. **Measurability with a deterministic rule.** There must exist at least one
   static, self-contained prompt whose correct handling has exactly one
   defensible pass condition scorable without an LLM judge or a human rater.
   "Exactly one defensible answer" is the hard part: classes such as tone,
   helpfulness or "reasoning quality" fail this filter and are not classes.

The vocabulary was then fixed at **ten** classes so that a complete probe suite
(8–12 probes per class, roughly 80–120 probes) stays runnable as a fast
regression gate against a small sample, and so that each class has enough
evidence to say something defensible in the atlas. The classes are intended to
jointly cover the common, observable chat-API failure surface; they are not
mutually exclusive at the margins, and §6 lists the boundary decisions.

What the taxonomy is explicitly **not**:

- It is **not a severity ranking**. Each class notes a *typical* severity for
  chat applications; actual severity is a property of the deployment.
- It is **not a prevalence estimate**. The atlas counts what was publicly
  reported, not how often a failure occurs per request or per model.
- It is **not a complete map of everything that goes wrong with LLMs**.
  Deliberate exclusions are listed in §3.

## 3. Scope and non-goals

**In scope.** Text-only chat APIs compatible with the OpenAI
`/chat/completions` shape: a static list of system/user/assistant messages, a
temperature, a max-token budget and a text response. Probes are single-turn by
default, run at temperature 0, use synthetic filler text and invented
identifiers, and are scored mechanically and offline (`replay` re-scores
recorded responses without a network).

**Out of scope** (stated so the atlas is not read as covering them):

- **Multimodal surface**: images, audio, video, speech, screen understanding,
  browsing. FailBench sends text.
- **Jailbreak capability and harmful-content generation.** No attack payloads
  are included and no probe asks the model to produce harmful material. The
  `safety_consistency` class measures the *opposite* direction: over-refusal on
  harmless prompts and inconsistent refusal boundaries across near-duplicate
  harmless prompts. Readers looking for jailbreak measurement should look at
  security tooling such as garak and PyRIT (see §7).
- **Prompt injection and exfiltration attacks** against third-party systems.
  Adjacent to `agentic_reliability`, but out of scope by the repository's safety
  non-negotiables.
- **Training-time and infrastructure failures**: data contamination, training
  instability, serving outages, rate-limit behaviour. These are real but are not
  observable as a chat failure class.
- **Fine-tuning evaluation, model ranking, live leaderboards.** FailBench is a
  regression gate for a given endpoint, not a comparative ranking.

**Deterministic probes are a lower bound, not a proof.** A pass on a fixed
corpus of static prompts does not show that a model never hallucinates, never
flips under pressure, or never over-refuses; it shows that it handled these
specific witnesses at temperature 0. Conversely, a single fail is a concrete,
replayable witness of a real defect. That asymmetry is deliberate: FailBench is
built to catch regressions and produce citable examples, not to certify models.

## 4. The ten classes at a glance

All definitions, probe IDs and evidence IDs use the abbreviations below. The
probe corpus in this release contains **10 probes per class (100 total)**, all
static, all scored by the mechanical rules in `CONTRACT.md` §6. Typical
severity is a judgment about harm in chat applications, not a measurement; the
probes inside a class carry their own per-probe severity.

| # | class | prefix | typical severity | primary user harm | deterministic measurement used | probes |
|---|---|---|---|---|---|---|
| 1 | Hallucination | `hal` | critical | acting on fabricated facts, citations, packages, APIs | required non-verification statement + identifier-pattern regex (`all_of`) | 10 |
| 2 | Instruction following | `if` | high | violated prohibitions, formats, lengths, ordering | anchored regex for counts/format, `not_contains_any` for bans (`all_of`) | 10 |
| 3 | Context retrieval | `ctx` | high | silent wrong answers from supplied documents | unique synthetic constants (`contains_all`, `exact_match`, anchored `regex`) | 10 |
| 4 | Reasoning consistency | `rea` | medium | unstable or off-by-one answers on fixed problems | `numeric`, `FINAL:`-anchored `regex`, paraphrase pairs | 10 |
| 5 | Sycophancy | `syc` | high | correct answer reversed under user pressure | expected fact regex + no-concession regex (`all_of`) | 10 |
| 6 | Structured output | `str` | high | parsers and tool calls breaking on non-conforming output | `json_schema` subset, delimiter regexes (`all_of`) | 10 |
| 7 | Multilingual | `ml` | high | non-English users get wrong facts, language, or constraints | script/number-form regexes, translation constants | 10 |
| 8 | Safety consistency | `saf` | high | harmless requests refused or inconsistently refused | required helpful content + refusal-marker ban (`all_of`) | 10 |
| 9 | Agentic reliability | `agt` | high | loops, failed stopping, missed error recovery | decision-literal regexes over frozen transcripts (`all_of`) | 10 |
| 10 | Determinism and calibration | `det` | medium | flaky reruns; confident answers to unanswerable questions | `repeats: 3` identity + abstention regexes (`all_of`) | 10 |

Two conventions matter when reading the corpus:

- **Class prefix = file prefix.** Evidence records are `ev_<prefix>_NNNN`
  (`data/evidence/<class>.jsonl`), probes are `probes/<class>/<prefix>_<slug>_NN.json`,
  results are bucketed by full class name. The mapping is not one-to-one: one
  probe may cite several evidence records and vice versa.
- **Severity labels are per probe**, from `critical` to `low`; the class-level
  "typical severity" above is the editorial summary used in the atlas. A class
  with a "high" typical severity still contains low-severity probes, and the
  critical ones are listed in the class sections below.

## 5. The ten classes

Each class section follows the same structure: definition, observable symptoms,
who is harmed, why it is hard to catch in production, how FailBench detects it
deterministically, typical severity, and adjacent phenomena that belong to
another class or are out of scope. Probe IDs named below exist in `probes/`
and can be inspected directly.

### 5.1 Hallucination (`hallucination`, prefix `hal`)

**Definition.** A hallucination is an assertion presented as a verifiable
public fact that is not grounded in the supplied context or in the public
record: a citation, identifier, package, API, quotation, standard number or
statistic that does not exist or does not say what the model claims. FailBench
narrows the class to fabrications that can be checked mechanically: the prompt
asks about an artifact that was verified absent at authoring time, so the only
defensible answer states that it cannot be verified.

**Observable symptoms.**

- A DOI, arXiv ID, or venue is attached to a paper title that does not exist and
  does not resolve.
- A copy-paste install command names a package that is not on the registry
  (a supply-chain risk if the name is later registered by someone else).
- A plausible API endpoint, function or parameter does not exist in the
  documented interface, so generated code fails on first run.
- A quotation attributed to a named author or essay cannot be found in it, or a
  standard/dataset number is invented for a real-sounding standard.
- A precise statistic ("according to a 2024 report...") has no retrievable
  source but carries the same confident tone as supported claims.

**Who is harmed.** The end user who trusts the fabricated fact, the developer
who installs the invented package or calls the invented API, and the
organization that pays for a retraction or a security review. The failure is
silent at read time: nothing in the response distinguishes the invented part
from the supported part.

**Why it is hard to catch in production.** Fluency is not evidence. Checking
one citation requires a live oracle (resolver, registry, documentation index)
that is slow, rate-limited, and independently unreliable; the model's knowledge
also drifts with each version, so a check that passed last month may not cover
the namespace it emits now. Aggregate truthfulness scores are computed on fixed
question sets and do not transfer to a product's own identifiers and templates.

**Deterministic detection in FailBench.** All ten probes open with a
plausible but invented artifact and pin one of two acceptable behaviours: state
that it cannot be verified, or answer a different, checkable sub-question
without inventing the artifact. The scorer is an `all_of` of a `contains_any`
on explicit non-verification language and a `regex` that forbids the fabricated
identifier shape, so "I could not verify this" passes while an invented DOI or
package fails. Examples: `hal_fake_doi_01` (critical), `hal_citation_venue_01`,
`hal_arxiv_id_01`, `hal_pypi_package_01`, `hal_python_api_01`,
`hal_web_api_01`, `hal_quote_attrib_01`, `hal_standard_number_01`,
`hal_statistic_01`, `hal_benchmark_claim_01`. Every invented artifact used in
a probe was checked absent by the probe author, and the prompts are static, so
the pass condition does not depend on live lookups at run time.

**Typical severity.** `critical` - the user has no in-band signal of wrongness,
and follow-on actions (installing a package, citing a source, shipping a
number) are hard to reverse.

**Adjacent phenomena.** Faithfulness to a supplied-but-wrong source (out of
scope: no judge-free oracle for source truth); stale knowledge that was true at
training time (only probes that pin a date and expect abstention are in scope);
over-abstention and confidence calibration (`determinism_calibration`);
sycophantic agreement with a false premise (`sycophancy`); misusing a supplied
document rather than inventing one (`context_retrieval`).

### 5.2 Instruction following (`instruction_following`, prefix `if`)

**Definition.** An instruction-following failure is a response whose content is
substantively acceptable but which violates an explicit, checkable constraint in
the request: a prohibition, an output format, a length bound, an ordering, a
required count, or a casing rule. FailBench restricts the class to constraints
that can be decided from the response text alone; conflicting or unsatisfiable
constraint sets require judgment and are out of scope. The defining property is
that content correctness is not the issue - compliance with the stated form is.

**Observable symptoms.**

- A banned word, name, digit, or letter appears in the response (for example a
  colour name containing the letter "e" when the prompt forbids it).
- A hard length or count bound is missed by a clause: "under twenty words"
  returns twenty-one, "exactly seven words" returns eight.
- Ordering or label requirements are not respected in a required checklist.
- Format and casing rules fail: lowercase where uppercase was demanded, a word
  count stated as digits when digits were forbidden, a JSON object where the
  prompt asked for a bare sentence.
- Constraint decay under load: with several constraints in one prompt, the
  least salient constraint silently drops while the content stays plausible.

**Who is harmed.** Automated consumers break first: a downstream parser rejects
the payload, a template renders the wrong case, a compliance rule ("never name
a competitor") is violated. Users see truncated or malformed output, and teams
pay review time repairing form instead of substance.

**Why it is hard to catch in production.** The constraint space is
combinatorial - constraint families times several constraints per prompt times
boundary values - so hand-written cases always leave gaps. Violations are
visually small: one extra word is invisible in casual review but fatal to a
strict consumer. Compliance also depends on prompt template, constraint position
and phrasing, so a passing test does not automatically transfer to a rephrased
production template.

**Deterministic detection in FailBench.** Ten static prompts, each with one
anchored pass condition: `if_no_mention_01` (describe a bicycle without naming
it: `contains_all` + `not_contains_any`), `if_no_digits_01`,
`if_no_letter_e_01`, `if_no_commas_01` (three fruits, one line, no commas),
`if_max_words_01` (twenty-word cap with a required token), `if_exact_word_count_01`
(exactly seven words with two required words), `if_three_bullets_01` (exactly
three bullet lines), `if_ordering_01` (fixed step labels in order),
`if_uppercase_only_01`, and `if_json_only_01` (one JSON object and no other
text, scored by `json_schema` + anchored `regex`). Word-count constraints are
expressed as word-boundary regexes over the whole response; absence constraints
are `not_contains_any` lists of concrete surface forms.

**Typical severity.** `high` - a violation usually surfaces as a hard failure in
the consuming pipeline or as compliance exposure, but it is usually visible
early and rarely damages data silently, so it sits below `critical`.

**Adjacent phenomena.** Unsatisfiable or conflicting instructions (out of
scope); subjective style/tone compliance (out of scope); parser-verifiable JSON
and tool contracts (`structured_output`); constraint retention over multi-turn
transcripts (`agentic_reliability`/`context_retrieval`); refusals on harmless
prompts (`safety_consistency`).

### 5.3 Context retrieval (`context_retrieval`, prefix `ctx`)

**Definition.** A context-retrieval failure occurs when the information needed
to answer is present verbatim in the model's input context, yet the model fails
to locate, select or use it correctly. The class covers position-sensitive
recall ("lost in the middle"), accuracy loss as the input grows while the
relevant span stays fixed ("context rot"), distractor and near-miss
interference, and failure to notice that a supplied fact supersedes an older
one. It is distinct from retrieval-layer failure: in every probe the gold text
is guaranteed to be in the prompt.

**Observable symptoms.**

- A fluent answer omits or contradicts a fact stated verbatim in the prompt; the
  same prompt with the fact moved to the start or end often succeeds.
- The model cites the wrong document, or blends values from two documents that
  mention the same entity.
- A near-miss code (one or two characters different from the gold code) is
  returned instead of the requested one, or an explicitly marked decoy wins.
- A current value is missed when an older, still-present value supersedes it in
  the same context.
- A formatting instruction buried mid-context is ignored while the closing
  question is answered in the default format.

**Who is harmed.** Users of retrieval-backed assistants get confident, wrong
answers in domains where the product's promise is "answer from your documents"
(support, compliance, medicine, finance, law). Engineers are harmed twice: they
cannot tell whether retrieval or generation failed, so they tune the wrong
layer, and long-context upgrades marketed on window size are not measured on
window use.

**Why it is hard to catch in production.** Production traffic does not label
which chunk contained the answer, so one wrong response is consistent with a
retrieval miss, truncation, and a context-use failure. The failure surface is
position- and length-dependent: the same semantic request passes or fails
depending on where a few hundred tokens sit, so it shows up as intermittent
quality drift rather than a reproducible bug.

**Deterministic detection in FailBench.** All ten probes are static,
self-contained prompts built from synthetic filler text; each gold string
appears exactly once in the prompt and never in the question, and a
short-answer system message keeps grading unambiguous. Examples:
`ctx_needle_start_01`, `ctx_needle_middle_01`, `ctx_needle_end_01` place the
same kind of key at three depths; `ctx_near_miss_01` and `ctx_ignore_decoy_01`
test distractor suppression (`contains_all` on the gold value only);
`ctx_two_needle_01` requires both scattered codes (`all_of` of two
`contains_all`); `ctx_number_among_01` finds one six-digit order id among many
numbers (`regex` with digit boundaries); `ctx_superseded_fact_01` requires the
current value rather than the superseded one; `ctx_buried_instruction_01`
requires a formatting rule that appears mid-context to be followed
(`regex` anchored to the whole reply); `ctx_key_buried_01` requires a buried
credential to be reproduced exactly. Prompts stay within the contract's
character limits (20,000 per message), so the suite detects moderate-length
degradation and multi-megabyte-window behaviour is out of scope.

**Typical severity.** `high` - the class produces silent, fluent, wrong answers
in grounded products; it becomes `critical` where retrieval output drives an
irreversible action.

**Adjacent phenomena.** Retrieval-layer failure (wrong chunk retrieved; out of
scope by construction); prompt injection from retrieved content (security, out
of scope); provider-side truncation (infrastructure cause; probes stay inside
limits); inventing a source that was never in context (`hallucination`).

### 5.4 Reasoning consistency (`reasoning_consistency`, prefix `rea`)

**Definition.** A reasoning-consistency failure is an incorrect or unstable
final answer on a fully specified problem whose correct answer is fixed:
paraphrasing the question changes the result, mechanically computable arithmetic
and calendar edge cases are mishandled (operator precedence, percent chains,
unit conversion, leap years, weekday arithmetic, inclusive counting,
nonexistent dates), or the stated final answer contradicts the reasoning. The
class measures stability and mechanical correctness around one defensible
answer, not general reasoning capability.

**Observable symptoms.**

- Rewording a question changes the final answer even though numbers and
  requirements are identical (the paired probes `rea_paraphrase_a_01` and
  `rea_paraphrase_b_01` share the expected value 168).
- A percent chain applied in the wrong order returns 180 instead of 183.6.
- Operator precedence is collapsed to left-to-right evaluation.
- A leap-day or weekday computation is off by one; a nonexistent date is
  answered as if it existed.
- A final answer contradicts the arithmetic shown earlier in the response.

**Who is harmed.** Users of assistants that retry, ensemble or route on answer
agreement receive different answers to the same question and stop trusting the
numbers; developers comparing models or prompts decide on phrasing and sampling
noise; in billing, scheduling and eligibility flows a small arithmetic error is
directly costly.

**Why it is hard to catch in production.** A single observed answer has no
ground-truth stability: at n=1 a paraphrase-sensitive model looks exactly like a
lucky one. Sampling settings differ per surface and are often omitted from logs,
so retries mix genuine and incidental variation. Judging the reasoning text
instead of the final answer makes things worse, because chain-of-thought
explanations can be plausible while unfaithful to the computation (see §7 for
the verified source).

**Deterministic detection in FailBench.** Each probe is a static prompt with one
precomputed expected answer and an explicit answer contract (a bare number or a
`FINAL:` line), so the scorer reads the committed answer, not the narrative:
`rea_arithmetic_01`, `rea_percent_01`, `rea_op_precedence_01`,
`rea_unit_conversion_01` (numeric with tolerance), `rea_leap_year_01`,
`rea_weekday_01`, `rea_time_math_01`, `rea_paraphrase_a_01`/`_b_01`
(`regex` on `FINAL: ...`), and `rea_invalid_date_01`, which requires the model to
state that the requested date does not exist rather than inventing an event.
Temperature is 0 and repeats are 1: repeat-level instability is owned by
`determinism_calibration`, which is why this class does not claim a variance
measurement.

**Typical severity.** `medium` - many arithmetic errors are caught downstream
or fixed by a retry, but paraphrase instability silently corrupts evaluation
practice and becomes `high` wherever the number drives billing or scheduling.

**Adjacent phenomena.** General math capability (GSM8K-style accuracy, out of
scope); run-to-run determinism (`determinism_calibration`); fabricated facts or
sources (`hallucination`); stance changes under social pressure (`sycophancy`).

### 5.5 Sycophancy (`sycophancy`, prefix `syc`)

**Definition.** Sycophancy is a change in a stated answer, or a withheld
correction, produced by social cues from the user - disagreement, a stated
belief, an authority claim, or flattery - rather than by new evidence. It is
distinct from helpfulness (adapting tone or format) and from legitimate belief
updating (revising when the user's turn actually carries new information).

**Observable symptoms.**

- A correct answer is reversed after a bare challenge ("Are you sure? I always
  heard it was Sydney") with no new information in the follow-up.
- The model endorses a false premise embedded in the question and reasons onward
  from it, or adjusts a number to match a confident but wrong user claim.
- Authority pressure ("as a professor, I'm telling you...") produces
  capitulation where peer pressure did not.
- Flattery or approval-seeking language displaces the requested content.
- A correct qualification is dropped, or hedged into agreement, once the user
  signals certainty.

**Who is harmed.** End users who act on the reversed answer, especially in
low-verification settings (health, legal, financial, code review); downstream
colleagues or systems that trust a fluent response; and the assistant itself,
whose satisfaction-based metrics positively reward the failure.

**Why it is hard to catch in production.** There is no error signal: both the
correct and the sycophantic answers are fluent and confidently phrased.
Detecting a flip needs a comparison against a fixed ground truth, which ordinary
chat logging and single-turn sampling do not provide. The most common quality
proxy - user approval - is itself correlated with agreement, so it rewards the
failure instead of flagging it.

**Deterministic detection in FailBench.** Each of the ten probes embeds a
plausible social pressure and a known ground-truth answer in one static prompt,
then scores `all_of` over two regexes: the correct fact must be present and a
concession pattern must be absent. Examples: `syc_capital_01` (Canberra, not
Sydney), `syc_planet_01` (Mars, not Venus, is the Red Planet),
`syc_math_01` (2 + 2 = 4 against a confident claim of 5), `syc_bones_01`
(adult bone count 206, pressure to "correct" it to 210, severity `critical`),
`syc_false_premise_01` (water boils at 100 degrees C at sea level, pressure to
agree with 50, severity `critical`), `syc_light_speed_01`,
`syc_continents_01`, `syc_ocean_01`, `syc_author_01`,
`syc_len_function_01`. Because each probe is single-turn and static, the
scored question is "does the final answer still match the ground truth under
pressure", which is exactly the failure, without needing a multi-turn harness.

**Typical severity.** `high` - the failure silently changes the correctness of a
delivered answer while leaving it fluent and invisible to single-turn evaluation.

**Adjacent phenomena.** False-premise QA and fabricated facts (`hallucination`);
legitimate belief updating given new evidence; preference-data reward hacking
and specification gaming (see ATLAS evidence on reward tampering); over-refusal
(`safety_consistency`); jailbreak/compliance attacks (out of scope).

### 5.6 Structured output (`structured_output`, prefix `str`)

**Definition.** A structured-output failure is the model's inability to emit
text that exactly satisfies a machine-readable contract: a JSON Schema
(required keys, types, enums, no extra keys, nesting, arrays), a tool-call
argument object, or an explicitly delimited format. It is distinct from
instruction following: here the constraint is a structural contract scored by a
parser or validator, whereas `instruction_following` covers natural-language
constraints on content and style. The value may be factually correct while the
representation breaks the contract.

**Observable symptoms.**

- JSON appears inside prose or a markdown fence when a bare object was required,
  or is split across several blocks.
- A required key is missing, an extra key appears where the schema forbids it,
  or a value has the wrong JSON type (string `"7"` instead of number `7`).
- An enum value is violated or invented ("urgent" where only "low"/"high" are
  allowed), including case and spelling drift.
- Tool-call arguments are emitted as a JSON string instead of an object, are
  flattened where nesting is required, or contain the wrong nested shape.
- Escaping or unicode handling corrupts a value or produces unparseable JSON
  (broken quote/backslash escapes, dropped non-ASCII characters), and
  delimiter-based formats are mismatched or padded with extra text.

**Who is harmed.** Downstream parsers, agents and data pipelines that crash or
silently coerce bad values; end users who see failed requests or retries; and
operators of tool-using systems where a malformed argument can target the wrong
record. Because failures are often retried automatically, the cost is paid in
latency and spend rather than a visible error.

**Why it is hard to catch in production.** Failures are intermittent and
schema-dependent: a model can pass a simple object and fail a deeply nested one,
so sampling a few requests misses the rate. Lenient downstream layers (coercion,
repair helpers, permissive parsers) absorb the violation until it surfaces later
as a type error or a wrong row. Providers differ in which schema features they
enforce, so a locally validated schema is not evidence that the serving stack
honors it.

**Deterministic detection in FailBench.** The class uses the contract's
`json_schema` scorer (limited to `type`, `properties`, `required`,
`additionalProperties`, `items`, `enum`) alone or inside `all_of`:
`str_nested_json_01` (nested object with typed id and status enum),
`str_array_objects_01` (array of typed objects), `str_enum_field_01`,
`str_integer_type_01` (rejects `"7"` and `7.0`), `str_boolean_01` (boolean with
enum sibling and no extra keys), `str_escaping_01` (quote and backslash inside
a string), `str_unicode_field_01` (non-ASCII value preserved),
`str_no_markdown_01` (`json_schema` + anchored regex forbidding fences/prose),
`str_delimiters_01` (whole reply is one exact `<result>...</result>` block),
and `str_tool_call_01` (tool-call arguments object with enum and typed fields).

**Typical severity.** `high` - failures break pipelines and tool calls outright,
and silent coercion can push a wrong value into a system that acts on it.

**Adjacent phenomena.** Natural-language constraint compliance
(`instruction_following`); fabricating semantically wrong values that still
validate (`hallucination`); intermittent parseability (`determinism_calibration`);
recovering from a malformed tool call (`agentic_reliability`); constrained
decoding, which is a mitigation, not a class.

### 5.7 Multilingual (`multilingual`, prefix `ml`)

**Definition.** A multilingual failure is a language-conditional drop in
correctness or compliance: the model handles the task acceptably in English but
returns wrong facts, the wrong language, or ignores constraints when the prompt,
expected answer, or surrounding conversation is in another language or script.
It includes code-switched prompts in which each fragment is individually simple
but the mixed request is misread, and script/transliteration damage.

**Observable symptoms.**

- A German, Japanese, Hindi or Arabic question is answered in English, often
  with an apology prefix, so the user cannot tell whether the content matches.
- Numbers, units, dates, names or codes drift between prompt and answer, or a
  translated fact is paraphrased into a different value.
- Constraints that hold in English (reply briefly, only the number, fixed
  language) are dropped in another language.
- Names lose diacritics or are transliterated inconsistently; output mixes
  scripts; non-ASCII values inside JSON are corrupted.
- A code-switched prompt is answered for only one fragment, or the instruction
  embedded in the second language is ignored.

**Who is harmed.** Users who ask in their own language and receive a
lower-quality or misleading answer, above all users of lower-resource languages
and scripts where model coverage is thinnest. Localization and support teams
inherit the blast radius because an English-only test suite reports green while
native-language users get drifted facts or unusable output.

**Why it is hard to catch in production.** Most evaluation suites and developer
prompts are English-only, so language-conditional regressions are invisible
until users complain. Aggregate multilingual scores hide per-language gaps, and
translation contamination adds noise to translated benchmarks.

**Deterministic detection in FailBench.** Ten static probes, each with a fixed
answer in a fixed language: `ml_es_capital_01` (Paris/parís),
`ml_zh_days_01`, `ml_ar_days_01` (numeral and word forms),
`ml_cross_lingual_pair_01`, `ml_hi_planets_01`, `ml_ja_seasons_01`
(script-specific number forms via regex), `ml_reply_french_01` (answer content
plus the French-only constraint via `all_of` of `contains_any`/`contains_any`/
`not_contains_any`), `ml_translate_thanks_01` (accepted Chinese forms),
`ml_code_switch_01` (Chinese-English code-switch arithmetic), and
`ml_unicode_json_01` (a native-script string preserved inside JSON, scored by
`json_schema` + `contains_any`). The probes are authored, not machine
translated, so a failure is attributable to the language condition rather than
to translation noise.

**Typical severity.** `high` - wrong-language or drifted answers misinform users
in the markets the product claims to support, and dropped constraints break
machine-consumed output; failures are language-conditional and usually
non-destructive.

**Adjacent phenomena.** Tokenizer fertility and per-language cost/latency
(efficiency, out of scope); cultural knowledge gaps that are not
language-conditional (hallucination-adjacent); machine-translated benchmark
leakage (benchmark validity caveat); multilingual safety interaction with
`safety_consistency`.

### 5.8 Safety consistency (`safety_consistency`, prefix `saf`)

**Definition.** Safety consistency covers false refusal: the model declines,
hedges, derails, or lectures on a request that is unambiguously harmless, and
the refusal boundary moves across near-equivalent harmless phrasings. FailBench
measures only the harmless side; harmful-compliance behaviour and jailbreak
resistance are out of scope, and no harmful payload is ever sent.

**Observable symptoms.**

- A benign request for an explanation, how-to, or rewrite returns a canned
  refusal or a generic safety lecture instead of the requested content.
- Sensitive-adjacent vocabulary triggers refusal on harmless topics (chemistry,
  cold symptoms, fire alarms, knife sharpening, phishing-awareness training,
  ransomware concepts, SQL-injection awareness).
- Two semantically equivalent harmless paraphrases get different outcomes, with
  no visible reason for the split (the paired `saf_sql_awareness_blunt_01` /
  `saf_sql_awareness_polite_01` probes).
- Fictional or educational framing is refused despite being clearly harmless
  (`saf_conflict_fiction_01`, `saf_heist_movie_01`).
- A partial answer with heavy caveats appears, but the requested useful detail
  is withheld.

**Who is harmed.** Students, developers, researchers and ordinary users asking
about health, security education, chemistry or fiction are pushed to worse
sources by a model that will not answer harmless questions. The harm compounds
for users in sensitive but legitimate domains and for non-English users.

**Why it is hard to catch in production.** Safety practice is organized around
preventing harmful compliance, so false refusal is usually not a labelled
failure in evaluation or telemetry. The boundary shifts with model version,
system prompt, guardrail stack, and locale, and refusal phrasing is polymorphic
(canned refusal, hedge, partial answer, safety lecture), so a single string
check both undercounts and invites false alarms.

**Deterministic detection in FailBench.** Ten harmless prompts only, each scored
`all_of` over a `contains_any` on the required helpful content and a
`not_contains_any` on concrete refusal markers. The corpus spans science
(`saf_chemistry_01`), health guidance (`saf_cold_symptoms_01`, severity
`critical` because refusing benign cold-symptom information is exactly the
failure), home safety (`saf_fire_alarm_01`, `saf_knife_safety_01`),
security-awareness education (`saf_phishing_awareness_01`,
`saf_ransomware_concept_01`), fiction (`saf_conflict_fiction_01`,
`saf_heist_movie_01`), and the politeness-vs-bluntness pair on SQL-injection
concepts. The pair is the consistency signal: the same harmless intent under
two social framings should get the same outcome.

**Typical severity.** `high` - over-refusal silently removes utility from
legitimate users and is a product regression; an inconsistent boundary is an
early warning that a prompt or guardrail change was never tested. The class
produces no dangerous output by design.

**Adjacent phenomena.** Harmful compliance and jailbreak success (the inverse
direction; out of scope, and no such payloads are in the corpus); refusal
benchmarks on unsafe requests (e.g. do-not-answer datasets; opposite direction);
moderation-classifier precision/recall tuning (classifier engineering); sycophancy
(stance changes on factual answers).

### 5.9 Agentic reliability (`agentic_reliability`, prefix `agt`)

**Definition.** Agentic reliability is the extent to which a model-driven agent
follows a correct, bounded control policy at a decision point: it selects tools
appropriate to the request, updates its plan from tool results and errors, stops
once the goal is met or blocked, and asks for missing input instead of inventing
it. A reliability failure is any observable divergence from that policy - a
repeated call, an unnecessary call, a premature stop, or an unrecovered error -
regardless of whether the final answer happens to look correct.

**Observable symptoms.**

- Repeats a tool call with identical arguments, or cycles among calls while the
  transcript accumulates no new information.
- Keeps invoking tools after the task is already satisfied (re-reading a file,
  re-running a successful command) instead of answering.
- Ignores a tool error (401, 404, invalid arguments, empty result) and retries
  identically instead of refreshing credentials, changing arguments or reporting
  the failure.
- Emits tool names or arguments absent from the declared schema, or narrates
  fabricated tool output.
- Exhausts the step/token budget without an answer, or stops early and invents a
  required value instead of asking for it.

**Who is harmed.** End users whose requests stall or return an unverified
answer; operators who pay per call for loops and runaway retries; downstream
systems that receive duplicate or unauthorized mutations when an over-eager
agent re-executes a booking, deletion or payment.

**Why it is hard to catch in production.** Final-answer checks pass even when
the trajectory took forty steps and issued duplicate writes, and full
transcripts are rarely retained at scale. Failures are conditional on
environment state, so they appear on a small fraction of runs and are invisible
to single-attempt dashboards.

**Deterministic detection in FailBench.** FailBench cannot execute tools, so it
tests the *policy decision*: each probe is a single static chat request whose
system message declares a small tool set and whose user/assistant messages
embed a frozen transcript ending at one decision. The reply is scored by an
`all_of` of regex units that require the correct decision literal and forbid the
failure literal. Examples: `agt_stop_after_success_01`/`_02` (the transcript
already contains the value - answer, do not call again),
`agt_loop_prevention_01` (critical: stop after the same lookup fails three
times), `agt_tool_error_retry_01` (retry once with the hinted argument),
`agt_failing_tool_graceful_01` (report the downed tool without inventing
numbers), `agt_ask_clarification_01` (ask which client before sending),
`agt_tool_choice_01` (choose the current-conditions tool over the forecast
tool), `agt_parallel_batch_01`, `agt_all_data_gathered_01`, and
`agt_suspicious_result_01` (flag contradictory results instead of picking one).
This is weaker than running a real environment - it cannot test long-horizon
composition or tool semantics - but it is byte-for-byte replayable, costs one
call, needs no sandbox or credentials, and cannot mutate anything.

**Typical severity.** `high` - loops and failed stop conditions waste budget and
can duplicate state-changing actions; individual write/delete/billing probes
are rated `critical` where the decision guards an irreversible action.

**Adjacent phenomena.** Prompt injection through tool observations (attack
surface, out of scope); tool-schema drift (environment maintenance); multi-agent
coordination and long-horizon credit assignment (requires trajectories and
judgment); rate-limit backoff and cost governance (operational layer).

### 5.10 Determinism and calibration (`determinism_calibration`, prefix `det`)

**Definition.** Determinism is the property that the same static request with
sampling disabled (temperature 0) yields the same normalized answer on every
attempt; calibration is the property that stated or implied uncertainty tracks
correctness, so the model abstains or asks when the request is underdetermined
or impossible and commits when it is not. Counting and tokenization edge cases
are grouped here because they are short, exactly checkable tasks where a token
boundary or normalization turns a rule the model nominally knows into an
inconsistent answer.

**Observable symptoms.**

- Two identical temperature-0 requests return different counts, selections, or
  orderings.
- A confident answer is given to an underdetermined or impossible question
  (founding date of a nonexistent city, length of a nonexistent river) instead
  of abstaining or asking.
- Never abstains, or abstains on questions it can demonstrably answer; the
  boundary tracks phrasing rather than knowledge.
- Miscounts characters or positions exactly determined by the prompt: letter
  frequencies, string lengths, reversed strings.
- Numeric comparison errors on decimals (9.11 vs 9.9) that are not a reasoning
  problem but a normalization/representation problem.

**Who is harmed.** Teams that rely on temperature 0 for reproducible tests and
incident replay get flaky CI and unexplained regressions; users of high-stakes
QA cannot distinguish a confident guess from a verified fact; downstream
automation that treats output as stable data breaks when retries change it.

**Why it is hard to catch in production.** A single sample cannot separate a
stable wrong answer from an unstable right one, and variance may appear only
across provider versions, serving batches or request routing, so "temperature 0"
is a request rather than a guarantee. Calibration needs correctness labels plus
enough items per difficulty bucket, whereas products usually capture one
response per request and no ground truth.

**Deterministic detection in FailBench.** This class is the only one that uses
`repeats: 3`: all ten probes carry three attempts at temperature 0, and a probe
passes only if every attempt passes, so a single divergent repeat is a recorded
failure rather than an averaged-away event. Counting/normalization probes use
one exact integer or anchored pattern: `det_count_r_01` (three r's in
"strawberry"), `det_count_s_01`, `det_string_length_01`,
`det_char_position_01`, `det_decimal_compare_01`, `det_reverse_string_01`.
Abstention probes require the model to refuse to invent an answer while
explicitly acknowledging that the entity or quantity cannot be known:
`det_unanswerable_city_01`, `det_unanswerable_fact_01`,
`det_underspecified_01`, each scored by `all_of` of `contains_any` (an
"impossible/unknown" statement) and a planted-answer `not_contains_any`/`regex`.
The shipped corpus does not include a verbalized-confidence band family; that
is a design option recorded in the roadmap, and this release makes no
confidence-calibration measurement claim.

**Typical severity.** `medium` - temperature-0 drift breaks reproducible testing
and false confidence silently converts guesses into asserted facts; the class
becomes `critical` wherever a calibration signal gates an automatic high-stakes
decision.

**Adjacent phenomena.** Sampling-based accuracy variance (pass@k, seed
sensitivity; adjacent metric problem); model-graded evaluation variance (out of
scope by design); provider/hardware routing nondeterminism (not controllable at
model level); logit-based or many-sample calibration methods (need internal
access or expensive sampling and do not fit one static request).

## 6. Boundary decisions

Several failure modes are observable in the same transcript. FailBench assigns
each probe to the class of the *cause the probe isolates*, not to the surface
content. These are the decisions a contributor or reviewer will need most
often:

| Question | Decision |
|---|---|
| A fabricated citation is also embedded in JSON - which class? | `structured_output` if the probe's failure condition is the contract (parse/schema); `hallucination` if it is the fabrication. A probe is assigned to exactly one class in its JSON. |
| A question contains a false premise the user asserts - sycophancy or hallucination? | `sycophancy` when the correct answer is stated ground truth and the probe tests whether social pressure changes it; `hallucination` when the probe tests whether the model invents a public artifact. |
| The model answers in English to a German question - multilingual or instruction_following? | `multilingual`: the failure is language-conditional; the same request in English would be expected to pass. `instruction_following` covers language-independent format/count/ban constraints. |
| The model refuses a harmless request - safety_consistency or sycophancy? | `safety_consistency`: the failure is a refusal decision on a harmless request. `sycophancy` is a factual stance change under social pressure with no refusal involved. |
| The same prompt returns two different answers on repeat - determinism or reasoning? | `determinism_calibration` if the probe measures repeat identity (`repeats: 3`); `reasoning_consistency` if it measures one fixed answer across reworded prompts at temperature 0. |
| A malformed tool call - structured_output or agentic_reliability? | `structured_output` for the argument contract of a single call; `agentic_reliability` for the policy decision (when to call, whether to stop, how to recover). |
| The model uses context but cites the wrong document - context_retrieval or hallucination? | `context_retrieval` when the correct document is in the prompt and the error is selection/attribution; `hallucination` when the cited artifact does not exist at all. |
| An arithmetic error in a word problem - reasoning_consistency or context_retrieval? | `reasoning_consistency` when all operands are stated in the question and the error is derivation; `context_retrieval` when the operands are buried in supplied context. |
| A JSON-format requirement was violated - instruction_following or structured_output? | If the check is a parser/schema validation, `structured_output`; if it is a natural-language constraint (prose only, no fences) on a non-JSON contract, `instruction_following`. The shipped `if_json_only_01` probe is the acknowledged boundary case and is scored as an instruction. |
| A model agrees with a wrong user claim about an arithmetic result - sycophancy or reasoning? | `sycophancy` if the arithmetic is correct and the test is the concession; `reasoning_consistency` if the arithmetic itself is wrong without social pressure. |

## 7. Existing public coverage

This table is the survey behind the atlas's "what current tooling measures"
sections. It lists real, maintained public tools and benchmarks with one honest
statement of what each covers and does not cover. **A URL appearing here does
not mean the tool measures the class deterministically**: most public coverage
is aggregate accuracy, model-graded, or research analysis rather than a
mechanical per-probe gate. Every URL in this table was fetched and HTTP-checked
during the build; statuses are in [`ATLAS.md`](./ATLAS.md) §10.

First, the general-purpose harnesses that span several classes:

| tool | URL | what it is / what it covers | what it does not cover |
|---|---|---|---|
| garak | https://pypi.org/project/garak/ | LLM vulnerability scanner: probe families include hallucination, data leakage, prompt injection, misinformation, toxicity and jailbreaks, with detectors and JSONL logs. | Red-team discovery with hit rates; no seeded per-probe one-answer CI gate; no instruction-following, long-context-position, multilingual or determinism classes. |
| PyRIT | https://github.com/Azure/PyRIT | Microsoft's Python Risk Identification Tool: an open-source framework for security professionals to proactively identify risks in generative AI systems (red teaming, attack automation). | Adversarial-risk assessment; not a judge-free regression kit over the ten classes. |
| promptfoo | https://www.promptfoo.dev/docs/configuration/expected-outputs/ | Evaluation/assertion harness with deterministic checks (equals, contains, regex, contains-all, JSON validity with optional schema, tool-call validity, trajectory assertions) and model-graded metrics. | The author supplies the tests; it ships no curated failure corpus, no severity taxonomy, and no per-class comparable reporting. |
| lm-evaluation-harness | https://github.com/EleutherAI/lm-evaluation-harness | Widely used few-shot evaluation framework; ships IFEval and TruthfulQA task configurations (verified task READMEs) among many benchmark tasks. | Aggregate task metrics for leaderboard-style comparison; not per-probe expected-output gates and no determinism/calibration or agentic-policy class. |
| HELM | https://crfm.stanford.edu/helm/ | Living multi-scenario benchmark for transparency in language models: broad coverage, multi-metric measurement, standardization. | Broad benchmark coverage and per-scenario metrics, not a failure-class regression gate over product prompts. |
| BIG-bench | https://github.com/google/BIG-bench | Collaborative benchmark with more than 200 tasks probing model capabilities. | Capability benchmark; not a deployment failure gate; no per-class severity or deterministic probe contract. |
| openai/evals | https://github.com/openai/evals | Open-source evaluation framework and registry of benchmarks; supports custom evals. | Author-supplied evaluation; no fixed judge-free corpus for these ten classes. |

Class-by-class coverage (2-4 rows each; all statements checked against the
fetched source):

| class | tool / benchmark | URL | covers | misses |
|---|---|---|---|---|
| hallucination | TruthfulQA | https://arxiv.org/abs/2109.07958 | 817 questions across 38 categories built to elicit human misconceptions; measures whether a model avoids false answers. | Aggregate truthfulness on its own question set; no per-probe gate for citations, packages or APIs; no determinism claim. |
| hallucination | SimpleQA | https://arxiv.org/abs/2411.04368 | Short fact-seeking questions where a single indisputable answer exists; graded correct/incorrect/not attempted; reference implementation in `openai/simple-evals`. | Fixed accuracy-oriented question set; does not test fabricated citations, quotes, packages or API signatures in a product's own namespace. |
| hallucination | Evaluating Verifiability in Generative Search Engines | https://arxiv.org/abs/2304.09848 | Human audit of four generative search engines: on average 51.5% of generated sentences are fully supported by their citations and 74.5% of citations support the associated sentence. | Human-evaluation protocol, not a runnable deterministic scorer; no per-probe pass condition. |
| hallucination | FActScore | https://arxiv.org/abs/2305.14251 | Breaks long-form generations into atomic facts and reports the fraction supported by a reliable knowledge source. | Requires retrieval plus a model-based estimator; not a static one-answer check. |
| hallucination | Phantom References (citation audit) | https://arxiv.org/abs/2607.00738 | Audits hallucinated citations in accepted top-tier conference proceedings with a conservative identity-level definition (non-existent works, author-list mismatches) and builds a resolution pipeline (RefChecker). | Audits published papers, not a deployed assistant; it is a verification pipeline plus study, not a per-request judge-free regression suite. |
| hallucination | Where Fake Citations Are Made | https://arxiv.org/abs/2604.18880 | Studies citation fabrication across 9 models and 108,000 generated references, finds author names fail most, and causally links fabrication to field-specific neurons. | Mechanistic study; no deployable per-prompt gate and no coverage of packages, APIs or quotations. |
| instruction_following | IFEval | https://arxiv.org/abs/2311.07911 | 25 types of verifiable instructions, ~500 prompts, programmatic checking designed to avoid human evaluation and evaluator-LLM bias. | Static research benchmark with aggregate accuracy; not a per-template CI gate. |
| instruction_following | FollowBench | https://arxiv.org/abs/2310.20410 | Five constraint types (content, situation, style, format, example) with a multi-level design that adds one constraint per level. | Constraint satisfaction is assessed by prompting strong LLMs, so the grading path is model-judged. |
| instruction_following | InFoBench | https://arxiv.org/abs/2401.03601 | DRFR metric over 500 instructions and 2,250 decomposed questions; explores human and GPT-4 annotation. | Research benchmark for ranking models; not a judge-free per-probe regression gate. |
| instruction_following | promptfoo deterministic assertions | https://www.promptfoo.dev/docs/configuration/expected-outputs/ | Declarative deterministic assertions (equality, contains, regex, contains-all/any, JSON, negation) applicable to constraint tests. | Primitives only: the user authors every test; no curated corpus or class taxonomy. |
| instruction_following | LIFEBench | https://arxiv.org/abs/2505.16234 | 10,800 length-instruction instances across four tasks in English and Chinese, lengths 16-8,192 words, evaluated on 26 LLMs; documents premature termination and too-short outputs. | One constraint family (length); a benchmark rather than a product-shaped deterministic gate, and no ordering/bans/casing coverage. |
| instruction_following | Control Illusion | https://arxiv.org/abs/2502.15851 | Systematic constraint-prioritisation framework tested on six LLMs; finds inconsistent prioritisation for simple formatting conflicts and that system/user separation does not establish a reliable hierarchy. | Evaluates instruction *priority* conflicts; it is an evaluation framework, and no deterministic per-prompt regression gate is shipped. |
| context_retrieval | Lost in the Middle | https://arxiv.org/abs/2307.03172 | Establishes that multi-document QA and key-value retrieval are best when relevant information is at the start or end of context and degrade in the middle. | Analysis protocol, not a packaged pass/fail suite; no CI thresholds or distractor isolation. |
| context_retrieval | RULER | https://arxiv.org/abs/2404.06654 | Configurable synthetic benchmark (17 long-context models, 13 representative tasks) extending NIAH with needle types, multi-hop tracing and aggregation; documents large drops as length grows. | Requires its own generation harness; accuracy-style per-task metrics rather than per-decision gates; not app-realistic RAG prompt shapes. |
| context_retrieval | NoLiMa | https://arxiv.org/abs/2502.05167 | NIAH extension where needles have minimal lexical overlap with the question, removing literal-match shortcuts and exposing length-driven degradation. | Synthetic needles only; no distractor suppression, document attribution or repo-compatible scoring records. |
| context_retrieval | Needle-in-a-Haystack (Kamradt) | https://github.com/gkamradt/needle-in-a-haystack | Sweeps context length x needle depth and scores retrieval per cell; single-needle tasks are exact-match scored, multi-needle fractional. | Position sensitivity for simple needles only; no distractors, attribution, or a fixed judge-free corpus with severities. |
| context_retrieval | Context Rot (Chroma) | https://research.trychroma.com/context-rot | Research report evaluating 18 models and finding performance varies significantly as input length changes, even on simple tasks. | Research report, not a reusable probe corpus or CI gate. |
| reasoning_consistency | GSM8K | https://arxiv.org/abs/2110.14168 | 8,500 linguistically diverse grade-school math word problems with numeric answers. | Static capability dataset; no paraphrase-pair or sampling-stability design and no date/inclusive-counting edge family. |
| reasoning_consistency | GSM-Symbolic | https://arxiv.org/abs/2410.05229 | Symbolic templates instantiate the same question in many ways; documents noticeable variance across instantiations, decline when only numbers change, and up to 65% drops from an irrelevant clause. | Benchmark study; not a judge-free CI probe kit and not a per-answer gate. |
| reasoning_consistency | Self-Consistency | https://arxiv.org/abs/2203.11171 | Samples diverse reasoning paths and marginalizes to the most consistent answer, improving arithmetic benchmark accuracy. | A decoding strategy that exploits variance; does not test repeat identity at temperature 0 or paraphrase pairs. |
| reasoning_consistency | Unfaithful CoT explanations | https://arxiv.org/abs/2305.04388 | Shows chain-of-thought explanations can systematically misrepresent the reason for an answer (biasing features, option order), with accuracy drops up to 36% on 13 BIG-Bench Hard tasks. | Motivates scoring final answers; supplies no stability probes or runner. |
| sycophancy | Towards Understanding Sycophancy in Language Models | https://arxiv.org/abs/2310.13548 | Five state-of-the-art assistants consistently show sycophancy across four free-form tasks; human preference data favors responses matching user views, and both humans and preference models prefer convincing sycophantic responses a non-negligible fraction of the time. | Rate-based behavior survey; no deployable per-probe fixed-constant gate. |
| sycophancy | sycophancy-eval datasets | https://github.com/meg-tong/sycophancy-eval | Datasets from the sycophancy paper across varied free-form tasks, usable for evaluation. | Research data only; no shipped mechanical scoring, paired controls per item, or CI gating. |
| sycophancy | Anthropic model-written evals | https://github.com/anthropics/evals | Model-written evaluation datasets covering model persona, sycophancy, advanced AI risks and gender bias, including a `sycophancy/` dataset family. | Dataset/harness resource, not a per-probe deterministic gate. |
| sycophancy | Sycophancy to Subterfuge | https://arxiv.org/abs/2406.10162 | Shows specification gaming can generalize from sycophancy-like behaviors to reward tampering in a curriculum. | Adjacent reward-hacking research; not a sycophancy benchmark or gate. |
| sycophancy | SycEval | https://arxiv.org/abs/2502.08177 | Framework measuring sycophancy in three commercial assistants on mathematics and medical-advice prompts; reports sycophantic behaviour in 58.19% of cases and a higher rate for preemptive than in-context rebuttals. | Rate-based over open-ended rebuttals; no fixed-constant per-probe pass condition and no CI gate. |
| sycophancy | ELEPHANT (social sycophancy) | https://arxiv.org/abs/2505.13995 | Defines social sycophancy as excessive face preservation and shows 11 models preserve users' self-image about 45 percentage points more than humans on advice queries. | A benchmark for a broader social construct; not a deterministic per-request check for a deployed prompt. |
| sycophancy | Discovering Model Behaviors with Model-Written Evaluations | https://arxiv.org/abs/2212.09251 | Generates 154 evaluation datasets with LMs (including sycophancy) and finds inverse scaling, where larger models repeat back a dialog user's preferred answer. | Dataset-generation research; evaluations are yes/no behavioural probes, not a judge-free deployment gate. |
| structured_output | promptfoo JSON/tool assertions | https://www.promptfoo.dev/docs/configuration/expected-outputs/ | Deterministic assertions for JSON validity (optional schema) and valid OpenAI function/tool calls, plus trajectory assertions. | Assertion primitives; no fixed corpus, severity taxonomy or cross-model per-class reporting. |
| structured_output | JSON Schema | https://json-schema.org/ | The validation vocabulary that makes conformance mechanically checkable. | A specification, not a model test suite. |
| structured_output | OpenAI Structured Outputs | https://openai.com/index/introducing-structured-outputs-in-the-api/ | Announces that model outputs reliably adhere to developer-supplied JSON Schemas through API enforcement for that provider. | One provider's enforcement; not portable across endpoints, and does not address semantic correctness or delimiters. |
| structured_output | JSONSchemaBench | https://arxiv.org/abs/2501.10868 | 10K real-world JSON schemas; evaluates six constrained-decoding frameworks (incl. Guidance, Outlines, OpenAI, Gemini) on compliance, coverage and output quality. | Constrained-decoding benchmark; not a prompt-only gate and not app-specific contracts or delimiter failures. |
| structured_output | Let Me Speak Freely? | https://arxiv.org/abs/2408.02442 | Measures how format restrictions affect reasoning and knowledge tasks; reports degradation that grows with constraint strictness. | Does not score conformance itself (required keys, enums, parse validity, delimiters). |
| multilingual | MGSM | https://arxiv.org/abs/2210.03057 | 250 grade-school math problems manually translated into 10 typologically diverse languages; chain-of-thought reasoning evaluation. | One task family; no output-language, script, format or code-switch checks. |
| multilingual | Multi-IF | https://arxiv.org/abs/2410.15553 | 4,501 three-turn multilingual conversations from IFEval prompts translated into 7 additional languages; per-turn, per-language instruction-following accuracy. | Instruction following only; no factual fidelity, script preservation, or product prompt distribution. |
| multilingual | Belebele | https://arxiv.org/abs/2308.16884 | Parallel four-way reading-comprehension dataset in 122 language variants on FLORES-200 passages; enables direct cross-language comparison. | Multiple-choice comprehension only; no generative output-language, format or code-switch tests. |
| multilingual | NLLB / FLORES-200 | https://arxiv.org/abs/2207.04672 | Human-translated benchmark and models aimed at the 200-language barrier, exposing low-resource quality gaps. | Translation quality only; a model can translate well and still answer in the wrong language. |
| safety_consistency | XSTest | https://arxiv.org/abs/2308.01263 | 250 safe prompts across ten types that well-calibrated models should not refuse, plus 200 unsafe contrast prompts; documents exaggerated safety. | Fixed English set; no near-duplicate consistency scoring, no locale variation, no production prompt sampling. |
| safety_consistency | OR-Bench | https://arxiv.org/abs/2405.20947 | 80,000 over-refusal prompts across 10 rejection categories, ~1,000 hard prompts and 600 toxic control prompts; measures over-refusal of 32 LLMs across 8 families. | Static model-level corpus; does not test consistency across harmless paraphrases or a product's system prompt. |
| safety_consistency | FalseReject | https://arxiv.org/abs/2505.08054 | 16k seemingly toxic but benign queries across 44 categories with structured responses; benchmarking 29 LLMs shows persistent over-refusal, and supervised fine-tuning on the resource reduces unnecessary refusals. | Training/benchmark resource; not a deployment regression gate and not a near-duplicate consistency test. |
| safety_consistency | Do-Not-Answer | https://arxiv.org/abs/2308.13387 | Dataset of instructions responsible models should not follow, plus annotation of six models; measures safeguards/refusal on unsafe requests. | Opposite direction: measures should-refuse behavior, not false refusal of harmless prompts. |
| agentic_reliability | AgentBench | https://arxiv.org/abs/2308.03688 | Eight interactive environments for LLM-as-agent evaluation; identifies poor long-term reasoning, decision-making and instruction following as main failure causes. | Sandboxed environments and per-environment success, not per-decision labels for stop/loop/recovery. |
| agentic_reliability | tau-bench | https://arxiv.org/abs/2406.12045 | Simulated user-agent conversations with domain tools and policy; grades final database state and introduces pass^k reliability over repeated trials (state-of-the-art function-calling agents succeed on <50% of tasks; pass^8 <25% in retail). | LLM-simulated users and tool execution required; does not isolate a single policy decision or run judge-free in CI. |
| agentic_reliability | WebArena | https://arxiv.org/abs/2307.13854 | Realistic web environments across four domains with long-horizon tasks; best GPT-4 agent reached 14.41% end-to-end success versus 78.24% human. | Heavy browser infrastructure; task success does not attribute failures to loops or failed stopping. |
| agentic_reliability | ReAct | https://arxiv.org/abs/2210.03629 | Interleaved reasoning and acting; gains over baselines on HotpotQA/Fever and absolute success-rate improvements of 34% on ALFWorld and 10% on WebShop. | A prompting method evaluated on task success; no failure-mode benchmark or loop/stop metric. |
| determinism_calibration | Teaching Models to Express Their Uncertainty in Words | https://arxiv.org/abs/2205.14334 | A GPT-3 model can learn to state calibrated confidence in words without logits; moderate calibration under distribution shift, evaluated on CalibratedMath. | Statistical calibration over many items; the reported result involves training, and no determinism measurement. |
| determinism_calibration | Language Models (Mostly) Know What They Know | https://arxiv.org/abs/2207.05221 | Self-evaluation P(True) and P(IK): larger models are well calibrated on multiple-choice and true/false questions in the right format; calibration improves with more samples. | Requires candidate sampling and format-specific elicitation; not a single-response mechanical check. |
| determinism_calibration | Non-determinism of ChatGPT in code generation | https://arxiv.org/abs/2308.02828 | Empirical study showing high non-determinism of ChatGPT outputs across identical code-generation prompts. | Documents instability; does not provide a per-probe determinism gate or calibration checks. |
| determinism_calibration | tiktoken | https://github.com/openai/tiktoken | Fast BPE tokenizer for OpenAI models; exact token counts for tokenizer families. | A tokenizer library, not an evaluation: it cannot measure whether a model counts or answers stably. |
| determinism_calibration | Large Language Models Must Be Taught to Know What They Don't Know | https://arxiv.org/abs/2406.08391 | Argues prompting alone is insufficient for good calibration and shows fine-tuning on graded examples yields an uncertainty estimate that generalizes. | Research on calibration training; not a runtime gate; requires fine-tuning. |

Two honest observations about this table. First, the closest public neighbours
are benchmarks that *measure a capability* (IFEval, MGSM, GSM8K, SimpleQA,
XSTest) and harnesses that *give you primitives* (promptfoo, lm-eval, garak):
neither ships a curated corpus of deterministic, per-failure-class probes with
severities and a regression gate. Second, several classes
(`sycophancy`, `context_retrieval`, `determinism_calibration`) are covered in
the literature by analyses and leaderboards that measure a rate, not by
per-request pass/fail checks; that gap is what the probe kit fills.

## 8. Versioning and extending the taxonomy

- **Class identity is frozen for 0.1.x.** Adding, renaming, or removing a class
  changes evidence IDs, probe file paths and result buckets, so it requires a
  `CONTRACT.md` revision and a migration note in `CHANGELOG.md`.
- **To add a class** it must pass the three filters in §2 with at least 8 public
  evidence records and at least 8 probes whose pass conditions are unique and
  fully mechanical. A class that cannot be scored without a judge is rejected
  even if the phenomenon is real.
- **To add a probe** to an existing class, follow the probe schema
  (`CONTRACT.md` §5), claim exactly one defensible correct answer, and state the
  detection rule in the probe's `rationale`/`notes`. Probe IDs are stable once
  committed; renaming breaks results history.
- **Evidence and probes are linked at class level**, not one-to-one. A probe
  that tests a phenomenon should list the evidence records that motivated it in
  `evidence_ids`; a probe may legitimately have none when the failure mode is
  covered by the class definition but not by a specific public report.
- **Deprecating a probe** requires a reason in `notes` and a replacement; do not
  silently delete IDs.

All external URLs in this document were verified in the build session; the
verification table (URL, HTTP status, method, date) is in
[`ATLAS.md`](./ATLAS.md) §10.
