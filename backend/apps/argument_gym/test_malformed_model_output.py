"""Three ways a run died or went quiet on real filings, and the guards for them.

All three were found by running the Lexis eviction corpus through the pipeline,
not by reading the code. Each is a case where the failure looked like a result:
the run reported success, or reported a plausible short brief, or produced a
challenge that was wrong in a way nothing in the output revealed.
"""

from django.test import TestCase
from django.test.utils import override_settings

from apps.argument_gym import ingestion, record
from apps.argument_gym.pipeline import known


class KnownIdTests(TestCase):
    """A model id that is not a string must be rejected, not raise.

    Every parser rejects a claim, finding or attack whose unitId is not a real
    unit. Spelled as `claim.get("unitId") not in unit_ids`, that raises
    TypeError: unhashable type when the model answers with a list -- so the
    guard against malformed output failed on the malformed output it existed to
    catch, and killed the run with an error naming no field.
    """

    def test_a_list_where_an_id_belongs_is_rejected_rather_than_raising(self):
        # Verbatim shape from a real run: a claim spanning several units.
        self.assertFalse(known(["u3", "u7", "u11", "u12", "u15"], {"u3", "u7"}))

    def test_other_unhashable_shapes_are_rejected_too(self):
        for value in ({"u3": 1}, {"u3"}, None, 3.5):
            self.assertFalse(known(value, {"u3"}), f"{value!r} should not be a known id")

    def test_a_real_id_still_matches(self):
        self.assertTrue(known("u3", {"u3", "u7"}))
        self.assertTrue(known(7, {7, 9}))

    def test_a_string_that_is_not_a_unit_is_still_rejected(self):
        self.assertFalse(known("u99", {"u3", "u7"}))


class RecordBudgetTests(TestCase):
    """The case record must be read whole, or the run must say it was not.

    The cap was a hard-coded 6,000 characters per material, applied after every
    brief-side budget was satisfied. A 72,407-character exhibit bundle reached
    the model as 8% of itself, and the evidence a record-support test turned on
    began at character 8,692 -- so the run raised a challenge saying the record
    did not contain the notice, which was true of what it had been given and
    false of the record.
    """

    def test_the_default_budget_reads_the_corpus_record_whole(self):
        # The largest record in the local corpus, an exhibit bundle filed with a
        # forcible entry and detainer motion.
        self.assertGreaterEqual(record.share_of_budget(1), 72_407)

    def test_the_budget_is_shared_when_several_materials_are_selected(self):
        self.assertLessEqual(record.share_of_budget(6) * 6,
                             record.record_budget_chars() + 6 * record.material_floor_chars())

    def test_no_material_falls_below_the_floor(self):
        self.assertGreaterEqual(record.share_of_budget(100), record.material_floor_chars())

    @override_settings(ARGUMENT_GYM_RECORD_BUDGET_CHARS=10_000)
    def test_the_budget_is_a_setting_so_a_smaller_deployment_can_lower_it(self):
        self.assertEqual(record.share_of_budget(1), 10_000)


class ExhibitBoundaryTests(TestCase):
    """An inline exhibit reference is not the start of the attachments.

    A filed motion's page 3 began mid-sentence with "...See attached Exhibit 2."
    The splitter read that as the first exhibit and reported a 2-page brief for
    a filing whose own footer said "Page 13 of 13", classifying nine pages of
    argument as an attachment. Nothing in the run said so.
    """

    def page(self, number, text):
        return {"page": number, "text": text}

    def test_prose_citing_an_exhibit_does_not_start_the_attachments(self):
        pages = [
            self.page(1, "IN THE COURT OF COMMON PLEAS\nPLAINTIFF'S MOTION FOR SUMMARY JUDGMENT"),
            self.page(2, "MEMORANDUM IN SUPPORT\nI. PRELIMINARY STATEMENT"),
            self.page(3, "all the decedent's property he could find, valued around $2 million, was "
                        "transferred to himself, including the Cedar Road Property. See attached "
                        "Exhibit 2. The grandaughter subsequently resided there rent free.\n"
                        "Anthony died on February 22, 2020, and Letters of Authority issued."),
            self.page(4, "III. LAW AND ARGUMENT\nA. Summary judgment standard."),
            self.page(5, "CERTIFICATE OF SERVICE\nA copy of the foregoing was served by mail."),
        ]
        split = ingestion.split_brief_and_exhibits(pages)
        self.assertEqual(split["briefPageCount"], 5, split["boundaryReason"])
        self.assertEqual(split["exhibits"], [])

    def test_a_real_cover_sheet_still_starts_the_attachments(self):
        pages = [
            self.page(1, "PLAINTIFF'S MOTION FOR SUMMARY JUDGMENT"),
            self.page(2, "III. LAW AND ARGUMENT\nThe statute requires three days' notice."),
            self.page(3, "EXHIBIT A"),
            self.page(4, "NOTICE TO LEAVE PREMISES\nYou are being asked to leave the premises."),
        ]
        split = ingestion.split_brief_and_exhibits(pages)
        self.assertEqual(split["briefPageCount"], 2, split["boundaryReason"])
        self.assertEqual(len(split["exhibits"]), 1)
        self.assertEqual(split["exhibits"][0]["label"], "Exhibit A")
