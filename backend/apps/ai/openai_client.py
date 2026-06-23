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

    def complete(self, *, system, user, temperature=0.2):
        return self.complete_messages(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )

    def complete_messages(self, *, messages, temperature=0.2):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
        except Exception as exc:
            raise OpenAIBackendError(str(exc)) from exc

        message = response.choices[0].message
        return (message.content or "").strip()
