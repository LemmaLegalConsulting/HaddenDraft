"""Reading format facts and separating a brief from the exhibits stapled to it."""

from django.test import TestCase

from apps.argument_gym import ingestion
from apps.argument_gym.testing import build_docx, build_pdf


BRIEF_PAGE = "IN THE COURT OF COMMON PLEAS\nCase No. CV-24-001234\nMOTION TO DISMISS"
ARGUMENT_PAGE = "The notice omitted the language R.C. 1923.04 requires."
CERTIFICATE_PAGE = "CERTIFICATE OF SERVICE\nA copy was served on counsel by email."


class DocxFormattingTests(TestCase):
    def test_type_size_spacing_and_margins_are_read_from_the_file(self):
        content = build_docx(["First paragraph.", "Second paragraph."], default_size_pt=12, margins_in=1.0, line=480)
        result = ingestion.ingest_upload(content, filename="brief.docx")
        formatting = result["metadata"]["formatting"]
        self.assertEqual(formatting["bodyFontSizePt"], 12.0)
        self.assertEqual(formatting["lineSpacing"], "double")
        self.assertEqual(formatting["marginsIn"], {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0})
        self.assertEqual(formatting["fonts"][0]["family"], "Times New Roman")

    def test_single_spacing_and_a_small_type_size_are_reported_as_measured(self):
        content = build_docx(["Cramped.", "Text."], default_size_pt=10, margins_in=0.5, line=240)
        formatting = ingestion.ingest_upload(content, filename="brief.docx")["metadata"]["formatting"]
        self.assertEqual(formatting["bodyFontSizePt"], 10.0)
        self.assertEqual(formatting["lineSpacing"], "single")
        self.assertEqual(formatting["marginsIn"]["left"], 0.5)

    def test_a_docx_reports_no_page_count_rather_than_a_wrong_one(self):
        formatting = ingestion.ingest_upload(build_docx(["Text."]), filename="brief.docx")["metadata"]["formatting"]
        self.assertIsNone(formatting["countedPageCount"])
        self.assertIn("pageCount", formatting["unavailable"])


class PdfFormattingTests(TestCase):
    def test_pages_and_type_size_are_read_from_the_file(self):
        content = build_pdf([BRIEF_PAGE, ARGUMENT_PAGE], font_size=12)
        formatting = ingestion.ingest_upload(content, filename="brief.pdf")["metadata"]["formatting"]
        self.assertEqual(formatting["countedPageCount"], 2)
        self.assertEqual(formatting["bodyFontSizePt"], 12.0)
        self.assertIn("fonts", formatting["measured"])
        self.assertIn("margins", formatting["unavailable"])

    def test_a_smaller_type_size_is_read_as_what_it_is(self):
        content = build_pdf([BRIEF_PAGE], font_size=9)
        formatting = ingestion.ingest_upload(content, filename="brief.pdf")["metadata"]["formatting"]
        self.assertEqual(formatting["bodyFontSizePt"], 9.0)


class ExhibitSplitTests(TestCase):
    """A filing with exhibits attached is mostly not a brief."""

    def _pages(self, texts):
        return [{"page": index, "text": text} for index, text in enumerate(texts, start=1)]

    def test_a_certificate_of_service_ends_the_brief(self):
        split = ingestion.split_brief_and_exhibits(
            self._pages([BRIEF_PAGE, ARGUMENT_PAGE, CERTIFICATE_PAGE, "EXHIBIT A", "lease text"])
        )
        self.assertEqual(split["briefPageCount"], 3)
        self.assertIn("certificate of service", split["boundaryReason"].casefold())
        self.assertEqual([exhibit["label"] for exhibit in split["exhibits"]], ["Exhibit A"])
        self.assertEqual(split["exhibits"][0]["startPage"], 4)
        self.assertEqual(split["exhibits"][0]["endPage"], 5)

    def test_an_exhibit_cover_sheet_ends_the_brief_when_there_is_no_certificate(self):
        split = ingestion.split_brief_and_exhibits(
            self._pages([BRIEF_PAGE, ARGUMENT_PAGE, "EXHIBIT 1", "ledger", "EXHIBIT 2", "notice"])
        )
        self.assertEqual(split["briefPageCount"], 2)
        self.assertEqual([exhibit["label"] for exhibit in split["exhibits"]], ["Exhibit 1", "Exhibit 2"])

    def test_an_index_of_exhibits_inside_the_brief_does_not_end_it(self):
        split = ingestion.split_brief_and_exhibits(
            self._pages([BRIEF_PAGE, "INDEX OF EXHIBITS\nExhibit A - Lease", ARGUMENT_PAGE, CERTIFICATE_PAGE])
        )
        self.assertEqual(split["briefPageCount"], 4)

    def test_a_long_file_with_no_boundary_falls_back_to_the_page_cap(self):
        split = ingestion.split_brief_and_exhibits(self._pages([ARGUMENT_PAGE] * 60))
        self.assertEqual(split["briefPageCount"], ingestion.BRIEF_PAGE_LIMIT)
        self.assertIn("first 30 pages", split["boundaryReason"])
        self.assertTrue(split["exhibits"])

    def test_a_short_brief_with_no_exhibits_is_left_whole(self):
        split = ingestion.split_brief_and_exhibits(self._pages([BRIEF_PAGE, ARGUMENT_PAGE]))
        self.assertEqual(split["briefPageCount"], 2)
        self.assertEqual(split["exhibits"], [])

    def test_ingesting_a_filing_returns_the_brief_and_its_exhibits_separately(self):
        content = build_pdf([BRIEF_PAGE, ARGUMENT_PAGE, CERTIFICATE_PAGE, "EXHIBIT A", "The lease says rent is $900."])
        result = ingestion.ingest_upload(content, filename="filing.pdf")
        self.assertNotIn("$900", result["text"])
        self.assertEqual(len(result["exhibits"]), 1)
        self.assertIn("$900", result["exhibits"][0]["text"])
        self.assertEqual(result["exhibits"][0]["pageRange"], {"start": 4, "end": 5})
        # The page limit applies to the brief, not to what is stapled behind it.
        self.assertEqual(result["metadata"]["formatting"]["countedPageCount"], 3)

    def test_the_text_a_run_reads_is_capped_and_says_so(self):
        long_page = " ".join(["argument"] * 4000)
        content = build_pdf([long_page] * 6)
        result = ingestion.ingest_upload(content, filename="huge.pdf")
        self.assertLessEqual(len(result["text"]), ingestion.MAX_BRIEF_CHARS)
        self.assertTrue(result["metadata"]["truncated"])
