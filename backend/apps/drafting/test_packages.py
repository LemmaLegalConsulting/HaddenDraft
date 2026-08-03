import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.drafting.models import DraftDocument, DraftingSession
from apps.drafting.packages import derive_relationships, package_payload, package_role
from apps.matters.models import Matter
from apps.templates_app.models import DocumentTemplate
from apps.validation.services import validate_document


@override_settings(AI_DRAFTING_ENABLED=False, ENABLE_DEMO_MATTERS=True)
class FilingPackageTests(TestCase):
    """Documents generated together are validated as one filing package."""

    def setUp(self):
        self.matter = Matter.objects.create(
            external_id="LS-PACKAGE",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Cleveland Housing Court",
            summary="Tenant seeks a continuance.",
            source_system="Demo",
        )
        self.motion_template = DocumentTemplate.objects.create(
            title="Motion to Continue",
            slug="motion-continue-package-test",
            kind="motion",
        )
        self.session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.motion_template,
        )

    def _draft(self, title, text, *, template=None):
        return DraftDocument.objects.create(
            session=self.session,
            template=template or self.motion_template,
            title=title,
            sections=[{"key": "body", "label": "Body", "body": text}],
            plain_text=text,
        )

    def test_package_role_prefers_the_template_declaration_then_the_title(self):
        declared_template = DocumentTemplate.objects.create(
            title="Support document",
            slug="declaration-package-test",
            kind="motion",
            metadata={"packageRole": "declaration"},
        )

        self.assertEqual(package_role(self._draft("Support document", "", template=declared_template)), "declaration")
        self.assertEqual(package_role(self._draft("Proposed Order", "")), "proposed_order")
        self.assertEqual(package_role(self._draft("Memorandum in support of motion", "")), "memorandum")
        self.assertEqual(package_role(self._draft("Motion to Continue", "")), "motion")

    def test_relationships_are_derived_from_the_roles_in_the_package(self):
        motion = self._draft("Motion to Continue", "Motion text.")
        order = self._draft("Proposed Order", "Order text.")
        declaration = self._draft("Declaration of Jane Tenant", "Declaration text.")

        derive_relationships(self.session)

        payload = package_payload(self.session)
        self.assertEqual(
            sorted(
                (item["sourceDocumentId"], item["relationshipType"], item["targetDocumentId"])
                for item in payload["relationships"]
            ),
            sorted(
                [
                    (order.id, "implements_relief", motion.id),
                    (declaration.id, "depends_on", motion.id),
                ]
            ),
        )
        self.assertEqual(
            {item["id"]: item["role"] for item in payload["documents"]},
            {motion.id: "motion", order.id: "proposed_order", declaration.id: "declaration"},
        )

    def test_deriving_relationships_twice_does_not_duplicate_them(self):
        self._draft("Motion to Continue", "Motion text.")
        self._draft("Proposed Order", "Order text.")

        derive_relationships(self.session)
        second_pass = derive_relationships(self.session)

        self.assertEqual(second_pass, [])
        self.assertEqual(len(package_payload(self.session)["relationships"]), 1)

    def test_a_case_number_that_disagrees_with_the_package_is_flagged(self):
        motion = self._draft("Motion to Continue", "Case No. 2024 CVG 001234\nThe tenant asks for more time.")
        self._draft("Proposed Order", "Case No. 2024 CVG 999999\nIt is so ordered.")

        findings = validate_document(motion, include_docx=False)

        case_number_findings = [finding for finding in findings if finding["ruleCode"] == "W800"]
        self.assertEqual(len(case_number_findings), 1)
        self.assertIn("2024 cvg 001234", case_number_findings[0]["message"].casefold())

    def test_matching_case_numbers_raise_nothing(self):
        motion = self._draft("Motion to Continue", "Case No. 2024 CVG 001234\nThe tenant asks for more time.")
        self._draft("Proposed Order", "Case No. 2024 CVG 001234\nIt is so ordered.")

        findings = validate_document(motion, include_docx=False)

        self.assertEqual([finding for finding in findings if finding["ruleCode"] == "W800"], [])

    def test_an_exhibit_no_declaration_identifies_is_flagged(self):
        motion = self._draft("Motion to Continue", "The ledger is attached as Exhibit A.")
        self._draft("Proposed Order", "It is so ordered.")

        findings = validate_document(motion, include_docx=False)

        self.assertEqual(
            [finding["target"] for finding in findings if finding["ruleCode"] == "W810"],
            ["package:exhibit:A"],
        )

    def test_an_exhibit_a_declaration_identifies_is_accepted(self):
        motion = self._draft("Motion to Continue", "The ledger is attached as Exhibit A.")
        self._draft("Declaration of Jane Tenant", "Exhibit A is a true copy of my rent ledger.")

        findings = validate_document(motion, include_docx=False)

        self.assertEqual([finding for finding in findings if finding["ruleCode"] == "W810"], [])

    def test_a_promised_companion_document_missing_from_the_package_is_flagged(self):
        motion = self._draft("Motion to Continue", "As set out in the attached declaration, more time is needed.")
        self._draft("Proposed Order", "It is so ordered.")

        findings = validate_document(motion, include_docx=False)

        missing = [finding for finding in findings if finding["ruleCode"] == "W820"]
        self.assertEqual([finding["action"]["payload"]["packageRole"] for finding in missing], ["declaration"])

    def test_a_single_document_session_is_not_package_validated(self):
        motion = self._draft("Motion to Continue", "Case No. 2024 CVG 001234\nSee the attached declaration.")

        findings = validate_document(motion, include_docx=False)

        self.assertEqual([finding for finding in findings if finding["category"] == "package_consistency"], [])

    def test_package_endpoint_returns_composition_and_relationships(self):
        motion = self._draft("Motion to Continue", "Motion text.")
        order = self._draft("Proposed Order", "Order text.")
        User.objects.create_user("reviewer", password="reviewer-pass")
        self.client.login(username="reviewer", password="reviewer-pass")

        response = self.client.post(reverse("api_session_package", args=[self.session.id]))

        self.assertEqual(response.status_code, 200)
        package = json.loads(response.content)["package"]
        self.assertEqual([item["id"] for item in package["documents"]], [motion.id, order.id])
        self.assertEqual(package["relationships"][0]["relationshipType"], "implements_relief")
