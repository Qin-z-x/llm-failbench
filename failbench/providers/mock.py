"""Deterministic, offline mock provider for FailBench (stdlib only).

WHAT THIS MODULE IS
-------------------
``MockProvider`` is a synthetic, fully deterministic stand-in provider used to
exercise the FailBench ``runner`` / ``gate`` / ``report`` / CI / committed demo
pipeline end to end. It is **not a measurement of any model**: no model
endpoint is contacted, no inference happens, and no API key or network socket is
used. Its pass/fail/error mix exists only so the pipeline exercises all three
status paths (never 100% pass, see CONTRACT sections 6 and 8).

WHAT THE NUMBERS MEAN
---------------------
``prompt_tokens`` and ``completion_tokens`` are synthetic estimates derived from
character counts (``len(text) // 4``), and ``latency_ms`` is a synthetic value
derived from the same hash. None of these reflect real model cost or timing.

ERRORS ARE NOT FAILURES
-----------------------
For roughly 2% of (probe id, attempt) pairs this provider raises
:class:`failbench.providers.base.ProviderError` to simulate a transport
failure. Per CONTRACT section 6 that is an **error**, never a model failure:
the runner must record ``status: "error"`` and must not treat it as a failed
probe.

DETERMINISM
-----------
Every decision is a pure function of
``hashlib.sha256("<probe_id>:<attempt>")``. There is no use of ``random``,
wall-clock time, environment variables or the network, so repeated runs on any
machine produce byte-identical text, tokens and latency. Candidate synthesis is
also pure: it depends only on the scoring spec.

PASS SYNTHESIS IS BEST EFFORT
-----------------------------
A "pass" bucket decision does not promise that a passing response can be
synthesized for an arbitrary scoring spec. Responses are built mechanically:
known scoring types get exact/idiomatic texts, regex specs are "un-regexed"
into literal candidates, nested ``all_of`` units are solved separately and then
combined (joined, reordered, or prefixed with a JSON instance). **Every
candidate is verified with** :func:`failbench.scoring.score` before it is
returned; if no candidate satisfies a degenerate or self-contradictory spec, a
plain fallback is returned instead. This keeps the demo mix honest (a mock
"pass" always actually passes in practice) while staying deterministic.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from ..scoring import score
from .base import Provider, ProviderError, ProviderResponse

# ---------------------------------------------------------------------------
# Deterministic decision boundaries
# ---------------------------------------------------------------------------

#: ``bucket`` in [0, 70) -> pass, [70, 98) -> fail, [98, 100) -> simulated error.
PASS_BUCKET_LIMIT = 70
ERROR_BUCKET_START = 98

#: Returned by pass synthesis only when no candidate can satisfy the spec.
PASS_FALLBACK = "I cannot comply with that request."

#: Last-resort failing text (used only after every candidate passed).
FAIL_FALLBACK = "XYZZY_INCORRECT"

#: Neutral texts that satisfy an empty ``not_contains_any`` forbidden list
#: without mentioning any forbidden value.
NEUTRAL_PASS_CANDIDATES: List[str] = [
    "Understood.",
    "Yes.",
    "The requested constraints are respected.",
    "Done.",
    "OK",
]

#: Candidate texts used to satisfy a ``regex`` scorer (best effort: a pattern
#: may be arbitrary, so this list is a fixed set of common response shapes).
REGEX_PASS_CANDIDATES: List[str] = [
    "OK",
    "42",
    "2026-11-24",
    "AURORA-7734",
    "yes",
    "no",
    "true",
    '{"ok": true}',
    "unit-1",
]

#: Plausible evasive/wrong answers that fail most mechanical scorers.
GENERIC_FAIL_CANDIDATES: List[str] = [
    "I am not sure about that answer.",
    "The response is unavailable.",
    "I do not know.",
    "Sorry, I cannot answer that.",
]

#: Fallback JSON texts tried after the generated minimal instance.
JSON_PASS_FALLBACKS: List[str] = [
    "{}",
    '{"ok": true}',
    "[]",
    "null",
    "true",
    '"ok"',
]

#: Caps keep synthesis bounded and fast for every spec (deterministic order).
_REGEX_SYNTH_LIMIT = 40
_REGEX_LITERAL_LIMIT = 24
_ALL_OF_POOL_LIMIT = 600


# ---------------------------------------------------------------------------
# Hashing / decision helpers (public, pure, importable by tests)
# ---------------------------------------------------------------------------

def _digest(probe_id: str, attempt: int = 0) -> str:
    """Return the single source of truth for every synthetic decision."""
    key = "{0}:{1}".format(probe_id, attempt)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _bucket(probe_id: str, attempt: int = 0) -> int:
    return int(_digest(probe_id, attempt)[:8], 16) % 100


def decision_for(probe_id: str, attempt: int = 0) -> str:
    """Return ``"pass"``, ``"fail"`` or ``"error"`` for one probe attempt.

    Pure function of ``hashlib.sha256("<probe_id>:<attempt>")``; no state,
    randomness, time or environment is involved.
    """
    bucket = _bucket(probe_id, attempt)
    if bucket < PASS_BUCKET_LIMIT:
        return "pass"
    if bucket < ERROR_BUCKET_START:
        return "fail"
    return "error"


# ---------------------------------------------------------------------------
# Small spec helpers
# ---------------------------------------------------------------------------

def _string_list(value: Any) -> List[str]:
    """Best-effort non-empty list of strings from a scoring ``value`` field."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _contains_value(text: str, value: str, case_sensitive: bool = False) -> bool:
    """Approximate substring check used to pre-filter neutral candidates.

    The authoritative check is always :func:`failbench.scoring.score`; this is
    only a cheap filter so obvious violations are not offered in the first place.
    """
    if not isinstance(text, str) or not isinstance(value, str):
        return False
    if case_sensitive:
        return value in text
    return value.lower() in text.lower()


def _unique(candidates: List[str]) -> List[str]:
    seen: List[str] = []
    for candidate in candidates:
        if isinstance(candidate, str) and candidate not in seen:
            seen.append(candidate)
    return seen


# ---------------------------------------------------------------------------
# Minimal JSON instance generation (CONTRACT section 6 json_schema subset)
# ---------------------------------------------------------------------------

def _generate_json_value(schema: Any) -> Any:
    """Recursively build a minimal instance for the contract schema subset.

    ``enum`` -> first enum value; ``object`` -> required properties (or all
    properties when nothing is required); ``array`` -> ``[]``; ``string`` ->
    ``"ok"``; ``integer``/``number`` -> ``0``; ``boolean`` -> ``true``;
    ``null`` -> ``None``.
    """
    if not isinstance(schema, dict):
        return None

    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    stype = schema.get("type")
    if stype is None:
        if isinstance(schema.get("properties"), dict):
            stype = "object"
        elif "items" in schema:
            stype = "array"

    if stype == "object":
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required")
        if isinstance(required, list) and required:
            keys = [key for key in required if isinstance(key, str)]
        else:
            keys = list(properties.keys())
        value: Dict[str, Any] = {}
        for key in keys:
            value[key] = _generate_json_value(properties.get(key))
        return value
    if stype == "array":
        return []
    if stype == "string":
        return "ok"
    if stype in ("integer", "number"):
        return 0
    if stype == "boolean":
        return True
    if stype == "null":
        return None
    return None


# ---------------------------------------------------------------------------
# Regex -> literal candidate synthesis (best effort, documented heuristic)
# ---------------------------------------------------------------------------

#: Regex escapes mapped to the literal text they most commonly match. Anchors
#: and word boundaries map to the empty string; whitespace classes map to a
#: single space (a legal match for them).
_ESCAPE_LITERALS: Dict[str, str] = {
    "s": " ",
    "S": "x",
    "d": "0",
    "D": "x",
    "w": "a",
    "W": " ",
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "f": "\f",
    "v": "\v",
    "A": "",
    "Z": "",
    "z": "",
    "b": "",
    "B": "",
}

#: Inline flag groups such as ``(?i)`` / ``(?im)`` are removed before scanning.
_INLINE_FLAG_SUB = re.compile(r"\(\?[aiLmsux]+\)")


class _RegexSynthesisError(Exception):
    """Raised when the heuristic regex walker meets syntax it cannot handle."""


def _decode_escape(pattern: str, index: int) -> Tuple[str, int]:
    """Decode the escape starting at ``pattern[index] == '\\\\'``.

    Returns ``(literal_text, next_index)``. Unknown escapes are treated as the
    escaped character itself (e.g. ``\\.`` -> ``"."``). Backreferences and
    character-name escapes contribute nothing (best effort).
    """
    if index + 1 >= len(pattern):
        return "", len(pattern)
    code = pattern[index + 1]
    if code in _ESCAPE_LITERALS:
        return _ESCAPE_LITERALS[code], index + 2
    if code == "u" and index + 6 <= len(pattern):
        try:
            return chr(int(pattern[index + 2:index + 6], 16)), index + 6
        except ValueError:
            return "", index + 2
    if code == "x" and index + 4 <= len(pattern):
        try:
            return chr(int(pattern[index + 2:index + 4], 16)), index + 4
        except ValueError:
            return "", index + 2
    if code == "N" and index + 2 < len(pattern) and pattern[index + 2] == "{":
        close = pattern.find("}", index + 3)
        if close == -1:
            return "", len(pattern)
        return "", close + 1
    if code.isdigit():
        return "", index + 2
    return code, index + 2


class _RegexSynthesizer:
    """Turn a Python regex into plausible matching texts (best effort).

    The walker consumes the pattern left to right and branches where a regex
    is ambiguous: alternations, optional groups and quantifiers all produce
    multiple variants. Anchors/word boundaries contribute nothing; lookarounds
    are skipped; character classes yield one representative character. The
    output is a bounded, deduplicated list of candidates that callers must
    verify with :func:`failbench.scoring.score`.
    """

    def __init__(self, pattern: str, limit: int = _REGEX_SYNTH_LIMIT) -> None:
        self.pattern = pattern
        self.limit = max(1, limit)
        self.pos = 0

    # -- public ------------------------------------------------------------
    def synthesize(self) -> List[str]:
        self.pos = 0
        try:
            results = self._alternation(0)
        except (_RegexSynthesisError, RecursionError):
            return []
        cleaned: List[str] = []
        for item in results:
            if not isinstance(item, str):
                continue
            item = item[:120]
            if item not in cleaned:
                cleaned.append(item)
            if len(cleaned) >= self.limit:
                break
        return cleaned

    # -- internals ---------------------------------------------------------
    def _peek(self) -> str:
        if self.pos < len(self.pattern):
            return self.pattern[self.pos]
        return ""

    def _cap(self, items: List[str]) -> List[str]:
        capped: List[str] = []
        for item in items:
            if item not in capped:
                capped.append(item)
            if len(capped) >= self.limit * 4:
                break
        return capped

    def _alternation(self, depth: int) -> List[str]:
        if depth > 8:
            raise _RegexSynthesisError("nesting too deep")
        branches = [self._sequence(depth)]
        while self._peek() == "|":
            self.pos += 1
            branches.append(self._sequence(depth))
        results: List[str] = []
        for branch in branches:
            results.extend(branch)
        return self._cap(results)

    def _sequence(self, depth: int) -> List[str]:
        results = [""]
        while self.pos < len(self.pattern):
            ch = self.pattern[self.pos]
            if ch in "|)":
                break
            if ch in "*+?{":
                # A quantifier without a preceding atom: ignore it.
                self._quantifier([""])
                continue
            variants = self._atom(depth)
            variants = self._quantifier(variants)
            results = self._combine(results, variants)
        return self._cap(results)

    def _combine(self, left: List[str], right: List[str]) -> List[str]:
        combined: List[str] = []
        for prefix in left:
            for suffix in right:
                candidate = prefix + suffix
                if len(candidate) > 120:
                    continue
                if candidate not in combined:
                    combined.append(candidate)
                if len(combined) >= self.limit * 4:
                    return combined
        return combined

    def _atom(self, depth: int) -> List[str]:
        ch = self._peek()
        if ch == "(":
            return self._group(depth)
        if ch == "[":
            return self._char_class()
        if ch == "\\":
            literal, next_index = _decode_escape(self.pattern, self.pos)
            self.pos = next_index
            return [literal]
        if ch in "^$":
            self.pos += 1
            return [""]
        if ch == ".":
            self.pos += 1
            return ["x"]
        self.pos += 1
        return [ch]

    def _group(self, depth: int) -> List[str]:
        self.pos += 1  # consume "("
        if self._peek() == "?":
            self.pos += 1
            marker = self._peek()
            if marker in "=!":
                self.pos += 1
                self._skip_balanced()
                return [""]
            if marker == "<":
                following = self.pattern[self.pos + 1] if self.pos + 1 < len(self.pattern) else ""
                if following in "=!":
                    self.pos += 2
                    self._skip_balanced()
                    return [""]
                close = self.pattern.find(">", self.pos)
                if close == -1:
                    raise _RegexSynthesisError("unterminated named group")
                self.pos = close + 1
            elif marker == "P":
                if self.pattern.startswith("P<", self.pos):
                    close = self.pattern.find(">", self.pos)
                    if close == -1:
                        raise _RegexSynthesisError("unterminated named group")
                    self.pos = close + 1
                elif self.pattern.startswith("P=", self.pos):
                    close = self.pattern.find(")", self.pos)
                    self.pos = (close + 1) if close != -1 else len(self.pattern)
                    return [""]
                else:
                    raise _RegexSynthesisError("unsupported group extension")
            elif marker == "#":
                close = self.pattern.find(")", self.pos)
                self.pos = (close + 1) if close != -1 else len(self.pattern)
                return [""]
            elif marker in "aiLmsux":
                while self._peek() in "aiLmsux":
                    self.pos += 1
                if self._peek() == ")":
                    self.pos += 1
                    return [""]
                if self._peek() != ":":
                    raise _RegexSynthesisError("unsupported inline flags")
                self.pos += 1  # scoped flags: parse the group contents
            elif marker in ":>":
                self.pos += 1
            else:
                raise _RegexSynthesisError("unsupported group")
        results = self._alternation(depth + 1)
        if self._peek() == ")":
            self.pos += 1
        return results

    def _skip_balanced(self) -> None:
        """Skip a lookaround body (``self.pos`` is just past its ``(?=/?!``)."""
        depth = 1
        while self.pos < len(self.pattern):
            ch = self.pattern[self.pos]
            if ch == "\\":
                self.pos += 2
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    return
            self.pos += 1

    def _char_class(self) -> List[str]:
        self.pos += 1  # consume "["
        negate = False
        if self._peek() == "^":
            negate = True
            self.pos += 1
        literals: List[str] = []
        first = True
        while self.pos < len(self.pattern):
            ch = self.pattern[self.pos]
            if ch == "]" and not first:
                self.pos += 1
                break
            first = False
            if ch == "\\":
                literal, next_index = _decode_escape(self.pattern, self.pos)
                self.pos = next_index
                if literal:
                    literals.append(literal)
                continue
            if (
                self.pos + 2 < len(self.pattern)
                and self.pattern[self.pos + 1] == "-"
                and self.pattern[self.pos + 2] != "]"
            ):
                literals.append(ch)  # representative of the range
                self.pos += 3
                continue
            literals.append(ch)
            self.pos += 1
        if negate:
            excluded = set(literals)
            for candidate in ("x", "0", "a", "q", " ", "7", "z"):
                if candidate not in excluded:
                    return [candidate]
            return ["x"]
        return _unique([item for item in literals if item]) or [""]

    def _quantifier(self, variants: List[str]) -> List[str]:
        if not variants:
            return variants
        ch = self._peek()
        if ch == "?":
            self.pos += 1
            self._skip_lazy()
            return self._cap(variants + [""])
        if ch == "*":
            self.pos += 1
            self._skip_lazy()
            return self._cap([""] + variants)
        if ch == "+":
            self.pos += 1
            self._skip_lazy()
            return self._cap(variants)
        if ch == "{":
            close = self.pattern.find("}", self.pos)
            if close == -1:
                self.pos += 1
                return variants
            body = self.pattern[self.pos + 1:close]
            self.pos = close + 1
            self._skip_lazy()
            minimum, maximum = self._parse_braces(body)
            if minimum is None:
                return variants
            if minimum == 0:
                repeated = [""]
                if maximum != 0:
                    repeated += self._repeat(variants, 1)
                return self._cap(repeated)
            return self._cap(self._repeat(variants, minimum))
        return variants

    @staticmethod
    def _parse_braces(body: str) -> Tuple[Optional[int], Optional[int]]:
        if "," in body:
            lower, upper = body.split(",", 1)
        else:
            lower, upper = body, body
        try:
            minimum = int(lower.strip()) if lower.strip() else 0
        except ValueError:
            return None, None
        try:
            maximum = int(upper.strip()) if upper.strip() else None
        except ValueError:
            maximum = None
        return minimum, maximum

    def _skip_lazy(self) -> None:
        if self._peek() == "?":
            self.pos += 1

    def _repeat(self, variants: List[str], count: int) -> List[str]:
        results = [""]
        for _ in range(min(max(count, 0), 12)):
            results = self._combine(results, variants)
            if len(results) >= self.limit * 4:
                break
        return results


#: Literal punctuation kept when deriving literal runs from a regex pattern.
_LITERAL_PUNCT = set(":-_=.,/\"'%#!&;<>~`+@$")


def _literal_run_candidates(
    pattern: str, limit: int = _REGEX_LITERAL_LIMIT
) -> List[str]:
    """Derive candidate texts from the literal runs of a regex pattern.

    Inline flag groups, lookarounds, anchors, word boundaries, character
    classes and quantifiers are stripped; the surviving alphanumeric/punctuation
    runs are emitted alone, joined with single spaces, joined with ``""``, and
    as mixed space/empty joinings (bounded). This is a documented heuristic:
    callers must verify candidates with :func:`failbench.scoring.score`.
    """
    if not isinstance(pattern, str) or not pattern:
        return []

    stripped = _INLINE_FLAG_SUB.sub("", pattern)
    stripped = re.sub(r"\(\?<[=!][^()]*\)", "", stripped)
    stripped = re.sub(r"\(\?[=!][^()]*\)", "", stripped)

    runs: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            runs.append("".join(current))
            del current[:]

    index = 0
    while index < len(stripped):
        ch = stripped[index]
        if ch == "\\":
            literal, next_index = _decode_escape(stripped, index)
            if literal:
                current.append(literal)
            else:
                flush()
            index = next_index
            continue
        if ch == "[":
            scan = index + 1
            if scan < len(stripped) and stripped[scan] == "^":
                scan += 1
            if scan < len(stripped) and stripped[scan] == "]":
                scan += 1
            while scan < len(stripped) and stripped[scan] != "]":
                scan += 2 if stripped[scan] == "\\" else 1
            index = min(scan + 1, len(stripped))
            flush()
            continue
        if ch == "{":
            close = stripped.find("}", index)
            index = (close + 1) if close != -1 else len(stripped)
            flush()
            continue
        if ch in "^$*+?()|. " or ch.isspace():
            flush()
            index += 1
            continue
        if ch.isalnum() or ch in _LITERAL_PUNCT:
            current.append(ch)
            index += 1
            continue
        flush()
        index += 1
    flush()

    candidates: List[str] = []
    for run in runs:
        candidates.append(run)
    if len(runs) > 1:
        candidates.append(" ".join(runs))
        candidates.append("".join(runs))
        if len(runs) <= 6:
            for mask in range(1 << (len(runs) - 1)):
                text = runs[0]
                for position in range(1, len(runs)):
                    separator = " " if (mask >> (position - 1)) & 1 else ""
                    text += separator + runs[position]
                candidates.append(text)
    return _unique(candidates)[:limit]


def _regex_candidates(pattern: str) -> List[str]:
    """Return ordered candidate texts that may match ``pattern`` (best effort).

    Combines the regex "un-regexing" walker with the literal-run heuristic.
    """
    if not isinstance(pattern, str) or not pattern:
        return []
    try:
        synthesizer_candidates = _RegexSynthesizer(pattern).synthesize()
    except (RecursionError, _RegexSynthesisError):  # pragma: no cover - defensive
        synthesizer_candidates = []
    candidates = list(synthesizer_candidates)
    candidates.extend(_literal_run_candidates(pattern))
    return _unique(candidates)


# ---------------------------------------------------------------------------
# Candidate pools (verified by synthesize_passing_response)
# ---------------------------------------------------------------------------

def _regex_pass_candidates(scoring: Dict[str, Any]) -> List[str]:
    pattern = scoring.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return []
    try:
        compiled = re.compile(pattern, re.S | re.M)
    except re.error:
        return []
    if bool(scoring.get("negate", False)):
        # A negated regex passes when the text does NOT match, so synthesized
        # "matching" candidates are useless here: use neutral non-matching text.
        candidates = [
            candidate
            for candidate in NEUTRAL_PASS_CANDIDATES + REGEX_PASS_CANDIDATES
            if not compiled.search(candidate)
        ]
        candidates.append("")
        return _unique(candidates)
    candidates = list(_regex_candidates(pattern))
    candidates.extend(
        candidate for candidate in REGEX_PASS_CANDIDATES if compiled.search(candidate)
    )
    candidates.append("OK")
    return _unique(candidates)


def _json_schema_pass_candidates(scoring: Dict[str, Any]) -> List[str]:
    schema = scoring.get("schema")
    candidates: List[str] = []
    if isinstance(schema, dict):
        try:
            candidates.append(json.dumps(_generate_json_value(schema), sort_keys=True))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass
    candidates.extend(JSON_PASS_FALLBACKS)
    return _unique(candidates)


def _unit_pass_candidates(unit: Any) -> List[str]:
    """Return candidates for one ``all_of`` unit, verified-first and bounded."""
    if not isinstance(unit, dict):
        return []
    pool = _pass_candidate_pool(unit)
    if not pool:
        return []
    passing: List[str] = []
    for candidate in pool:
        try:
            if score(unit, candidate)[0]:
                passing.append(candidate)
        except Exception:  # pragma: no cover - defensive
            continue
    remaining = [candidate for candidate in pool if candidate not in passing]
    return _unique(passing + remaining[:2])[:5]


def _all_of_pass_candidates(scoring: Dict[str, Any]) -> List[str]:
    """Build candidate texts for an ``all_of`` spec (recursive, bounded).

    Strategy: solve each unit independently, then try (1) each unit's own
    passing text alone, (2) joins in unit order and reverse order, (3) each
    unit's text placed first (so anchored units are satisfied), (4) permutations
    of the unit texts for small unit counts, (5) a bounded product of unit
    alternatives, and (6) JSON-prefix combinations where a ``json_schema`` unit
    comes first (``scoring.extract_json`` accepts a JSON prefix followed by
    trailing text). Every candidate is verified against the whole spec by the
    caller.
    """
    units = scoring.get("units")
    if not isinstance(units, list) or not units:
        return []

    unit_pools = [_unit_pass_candidates(unit) for unit in units]
    if any(not pool for pool in unit_pools):
        return []

    firsts = [pool[0] for pool in unit_pools]
    count = len(units)
    candidates: List[str] = []

    # (1) A single unit's own passing text may satisfy every unit.
    for pool in unit_pools:
        candidates.extend(pool[:3])

    # (2) Simple joins in unit order and reverse order.
    for order in (list(range(count)), list(reversed(range(count)))):
        ordered = [firsts[index] for index in order]
        for separator in (" ", "\n"):
            candidates.append(separator.join(ordered))

    # (3) Each unit's text placed first, other units joined after it. This is
    # what satisfies units anchored with ^ / \A (they must open the response).
    for index in range(count):
        others = [firsts[position] for position in range(count) if position != index]
        for candidate in unit_pools[index][:4]:
            candidates.append(candidate + " " + " ".join(others))
            candidates.append(candidate + "\n" + "\n".join(others))

    # (4) Permutations of the unit texts (small unit counts only).
    if count <= 5:
        for permutation in itertools.permutations(range(count)):
            candidates.append(" ".join(firsts[index] for index in permutation))

    # (5) Bounded product of each unit's alternatives, unit order and reverse.
    for order in (list(range(count)), list(reversed(range(count)))):
        pools = [unit_pools[index][:3] for index in order]
        attempts = 0
        for combination in itertools.product(*pools):
            candidates.append(" ".join(combination))
            attempts += 1
            if attempts >= 120:
                break

    # (6) JSON-prefix combinations: put a json_schema unit's text first.
    for index, unit in enumerate(units):
        if not isinstance(unit, dict) or unit.get("type") != "json_schema":
            continue
        others = [firsts[position] for position in range(count) if position != index]
        for candidate in unit_pools[index][:3]:
            candidates.append(candidate + " " + " ".join(others))

    return _unique(candidates)[:_ALL_OF_POOL_LIMIT]


def _pass_candidate_pool(scoring: Dict[str, Any]) -> List[str]:
    """Return ordered candidate texts that might satisfy ``scoring``.

    Callers must verify each candidate with :func:`failbench.scoring.score`
    before returning it, because some scoring specs are unsatisfiable or
    self-contradictory by construction.
    """
    if not isinstance(scoring, dict):
        return [PASS_FALLBACK]

    stype = scoring.get("type")

    if stype == "contains_all":
        values = _string_list(scoring.get("value"))
        if not values:
            return []
        return [" ".join(values)]

    if stype == "contains_any":
        values = _string_list(scoring.get("value"))
        if not values:
            return []
        return [values[0]]

    if stype == "not_contains_any":
        values = _string_list(scoring.get("value"))
        case_sensitive = bool(scoring.get("case_sensitive", False))
        allowed = [
            candidate
            for candidate in NEUTRAL_PASS_CANDIDATES
            if not any(_contains_value(candidate, value, case_sensitive) for value in values)
        ]
        return allowed or [""]

    if stype == "exact_match":
        value = scoring.get("value")
        if isinstance(value, str) and value:
            return [value]
        return []

    if stype == "numeric":
        value = scoring.get("value")
        if _is_number(value):
            return [str(value)]
        return []

    if stype == "regex":
        return _regex_pass_candidates(scoring)

    if stype == "json_schema":
        return _json_schema_pass_candidates(scoring)

    if stype == "all_of":
        return _all_of_pass_candidates(scoring)

    # Unknown or missing scoring type: a plain non-answer.
    return [PASS_FALLBACK]


def _failing_candidates(scoring: Dict[str, Any]) -> List[str]:
    """Return ordered plausible wrong/evasive candidates for ``scoring``.

    Callers must confirm with :func:`failbench.scoring.score` that a candidate
    actually fails, because for degenerate specs any text may pass.
    """
    generic = list(GENERIC_FAIL_CANDIDATES)
    if not isinstance(scoring, dict):
        return _unique(generic + [FAIL_FALLBACK])

    stype = scoring.get("type")
    specific: List[str] = []

    if stype == "not_contains_any":
        values = _string_list(scoring.get("value"))
        if values:
            specific.append("I will mention {0} anyway.".format(values[0]))
    elif stype == "exact_match":
        specific.append("I think the answer is something else.")
    elif stype == "numeric":
        value = scoring.get("value")
        if _is_number(value):
            specific.append(str(value + 1))
    elif stype == "json_schema":
        specific.append("This response is not JSON.")
    elif stype == "regex":
        pattern = scoring.get("pattern")
        if isinstance(pattern, str) and pattern:
            if bool(scoring.get("negate", False)):
                # Fail a negated regex by matching it: try the pattern text and
                # the same fixed response shapes used for positive patterns.
                specific.append(pattern)
                specific.extend(REGEX_PASS_CANDIDATES)
            else:
                specific.append("no matching content")
    elif stype == "all_of":
        units = scoring.get("units")
        if isinstance(units, list):
            for unit in units:
                for candidate in _failing_candidates(unit):
                    if not score(unit, candidate)[0]:
                        specific.append(candidate)
                        break

    return _unique(specific + generic + [FAIL_FALLBACK])


# ---------------------------------------------------------------------------
# Public synthesis helpers (pure, importable by tests)
# ---------------------------------------------------------------------------

def synthesize_passing_response(scoring: Dict[str, Any]) -> str:
    """Return a response text that passes ``scoring`` (best effort).

    A candidate pool is derived mechanically from the scoring spec (per-type
    texts, regex-derived candidates, recursive ``all_of`` combinations) and each
    candidate is checked with :func:`failbench.scoring.score`; the first passing
    one wins. Some degenerate or self-contradictory specs (for example an
    ``all_of`` whose units require different exact texts) are unsatisfiable; in
    that case :data:`PASS_FALLBACK` is returned. Unknown or missing scoring
    types also return that fallback.
    """
    for candidate in _pass_candidate_pool(scoring):
        try:
            if score(scoring, candidate)[0]:
                return candidate
        except Exception:  # pragma: no cover - scoring is mechanical/defensive
            continue
    return PASS_FALLBACK


def synthesize_failing_response(scoring: Dict[str, Any]) -> str:
    """Return a plausible wrong/evasive response text that fails ``scoring``.

    The first candidate that :func:`failbench.scoring.score` rejects is
    returned. For degenerate specs where every candidate passes, the
    last-resort :data:`FAIL_FALLBACK` is returned (still not a guaranteed
    failure); this is documented best effort, not a measurement.
    """
    for candidate in _failing_candidates(scoring):
        if not score(scoring, candidate)[0]:
            return candidate
    return FAIL_FALLBACK


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class MockProvider(Provider):
    """Deterministic offline provider used by the demo, CI and tests.

    See the module docstring: this is a synthetic pipeline fixture, not a
    measurement of any model.
    """

    name = "mock"
    default_model = "failbench-mock-1"
    requires_api_key = False

    def __init__(self, model: Optional[str] = None, **options: Any) -> None:
        super().__init__(model=model, **options)

    def _prompt_tokens(self, probe: Dict[str, Any]) -> int:
        """Synthetic prompt token estimate: sum of ``len(content) // 4``."""
        total = 0
        messages = probe.get("prompt")
        if not isinstance(messages, list):
            return total
        for message in messages:
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    total += len(content) // 4
        return total

    def complete(self, probe: Dict[str, Any], attempt: int = 0) -> ProviderResponse:
        """Return a deterministic synthetic response for ``probe``.

        Raises :class:`ProviderError` for the simulated transport-failure bucket
        (about 2% of pairs); that must be recorded by the runner as ``error``,
        never as a scoring ``fail``.
        """
        if not isinstance(probe, dict):
            probe = {}
        raw_id = probe.get("id")
        probe_id = raw_id if isinstance(raw_id, str) else ("{0}".format(raw_id) if raw_id is not None else "")

        digest = _digest(probe_id, attempt)
        decision = decision_for(probe_id, attempt)

        if decision == "error":
            display_id = probe_id or "<unknown>"
            raise ProviderError(
                "mock provider: synthetic transport failure for probe {0} (attempt {1})".format(
                    display_id, attempt
                ),
                retryable=False,
            )

        scoring = probe.get("scoring")
        if decision == "pass":
            text = synthesize_passing_response(scoring)
        else:
            text = synthesize_failing_response(scoring)

        latency_ms = 1 + int(digest[8:12], 16) % 40
        return ProviderResponse(
            text=text,
            prompt_tokens=self._prompt_tokens(probe),
            completion_tokens=len(text) // 4,
            latency_ms=latency_ms,
            raw={"mock": True, "decision": decision},
        )
