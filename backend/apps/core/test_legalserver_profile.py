from django.test import TestCase

from apps.core.legalserver_profile import (
    apply_legalserver_user_to_profile,
    profile_values_from_legalserver_user,
)
from apps.core.models import AuthorProfile


# Shaped after a live LegalServer /api/v1/users record.
LEGALSERVER_USER = {
    "first": "Dana",
    "middle": "R",
    "last": "Ruiz",
    "suffix": "",
    "title": "Staff Attorney",
    "email": "druiz@example.org",
    "phone_business": "216.555.0142",
    "phone_fax": "440.352.0015",
    "bar_number": "0091234",
    "salutation": "Ms.",
    "office": {"office_name": "Cleveland", "office_code": "CLE", "office_display": "Cleveland Office"},
    "address_work": {
        "street": "1223 West Sixth Street",
        "street_2": "",
        "apt_num": "",
        "city": "Cleveland",
        "state": "OH",
        "zip": "44113",
    },
}


class LegalServerProfileMappingTests(TestCase):
    def test_letterhead_fields_map_from_a_user_record(self):
        values = profile_values_from_legalserver_user(LEGALSERVER_USER)

        self.assertEqual(values["display_name"], "Dana R Ruiz")
        self.assertEqual(values["title"], "Staff Attorney")
        self.assertEqual(values["phone"], "216.555.0142")
        self.assertEqual(values["fax"], "440.352.0015")
        self.assertEqual(values["bar_number"], "0091234")
        self.assertEqual(values["office_name"], "Cleveland Office")
        self.assertEqual(values["address"], "1223 West Sixth Street\nCleveland, OH 44113")

    def test_placeholder_emails_are_not_carried_onto_a_letterhead(self):
        """LegalServer demo/inactive records store "@" and "none@none"."""
        for placeholder in ("@", "none@none", ""):
            values = profile_values_from_legalserver_user({**LEGALSERVER_USER, "email": placeholder})
            self.assertNotIn("email", values, placeholder)

    def test_missing_office_and_address_are_omitted_rather_than_blank(self):
        values = profile_values_from_legalserver_user(
            {
                "first": "Sam",
                "last": "Okafor",
                "office": {"office_name": None, "office_display": None},
                "address_work": {"street": None, "city": None, "state": None, "zip": None},
            }
        )

        self.assertEqual(values["display_name"], "Sam Okafor")
        self.assertNotIn("office_name", values)
        self.assertNotIn("address", values)

    def test_apply_fills_blanks_without_overwriting_corrections(self):
        profile = AuthorProfile(display_name="Dana Ruiz, Esq.", title="", phone="")

        changed = apply_legalserver_user_to_profile(profile, LEGALSERVER_USER)

        # The advocate's own edit stands; the blanks get filled.
        self.assertEqual(profile.display_name, "Dana Ruiz, Esq.")
        self.assertEqual(profile.title, "Staff Attorney")
        self.assertNotIn("display_name", changed)
        self.assertIn("title", changed)

    def test_overwrite_replaces_existing_values(self):
        profile = AuthorProfile(display_name="Stale Name", title="Old Title")

        changed = apply_legalserver_user_to_profile(profile, LEGALSERVER_USER, overwrite=True)

        self.assertEqual(profile.display_name, "Dana R Ruiz")
        self.assertIn("display_name", changed)

    def test_unusable_payload_is_ignored(self):
        self.assertEqual(profile_values_from_legalserver_user(None), {})
        self.assertEqual(profile_values_from_legalserver_user("nope"), {})
