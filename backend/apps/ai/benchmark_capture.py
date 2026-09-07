"""Capture actual model requests for private, reproducible local experiments."""
import json
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from apps.ai.openai_client import OpenAICompatibleClient


class CaptureCalls:
    def __init__(self, directory, *, live, model, reasoning):
        self.directory = Path(directory)
        self.live, self.model, self.reasoning = live, model, reasoning
        self.calls = []

    def __enter__(self):
        original = OpenAICompatibleClient.complete_messages
        capture = self

        def complete(client, *, messages, **kwargs):
            if not capture.live:
                raise RuntimeError("Model execution attempted in an offline benchmark")
            kwargs.update(model=capture.model, reasoning_level=capture.reasoning, temperature=0)
            started = monotonic()
            row = dict(messages=messages, settings=kwargs, status="running")
            capture.calls.append(row)
            path = capture.directory / f"call-{len(capture.calls):03}.json"
            path.write_text(json.dumps(row, indent=2))
            try:
                client.client = client.client.with_options(timeout=180, max_retries=0)
                raw = original(client, messages=messages, **kwargs)
                row.update(status="complete", response=raw)
                return raw
            except Exception as exc:
                row.update(status="failed", error_type=type(exc).__name__)
                raise
            finally:
                row["elapsed_seconds"] = round(monotonic() - started, 3)
                path.write_text(json.dumps(row, indent=2))

        self.patch = patch.object(OpenAICompatibleClient, "complete_messages", complete)
        self.patch.start()
        return self

    def __exit__(self, *args):
        self.patch.stop()
