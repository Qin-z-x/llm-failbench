"""Base provider interface and response types for FailBench (stdlib only).

Authoritative context: ``docs/CONTRACT.md`` section 8. A provider adapts one
model backend (deterministic mock, OpenAI-compatible HTTP endpoint, or a
recorded ``raw.jsonl`` file) to a single tiny interface used by
``failbench.runner``.

Error model (do not break this): a provider that cannot produce a response
raises :class:`ProviderError`; the runner records that attempt as
``status: "error"``. Provider/network failures must never be reported as a
scoring ``fail`` (see CONTRACT section 6), and provider exceptions, logs and
``repr`` output must never contain API keys.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _as_int(value: Any) -> int:
    """Best-effort non-negative int coercion (never raises)."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


class ProviderError(Exception):
    """A provider failed to produce a response.

    The runner records these as ``status: "error"`` so a transport/API problem
    is never misreported as a model failure. ``retryable`` tells
    :meth:`Provider.complete_with_retry` whether another attempt may succeed;
    ``status_code`` carries an HTTP status code when one exists.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = str(message)
        self.retryable = bool(retryable)
        self.status_code = status_code

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class ProviderConfigError(ProviderError):
    """Provider is misconfigured (unknown name, missing endpoint/key, ...).

    This is a usage error: the CLI reports the message and exits non-zero
    before any probe is executed.
    """


@dataclass
class ProviderResponse:
    """One completed model call.

    ``text`` is the assistant text used for mechanical scoring. Token counts and
    latency are informational (mock values are synthetic and documented as
    such). ``raw`` is provider-specific diagnostic metadata that must never
    contain credentials.
    """

    text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    raw: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.text is None:
            self.text = ""
        elif not isinstance(self.text, str):
            self.text = str(self.text)
        self.prompt_tokens = _as_int(self.prompt_tokens)
        self.completion_tokens = _as_int(self.completion_tokens)
        self.latency_ms = _as_int(self.latency_ms)


def probe_messages(probe: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return a normalized ``messages`` list from a probe record."""
    messages: List[Dict[str, str]] = []
    for message in probe.get("prompt") or []:
        if not isinstance(message, dict):
            continue
        messages.append(
            {
                "role": str(message.get("role") or "user"),
                "content": str(message.get("content") or ""),
            }
        )
    return messages


def probe_sampling_params(
    probe: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge contract defaults with the probe's ``params`` object.

    Defaults match CONTRACT section 5: ``temperature`` 0 and ``max_tokens`` 256.
    """
    params: Dict[str, Any] = {"temperature": 0, "max_tokens": 256}
    if defaults:
        params.update(defaults)
    supplied = probe.get("params")
    if isinstance(supplied, dict):
        for key in ("temperature", "max_tokens", "top_p"):
            if key in supplied and supplied[key] is not None:
                params[key] = supplied[key]
    return params


class Provider:
    """Uniform provider interface.

    Subclasses implement :meth:`complete`; :meth:`complete_with_retry` supplies
    bounded exponential backoff for providers that expose ``retries`` and
    ``retry_backoff`` options.
    """

    name: str = "base"
    default_model: str = "unknown"
    requires_api_key: bool = False

    def __init__(self, model: Optional[str] = None, **options: Any) -> None:
        self.model: str = str(model if model else self.default_model)
        self.options: Dict[str, Any] = dict(options)

    # -- interface ---------------------------------------------------------
    def complete(self, probe: Dict[str, Any], attempt: int = 0) -> ProviderResponse:
        """Return one response for ``probe``; ``attempt`` is the repeat index."""
        raise NotImplementedError("providers must implement complete()")

    # -- helpers -----------------------------------------------------------
    def get_option(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    def int_option(self, key: str, default: int = 0) -> int:
        try:
            return int(self.options.get(key, default))
        except (TypeError, ValueError):
            return default

    def float_option(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.options.get(key, default))
        except (TypeError, ValueError):
            return default

    def complete_with_retry(
        self, probe: Dict[str, Any], attempt: int = 0
    ) -> ProviderResponse:
        """Call :meth:`complete`, retrying retryable ``ProviderError`` only."""
        retries = max(0, self.int_option("retries", 0))
        backoff = max(0.0, self.float_option("retry_backoff", 0.2))
        last_error: Optional[ProviderError] = None
        for index in range(retries + 1):
            try:
                return self.complete(probe, attempt=attempt)
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable or index >= retries:
                    raise
                if backoff:
                    time.sleep(min(backoff * (2.0 ** index), 8.0))
        if last_error is not None:  # pragma: no cover - defensive
            raise last_error
        raise ProviderError("provider produced no response")  # pragma: no cover

    def describe(self) -> Dict[str, Any]:
        """Metadata recorded in ``results.json`` (never secrets)."""
        return {
            "provider": self.name,
            "model": self.model,
            "base_url": getattr(self, "base_url", None),
        }

    def redact(self, message: str) -> str:
        """Remove secrets from a message before it reaches logs/artifacts."""
        return str(message)

    def __repr__(self) -> str:
        return "<{cls} model={model!r} base_url={base!r}>".format(
            cls=type(self).__name__,
            model=self.model,
            base=getattr(self, "base_url", None),
        )
