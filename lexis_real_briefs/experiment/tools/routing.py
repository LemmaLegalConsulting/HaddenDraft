"""Route different pipeline stages to different models, and capture what happened.

The Gym asks one client for every stage, and the benchmark capture in
`apps.ai.benchmark_capture` pins every call to a single model. The 2x2 study
needs two models in one run -- one writing the attacks, another judging them --
so this replaces that capture with one that chooses the model per call.

How a call is attributed to a stage: `Stage.run` renders its prompt immediately
before calling the client, and the experiment runner already patches
`render_prompt`. So the prompt key is recorded there, in a thread-local, and the
client wrapper reads it. It is a seam that already exists rather than a new hook
in the Gym, and it means the Gym is unmodified.

Every call is written to disk with its prompt key, its role, the model actually
used, and the full request and response, so a later analysis can recover the
opponent's complete attack list and the judge's complete assessment list --
including the attacks the judge dropped, which never become challenge rows and
are the whole point of the "what falls out" question.
"""

import json
import threading
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from apps.ai.openai_client import OpenAICompatibleClient

# Which stage each prompt belongs to. Anything unlisted runs on the base model,
# held constant across all four cells so the 2x2 varies two factors and not ten.
ROLE_BY_PROMPT = {
    "argument_gym.opponent": "attack",
    "argument_gym.record_opponent": "attack",
    "argument_gym.authority_opponent": "attack",
    "argument_gym.judge": "judge",
    "argument_gym.correctness_judge": "judge",
}

_local = threading.local()


def note_prompt(prompt_key):
    _local.prompt_key = prompt_key


def current_prompt():
    return getattr(_local, "prompt_key", "")


def role_for(prompt_key):
    return ROLE_BY_PROMPT.get(prompt_key, "base")


class RoutedCapture:
    """Per-call model selection plus a full transcript on disk."""

    def __init__(self, directory, *, live, models, reasoning):
        self.directory = Path(directory)
        self.live = live
        self.models = models          # {"attack": ..., "judge": ..., "base": ...}
        self.reasoning = reasoning
        self.calls = []

    def __enter__(self):
        original = OpenAICompatibleClient.complete_messages
        capture = self

        def complete(client, *, messages, **kwargs):
            if not capture.live:
                raise RuntimeError("Model execution attempted in an offline run")
            prompt_key = current_prompt()
            role = role_for(prompt_key)
            model = capture.models[role]
            kwargs.update(model=model, reasoning_level=capture.reasoning, temperature=0)
            started = monotonic()
            row = {"prompt_key": prompt_key, "role": role, "model": model,
                   "messages": messages, "settings": kwargs, "status": "running"}
            capture.calls.append(row)
            path = capture.directory / f"call-{len(capture.calls):03}.json"
            path.write_text(json.dumps(row, indent=2, default=str))
            try:
                client.client = client.client.with_options(timeout=300, max_retries=1)
                raw = original(client, messages=messages, **kwargs)
                row.update(status="complete", response=raw)
                return raw
            except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
                row.update(status="failed", error_type=type(exc).__name__, error=str(exc)[:400])
                raise
            finally:
                row["elapsed_seconds"] = round(monotonic() - started, 3)
                path.write_text(json.dumps(row, indent=2, default=str))

        self.patch = patch.object(OpenAICompatibleClient, "complete_messages", complete)
        self.patch.start()
        return self

    def __exit__(self, *args):
        self.patch.stop()

    def payload_for(self, role):
        """The parsed JSON response of the last completed call in a role."""
        for row in reversed(self.calls):
            if row["role"] == role and row["status"] == "complete":
                try:
                    return json.loads(row["response"]) if isinstance(row["response"], str) \
                        else row["response"]
                except (TypeError, ValueError):
                    return None
        return None

    def payloads_for(self, role):
        """Every parsed response for a role, preserving call order."""
        payloads = []
        for row in self.calls:
            if row["role"] != role or row["status"] != "complete":
                continue
            try:
                payload = json.loads(row["response"]) if isinstance(row["response"], str) else row["response"]
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict):
                payloads.append({"prompt_key": row["prompt_key"], "payload": payload})
        return payloads

    def failures(self, role):
        """Failed calls in a role, with why."""
        return [{"prompt_key": row["prompt_key"], "model": row["model"],
                 "error_type": row.get("error_type"), "error": row.get("error", "")[:300]}
                for row in self.calls
                if row["role"] == role and row["status"] == "failed"]

    def degraded(self):
        """Whether a stage under test silently fell back to the deterministic path.

        When a model call fails, `Stage.run` returns the deterministic fallback
        and the run still reports "complete" with challenges in it. Those
        challenges did not come from the model this cell is testing, so a run
        that hit this is not a result -- it is an outage wearing a result's
        clothes. It gets recorded and excluded rather than averaged in.
        """
        problems = {role: self.failures(role) for role in ("attack", "judge")}
        problems = {role: items for role, items in problems.items() if items}
        if not problems:
            return None
        return {
            "degraded": True,
            "roles": sorted(problems),
            "reason": "a model call for a stage under test failed; the Gym fell back to "
                      "its deterministic path, so these challenges are not this cell's output",
            "failures": problems,
        }

    def summary(self):
        return [{k: v for k, v in row.items() if k not in {"messages", "response"}}
                for row in self.calls]
