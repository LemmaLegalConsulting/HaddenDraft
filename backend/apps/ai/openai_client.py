from django.conf import settings
from openai import OpenAI

from apps.sources.models import SourceConfiguration


class OpenAIBackendError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, *, api_key=None, base_url=None, model=None, client=None):
        config = SourceConfiguration.effective_settings(
            "openai",
            {
                "api_key": settings.OPENAI_API_KEY,
                "base_url": settings.OPENAI_BASE_URL,
                "model": settings.OPENAI_MODEL,
            },
        )
        self.model = model or config["model"]
        self.client = client or OpenAI(
            api_key=api_key or config["api_key"],
            base_url=base_url or config["base_url"] or None,
        )

    def complete(self, *, system, user, temperature=0.2, model=None, reasoning_level=None):
        return self.complete_messages(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            model=model,
            reasoning_level=reasoning_level,
        )

    def complete_messages(self, *, messages, temperature=0.2, model=None, reasoning_level=None):
        selected_model = model or self.model
        request = {
            "model": selected_model,
            "messages": messages,
        }
        if temperature is not None and self._supports_temperature(selected_model):
            request["temperature"] = temperature
        if reasoning_level:
            request["reasoning_effort"] = reasoning_level
        # Azure's OpenAI-compatible catalog mixes deployments with different
        # request schemas and does not expose one dependable capabilities
        # endpoint. Remove only an option the provider explicitly rejects, then
        # retry the same request. A substantive model failure still propagates.
        while True:
            try:
                response = self.client.chat.completions.create(**request)
                break
            except Exception as exc:
                if "temperature" in request and self._temperature_is_unsupported(exc):
                    request.pop("temperature")
                    continue
                if "reasoning_effort" in request and self._reasoning_is_unsupported(exc):
                    request.pop("reasoning_effort")
                    continue
                raise OpenAIBackendError(str(exc)) from exc

        message = response.choices[0].message
        return (message.content or "").strip()

    @staticmethod
    def _supports_temperature(model):
        """Return whether a model accepts a non-default temperature setting."""
        normalized_model = (model or "").strip().lower()
        return not normalized_model.startswith(("gpt-5", "o1", "o3", "o4-mini"))

    @staticmethod
    def _temperature_is_unsupported(exc):
        message = str(exc).lower()
        return "temperature" in message and (
            "unsupported" in message or "only the default" in message
        )

    @staticmethod
    def _reasoning_is_unsupported(exc):
        message = str(exc).lower()
        return "reasoning_effort" in message and (
            "unsupported" in message
            or "not supported" in message
            or "invalid input" in message
            or 'type":"enum"' in message
        )
