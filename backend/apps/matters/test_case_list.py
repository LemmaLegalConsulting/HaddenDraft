from django.test import TestCase

from apps.matters import case_list
from apps.matters.models import Matter
from apps.matters.serializers import matter_is_open, matter_opened_at, matter_to_dict


def case(**overrides):
    base = {
        "id": "26-0001",
        "title": "Tenant v. Landlord",
        "isOpen": True,
        "assignedToViewer": True,
        "legalProblemCode": "63 Private Landlord/Tenant",
        "lastActivityAt": "2026-08-01T00:00:00+00:00",
        "openedAt": "2026-01-01T00:00:00+00:00",
    }
    return {**base, **overrides}


class CaseFilterTests(TestCase):
    def setUp(self):
        self.cases = [
            case(id="open-mine"),
            case(id="open-theirs", assignedToViewer=False),
            case(id="closed-mine", isOpen=False),
            case(id="open-medicaid", legalProblemCode="51 Medicaid"),
        ]

    def ids(self, **kwargs):
        return [item["id"] for item in case_list.filter_cases(self.cases, **kwargs)]

    def test_open_cases_are_the_default_view(self):
        self.assertEqual(self.ids(), ["open-mine", "open-theirs", "open-medicaid"])

    def test_closed_cases_are_reachable_by_asking_for_them(self):
        self.assertEqual(self.ids(status=case_list.STATUS_CLOSED), ["closed-mine"])
        self.assertEqual(len(self.ids(status=case_list.STATUS_ALL)), 4)

    def test_assignment_filter_narrows_to_the_viewer(self):
        self.assertEqual(
            self.ids(status=case_list.STATUS_ALL, assigned=case_list.ASSIGNED_MINE),
            ["open-mine", "closed-mine", "open-medicaid"],
        )

    def test_legal_problem_code_filter_is_exact(self):
        self.assertEqual(self.ids(problem_code="51 Medicaid"), ["open-medicaid"])
        self.assertEqual(self.ids(problem_code="51 medicaid"), ["open-medicaid"])
        self.assertEqual(self.ids(problem_code="99 Other"), [])

    def test_a_case_that_says_nothing_about_disposition_is_open(self):
        self.assertEqual(case_list.filter_cases([{"id": "quiet"}]), [{"id": "quiet"}])


class CaseSortTests(TestCase):
    def setUp(self):
        self.cases = [
            case(id="stale", lastActivityAt="2026-01-05T00:00:00+00:00", openedAt="2026-06-01T00:00:00+00:00"),
            case(id="fresh", lastActivityAt="2026-08-07T00:00:00+00:00", openedAt="2026-02-01T00:00:00+00:00"),
            case(id="undated", lastActivityAt="", openedAt=""),
        ]

    def test_most_recently_active_first(self):
        ordered = case_list.sort_cases(self.cases, sort=case_list.SORT_ACTIVITY)
        self.assertEqual([item["id"] for item in ordered], ["fresh", "stale", "undated"])

    def test_most_recently_opened_first(self):
        ordered = case_list.sort_cases(self.cases, sort=case_list.SORT_OPENED)
        self.assertEqual([item["id"] for item in ordered], ["stale", "fresh", "undated"])

    def test_a_case_with_no_date_sorts_last_rather_than_first(self):
        ordered = case_list.sort_cases(self.cases, sort=case_list.SORT_ACTIVITY)
        self.assertEqual(ordered[-1]["id"], "undated")


class CaseParameterTests(TestCase):
    def test_a_search_widens_the_status_filter_instead_of_narrowing_it(self):
        self.assertEqual(case_list.normalize_status("", searching=True), case_list.STATUS_ALL)
        self.assertEqual(case_list.normalize_status("", searching=False), case_list.STATUS_OPEN)

    def test_an_explicit_status_survives_a_search(self):
        self.assertEqual(case_list.normalize_status("open", searching=True), case_list.STATUS_OPEN)

    def test_junk_parameters_fall_back_rather_than_raising(self):
        self.assertEqual(case_list.normalize_sort("sideways"), case_list.SORT_ACTIVITY)
        self.assertEqual(case_list.normalize_assigned("everyone"), case_list.ASSIGNED_ALL)
        self.assertEqual(case_list.normalize_page_size("many"), case_list.DEFAULT_PAGE_SIZE)
        self.assertEqual(case_list.normalize_offset("-5"), 0)

    def test_page_size_is_bounded(self):
        self.assertEqual(case_list.normalize_page_size("100000"), case_list.MAX_PAGE_SIZE)
        self.assertEqual(case_list.normalize_page_size("0"), 1)


class CasePaginationTests(TestCase):
    def setUp(self):
        self.cases = [case(id=f"case-{index}") for index in range(45)]

    def test_first_page_is_one_screen_and_reports_more(self):
        page, has_more = case_list.paginate(self.cases, limit=20, offset=0)
        self.assertEqual(len(page), 20)
        self.assertTrue(has_more)

    def test_last_page_reports_no_more(self):
        page, has_more = case_list.paginate(self.cases, limit=20, offset=40)
        self.assertEqual(len(page), 5)
        self.assertFalse(has_more)

    def test_paging_past_the_end_is_empty_rather_than_an_error(self):
        page, has_more = case_list.paginate(self.cases, limit=20, offset=500)
        self.assertEqual(page, [])
        self.assertFalse(has_more)


class LegalProblemFacetTests(TestCase):
    def test_options_are_the_codes_actually_present(self):
        options = case_list.legal_problem_options([
            case(legalProblemCode="63 Private Landlord/Tenant"),
            case(legalProblemCode="51 Medicaid"),
            case(legalProblemCode="63 Private Landlord/Tenant"),
            case(legalProblemCode=""),
        ])

        self.assertEqual(options, ["51 Medicaid", "63 Private Landlord/Tenant"])


class MatterStatusTests(TestCase):
    def test_a_legalserver_close_date_closes_the_case(self):
        matter = Matter.objects.create(
            external_id="26-CLOSED",
            client_name="Closed Client",
            matter_type="Eviction",
            jurisdiction="Housing Court",
            raw_payload={
                "case_disposition": "Open",
                "date_closed": {"raw_value": "2026-05-04", "text_value": "05/04/2026"},
            },
        )

        self.assertFalse(matter_is_open(matter))

    def test_an_undispositioned_matter_is_open(self):
        matter = Matter.objects.create(
            external_id="26-OPEN",
            client_name="Open Client",
            matter_type="Eviction",
            jurisdiction="Housing Court",
            raw_payload={
                "case_disposition": "Open",
                "date_closed": {"raw_value": None, "text_value": "N/A"},
                "date_opened": {"raw_value": "2026-03-08", "text_value": "03/08/2026"},
            },
        )

        self.assertTrue(matter_is_open(matter))
        self.assertTrue(matter_opened_at(matter).startswith("2026-03-08"))

    def test_a_rejected_matter_is_not_open(self):
        matter = Matter.objects.create(
            external_id="26-REJECTED",
            client_name="Rejected Client",
            matter_type="Eviction",
            jurisdiction="Housing Court",
            raw_payload={"case_disposition": "Rejected"},
        )

        self.assertFalse(matter_is_open(matter))

    def test_a_quick_case_belongs_to_the_advocate_who_created_it(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username="advocate", password="x")
        matter = Matter.objects.create(
            external_id=f"MANUAL-{user.id}-abc",
            client_name="Walk-in",
            matter_type="Housing matter",
            jurisdiction="",
            source_system="Manual",
            raw_payload={"manual_entry": True, "created_by_user_id": user.id},
        )

        payload = matter_to_dict(matter, viewer=user)

        self.assertTrue(payload["assignedToViewer"])
        self.assertTrue(payload["isOpen"])
