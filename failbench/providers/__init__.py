"""FailBench provider registry (stdlib only).

Public API::

    from failbench.providers import get_provider

    provider = get_provider("mock")
    provider = get_provider("openai", base_url="https://api.openai.com/v1",
                            api_key_env="OPENAI_API_KEY", model="gpt-4o-mini")
    provider = get_provider("replay", results="results/run1")

Provider implementations are imported lazily so that each backend (and its
tests) can be developed and imported independently. See ``docs/CONTRACT.md``
section 8 for the provider contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .base import (
    Provider,
    ProviderConfigError,
    ProviderError,
    ProviderResponse,
    probe_messages,
    probe_sampling_params,
)

__all__ = [
    "Provider",
    "ProviderConfigError",
    "ProviderError",
    "ProviderResponse",
    "available_providers",
    "get_provider",
    "probe_messages",
    "probe_sampling_params",
]

#: Canonical provider names in CLI help order.
_CANONICAL: Tuple[str, ...] = ("mock", "openai", "replay")

#: Alias -> canonical name.
_ALIASES: Dict[str, str] = {
    "mock": "mock",
    "fake": "mock",
    "openai": "openai",
    "openai-compatible": "openai",
    "openai_compatible": "openai",
    "openai-compat": "openai",
    "compatible": "openai",
    "replay": "replay",
    "recorded": "replay",
}


def available_providers() -> List[str]:
    """Return the canonical provider names accepted by :func:`get_provider`."""
    return list(_CANONICAL)


def get_provider(name: str, **options: Any) -> Provider:
    """Construct a provider by name.

    ``options`` are forwarded to the provider class constructor. Raises
    :class:`ProviderConfigError` (not :class:`KeyError`) for unknown names so
    the CLI can exit with a clean usage error.
    """
    if not isinstance(name, str) or not name.strip():
        raise ProviderConfigError(
            "provider name is required; expected one of: "
            + ", ".join(_CANONICAL)
        )
    key = name.strip().lower()
    canonical = _ALIASES.get(key)
    if canonical is None:
        raise ProviderConfigError(
            "unknown provider {0!r}; expected one of: {1}".format(
                name, ", ".join(_CANONICAL)
            )
        )

    if canonical == "mock":
        from .mock import MockProvider

        return MockProvider(**options)
    if canonical == "openai":
        from .openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(**options)
    if canonical == "replay":  # pragma: no cover - defensive
        from .replay import ReplayProvider

        return ReplayProvider(**options)
    raise ProviderConfigError(  # pragma: no cover - defensive
        "unknown provider {0!r}".format(name)
    )
