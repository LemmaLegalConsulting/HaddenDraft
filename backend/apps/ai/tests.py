from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings

from apps.ai.case_chat import case_chat_reply
from apps.ai.case_chat import normalize_ai_text as normalize_chat_text
from apps.ai.openai_client import OpenAICompatibleClient
from apps.ai.models import PromptOverride
from apps.ai.prompt_catalog import PromptCatalogError, PromptRenderError, get_prompt, load_file_prompts, render_prompt
from apps.ai.services import ConstrainedDraftingService, GenerationContext
from apps.matters.models import Matter
from apps.matters.serializers import matter_to_dict
from apps.sources.document_text import extract_text
from apps.sources.models import SourceConfiguration


class FakeChatCompletions:
    def __init__(self):
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        message = SimpleNamespace(content="Generated section")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAIClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeChatCompletions())


class OpenAICompatibleClientTests(TestCase):
    def test_complete_uses_chat_completions_endpoint(self):
        fake_client = FakeOpenAIClient()
        client = OpenAICompatibleClient(client=fake_client, model="test-model")

        result = client.complete(system="System", user="User")

        self.assertEqual(result, "Generated section")
        request = fake_client.chat.completions.request
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["messages"][0]["role"], "system")
        self.assertEqual(request["messages"][1]["content"], "User")

    def test_complete_uses_prompt_model_and_reasoning_level(self):
        fake_client = FakeOpenAIClient()
        client = OpenAICompatibleClient(client=fake_client, model="fallback-model")

        client.complete(
            system="System",
            user="User",
            model="prompt-model",
            reasoning_level="medium",
        )

        request = fake_client.chat.completions.request
        self.assertEqual(request["model"], "prompt-model")
        self.assertEqual(request["reasoning_effort"], "medium")

    def test_complete_omits_temperature_for_fixed_temperature_models(self):
        fake_client = FakeOpenAIClient()
        client = OpenAICompatibleClient(client=fake_client, model="gpt-5.4-mini")

        client.complete(system="System", user="User", temperature=0.1)

        self.assertNotIn("temperature", fake_client.chat.completions.request)

    def test_complete_retries_without_temperature_when_provider_rejects_it(self):
        class TemperatureRejectingCompletions:
            def __init__(self):
                self.requests = []

            def create(self, **kwargs):
                self.requests.append(kwargs)
                if "temperature" in kwargs:
                    raise RuntimeError(
                        "Unsupported value: 'temperature' does not support 0.1 with this model. "
                        "Only the default (1) value is supported."
                    )
                message = SimpleNamespace(content="Generated section")
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        completions = TemperatureRejectingCompletions()
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        client = OpenAICompatibleClient(client=fake_client, model="provider-specific-model")

        result = client.complete(system="System", user="User", temperature=0.1)

        self.assertEqual(result, "Generated section")
        self.assertIn("temperature", completions.requests[0])
        self.assertNotIn("temperature", completions.requests[1])

    @override_settings(OPENAI_MODEL="env-model", OPENAI_API_KEY="env-key", OPENAI_BASE_URL="https://env.example/v1")
    def test_admin_source_configuration_overrides_openai_env_defaults(self):
        fake_client = FakeOpenAIClient()
        SourceConfiguration.objects.create(
            name="AI",
            kind="openai",
            openai_model="admin-model",
            openai_api_key="admin-key",
            openai_base_url="https://admin.example/v1",
            openai_enabled=True,
        )

        client = OpenAICompatibleClient(client=fake_client)
        client.complete(system="System", user="User")

        self.assertEqual(fake_client.chat.completions.request["model"], "admin-model")


class PromptCatalogTests(TestCase):
    def test_default_catalog_loads_all_expected_prompt_keys(self):
        prompts = load_file_prompts()

        self.assertEqual(
            set(prompts),
            {
                "drafting.constrained_section",
                "triage.apply_rubric",
                "case_chat.document_summary",
                "case_chat.suggest_actions",
                "case_chat.reply",
                "research.answer",
            },
        )

    def test_prompt_is_rendered_from_yaml_with_named_context(self):
        prompt = render_prompt(
            "drafting.constrained_section",
            allow_database_override=False,
            label="Argument",
            matter_summary="Repairs needed",
            jurisdiction="Housing Court",
            client_name="Tenant",
            instructions="Focus on habitability.",
            facts="- Mold in bedroom",
            sources="- Inspection report",
        )

        self.assertIn("Draft the Argument section", prompt.user)
        self.assertIn("- Mold in bedroom", prompt.user)
        self.assertEqual(prompt.default_model, "gpt-5.4-mini")
        self.assertEqual(prompt.default_reasoning_level, "low")
        self.assertEqual(prompt.source, str(Path(settings.PROMPT_CATALOG_DIR) / "drafting.constrained_section.yaml"))

    def test_enabled_database_override_replaces_file_prompt(self):
        PromptOverride.objects.create(
            key="case_chat.reply",
            system="Override system for {client}",
            user="Override user for {client}",
            default_model="override-model",
            default_reasoning_level="medium",
        )

        prompt = render_prompt("case_chat.reply", client="Sam")

        self.assertEqual(prompt.system, "Override system for Sam")
        self.assertEqual(prompt.user, "Override user for Sam")
        self.assertEqual(prompt.default_model, "override-model")
        self.assertEqual(prompt.default_reasoning_level, "medium")
        self.assertEqual(prompt.source, "database override")

    def test_missing_context_is_reported_before_an_llm_request(self):
        with self.assertRaisesRegex(PromptRenderError, "matter_summary"):
            render_prompt("drafting.constrained_section", allow_database_override=False, label="Argument")

    def test_catalog_directory_can_be_swapped_for_benchmark_variant(self):
        with TemporaryDirectory() as directory:
            Path(directory, "benchmark.sample.yaml").write_text(
                "system prompt: System {name}\nuser prompt: User {name}\nsettings:\n  default model: benchmark-model\n  default reasoning level: high\n",
                encoding="utf-8",
            )
            with self.settings(PROMPT_CATALOG_DIR=Path(directory)):
                prompt = render_prompt("benchmark.sample", allow_database_override=False, name="variant")

        self.assertEqual(prompt.system, "System variant")
        self.assertEqual(prompt.user, "User variant")
        self.assertEqual(prompt.default_model, "benchmark-model")
        self.assertEqual(prompt.default_reasoning_level, "high")

    def test_invalid_catalog_schema_fails_clearly(self):
        with TemporaryDirectory() as directory:
            Path(directory, "broken.yaml").write_text("system prompt: System\n", encoding="utf-8")
            with self.settings(PROMPT_CATALOG_DIR=Path(directory)):
                with self.assertRaisesRegex(PromptCatalogError, "user prompt"):
                    get_prompt("anything", allow_database_override=False)


class DraftingServiceLLMTests(TestCase):
    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_constrained_generation_uses_openai_compatible_client(self):
        captured_request = {}

        def complete(**kwargs):
            captured_request.update(kwargs)
            return "LLM body"

        fake_llm = SimpleNamespace(complete=complete)
        service = ConstrainedDraftingService(llm_client=fake_llm)
        matter = SimpleNamespace(summary="Repairs needed", jurisdiction="Housing Court", client_name="Tenant")
        fact = SimpleNamespace(text="There is mold in the bedroom.", source_label="LegalServer note")
        context = GenerationContext(
            matter=matter,
            selected_facts=[fact],
            selected_curated_facts=[],
            selected_sources=[{"title": "Guide", "snippet": "Use repair evidence."}],
            template=SimpleNamespace(),
            mode="draft_from_scratch",
            instructions="Focus on habitability.",
        )

        body = service.generate_constrained_section(label="Argument", context=context, fallback="Fallback")

        self.assertEqual(body, "LLM body")
        self.assertEqual(
            captured_request["system"],
            "You draft constrained legal document sections from supplied facts and sources.\n",
        )
        self.assertIn("Draft the Argument section", captured_request["user"])
        self.assertIn("There is mold in the bedroom.", captured_request["user"])
        self.assertEqual(captured_request["model"], "gpt-5.4-mini")
        self.assertEqual(captured_request["reasoning_level"], "low")


class CaseChatTests(TestCase):
    def test_chat_text_normalizes_html_breaks(self):
        self.assertEqual(normalize_chat_text("One<br/>Two<br>Three"), "One\nTwo\nThree")

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_document_question_uses_case_documents(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )

        with patch("apps.ai.case_chat.get_case_documents", return_value=[{"title": "Lease.pdf", "id": "doc-1"}]):
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "What documents does this case have?"}],
            )

        self.assertIn("Lease.pdf", reply["message"])
        self.assertEqual(reply["toolsUsed"], ["legalserver.documents"])

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_note_question_uses_case_notes_tool(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
            raw_payload={
                "notes": [
                    {
                        "subject": "Documents Received",
                        "body": "Documents received via webhook.",
                        "date_posted": "2026-03-08",
                        "created_by": {"user_name": "Docassemble API"},
                    }
                ]
            },
        )

        reply = case_chat_reply(
            matter=matter,
            messages=[{"role": "user", "content": "Does it have any case notes?"}],
        )

        self.assertIn("Documents Received", reply["message"])
        self.assertEqual(reply["toolsUsed"], ["legalserver.case_notes"])
        self.assertEqual(reply["toolResults"]["case_notes"][0]["createdBy"], "Docassemble API")

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_note_tool_results_are_answered_deterministically(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
            raw_payload={"notes": [{"subject": "Documents Received", "body": "Documents received via webhook."}]},
        )

        reply = case_chat_reply(
            matter=matter,
            messages=[{"role": "user", "content": "Does it have any case notes?"}],
            llm_client=SimpleNamespace(complete_messages=lambda **kwargs: "No notes."),
        )

        self.assertIn("Documents Received", reply["message"])
        self.assertIn("legalserver.case_notes", reply["toolsUsed"])

    def test_matter_serializer_does_not_return_raw_note_json_as_summary(self):
        matter = Matter.objects.create(
            external_id="LS-2",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
            summary="[{'body': 'raw note json'}]",
            raw_payload={"case_title": "Readable case title", "case_number": "26-0000009"},
        )

        data = matter_to_dict(matter)

        self.assertEqual(data["summary"], "Readable case title")
        self.assertIn({"label": "Case number", "value": "26-0000009"}, data["details"])

    def test_stdlib_text_extractor_handles_plain_text(self):
        result = extract_text(b"Hello from a pleading", filename="motion.txt")

        self.assertEqual(result["extractor"], "stdlib")
        self.assertEqual(result["text"], "Hello from a pleading")

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_document_text_question_extracts_relevant_document(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )
        document = {"title": "Lease.txt", "id": "doc-1", "url": "https://legalserver.example/doc-1"}

        with patch("apps.ai.case_chat.get_case_documents", return_value=[document]), patch(
            "apps.ai.case_chat.LegalServerClient"
        ) as client_class:
            client_class.return_value.download_document.return_value = {
                "content": b"Tenant lease text",
                "content_type": "text/plain",
                "filename": "Lease.txt",
            }
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "What does Lease.txt say?"}],
            )

        self.assertIn("Tenant lease text", reply["message"])
        self.assertIn("document.extract_text", reply["toolsUsed"])
        self.assertEqual(reply["toolResults"]["document_text"]["extractor"], "stdlib")

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_document_summary_language_triggers_extraction(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )
        document = {"title": "Lease - 56_VII_Steenhuis.txt", "id": "doc-1", "url": "https://legalserver.example/doc-1"}

        with patch("apps.ai.case_chat.get_case_documents", return_value=[document]), patch(
            "apps.ai.case_chat.LegalServerClient"
        ) as client_class:
            client_class.return_value.download_document.return_value = {
                "content": b"This lease is for unit 56. Tenant pays monthly rent. This sentence should not be needed.",
                "content_type": "text/plain",
                "filename": "Lease.txt",
            }
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "Tell me what the Lease document is all about"}],
            )

        self.assertIn("Summary of Lease", reply["message"])
        self.assertIn("This lease is for unit 56", reply["message"])
        self.assertIn("document.extract_text", reply["toolsUsed"])
        self.assertIn("document.summarize", reply["toolsUsed"])

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_document_summary_can_use_llm_without_returning_full_text(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )
        document = {"title": "Lease.txt", "id": "doc-1", "url": "https://legalserver.example/doc-1"}
        long_text = b"Sentence one. Sentence two. Sentence three. Sentence four."

        with patch("apps.ai.case_chat.get_case_documents", return_value=[document]), patch(
            "apps.ai.case_chat.LegalServerClient"
        ) as client_class:
            client_class.return_value.download_document.return_value = {
                "content": long_text,
                "content_type": "text/plain",
                "filename": "Lease.txt",
            }
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "Summarize this document"}],
                llm_client=SimpleNamespace(complete=lambda **kwargs: "Short lease summary."),
            )

        self.assertIn("Short lease summary", reply["message"])
        self.assertNotIn("Sentence four", reply["message"])
        self.assertIn("document.summarize", reply["toolsUsed"])

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_raw_text_request_returns_extracted_text(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )
        document = {"title": "Lease.txt", "id": "doc-1", "url": "https://legalserver.example/doc-1"}

        with patch("apps.ai.case_chat.get_case_documents", return_value=[document]), patch(
            "apps.ai.case_chat.LegalServerClient"
        ) as client_class:
            client_class.return_value.download_document.return_value = {
                "content": b"Full lease text.",
                "content_type": "text/plain",
                "filename": "Lease.txt",
            }
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "Show me the full text of Lease.txt"}],
            )

        self.assertIn("Extracted text", reply["message"])
        self.assertIn("Full lease text", reply["message"])
        self.assertNotIn("document.summarize", reply["toolsUsed"])

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_do_it_reuses_prior_document_extraction_request(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )
        document = {"title": "Lease - 56_VII_Steenhuis.txt", "id": "doc-1", "url": "https://legalserver.example/doc-1"}

        with patch("apps.ai.case_chat.get_case_documents", return_value=[document]), patch(
            "apps.ai.case_chat.LegalServerClient"
        ) as client_class:
            client_class.return_value.download_document.return_value = {
                "content": b"Lease text from the follow-up request.",
                "content_type": "text/plain",
                "filename": "Lease.txt",
            }
            reply = case_chat_reply(
                matter=matter,
                messages=[
                    {"role": "user", "content": "Tell me what the Lease document is all about"},
                    {"role": "assistant", "content": "A document content retrieval API call would be needed."},
                    {"role": "user", "content": "do it"},
                ],
            )

        self.assertIn("Lease text from the follow-up request", reply["message"])
        self.assertIn("document.extract_text", reply["toolsUsed"])

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_specific_document_request_does_not_extract_unrelated_document(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )
        document = {"title": "Chart.png", "id": "doc-1", "url": "https://legalserver.example/doc-1"}

        with patch("apps.ai.case_chat.get_case_documents", return_value=[document]), patch(
            "apps.ai.case_chat.LegalServerClient"
        ) as client_class:
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "Tell me what the Lease document is all about"}],
            )

        self.assertIn("matching case document", reply["message"])
        self.assertNotIn("document.extract_text", reply["toolsUsed"])
        client_class.return_value.download_document.assert_not_called()

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_document_listing_uses_deterministic_tool_answer_even_with_ai_enabled(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
        )

        with patch("apps.ai.case_chat.get_case_documents", return_value=[{"title": "Lease.pdf", "id": "doc-1"}]):
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "any documents in this case?"}],
                llm_client=SimpleNamespace(complete_messages=lambda **kwargs: "No documents."),
            )

        self.assertIn("Lease.pdf", reply["message"])
        self.assertEqual(reply["toolsUsed"], ["legalserver.documents"])

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_timeline_question_builds_deterministic_timeline(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
            raw_payload={
                "case_number": "26-0000009",
                "date_opened": "2026-03-08",
                "notes": [{"subject": "Documents Received", "body": "Documents received.", "date_posted": "2026-03-09"}],
            },
        )

        with patch("apps.ai.case_chat.get_case_documents", return_value=[{"title": "Lease.pdf", "date": "2026-03-10"}]):
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "What's happened in this case so far?"}],
            )

        self.assertIn("case.timeline", reply["toolsUsed"])
        self.assertIn("Documents Received", reply["message"])
        self.assertIn("Lease.pdf", reply["message"])

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_next_step_question_returns_action_cards(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="API TestOne",
            matter_type="Housing",
            jurisdiction="Housing Court",
            raw_payload={"notes": [{"subject": "Intake", "body": "Client needs a motion."}]},
        )

        with patch("apps.ai.case_chat.get_case_documents", return_value=[{"title": "Complaint.pdf", "id": "doc-1"}]):
            reply = case_chat_reply(
                matter=matter,
                messages=[{"role": "user", "content": "What's the next step I should take?"}],
            )

        self.assertIn("case.suggest_actions", reply["toolsUsed"])
        self.assertGreaterEqual(len(reply["actions"]), 2)
        self.assertIn("custom_motion", {action["type"] for action in reply["actions"]})
