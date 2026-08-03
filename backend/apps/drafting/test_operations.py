import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.drafting import operations
from apps.drafting.models import DraftDocument, DraftingSession
from apps.drafting.services import create_draft, regenerate_draft_block
from apps.matters.models import Matter
from apps.templates_app.models import DocumentTemplate, TemplateBlock


@override_settings(AI_DRAFTING_ENABLED=False, ENABLE_DEMO_MATTERS=True)
class DraftOperationTests(TestCase):
    """Document changes are described, validated, and applied as typed patches."""

    def setUp(self):
        self.matter = Matter.objects.create(
            external_id="LS-OPERATIONS",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Cleveland Housing Court",
            summary="Tenant disputes rent.",
            source_system="Demo",
        )
        self.template = DocumentTemplate.objects.create(
            title="Answer and Counterclaims",
            slug="answer-operations-test",
            kind="answer_counterclaims",
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="caption",
            label="Caption",
            block_type="caption",
            order=10,
            body="IN THE HOUSING COURT",
            required=True,
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="defenses",
            label="Defenses",
            block_type="argument",
            order=20,
            body="The tenant denies the allegations.",
            required=True,
        )
        self.session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_block_keys=["caption", "defenses"],
        )
        self.draft = create_draft(self.session)

    def _keys(self):
        return [section["key"] for section in DraftDocument.objects.get(id=self.draft.id).sections]

    def test_proposed_operation_does_not_change_the_document_until_applied(self):
        operation = operations.propose(
            self.draft,
            "replace_component",
            payload={"stableKey": "defenses", "body": "Rewritten defenses."},
            rationale="Reviewer asked for a firmer denial.",
        )

        self.assertEqual(operation.status, "proposed")
        self.assertNotIn("Rewritten defenses.", DraftDocument.objects.get(id=self.draft.id).plain_text)

        operations.apply(operation)

        operation.refresh_from_db()
        self.assertEqual(operation.status, "applied")
        self.assertEqual(operation.result["componentVersionSequence"], 2)
        self.assertIn("Rewritten defenses.", DraftDocument.objects.get(id=self.draft.id).plain_text)

    def test_an_operation_can_only_be_resolved_once(self):
        operation = operations.propose(
            self.draft, "replace_component", payload={"stableKey": "defenses", "body": "Once."}
        )
        operations.apply(operation)

        with self.assertRaises(operations.OperationError):
            operations.apply(operation)
        with self.assertRaises(operations.OperationError):
            operations.reject(operation)

    def test_rejecting_an_operation_leaves_the_document_alone(self):
        operation = operations.propose(
            self.draft, "replace_component", payload={"stableKey": "defenses", "body": "Never applied."}
        )

        operations.reject(operation, "Not what the reviewer wanted.")

        operation.refresh_from_db()
        self.assertEqual(operation.status, "rejected")
        self.assertEqual(operation.decision_note, "Not what the reviewer wanted.")
        self.assertNotIn("Never applied.", DraftDocument.objects.get(id=self.draft.id).plain_text)

    def test_insert_move_and_delete_reorder_the_document(self):
        operations.propose_and_apply(
            self.draft,
            "insert_component",
            payload={"key": "certificate", "label": "Certificate of service", "body": "Served by mail."},
        )
        self.assertEqual(self._keys(), ["caption", "defenses", "certificate"])

        operations.propose_and_apply(
            self.draft, "move_component", payload={"stableKey": "certificate", "position": 1}
        )
        self.assertEqual(self._keys(), ["caption", "certificate", "defenses"])

        operations.propose_and_apply(self.draft, "delete_component", payload={"stableKey": "certificate"})
        self.assertEqual(self._keys(), ["caption", "defenses"])

    def test_operations_are_rejected_before_they_can_damage_the_document(self):
        with self.assertRaises(operations.OperationError):
            operations.propose(self.draft, "rewrite_everything", payload={})
        with self.assertRaises(operations.OperationError):
            operations.propose(self.draft, "replace_component", payload={"stableKey": "missing", "body": "x"})
        with self.assertRaises(operations.OperationError):
            operations.propose(self.draft, "replace_component", payload={"stableKey": "defenses"})
        with self.assertRaises(operations.OperationError):
            operations.propose(self.draft, "insert_component", payload={"key": "caption", "body": "Duplicate."})
        with self.assertRaises(operations.OperationError):
            operations.propose(
                self.draft, "move_component", payload={"stableKey": "defenses", "position": "first"}
            )

    def test_revert_restores_an_earlier_version_as_a_new_version(self):
        original = next(section["body"] for section in self.draft.sections if section["key"] == "defenses")
        operations.propose_and_apply(
            self.draft, "replace_component", payload={"stableKey": "defenses", "body": "A worse draft."}
        )

        operations.propose_and_apply(
            self.draft, "revert_component", payload={"stableKey": "defenses", "sequence": 1}
        )

        component = self.draft.components.get(stable_key="defenses")
        self.assertEqual([version.sequence for version in component.versions.order_by("sequence")], [1, 2, 3])
        self.assertEqual(component.current_version.body, original)
        self.assertEqual(component.current_version.origin, "rollback")

    def test_regenerating_a_block_records_an_applied_operation(self):
        regenerate_draft_block(self.draft, "defenses", "Cite the ledger.")

        operation = self.draft.operations.get()
        self.assertEqual(operation.operation_type, "replace_component")
        self.assertEqual(operation.status, "applied")
        self.assertEqual(operation.origin, "ai")
        self.assertEqual(operation.rationale, "Cite the ledger.")
        self.assertEqual(operation.target_component.stable_key, "defenses")

    def test_operations_api_proposes_reviews_and_lists_changes(self):
        User.objects.create_user("reviewer", password="reviewer-pass")
        self.client.login(username="reviewer", password="reviewer-pass")
        url = reverse("api_draft_operations", args=[self.draft.id])

        proposed = self.client.post(
            url,
            data=json.dumps(
                {
                    "operationType": "replace_component",
                    "payload": {"stableKey": "defenses", "body": "Proposed text."},
                    "rationale": "Tighten the denial.",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(proposed.status_code, 201)
        operation_id = json.loads(proposed.content)["operation"]["id"]
        self.assertNotIn("Proposed text.", json.loads(proposed.content)["draft"]["plainText"])

        applied = self.client.post(
            reverse("api_draft_operation_decision", args=[self.draft.id, operation_id]),
            data=json.dumps({"decision": "apply"}),
            content_type="application/json",
        )
        self.assertEqual(applied.status_code, 200)
        payload = json.loads(applied.content)
        self.assertEqual(payload["operation"]["status"], "applied")
        self.assertEqual(payload["operation"]["requestedBy"], "reviewer")
        self.assertIn("Proposed text.", payload["draft"]["plainText"])

        listed = json.loads(self.client.get(url).content)["operations"]
        self.assertEqual([item["status"] for item in listed], ["applied"])

    def test_operations_api_reports_invalid_proposals_as_client_errors(self):
        User.objects.create_user("reviewer", password="reviewer-pass")
        self.client.login(username="reviewer", password="reviewer-pass")

        response = self.client.post(
            reverse("api_draft_operations", args=[self.draft.id]),
            data=json.dumps({"operationType": "replace_component", "payload": {"stableKey": "nope", "body": "x"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nope", json.loads(response.content)["error"])
