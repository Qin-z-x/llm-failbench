"""OpenAI-compatible ``/chat/completions`` provider for FailBench (stdlib only).

This adapter works with any endpoint that speaks the OpenAI Chat Completions
wire format (OpenAI and compatibles such as DeepSeek, Groq, Together, Mistral,
Ollama, vLLM or LiteLLM). It uses the standard library only (``urllib`` /
``json``) so the project keeps its zero-third-party-dependency promise.

Operational rules (``docs/CONTRACT.md`` sections 1 and 8):

* One request is bounded by ``timeout`` seconds; bounded exponential-backoff
  retries are provided by the inherited
  :meth:`~failbench.providers.base.Provider.complete_with_retry`. Only
  transient failures (timeouts, transport errors and HTTP 408/409/429/5xx)
  are marked retryable.
* The API key is kept in a private attribute. It is never logged, never
  stored in :class:`~failbench.providers.base.ProviderResponse` artifacts and
  never included in exception messages or ``repr`` output; :meth:`redact`
  additionally scrubs ``sk-...`` shaped tokens from arbitrary strings.
* The module performs no network I/O at import time. Tests exercise it
  against a localhost fake HTTP server only.
"""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .base import (
    Provider,
    ProviderConfigError,
    ProviderError,
    ProviderResponse,
    probe_messages,
    probe_sampling_params,
)

__all__ = ["OpenAICompatibleProvider"]

#: HTTP status codes worth retrying (transport/transient server conditions).
RETRYABLE_STATUS_CODES = frozenset((408, 409, 429, 500, 502, 503, 504))

#: Replacement text used whenever a secret must be hidden.
REDACTED = "***REDACTED***"

#: Catch OpenAI-style key tokens in arbitrary text (defense in depth).
_SECRET_TOKEN_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")

_DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
_DEFAULT_TIMEOUT = 30.0
_ENDPOINT_SUFFIX = "/chat/completions"
_MAX_ERROR_BODY_CHARS = 200


def _status_of(response: Any) -> int:
    """Best-effort integer HTTP status from a ``urlopen`` response object."""
    status = getattr(response, "status", None)
    if isinstance(status, int) and status > 0:
        return status
    try:
        return int(response.getcode())
    except (AttributeError, TypeError, ValueError):
        return 0


def _token_count(usage: Any, key: str) -> int:
    """Read one non-negative token count from an OpenAI ``usage`` object."""
    try:
        return max(0, int(usage.get(key) or 0))
    except (AttributeError, TypeError, ValueError):
        return 0


def _content_text(content: Any) -> Optional[str]:
    """Normalize assistant ``message.content`` to text, or ``None`` if absent.

    Chat Completions returns either a plain string or a list of content parts
    such as ``{"type": "text", "text": "..."}``; text parts are concatenated in
    order.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: List[str] = []
        for part in content:
            if isinstance(part, dict):
                part_text = part.get("text")
                if isinstance(part_text, str):
                    chunks.append(part_text)
            elif isinstance(part, str):
                chunks.append(part)
        return "".join(chunks)
    return None


class OpenAICompatibleProvider(Provider):
    """Provider for any OpenAI-compatible ``/chat/completions`` endpoint."""

    name = "openai"
    default_model = "gpt-4o-mini"
    requires_api_key = True

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_env: str = _DEFAULT_API_KEY_ENV,
        model: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
        retries: int = 2,
        retry_backoff: float = 0.2,
        **options: Any,
    ) -> None:
        if (
            not isinstance(base_url, str)
            or not base_url
            or not base_url.startswith(("http://", "https://"))
        ):
            raise ProviderConfigError(
                "base_url is required and must start with http:// or https://"
            )

        env_name = str(api_key_env or _DEFAULT_API_KEY_ENV)
        key: Optional[str] = None
        if api_key:
            key = str(api_key)
        else:
            env_value = os.environ.get(env_name)
            if env_value:
                key = str(env_value)
        if not key:
            # The env var *name* is safe to mention; a key value never is.
            raise ProviderConfigError(
                "no API key found: set environment variable {0} or pass "
                "--api-key-env to a populated variable".format(env_name)
            )

        if timeout is None:
            timeout = _DEFAULT_TIMEOUT
        try:
            timeout_value = float(timeout)
        except (TypeError, ValueError):
            raise ProviderConfigError(
                "timeout must be a number of seconds"
            ) from None

        self._api_key: str = key
        normalized = base_url.rstrip("/")
        self.base_url: str = normalized
        if normalized.endswith(_ENDPOINT_SUFFIX):
            self.endpoint: str = normalized
        else:
            self.endpoint = normalized + _ENDPOINT_SUFFIX
        self.timeout: float = max(0.01, timeout_value)
        super().__init__(
            model=model,
            retries=retries,
            retry_backoff=retry_backoff,
            timeout=self.timeout,
            **options,
        )

    # -- Provider interface ------------------------------------------------
    def complete(self, probe: Dict[str, Any], attempt: int = 0) -> ProviderResponse:
        """POST one probe prompt to :attr:`endpoint` and normalize the reply.

        Network/transport/API failures raise :class:`ProviderError` (the runner
        records them as ``status: "error"``, never as a scoring failure).
        Retries are *not* handled here; :meth:`complete_with_retry` does that.
        """
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": probe_messages(probe),
            "stream": False,
        }
        sampling = probe_sampling_params(probe)
        for key in ("temperature", "max_tokens", "top_p"):
            if key in sampling and sampling[key] is not None:
                body[key] = sampling[key]

        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer " + self._api_key,
            },
            method="POST",
        )

        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = _status_of(response)
                raw_body = response.read()
        except urllib.error.HTTPError as exc:
            status_code = int(getattr(exc, "code", 0) or 0)
            try:  # read/ignore the error body; it is never surfaced
                exc.read()
            except Exception:  # pragma: no cover - defensive cleanup
                pass
            try:
                exc.close()
            except Exception:  # pragma: no cover - defensive cleanup
                pass
            raise ProviderError(
                self.redact(
                    "HTTP {0} from provider endpoint {1}".format(
                        status_code, self.endpoint
                    )
                ),
                retryable=status_code in RETRYABLE_STATUS_CODES,
                status_code=status_code,
            ) from None
        except (socket.timeout, TimeoutError):
            raise ProviderError(
                "provider request timed out after {0}s".format(self.timeout),
                retryable=True,
            ) from None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise ProviderError(
                self.redact("could not reach provider endpoint: {0}".format(reason)),
                retryable=True,
            ) from None
        except OSError as exc:
            raise ProviderError(
                self.redact("provider I/O error: {0}".format(exc)),
                retryable=True,
            ) from None

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            excerpt = raw_body.decode("utf-8", "replace")[:_MAX_ERROR_BODY_CHARS]
            raise ProviderError(
                self.redact(
                    "malformed JSON response from provider endpoint "
                    "(HTTP {0}): {1}".format(status, excerpt)
                ),
                retryable=False,
            ) from None

        if not isinstance(payload, dict):
            raise ProviderError("response had no message content", retryable=False)
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("response had no message content", retryable=False)
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ProviderError("response had no message content", retryable=False)
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ProviderError("response had no message content", retryable=False)
        text = _content_text(message.get("content"))
        if text is None:
            raise ProviderError("response had no message content", retryable=False)

        usage = payload.get("usage")
        latency_ms = int((time.monotonic() - started) * 1000)
        return ProviderResponse(
            text=text,
            prompt_tokens=_token_count(usage, "prompt_tokens"),
            completion_tokens=_token_count(usage, "completion_tokens"),
            latency_ms=latency_ms,
            raw={
                "status": status,
                "id": payload.get("id"),
                "model": payload.get("model"),
            },
        )

    # -- secret hygiene ----------------------------------------------------
    def redact(self, message: Any) -> str:
        """Return ``message`` with the API key and ``sk-...`` tokens masked."""
        text = str(message)
        key = getattr(self, "_api_key", "")
        if key:
            text = text.replace(key, REDACTED)
        return _SECRET_TOKEN_RE.sub(REDACTED, text)

    def __repr__(self) -> str:
        return (
            "<OpenAICompatibleProvider model={0!r} base_url={1!r} "
            "api_key={2}>".format(self.model, self.base_url, REDACTED)
        )
