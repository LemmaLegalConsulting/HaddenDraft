"""Boundary controls using maintained rules, without real client documents."""
from pathlib import Path

from django.test import SimpleTestCase

from apps.argument_gym.rule_audit import pleading_state
from apps.rules.court_profiles import load_court_profile_file
from apps.rules.legal_rules import load_legal_rule_file
from apps.rules.models import CourtProfile
from apps.validation.court_formatting import check_required_elements


ROOT = Path(__file__).resolve().parents[3]


class RulePatternBoundaryTests(SimpleTestCase):
    def test_remediation_abatement_is_not_a_claimed_rent_remedy(self):
        seed = load_legal_rule_file(ROOT / "content/legal-rules/rc-5321-04-landlord-duties.yaml")
        element = next(e for e in seed["elements"] if e["id"] == "consequence_claimed")
        for text in ("Lead abatement work was completed.", "The contractor performed asbestos abatement."):
            self.assertEqual(pleading_state(element, text)[0], "unknown")
        for text in ("Tenant seeks rent abatement.", "Tenant requests abatement of the rent."):
            self.assertEqual(pleading_state(element, text)[0], "yes")

    def test_municipal_caption_does_not_require_in_the(self):
        seed = load_court_profile_file(ROOT / "content/court-rules/generic-ohio-trial-court.yaml")
        profile = CourtProfile(**seed)
        for text in ("EXAMPLE MUNICIPAL COURT\nHOUSING DIVISION", "NORTH COUNTY DISTRICT COURT"):
            findings = check_required_elements(profile, text, "motion", 0)
            self.assertNotIn("caption", [f["target"] for f in findings])
        findings = check_required_elements(profile, "The tenant filed a motion yesterday.", "motion", 0)
        self.assertIn("caption", [f["target"] for f in findings])
