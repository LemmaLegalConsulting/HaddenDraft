"""Deterministic filing-format checks, and what they refuse to claim."""

from django.test import TestCase

from apps.rules.models import CourtProfile
from apps.validation.court_formatting import check_court_compliance


BRIEF = """
IN THE CLEVELAND MUNICIPAL COURT, HOUSING DIVISION
Case No. CV-24-001234

MOTION TO DISMISS

The notice was defective.

Respectfully submitted,
Jane Advocate (0012345)

CERTIFICATE OF SERVICE
A copy was served on counsel by email.
"""

REQUIRED_ELEMENTS = [
    {"id": "caption", "label": "Caption naming the court", "severity": "error", "patterns": ["in the .{0,60}court"]},
    {"id": "certificate_of_service", "label": "Certificate of service", "severity": "error", "patterns": ["certificate of service"]},
    {
        "id": "table_of_contents",
        "label": "Table of contents",
        "severity": "error",
        "pleading_types": ["appellate_brief"],
        "patterns": ["table of contents"],
    },
]

FORMATTING_RULES = {
    "fonts": {"min_size_pt": 12, "allowed_families": ["Times New Roman"]},
    "spacing": {"body": "double"},
    "margins_in": {"top": 1.0, "left": 1.0},
    "page_limits": [{"pleading_types": ["motion"], "max_pages": 15}],
}

MEASURED = {
    "countedPageCount": 8,
    "fonts": [{"family": "Times New Roman", "sizePt": 12.0, "runs": 100}],
    "bodyFontSizePt": 12.0,
    "lineSpacing": "double",
    "marginsIn": {"top": 1.0, "left": 1.0},
    "measured": ["fonts", "lineSpacing", "margins", "pageCount"],
    "unavailable": [],
}


def profile(**overrides):
    defaults = {
        "slug": "test-court",
        "name": "Test Municipal Court",
        "court_type": CourtProfile.MUNICIPAL,
        "verification": CourtProfile.VERIFIED,
        "source": "Local Rule 3.1",
        "pleading_types": ["motion", "answer"],
        "formatting": FORMATTING_RULES,
        "required_elements": REQUIRED_ELEMENTS,
    }
    return CourtProfile(**{**defaults, **overrides})


def codes(result):
    return [finding["ruleCode"] for finding in result["findings"]]


def messages(result):
    return " ".join(finding["message"] for finding in result["findings"])


class ComplianceTests(TestCase):
    def test_a_conforming_motion_produces_no_findings(self):
        result = check_court_compliance(
            profile=profile(), formatting=MEASURED, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertTrue(result["checked"])
        self.assertEqual(result["findings"], [])

    def test_a_missing_required_element_is_reported_against_the_rule_it_comes_from(self):
        result = check_court_compliance(
            profile=profile(),
            formatting=MEASURED,
            text="A brief with no certificate.\nIN THE TEST COURT\nCase No. 1",
            pleading_type="motion",
            document_id=1,
        )
        self.assertIn("E900", codes(result))
        self.assertIn("Certificate of service", messages(result))
        self.assertIn("Local Rule 3.1", messages(result))

    def test_a_requirement_scoped_to_another_pleading_type_is_not_applied(self):
        result = check_court_compliance(
            profile=profile(), formatting=MEASURED, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertNotIn("Table of contents", messages(result))

    def test_an_unverified_profile_warns_and_says_so(self):
        result = check_court_compliance(
            profile=profile(verification=CourtProfile.UNVERIFIED, source=""),
            formatting=MEASURED,
            text="No certificate here.\nIN THE TEST COURT",
            pleading_type="motion",
            document_id=1,
        )
        self.assertIn("W900", codes(result))
        self.assertNotIn("E900", codes(result))
        self.assertIn("unverified starter profile", messages(result))

    def test_type_below_the_minimum_is_reported_with_the_size_measured(self):
        formatting = {**MEASURED, "fonts": [{"family": "Times New Roman", "sizePt": 10.0, "runs": 100}]}
        result = check_court_compliance(
            profile=profile(), formatting=formatting, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertIn("E911", codes(result))
        self.assertIn("10 point", messages(result))

    def test_a_handful_of_small_runs_is_not_a_type_size_violation(self):
        formatting = {
            **MEASURED,
            "fonts": [
                {"family": "Times New Roman", "sizePt": 12.0, "runs": 400},
                {"family": "Times New Roman", "sizePt": 8.0, "runs": 3},
            ],
        }
        result = check_court_compliance(
            profile=profile(), formatting=formatting, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertNotIn("E911", codes(result))

    def test_a_disallowed_typeface_is_flagged(self):
        formatting = {**MEASURED, "fonts": [{"family": "Comic Sans MS", "sizePt": 12.0, "runs": 100}]}
        result = check_court_compliance(
            profile=profile(), formatting=formatting, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertIn("W910", codes(result))

    def test_single_spacing_against_a_double_spacing_rule_is_an_error(self):
        formatting = {**MEASURED, "lineSpacing": "single"}
        result = check_court_compliance(
            profile=profile(), formatting=formatting, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertIn("E920", codes(result))

    def test_a_narrow_margin_is_reported_with_both_numbers(self):
        formatting = {**MEASURED, "marginsIn": {"top": 1.0, "left": 0.5}}
        result = check_court_compliance(
            profile=profile(), formatting=formatting, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertIn("E930", codes(result))
        self.assertIn("0.50 inches", messages(result))
        self.assertIn("1.00 inches", messages(result))

    def test_a_brief_over_the_page_limit_is_an_error(self):
        formatting = {**MEASURED, "countedPageCount": 22}
        result = check_court_compliance(
            profile=profile(), formatting=formatting, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertIn("E940", codes(result))
        self.assertIn("22 pages", messages(result))

    def test_a_property_that_could_not_be_measured_is_reported_as_unmeasured_not_as_a_pass(self):
        formatting = {
            "countedPageCount": None,
            "fonts": [],
            "lineSpacing": None,
            "marginsIn": {},
            "measured": [],
            "unavailable": ["fonts", "lineSpacing", "margins", "pageCount"],
        }
        result = check_court_compliance(
            profile=profile(), formatting=formatting, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertEqual(sorted(codes(result)), ["I950", "I951", "I952", "I953"])
        self.assertIn("no fixed page count", messages(result))
        self.assertEqual(result["unmeasured"], ["fonts", "lineSpacing", "margins", "pageCount"])

    def test_a_pleading_type_the_court_has_no_rules_for_says_so(self):
        result = check_court_compliance(
            profile=profile(), formatting=MEASURED, text=BRIEF, pleading_type="appellate_brief", document_id=1
        )
        self.assertIn("I960", codes(result))
        self.assertIn("no rules on file", messages(result))

    def test_no_selected_court_means_nothing_was_checked(self):
        result = check_court_compliance(profile=None, formatting=MEASURED, text=BRIEF, document_id=1)
        self.assertFalse(result["checked"])
        self.assertEqual(result["findings"], [])
        self.assertIn("not applied", result["reason"])

    def test_a_malformed_pattern_leaves_the_element_unchecked_rather_than_crashing(self):
        broken = profile(required_elements=[{"id": "x", "label": "X", "severity": "error", "patterns": ["([unclosed"]}])
        result = check_court_compliance(
            profile=broken, formatting=MEASURED, text=BRIEF, pleading_type="motion", document_id=1
        )
        self.assertIn("E900", codes(result))
