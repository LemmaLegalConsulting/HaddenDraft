from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.drafting.models import DraftDocument, DraftingSession
from apps.matters.models import Matter, MatterFact
from apps.templates_app.models import DocumentTemplate, TemplateBlock
from apps.templates_app.template_variables import declared_template_fields, normalize_field_path
from apps.validation.findings import error_finding, make_finding, warning_finding
from apps.validation.repair import apply_repairs, is_repairable, validate_with_auto_repair
from apps.validation.revision import apply_revision_plan, build_revision_plan
from apps.validation.services import validate_document

VALID_SEVERITIES = {"error", "warning", "info"}
SEVERITY_PREFIX = {"error": "E", "warning": "W", "info": "I"}


def make_matter(**overrides):
    defaults = dict(
        external_id=f"CASE-{MatterFact.objects.count()}-{DraftDocument.objects.count()}",
        client_name="Jane Tenant",
        matter_type="Eviction",
        jurisdiction="Cuyahoga County Housing Court",
    )
    defaults.update(overrides)
    return Matter.objects.create(**defaults)


def make_session(matter, template=None, **overrides):
    defaults = dict(mode="draft_from_template", matter=matter, template=template)
    defaults.update(overrides)
    return DraftingSession.objects.create(**defaults)


def make_draft(session, sections=None, plain_text="", **overrides):
    defaults = dict(session=session, title="Test draft", sections=sections or [], plain_text=plain_text)
    defaults.update(overrides)
    return DraftDocument.objects.create(**defaults)


class FindingSchemaTests(TestCase):
    def test_error_finding_requires_e_prefix(self):
        with self.assertRaises(ValueError):
            error_finding(draft_id=1, rule_code="W100", category="template", target="x", message="m")

    def test_warning_finding_requires_w_prefix(self):
        with self.assertRaises(ValueError):
            warning_finding(draft_id=1, rule_code="E100", category="template", target="x", message="m")

    def test_invalid_severity_rejected(self):
        with self.assertRaises(ValueError):
            make_finding(draft_id=1, rule_code="N100", severity="needs_check", category="template", target="x", message="m")

    def test_finding_id_is_stable_across_calls(self):
        first = error_finding(draft_id=7, rule_code="E100", category="template", target="field:court", message="Missing court.")
        second = error_finding(draft_id=7, rule_code="E100", category="template", target="field:court", message="Missing court.")
        self.assertEqual(first["findingId"], second["findingId"])

    def test_finding_has_required_shape(self):
        finding = error_finding(
            draft_id=1,
            rule_code="E100",
            category="template",
            target="field:court",
            message="Missing court.",
            location={"view": "json", "excerpt": "[Court]"},
            action={"type": "fill_template_field", "label": "Fill it in.", "payload": {}},
        )
        for key in ("findingId", "ruleCode", "severity", "outcome", "category", "target", "location", "message", "action", "manualReview", "details"):
            self.assertIn(key, finding)
        self.assertEqual(finding["severity"], "error")
        self.assertIn("view", finding["location"])


class ValidateDocumentFixtureTests(TestCase):
    def _all_findings_are_well_formed(self, findings):
        for finding in findings:
            self.assertIn(finding["severity"], VALID_SEVERITIES)
            self.assertNotEqual(finding["severity"], "needs_check")
            self.assertEqual(finding["ruleCode"][0], SEVERITY_PREFIX[finding["severity"]])
            for key in ("findingId", "ruleCode", "severity", "outcome", "category", "target", "location", "message", "action", "manualReview", "details"):
                self.assertIn(key, finding)

    def test_findings_never_use_needs_check_and_match_rule_prefix(self):
        matter = make_matter()
        template = DocumentTemplate.objects.create(title="Motion", slug="quality-motion", kind="motion")
        TemplateBlock.objects.create(template=template, key="body", label="Body", block_type="argument", body="Static body.")
        session = make_session(matter, template=template)
        draft = make_draft(
            session,
            sections=[{"key": "body", "label": "Body", "body": "Hearing on [Court]. Id. at 5."}],
            plain_text="Hearing on [Court]. Id. at 5.",
        )

        findings = validate_document(draft)

        self.assertTrue(findings)
        self._all_findings_are_well_formed(findings)

    def test_court_placeholder_in_plain_text_is_error_with_json_view(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[], plain_text="The case is pending before [Court].")

        findings = validate_document(draft)

        placeholder_findings = [f for f in findings if f["ruleCode"] == "E140"]
        self.assertTrue(placeholder_findings, findings)
        self.assertEqual(placeholder_findings[0]["severity"], "error")
        self.assertEqual(placeholder_findings[0]["location"]["view"], "json")

    def test_court_placeholder_only_in_docx_is_error_with_docx_view(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(
            session,
            sections=[{"key": "body", "label": "Body", "body": "Hearing before [Court]."}],
            plain_text="Motion filed on time.",
        )

        findings = validate_document(draft)

        placeholder_findings = [f for f in findings if f["ruleCode"] == "E140"]
        self.assertTrue(placeholder_findings, findings)
        self.assertEqual(placeholder_findings[0]["location"]["view"], "docx")

    def test_jinja_syntax_in_plain_text_is_error(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[], plain_text="Hearing on {{ fields.hearing_date }}.")

        findings = validate_document(draft)

        jinja_findings = [f for f in findings if f["ruleCode"] == "E130"]
        self.assertTrue(jinja_findings, findings)
        self.assertEqual(jinja_findings[0]["location"]["view"], "json")

    def test_jinja_syntax_only_in_rendered_docx_is_error(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(
            session,
            sections=[{"key": "body", "label": "Body", "body": "Hearing on {{ fields.hearing_date }}."}],
            plain_text="Hearing on the scheduled date.",
        )

        findings = validate_document(draft)

        jinja_findings = [f for f in findings if f["ruleCode"] == "E131"]
        self.assertTrue(jinja_findings, findings)
        self.assertEqual(jinja_findings[0]["location"]["view"], "docx")

    def test_required_block_missing_from_sections_is_error(self):
        matter = make_matter()
        template = DocumentTemplate.objects.create(title="Answer", slug="required-block-test", kind="answer_counterclaims")
        TemplateBlock.objects.create(template=template, key="caption", label="Case Caption", block_type="caption", required=True, body="Caption body.")
        session = make_session(matter, template=template)
        draft = make_draft(session, sections=[], plain_text="")

        findings = validate_document(draft)

        codes = {f["ruleCode"] for f in findings}
        self.assertIn("E210", codes)
        target_findings = [f for f in findings if f["ruleCode"] == "E210"]
        self.assertEqual(target_findings[0]["target"], "block:caption")

    def test_json_content_with_empty_rendered_docx_is_error(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[], plain_text="This draft has narrative content that should render.")

        findings = validate_document(draft)

        codes = {f["ruleCode"] for f in findings}
        self.assertIn("E310", codes)

    def test_dangling_short_form_citation_is_error(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[], plain_text="Id. at 5 supports the tenant's argument regarding notice.")

        findings = validate_document(draft)

        codes = {f["ruleCode"] for f in findings}
        self.assertIn("E420", codes)

    def test_full_citation_produces_warning_not_needs_check(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[], plain_text="This is grounded in 410 U.S. 113, a controlling case.")

        findings = validate_document(draft)

        citation_findings = [f for f in findings if f["ruleCode"] == "W440"]
        self.assertTrue(citation_findings, findings)
        self.assertEqual(citation_findings[0]["severity"], "warning")
        self.assertNotIn("needs_check", {f["severity"] for f in findings})

    def test_selected_fact_absent_from_draft_is_warning(self):
        matter = make_matter()
        fact = MatterFact.objects.create(
            matter=matter,
            slug="unused-fact",
            title="Unused fact",
            text="The tenant's water heater has been broken for six months without repair.",
            source_label="Intake notes",
        )
        session = make_session(matter, selected_fact_ids=[fact.id])
        draft = make_draft(session, sections=[], plain_text="This motion addresses an unrelated notice defect.")

        findings = validate_document(draft)

        fact_findings = [f for f in findings if f["ruleCode"] == "W520"]
        self.assertTrue(fact_findings, findings)
        self.assertEqual(fact_findings[0]["severity"], "warning")

    def test_unsupported_dollar_and_date_assertion_is_warning(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(
            session,
            sections=[],
            plain_text="The tenant paid $500 in rent on March 3, 2024, which is not reflected in any selected fact.",
        )

        findings = validate_document(draft)

        support_findings = [f for f in findings if f["ruleCode"] == "W530"]
        self.assertTrue(support_findings, findings)
        self.assertEqual(support_findings[0]["severity"], "warning")

    def test_bare_party_role_mention_does_not_force_error_severity(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(
            session,
            sections=[],
            plain_text="Defendant paid $500 in rent on March 3, 2024, which is not reflected in any selected fact.",
        )

        findings = validate_document(draft)

        codes = {f["ruleCode"] for f in findings}
        self.assertNotIn("E530", codes)
        self.assertIn("W530", codes)

    def test_curated_fact_text_counts_as_support(self):
        matter = make_matter()
        session = make_session(
            matter,
            selected_curated_facts=[
                {
                    "id": "chunk:1",
                    "title": "Intake notes excerpt",
                    "text": "Defendant Eleanor Vance withheld the April, May, and June 2026 rent because of a severe ceiling leak and black mold.",
                }
            ],
        )
        draft = make_draft(
            session,
            sections=[],
            plain_text="Defendant Eleanor Vance has withheld rent for April, May, and June 2026.",
        )

        findings = validate_document(draft)

        codes = {f["ruleCode"] for f in findings}
        self.assertNotIn("W530", codes)
        self.assertNotIn("E530", codes)

    def test_unreflected_curated_fact_is_warning(self):
        matter = make_matter()
        session = make_session(
            matter,
            selected_curated_facts=[
                {"id": "chunk:2", "title": "Unused note", "text": "The water heater has been broken for six months without repair."}
            ],
        )
        draft = make_draft(session, sections=[], plain_text="This motion addresses an unrelated notice defect.")

        findings = validate_document(draft)

        curated_findings = [f for f in findings if f["ruleCode"] == "W521"]
        self.assertTrue(curated_findings, findings)
        self.assertEqual(curated_findings[0]["severity"], "warning")

    def test_matter_summary_counts_as_support(self):
        matter = make_matter(summary="Apex Properties LLC filed an eviction action against the tenant for alleged non-payment of rent.")
        session = make_session(matter)
        draft = make_draft(
            session,
            sections=[],
            plain_text="Plaintiff Apex Properties LLC filed this eviction action for alleged non-payment of rent.",
        )

        findings = validate_document(draft)

        codes = {f["ruleCode"] for f in findings}
        self.assertNotIn("W530", codes)

    def test_prayer_for_relief_block_is_not_scanned_for_fact_support(self):
        matter = make_matter()
        template = DocumentTemplate.objects.create(title="Answer", slug="relief-block-fact-support-test", kind="answer_counterclaims")
        TemplateBlock.objects.create(template=template, key="relief", label="Prayer for Relief", block_type="relief", body="")
        session = make_session(matter, template=template)
        draft = make_draft(
            session,
            sections=[
                {
                    "key": "relief",
                    "label": "Prayer for Relief",
                    "body": "Defendant requests dismissal, reduction or offset of any claimed balance as appropriate.",
                }
            ],
            plain_text="PRAYER FOR RELIEF\nDefendant requests dismissal, reduction or offset of any claimed balance as appropriate.",
        )

        findings = validate_document(draft)

        support_findings = [f for f in findings if f["category"] == "fact_support" and f["ruleCode"] in {"E530", "W530"}]
        self.assertEqual(support_findings, [])


@override_settings(AI_DRAFTING_ENABLED=False)
class AutoRepairTests(TestCase):
    def _draft_with_repairable_empty_block(self):
        matter = make_matter()
        template = DocumentTemplate.objects.create(title="Motion", slug="repair-motion", kind="motion")
        TemplateBlock.objects.create(template=template, key="body", label="Body", block_type="argument", required=True, body="")
        session = make_session(matter, template=template, selected_block_keys=["body"])
        return make_draft(session, sections=[{"key": "body", "label": "Body", "body": ""}], plain_text="")

    def test_repair_loop_stops_after_max_attempts(self):
        draft = self._draft_with_repairable_empty_block()

        final_draft, summary = validate_with_auto_repair(draft, max_attempts=1)

        self.assertEqual(len(summary["attempts"]), 2)
        self.assertGreater(summary["remainingErrorCount"], 0)
        final_draft.refresh_from_db()
        self.assertEqual(final_draft.validation_flags, summary["attempts"][-1]["findings"])

    def test_repairable_error_triggers_block_regeneration(self):
        draft = self._draft_with_repairable_empty_block()

        final_draft, summary = validate_with_auto_repair(draft, max_attempts=1)

        self.assertTrue(summary["autoRepaired"])
        regenerated = next(section for section in final_draft.sections if section["key"] == "body")
        self.assertEqual(regenerated.get("origin"), "ai")

    def test_nonrepairable_error_does_not_trigger_regeneration(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(
            session,
            sections=[{"key": "body", "label": "Body", "body": "The case is pending before [Court]."}],
            plain_text="The case is pending before [Court].",
        )

        final_draft, summary = validate_with_auto_repair(draft, max_attempts=2)

        self.assertFalse(summary["autoRepaired"])
        self.assertEqual(len(summary["attempts"]), 1)
        placeholder_findings = [f for f in summary["attempts"][0]["findings"] if f["ruleCode"] == "E140"]
        self.assertTrue(placeholder_findings)
        self.assertFalse(is_repairable(placeholder_findings[0]))

    def test_apply_repairs_ignores_nonrepairable_findings(self):
        draft = self._draft_with_repairable_empty_block()
        nonrepairable = error_finding(
            draft_id=draft.id,
            rule_code="E140",
            category="template",
            target="placeholder:[court]",
            message="Placeholder present.",
            action={"type": "fill_template_field", "label": "Fill it in.", "payload": {}},
        )
        self.assertFalse(is_repairable(nonrepairable))

        result = apply_repairs(draft, [nonrepairable])

        self.assertEqual(result.sections, draft.sections)


class ValidateDraftEndpointTests(TestCase):
    def test_validate_endpoint_returns_draft_and_validation_summary(self):
        user = get_user_model().objects.create_user(username="reviewer", password="pass", is_superuser=True)
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[], plain_text="The case is pending before [Court].")

        self.client.login(username="reviewer", password="pass")
        url = reverse("api_validate_draft", args=[draft.id])
        with override_settings(AI_DRAFTING_ENABLED=False):
            response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("draft", payload)
        self.assertIn("validation", payload)
        self.assertIn("attempts", payload["validation"])
        self.assertIn("remainingErrorCount", payload["validation"])
        self.assertEqual(payload["draft"]["id"], draft.id)


class DeclaredTemplateFieldsTests(TestCase):
    def test_plaintiff_alias_resolves_to_plaintiff_name_field(self):
        template = DocumentTemplate.objects.create(title="Answer", slug="declared-fields-alias-test", kind="answer_counterclaims")
        TemplateBlock.objects.create(template=template, key="caption", label="Caption", block_type="caption", body="{{ plaintiff }} v. {{ defendant }}")

        declared = declared_template_fields(template)

        self.assertIn("fields.plaintiff_name", declared)
        self.assertEqual(normalize_field_path("fields.plaintiff_name"), "plaintiff_name")

    def test_explicit_fields_path_is_declared_directly(self):
        template = DocumentTemplate.objects.create(title="Motion", slug="declared-fields-explicit-test", kind="motion")
        TemplateBlock.objects.create(template=template, key="body", label="Body", block_type="argument", body="Hearing on {{ fields.hearing_date }}.")

        declared = declared_template_fields(template)

        self.assertIn("fields.hearing_date", declared)

    def test_no_template_returns_empty_list(self):
        self.assertEqual(declared_template_fields(None), [])


class RevisionPlanTests(TestCase):
    def _findings(self, draft_id):
        return [
            error_finding(
                draft_id=draft_id,
                rule_code="E140",
                category="template",
                target="placeholder:[court]",
                message="The draft still contains the visible placeholder [Court].",
                location={"view": "json", "blockKey": "caption"},
                action={"type": "fill_template_field", "label": "Fill it in.", "payload": {"blockKey": "caption"}},
            ),
            warning_finding(
                draft_id=draft_id,
                rule_code="W530",
                category="fact_support",
                target="assertion:x",
                message="This factual statement does not appear supported.",
                location={"view": "json", "blockKey": "caption"},
                action={"type": "review_fact_support", "label": "Confirm support.", "payload": {}},
            ),
            warning_finding(
                draft_id=draft_id,
                rule_code="W440",
                category="citations",
                target="citation:410 U.S. 113",
                message="Citation was detected but cannot be validated automatically.",
                location={"view": "json"},
                action={"type": "review_citation", "label": "Review this citation.", "payload": {}},
            ),
        ]

    def test_plan_groups_findings_by_block_and_separates_unscoped(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[{"key": "caption", "label": "Caption", "body": "Some caption text."}], plain_text="Some caption text.")

        result = build_revision_plan(draft, self._findings(draft.id))

        self.assertEqual(len(result["plan"]), 1)
        self.assertEqual(result["plan"][0]["blockKey"], "caption")
        self.assertEqual(len(result["plan"][0]["findingIds"]), 2)
        self.assertEqual(len(result["unscoped"]), 1)
        self.assertEqual(result["unscoped"][0]["severity"], "warning")

    def test_findings_for_unknown_block_key_are_unscoped(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[], plain_text="")

        result = build_revision_plan(draft, self._findings(draft.id))

        self.assertEqual(result["plan"], [])
        self.assertEqual(len(result["unscoped"]), 3)

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_apply_revision_plan_only_regenerates_included_blocks(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(
            session,
            sections=[
                {"key": "caption", "label": "Caption", "body": "Caption text."},
                {"key": "relief", "label": "Relief", "body": "Relief text."},
            ],
            plain_text="Caption text.\n\nRelief text.",
        )

        result = apply_revision_plan(
            draft,
            [
                {"blockKey": "caption", "instruction": "Fix the caption.", "include": True},
                {"blockKey": "relief", "instruction": "Fix the relief.", "include": False},
            ],
        )

        caption = next(section for section in result.sections if section["key"] == "caption")
        relief = next(section for section in result.sections if section["key"] == "relief")
        self.assertEqual(caption.get("origin"), "ai")
        self.assertNotEqual(relief.get("origin"), "ai")

    def test_apply_revision_plan_skips_items_without_instruction(self):
        matter = make_matter()
        session = make_session(matter)
        draft = make_draft(session, sections=[{"key": "caption", "label": "Caption", "body": "Caption text."}], plain_text="Caption text.")

        result = apply_revision_plan(draft, [{"blockKey": "caption", "instruction": "  ", "include": True}])

        caption = next(section for section in result.sections if section["key"] == "caption")
        self.assertNotEqual(caption.get("origin"), "ai")


class RevisionPlanEndpointTests(TestCase):
    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_revision_plan_and_apply_endpoints(self):
        user = get_user_model().objects.create_user(username="reviser", password="pass", is_superuser=True)
        matter = make_matter()
        template = DocumentTemplate.objects.create(title="Motion", slug="revision-endpoint-test", kind="motion")
        TemplateBlock.objects.create(template=template, key="body", label="Body", block_type="argument", required=True, body="Static body.")
        session = make_session(matter, template=template)
        draft = make_draft(
            session,
            sections=[{"key": "body", "label": "Body", "body": "The case is pending before [Court]."}],
            plain_text="The case is pending before [Court].",
        )

        self.client.login(username="reviser", password="pass")
        plan_response = self.client.post(reverse("api_draft_revision_plan", args=[draft.id]))
        self.assertEqual(plan_response.status_code, 200)
        plan_payload = plan_response.json()["revisionPlan"]
        self.assertTrue(plan_payload["plan"])
        self.assertEqual(plan_payload["plan"][0]["blockKey"], "body")

        apply_response = self.client.post(
            reverse("api_apply_draft_revision", args=[draft.id]),
            data={"plan": plan_payload["plan"]},
            content_type="application/json",
        )
        self.assertEqual(apply_response.status_code, 200)
        apply_payload = apply_response.json()
        self.assertIn("draft", apply_payload)
        self.assertIn("validation", apply_payload)
        revised_body = next(section for section in apply_payload["draft"]["sections"] if section["key"] == "body")
        self.assertEqual(revised_body.get("origin"), "ai")
