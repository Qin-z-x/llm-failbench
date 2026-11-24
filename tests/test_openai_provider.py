"""Offline tests for the OpenAI-compatible provider (stdlib ``unittest`` only).

Tests that exercise HTTP talk to a local ``ThreadingHTTPServer`` bound to
127.0.0.1 on an ephemeral port. No external host, real endpoint or real API key
is contacted; the API key values below are synthetic test strings.

Run from the repository root::

    python -m unittest tests.test_openai_provider -v
"""

from __future__ import annotations

import json
import os
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple
from unittest import mock

from failbench.providers import get_provider
from failbench.providers.base import (
    ProviderConfigError,
    ProviderError,
    probe_messages,
)
from failbench.providers.openai_compatible import OpenAICompatibleProvider

from tests.support import make_probe


#: Canned successful Chat Completions payload served in "success" mode.
SUCCESS_PAYLOAD: Dict[str, Any] = {
    "id": "chatcmpl-fake-0001",
    "object": "chat.completion",
    "created": 0,
    "model": "fake-model",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Paris"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
}

#: How long "slow" mode stalls before answering, so a short client timeout fires.
SLOW_DELAY_SECONDS = 0.6

#: Probe fixture id / class shared by the tests (valid per CONTRACT section 3).
PROBE_ID = "hal_oa_01"
PROBE_CLASS = "hallucination"


def make_test_probe() -> Dict[str, Any]:
    """Return a schema-valid hallucination probe built by the shared fixture."""
    return make_probe(PROBE_ID, PROBE_CLASS)


class _FakeHandler(BaseHTTPRequestHandler):
    """Fake ``/chat/completions`` endpoint; behavior is driven by ``server.mode``."""

    server_version = "FailBenchFakeServer/1.0"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 - silence
        """Silence per-request logging so test output stays readable."""
        return

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        raw, body = self._read_json_body()
        self.server.requests.append(
            {
                "path": self.path,
                "headers": {name.lower(): value for name, value in self.headers.items()},
                "body": body,
                "raw": raw,
            }
        )
        try:
            self._respond(getattr(self.server, "mode", "success"))
        except OSError:
            # The client may already have timed out and closed its socket.
            pass

    # -- helpers -----------------------------------------------------------
    def _read_json_body(self) -> Tuple[bytes, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            body = None
        return raw, body

    def _respond(self, mode: str) -> None:
        if mode == "slow":
            time.sleep(SLOW_DELAY_SECONDS)
            self._send_json(200, SUCCESS_PAYLOAD)
            return
        if mode == "always_500":
            self._send_json(500, {"error": {"message": "internal server error"}})
            return
        if mode == "500_once":
            with self.server.state_lock:
                is_first = not self.server.failed_once
                if is_first:
                    self.server.failed_once = True
            if is_first:
                self._send_json(500, {"error": {"message": "internal server error"}})
                return
            self._send_json(200, SUCCESS_PAYLOAD)
            return
        if mode == "malformed":
            self._send_raw(200, b'{"choices": [this is not valid json')
            return
        if mode == "empty_choices":
            self._send_json(
                200,
                {
                    "id": "chatcmpl-empty",
                    "choices": [],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                },
            )
            return
        if mode == "content_parts":
            payload = json.loads(json.dumps(SUCCESS_PAYLOAD))
            payload["choices"][0]["message"]["content"] = [
                {"type": "text", "text": "Par"},
                {"type": "text", "text": "is"},
            ]
            self._send_json(200, payload)
            return
        self._send_json(200, SUCCESS_PAYLOAD)

    def _send_json(self, status: int, payload: Any) -> None:
        self._send_raw(status, json.dumps(payload).encode("utf-8"))

    def _send_raw(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _FakeServer(ThreadingHTTPServer):
    """Threaded HTTP server that records every request it receives."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: Tuple[str, int], handler_class: Any) -> None:
        super().__init__(address, handler_class)
        self.mode: str = "success"
        self.requests: List[Dict[str, Any]] = []
        self.failed_once: bool = False
        self.state_lock = threading.Lock()

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Swallow expected aborted-connection errors (timeout test)."""
        return


@contextmanager
def fake_server(mode: str = "success"):
    """Run a fake chat-completions server for the duration of the block."""
    server = _FakeServer(("127.0.0.1", 0), _FakeHandler)
    server.mode = mode
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        name="failbench-fake-openai",
        daemon=True,
    )
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)


def server_url(server: _FakeServer) -> str:
    """Return the ``http://127.0.0.1:<port>`` base URL of a running fake server."""
    host, port = server.server_address[0], int(server.server_address[1])
    return "http://{0}:{1}".format(host, port)


class OpenAICompatibleProviderTests(unittest.TestCase):
    """Behavioral tests for ``OpenAICompatibleProvider``."""

    def _provider(self, server: _FakeServer, **overrides: Any) -> OpenAICompatibleProvider:
        options: Dict[str, Any] = {
            "base_url": server_url(server),
            "api_key": "test-key",
            "model": "fake-model",
            "retries": 0,
        }
        options.update(overrides)
        return OpenAICompatibleProvider(**options)

    # -- success path ------------------------------------------------------
    def test_success_builds_contract_shaped_request(self) -> None:
        probe = make_test_probe()
        with fake_server("success") as server:
            provider = self._provider(server, base_url=server_url(server) + "/v1")
            self.assertEqual(provider.endpoint, server_url(server) + "/v1/chat/completions")
            response = provider.complete(probe)
            self.assertEqual(len(server.requests), 1)
            record = server.requests[0]

        self.assertEqual(provider.name, "openai")
        self.assertEqual(OpenAICompatibleProvider.default_model, "gpt-4o-mini")
        self.assertTrue(OpenAICompatibleProvider.requires_api_key)

        self.assertEqual(response.text, "Paris")
        self.assertEqual(response.prompt_tokens, 12)
        self.assertEqual(response.completion_tokens, 3)
        self.assertIsInstance(response.latency_ms, int)
        self.assertGreaterEqual(response.latency_ms, 0)
        self.assertEqual(
            response.raw,
            {"status": 200, "id": "chatcmpl-fake-0001", "model": "fake-model"},
        )
        self.assertNotIn("test-key", json.dumps(response.raw))

        self.assertEqual(record["path"], "/v1/chat/completions")
        body = record["body"]
        self.assertEqual(body["model"], "fake-model")
        self.assertEqual(body["messages"], probe_messages(probe))
        self.assertIs(body["stream"], False)
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["max_tokens"], 64)
        self.assertNotIn("top_p", body)
        self.assertEqual(record["headers"]["authorization"], "Bearer test-key")
        self.assertEqual(record["headers"]["content-type"], "application/json")

    def test_content_parts_are_joined(self) -> None:
        with fake_server("content_parts") as server:
            provider = self._provider(server)
            response = provider.complete(make_test_probe())
        self.assertEqual(response.text, "Paris")
        self.assertEqual(response.prompt_tokens, 12)
        self.assertEqual(response.completion_tokens, 3)

    # -- endpoint normalization --------------------------------------------
    def test_endpoint_normalization(self) -> None:
        with fake_server("success") as server:
            base = server_url(server)
            already = OpenAICompatibleProvider(
                base_url=base + "/v1/chat/completions", api_key="k", retries=0
            )
            self.assertEqual(already.endpoint, base + "/v1/chat/completions")
            already.complete(make_test_probe())

            trailing = OpenAICompatibleProvider(
                base_url=base + "/v1/", api_key="k", retries=0
            )
            self.assertEqual(trailing.base_url, base + "/v1")
            self.assertEqual(trailing.endpoint, base + "/v1/chat/completions")
            trailing.complete(make_test_probe())

            suffixed_trailing = OpenAICompatibleProvider(
                base_url=base + "/v1/chat/completions/", api_key="k", retries=0
            )
            self.assertEqual(suffixed_trailing.endpoint, base + "/v1/chat/completions")
            self.assertEqual(
                suffixed_trailing.base_url, base + "/v1/chat/completions"
            )
            self.assertEqual(
                [record["path"] for record in server.requests],
                ["/v1/chat/completions", "/v1/chat/completions"],
            )

    # -- retry behavior (inherited complete_with_retry) --------------------
    def test_retry_recovers_from_transient_500(self) -> None:
        with fake_server("500_once") as server:
            provider = self._provider(server, retries=2, retry_backoff=0)
            response = provider.complete_with_retry(make_test_probe())
            self.assertEqual(response.text, "Paris")
            self.assertEqual(len(server.requests), 2)

    def test_always_500_is_retried_then_raised(self) -> None:
        with fake_server("always_500") as server:
            provider = self._provider(server, retries=1, retry_backoff=0)
            with self.assertRaises(ProviderError) as caught:
                provider.complete_with_retry(make_test_probe())
            exception = caught.exception
            self.assertEqual(exception.status_code, 500)
            self.assertTrue(exception.retryable)
            self.assertIn("HTTP 500", str(exception))
            self.assertEqual(len(server.requests), 2)

    # -- malformed / empty responses ---------------------------------------
    def test_malformed_json_fails_without_retry(self) -> None:
        with fake_server("malformed") as server:
            provider = self._provider(server, retries=2, retry_backoff=0)
            with self.assertRaises(ProviderError) as caught:
                provider.complete_with_retry(make_test_probe())
            exception = caught.exception
            self.assertFalse(exception.retryable)
            self.assertIn("malformed JSON", str(exception))
            self.assertEqual(len(server.requests), 1)

    def test_empty_choices_raise_provider_error(self) -> None:
        with fake_server("empty_choices") as server:
            provider = self._provider(server, retries=2, retry_backoff=0)
            with self.assertRaises(ProviderError) as caught:
                provider.complete_with_retry(make_test_probe())
            self.assertIn("no message content", str(caught.exception))
            self.assertFalse(caught.exception.retryable)
            self.assertEqual(len(server.requests), 1)

    # -- timeout -----------------------------------------------------------
    def test_timeout_is_retryable_and_bounded(self) -> None:
        with fake_server("slow") as server:
            provider = self._provider(server, timeout=0.15)
            started = time.monotonic()
            with self.assertRaises(ProviderError) as caught:
                provider.complete_with_retry(make_test_probe())
            elapsed = time.monotonic() - started
            self.assertTrue(caught.exception.retryable)
            self.assertIn("timed out", str(caught.exception))
            self.assertLess(elapsed, 3.0)
            self.assertEqual(len(server.requests), 1)

    # -- configuration errors ---------------------------------------------
    def test_config_errors_are_clear(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FAILBENCH_TEST_NO_SUCH_KEY_XYZ", None)
            os.environ.pop("OPENAI_API_KEY", None)
            with self.assertRaises(ProviderConfigError) as caught:
                OpenAICompatibleProvider(
                    base_url="http://127.0.0.1:9",
                    api_key_env="FAILBENCH_TEST_NO_SUCH_KEY_XYZ",
                )
            missing_key_message = str(caught.exception)
            with self.assertRaises(ProviderConfigError) as default_caught:
                OpenAICompatibleProvider(base_url="http://127.0.0.1:9")
            default_message = str(default_caught.exception)

        self.assertIn("FAILBENCH_TEST_NO_SUCH_KEY_XYZ", missing_key_message)
        self.assertIn("no API key found", missing_key_message)
        self.assertIn("OPENAI_API_KEY", default_message)

        for bad_base_url in ("", "ftp://example", "127.0.0.1:9", None):
            with self.subTest(base_url=bad_base_url):
                with self.assertRaises(ProviderConfigError) as caught:
                    OpenAICompatibleProvider(base_url=bad_base_url, api_key="k")
                self.assertIn("base_url", str(caught.exception))

    def test_env_var_supplies_key(self) -> None:
        with mock.patch.dict(
            os.environ, {"FAILBENCH_TEST_KEY_ENV": "env-secret-key"}, clear=False
        ):
            provider = OpenAICompatibleProvider(
                base_url="http://127.0.0.1:9",
                api_key_env="FAILBENCH_TEST_KEY_ENV",
            )
            self.assertEqual(provider.redact("env-secret-key"), "***REDACTED***")
            self.assertNotIn("env-secret-key", repr(provider))

    # -- secret safety -----------------------------------------------------
    def test_secrets_never_appear_in_errors_repr_or_describe(self) -> None:
        secret = "sk-" + "secret-DO-NOT-PRINT-abcdef123456"
        with fake_server("always_500") as server:
            provider = self._provider(server, api_key=secret)
            with self.assertRaises(ProviderError) as caught:
                provider.complete(make_test_probe())
            error = caught.exception
            describe_text = json.dumps(provider.describe(), default=str)

        self.assertNotIn(secret, str(error))
        self.assertNotIn(secret, repr(error))
        self.assertNotIn(secret, repr(provider))
        self.assertIn("***REDACTED***", repr(provider))
        self.assertNotIn(secret, describe_text)
        self.assertEqual(provider.describe()["provider"], "openai")

        redacted = provider.redact("token " + secret)
        self.assertNotIn(secret, redacted)
        self.assertEqual(redacted, "token ***REDACTED***")
        self.assertEqual(
            provider.redact("sk-" + "should-be-redacted-12345678"), "***REDACTED***"
        )

    # -- provider factory --------------------------------------------------
    def test_factory_builds_provider_with_explicit_key(self) -> None:
        with fake_server("success") as server:
            provider = get_provider(
                "openai",
                base_url=server_url(server),
                api_key="factory-key",
                model="m",
            )
            self.assertIsInstance(provider, OpenAICompatibleProvider)
            self.assertEqual(provider.model, "m")
            self.assertEqual(provider.name, "openai")
            response = provider.complete(make_test_probe())
            self.assertEqual(response.text, "Paris")
            self.assertEqual(
                server.requests[0]["headers"]["authorization"], "Bearer factory-key"
            )

    def test_factory_without_key_reports_config_error(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with self.assertRaises(ProviderConfigError) as caught:
                get_provider("openai", base_url="http://127.0.0.1:9")
            self.assertIn("OPENAI_API_KEY", str(caught.exception))


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    unittest.main()
