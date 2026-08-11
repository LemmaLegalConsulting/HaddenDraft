import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.caselaw.importing import discover_case_groups, ingest_caselaw_directory
from apps.caselaw.models import CaseLawArtifact, CaseLawDecision, CaseLawSearchDocument
from apps.sources.connectors.local_cases import LocalCaseIndexConnector


FIXTURE_ROOT = Path(__file__).parent / "tests" / "fixtures" / "sample_corpus"


class CaseLawImportTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus"
        self.storage = Path(self.tmp.name) / "storage"
        shutil.copytree(FIXTURE_ROOT, self.corpus)

    def tearDown(self):
        self.tmp.cleanup()

    def test_file_grouping_recognizes_case_sidecars(self):
        groups, total_files = discover_case_groups(self.corpus)

        self.assertEqual(total_files, 4)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group.stem, "sample-case")
        self.assertTrue(group.pdf_path.name.endswith(".pdf"))
        self.assertTrue(group.txt_path.name.endswith(".pdf.txt"))
        self.assertTrue(group.json_path.name.endswith(".pdf.json"))
        self.assertTrue(group.verified_json_path.name.endswith(".verified.json"))
        self.assertEqual(group.metadata_path, group.verified_json_path)

    def test_file_grouping_recognizes_published_artifact_layout(self):
        """The published layout must be re-ingestable.

        Published artifacts are hash-named with plain extensions and split
        across per-type directories. Recognizing only the download naming made
        every group report missing_text, which is how a 1,215-case corpus
        ingested as zero decisions.
        """
        published = Path(self.tmp.name) / "published"
        sha = "a" * 64
        for subdir, suffix in (("originals", ".pdf"), ("ocr-text", ".txt"),
                               ("metadata", ".json"), ("metadata", ".verified.json")):
            target = published / subdir / f"{sha}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"x")

        groups, total_files = discover_case_groups(published)

        self.assertEqual(total_files, 4)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group.stem, sha)
        self.assertEqual(group.incomplete_reasons(), [])
        self.assertTrue(group.txt_path.name.endswith(".txt"))
        self.assertTrue(group.json_path.name.endswith(".json"))
        self.assertEqual(group.metadata_path, group.verified_json_path)

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_overlong_metadata_values_are_truncated_not_fatal(self):
        """A verbose classification label must not cost the whole decision.

        Model-generated sidecars put sentences in fields sized for short labels,
        which dropped 17 of 1,215 cases with "value too long for type character
        varying(120)".
        """
        metadata_path = self.corpus / "sample-case.pdf.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["tenant_landlord_role"] = "Tenant/Appellant asserting habitability " * 6
        metadata["publication_status"] = "Unpublished judgment entry under App.R. 11.1(E) " * 4
        metadata_path.write_text(json.dumps(metadata))
        # The verified sidecar would otherwise take precedence over this file.
        (self.corpus / "sample-case.verified.json").unlink()

        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            report = ingest_caselaw_directory(self.corpus)

        self.assertEqual(report["failed"], [])
        self.assertEqual(len(report["imported"]), 1)
        decision = CaseLawDecision.objects.get()
        self.assertEqual(len(decision.tenant_landlord_role), 120)
        self.assertEqual(len(decision.publication_status), 80)
        self.assertTrue(decision.tenant_landlord_role.startswith("Tenant/Appellant"))

    def test_specific_sidecar_naming_wins_over_plain_extension(self):
        """A directory carrying both namings resolves to the specific one."""
        mixed = Path(self.tmp.name) / "mixed"
        mixed.mkdir(parents=True)
        (mixed / "case.pdf").write_bytes(b"x")
        (mixed / "case.pdf.txt").write_bytes(b"specific")
        (mixed / "case.txt").write_bytes(b"plain")

        groups, _ = discover_case_groups(mixed)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].txt_path.name, "case.pdf.txt")

    @override_settings(
        DOCUMENT_STORAGE_BACKEND="filesystem",
        CASELAW_IMPORT_APPROVE_VERIFIED_FOR_SEARCH=True,
        CASELAW_IMPORT_APPROVE_UNVERIFIED_FOR_SEARCH=False,
    )
    def test_ingestion_prefers_verified_metadata_and_copies_artifacts(self):
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            report = ingest_caselaw_directory(self.corpus, allow_missing_text=False)

        self.assertEqual(len(report["imported"]), 1)
        decision = CaseLawDecision.objects.get()
        self.assertEqual(decision.title, "Tenant v. Landlord")
        self.assertTrue(decision.metadata_verified)
        self.assertTrue(decision.approved_for_search)
        self.assertIn("habitability defense", decision.issues)
        self.assertEqual(decision.pages.count(), 1)
        self.assertGreater(CaseLawSearchDocument.objects.count(), 1)
        self.assertTrue(CaseLawArtifact.objects.filter(artifact_type="original_pdf").exists())
        # Derived artifacts land in the published area, never at the store root:
        # raw uploads and served files have to stay on opposite sides of it.
        self.assertTrue((self.storage / "published" / "caselaw" / "originals").exists())
        self.assertFalse((self.storage / "caselaw").exists())

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_ingestion_is_idempotent_and_updates_verified_json(self):
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)
            verified = self.corpus / "sample-case.verified.json"
            payload = json.loads(verified.read_text(encoding="utf-8"))
            payload["judge"] = "Updated Judge"
            verified.write_text(json.dumps(payload), encoding="utf-8")
            ingest_caselaw_directory(self.corpus)

        self.assertEqual(CaseLawDecision.objects.count(), 1)
        self.assertEqual(CaseLawDecision.objects.get().judge, "Updated Judge")
        self.assertEqual(CaseLawArtifact.objects.filter(artifact_type="verified_metadata_json").count(), 1)

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_missing_pdf_can_be_allowed(self):
        (self.corpus / "sample-case.pdf").unlink()
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            report = ingest_caselaw_directory(self.corpus, allow_missing_pdf=True)

        self.assertEqual(len(report["imported"]), 1)
        self.assertEqual(CaseLawDecision.objects.count(), 1)
        self.assertIn("missing_pdf", report["imported"][0]["incomplete"])

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_missing_text_creates_metadata_only_case_when_allowed(self):
        (self.corpus / "sample-case.pdf.txt").unlink()
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            report = ingest_caselaw_directory(self.corpus, allow_missing_text=True)

        self.assertEqual(len(report["imported"]), 1)
        decision = CaseLawDecision.objects.get()
        self.assertEqual(decision.pages.count(), 0)
        self.assertTrue(decision.search_documents.exclude(document_type="ocr_chunk").exists())

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_connector_returns_real_database_cases_with_metadata(self):
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)

        results = LocalCaseIndexConnector().search("habitability repair", jurisdiction="Ohio")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Tenant v. Landlord")
        self.assertEqual(results[0].metadata["court"], "Cleveland Municipal Court Housing Division")
        self.assertEqual(results[0].metadata["treatmentStatus"], "unchecked")
        self.assertTrue(results[0].metadata["metadataVerified"])
        self.assertIn("warning", results[0].metadata)

    def test_a_jurisdiction_from_elsewhere_does_not_hide_the_case(self):
        # Trial-court decisions are persuasive, not binding. Jurisdiction orders
        # them; it is the reader who narrows, and only in the result list.
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)

        results = LocalCaseIndexConnector().search("habitability repair", jurisdiction="Michigan")

        self.assertEqual([result.title for result in results], ["Tenant v. Landlord"])

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_search_keywords_metadata_is_ingested_and_retrievable(self):
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)

        decision = CaseLawDecision.objects.get()
        self.assertIn("deficient notice", decision.search_keywords)
        self.assertTrue(decision.search_documents.filter(document_type="keywords").exists())

        # The opinion text never says "deficient notice"; the researcher-phrased
        # keyword sidecar is what surfaces the case.
        results = LocalCaseIndexConnector().search("deficient notice")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Tenant v. Landlord")
        self.assertIn("deficient notice", results[0].metadata["searchKeywords"])

    def test_concept_expansion_surfaces_synonym_only_case_text(self):
        decision = CaseLawDecision.objects.create(
            title="Landlord v. Renter",
            court="Cleveland Municipal Court",
            jurisdiction="Ohio",
            source_sha256="a" * 64,
            approved_for_search=True,
        )
        CaseLawSearchDocument.objects.create(
            decision=decision,
            document_type="holdings",
            title=decision.title,
            search_text="The writ was defective because service did not comply with R.C. 1923.04.",
        )

        results = LocalCaseIndexConnector().search("deficient notice")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Landlord v. Renter")


class CaseLawApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="advocate", password="password")
        self.client.force_login(self.user)
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus"
        self.storage = Path(self.tmp.name) / "storage"
        shutil.copytree(FIXTURE_ROOT, self.corpus)

    def tearDown(self):
        self.tmp.cleanup()

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_decision_detail_and_artifacts_endpoints_return_json(self):
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)
            decision = CaseLawDecision.objects.get()

            list_response = self.client.get("/api/caselaw/decisions/")
            detail_response = self.client.get(f"/api/caselaw/decisions/{decision.id}/")
            artifacts_response = self.client.get(f"/api/caselaw/decisions/{decision.id}/artifacts/")
            pdf_response = self.client.get(f"/api/caselaw/decisions/{decision.id}/pdf/")
            similar_response = self.client.get(f"/api/caselaw/decisions/{decision.id}/similar/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(artifacts_response.status_code, 200)
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertIn("inline", pdf_response["Content-Disposition"])
        self.assertEqual(pdf_response["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(similar_response.status_code, 200)
        self.assertEqual(detail_response.json()["decision"]["title"], "Tenant v. Landlord")
        self.assertGreaterEqual(len(artifacts_response.json()["artifacts"]), 3)

    @override_settings(DOCUMENT_STORAGE_BACKEND="filesystem")
    def test_case_browse_returns_facets_and_source_results(self):
        with override_settings(DOCUMENT_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)
        decision = CaseLawDecision.objects.get()

        response = self.client.get(f"/api/caselaw/browse/?q=habitability&decisionId={decision.id}")
        facet_response = self.client.get("/api/caselaw/browse/?facet=county&value=Cuyahoga")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("county", payload["facets"])
        self.assertIn("results", payload)
        self.assertEqual(payload["seed"]["title"], "Tenant v. Landlord")
        self.assertEqual(facet_response.status_code, 200)
        self.assertGreaterEqual(facet_response.json()["totalCandidates"], 1)


class LocalCaseJurisdictionRankingTests(TestCase):
    """Where a trial-court decision was decided orders results; it never hides them.

    These are municipal and common pleas decisions -- persuasive everywhere,
    binding nowhere -- so a case from the next county over is worth reading.
    The connector used to filter them out by jurisdiction, which also meant a
    matter punctuating its court differently from the corpus
    ("Cleveland Municipal Court - Housing Division" against
    "Cleveland Municipal Court, Housing Division") lost local case law entirely
    while the treatise still answered, so the search looked like it had worked.
    """

    def setUp(self):
        self.local = self._decision(
            title="Tenant v. Cleveland Landlord",
            court="Cleveland Municipal Court, Housing Division",
            county="Cuyahoga",
            jurisdiction="Ohio Municipal Court, Cuyahoga County",
            sha="b",
        )
        self.elsewhere = self._decision(
            title="Renter v. Columbus Landlord",
            court="Franklin County Municipal Court",
            county="Franklin",
            jurisdiction="Ohio Municipal Court, Franklin County",
            sha="c",
        )

    def _decision(self, *, title, court, county, jurisdiction, sha):
        decision = CaseLawDecision.objects.create(
            title=title,
            court=court,
            county=county,
            jurisdiction=jurisdiction,
            source_sha256=sha * 64,
            approved_for_search=True,
        )
        CaseLawSearchDocument.objects.create(
            decision=decision,
            document_type="holdings",
            title=decision.title,
            search_text="Rent abatement was allowed where habitability repairs went unmade.",
        )
        return decision

    def _titles(self, jurisdiction):
        return [
            result.title
            for result in LocalCaseIndexConnector().search("habitability repairs", jurisdiction=jurisdiction)
        ]

    def test_a_case_from_another_county_is_still_returned(self):
        self.assertCountEqual(
            self._titles("Cleveland Municipal Court - Housing Division"),
            ["Tenant v. Cleveland Landlord", "Renter v. Columbus Landlord"],
        )

    def test_an_unrelated_state_does_not_hide_anything_either(self):
        self.assertCountEqual(
            self._titles("Michigan"),
            ["Tenant v. Cleveland Landlord", "Renter v. Columbus Landlord"],
        )

    def test_the_matters_own_court_leads_despite_different_punctuation(self):
        # The matter writes a hyphen where the corpus writes a comma. The two
        # cases are otherwise identical in text, so only the jurisdiction
        # nudge can decide the order.
        self.assertEqual(self._titles("Cleveland Municipal Court - Housing Division")[0], "Tenant v. Cleveland Landlord")
        self.assertEqual(self._titles("Franklin County Municipal Court")[0], "Renter v. Columbus Landlord")
        self.assertEqual(self._titles("Cuyahoga")[0], "Tenant v. Cleveland Landlord")

    def test_results_carry_the_court_and_county_the_reader_narrows_by(self):
        results = LocalCaseIndexConnector().search("habitability repairs", jurisdiction="Ohio")
        courts = {result.metadata["court"] for result in results}
        self.assertEqual(courts, {"Cleveland Municipal Court, Housing Division", "Franklin County Municipal Court"})
        self.assertEqual({result.metadata["county"] for result in results}, {"Cuyahoga", "Franklin"})

    def test_a_deeper_pool_is_returned_than_other_sources_so_it_can_be_narrowed(self):
        self.assertGreater(LocalCaseIndexConnector.limit_multiplier, 1)


class CaseLawCatalogTests(TestCase):
    """Browsing the corpus without a question in hand.

    Search answers "what is on point"; the catalog answers "what is in here",
    so it has to page the whole approved corpus and count facets against
    everything else the reader has already narrowed by.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="browser", password="password")
        self.client.force_login(self.user)
        self._decision(
            title="Tenant v. Cleveland Landlord",
            county="Cuyahoga County",
            judge="Judge Raymond L. Pianka",
            decision_date=date(2015, 4, 1),
            statutes=["Ohio Rev. Code § 1923.04"],
            sha="a",
        )
        self._decision(
            title="Renter v. Cleveland Owner",
            county="Cuyahoga",
            judge="Raymond L. Pianka",
            decision_date=date(2016, 6, 2),
            statutes=["Ohio Rev. Code § 5321.04"],
            sha="b",
        )
        self._decision(
            title="Occupant v. Columbus Landlord",
            county="Franklin County",
            judge="W. David Branstool",
            decision_date=date(2016, 8, 3),
            statutes=["Ohio Rev. Code § 1923.04"],
            sha="c",
        )

    def _decision(self, *, title, county, judge, decision_date, statutes, sha):
        return CaseLawDecision.objects.create(
            title=title,
            county=county,
            judge=judge,
            court="Municipal Court",
            decision_date=decision_date,
            statutes_cited=statutes,
            key_facts="Rent was withheld over unmade repairs.",
            source_sha256=sha * 64,
            approved_for_search=True,
        )

    def test_catalog_lists_the_whole_corpus_with_facet_counts(self):
        payload = self.client.get("/api/caselaw/catalog/").json()

        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["corpusTotal"], 3)
        self.assertEqual(len(payload["results"]), 3)
        self.assertEqual(
            {item["value"]: item["count"] for item in payload["facets"]["decisionYear"]},
            {"2016": 2, "2015": 1},
        )
        self.assertEqual(payload["facets"]["statute"][0]["value"], "Ohio Rev. Code § 1923.04")

    def test_one_county_spelled_two_ways_is_one_shelf(self):
        # The metadata came out of documents, so "Cuyahoga" and "Cuyahoga
        # County" are the same county written twice; splitting them would hide
        # a case from a reader who narrowed correctly.
        counties = {item["value"]: item["count"] for item in self.client.get("/api/caselaw/catalog/").json()["facets"]["county"]}
        narrowed = self.client.get("/api/caselaw/catalog/?county=Cuyahoga").json()

        self.assertEqual(counties, {"Cuyahoga County": 2, "Franklin County": 1})
        self.assertEqual(narrowed["total"], 2)
        # One judge, written with and without the honorific, is likewise one
        # entry -- labelled with a spelling that appears in the documents.
        self.assertEqual(len(narrowed["facets"]["judge"]), 1)
        self.assertEqual(narrowed["facets"]["judge"][0]["count"], 2)
        self.assertIn("Raymond L. Pianka", narrowed["facets"]["judge"][0]["value"])

    def test_facets_combine_and_alternatives_within_one_facet_stay_countable(self):
        both_years = self.client.get("/api/caselaw/catalog/?decisionYear=2015&decisionYear=2016").json()
        crossed = self.client.get("/api/caselaw/catalog/?decisionYear=2016&county=Franklin County").json()

        self.assertEqual(both_years["total"], 3)
        self.assertEqual(crossed["total"], 1)
        self.assertEqual(crossed["results"][0]["title"], "Occupant v. Columbus Landlord")
        # The year counts are still measured against the county narrowing, but
        # not against the year narrowing itself, so the other year is offered
        # with the number of cases it would actually show.
        self.assertEqual(
            {item["value"]: item["count"] for item in crossed["facets"]["decisionYear"]},
            {"2016": 1},
        )

    def test_paging_and_sorting_cover_the_corpus_in_a_stated_order(self):
        newest = self.client.get("/api/caselaw/catalog/?limit=2").json()
        oldest = self.client.get("/api/caselaw/catalog/?sort=oldest&limit=2&offset=2").json()

        self.assertEqual([item["title"] for item in newest["results"]], ["Occupant v. Columbus Landlord", "Renter v. Cleveland Owner"])
        self.assertEqual(newest["total"], 3)
        self.assertEqual([item["title"] for item in oldest["results"]], ["Occupant v. Columbus Landlord"])
        self.assertEqual(oldest["offset"], 2)

    def test_a_query_narrows_the_catalog_and_its_facets_together(self):
        payload = self.client.get("/api/caselaw/catalog/?q=columbus").json()

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["corpusTotal"], 3)
        self.assertEqual({item["value"] for item in payload["facets"]["county"]}, {"Franklin County"})


class DecisionDateScanningTests(TestCase):
    """Reading dates out of scanned trial-court paper.

    OCR of this corpus splits digits, drops punctuation, and stamps dates in
    orders no prose uses. A date that cannot be found in the text is not thereby
    wrong -- it is unconfirmable, which the reader has to be told.
    """

    def test_the_orders_a_court_writes_dates_in_are_all_read(self):
        from apps.caselaw.dates import scan_dates

        found = {item["matchedText"]: item["value"] for item in scan_dates(
            "Decided March 9, 2005. Hearing was 4/26/2006. Entry 2009-02-17. "
            "Signed this 3rd day of June 2013."
        )}

        self.assertEqual(found["March 9, 2005"], date(2005, 3, 9))
        self.assertEqual(found["4/26/2006"], date(2006, 4, 26))
        self.assertEqual(found["2009-02-17"], date(2009, 2, 17))
        self.assertEqual(found["3rd day of June 2013"], date(2013, 6, 3))

    def test_a_clerks_file_stamp_is_read_despite_the_scan_splitting_it(self):
        # "2009 FEB 17 PM 2:47" is where a trial-court date actually lives, and
        # the scan routinely puts a space through the day.
        from apps.caselaw.dates import scan_dates

        stamped = scan_dates("CUYAHOGA CTY. MUN. COURT 2009 FEB 17 PH 2:47 FILED")
        split_day = scan_dates("EARLE B. TURNER, CLERK MAR 1 6 2005 RECEIVED")

        self.assertEqual(stamped[0]["value"], date(2009, 2, 17))
        self.assertEqual(stamped[0]["kind"], "file-stamp")
        # A bare stamp carries no label word, but its shape says "filed".
        self.assertEqual(stamped[0]["label"], "filed")
        self.assertEqual(split_day[0]["value"], date(2005, 3, 16))

    def test_the_wording_around_a_date_is_kept_because_dates_look_alike(self):
        from apps.caselaw.dates import scan_dates

        scanned = {item["value"]: item["label"] for item in scan_dates(
            "The matter came on for hearing on August 12, 1991. "
            "Journalized October 25, 1991. Served on the tenant November 1, 1991."
        )}

        self.assertEqual(scanned[date(1991, 8, 12)], "hearing")
        self.assertEqual(scanned[date(1991, 10, 25)], "entry")
        self.assertEqual(scanned[date(1991, 11, 1)], "service")

    def test_nonsense_that_looks_like_a_date_is_not_one(self):
        from apps.caselaw.dates import scan_dates

        self.assertEqual(scan_dates("Case No. 13/45/2001 and 2005-19-40"), [])
        self.assertEqual(scan_dates(""), [])
        self.assertEqual(scan_dates(None), [])

    def test_one_date_is_reported_once_however_many_patterns_could_read_it(self):
        from apps.caselaw.dates import scan_dates

        self.assertEqual(len(scan_dates("Decided March 9, 2005.")), 1)

    def test_corroboration_returns_the_passage_that_supports_a_date(self):
        from apps.caselaw.dates import corroborate

        supported = corroborate(date(2005, 3, 9), "DATE: March 9, 2005 CASE NO.: 2004 CVG 28660")
        unsupported = corroborate(date(1996, 2, 1), "The hearing was held December 7, 1995.")

        self.assertIn("March 9, 2005", supported["snippet"])
        self.assertEqual(supported["label"], "dated")
        self.assertIsNone(unsupported)


class DecisionDateImportTests(TestCase):
    """Dates reach the database, and each one says where it came from.

    ``as_date`` was a stub returning None for every value, so every date field
    imported empty and the corpus looked like documents without dates.
    """

    def test_sidecar_date_formats_all_parse(self):
        from apps.caselaw.importing import as_date

        self.assertEqual(as_date("1991-10-25"), date(1991, 10, 25))
        self.assertEqual(as_date("10/25/1991"), date(1991, 10, 25))
        self.assertEqual(as_date("October 25, 1991"), date(1991, 10, 25))
        self.assertEqual(as_date("Oct 25, 1991"), date(1991, 10, 25))
        self.assertEqual(as_date(date(1991, 10, 25)), date(1991, 10, 25))
        self.assertIsNone(as_date(""))
        self.assertIsNone(as_date(None))
        self.assertIsNone(as_date("sometime in 1991"))

    def test_a_hearing_date_written_as_argued_or_submitted_still_parses(self):
        # Appellate reporters write "Argued April 18, 2005" rather than the
        # bare date; the verb is not part of the date.
        from apps.caselaw.importing import as_date

        self.assertEqual(as_date("Argued April 18, 2005"), date(2005, 4, 18))
        self.assertEqual(as_date("Submitted October 8, 2008"), date(2008, 10, 8))
        self.assertEqual(as_date("Decided Jan. 16, 1978"), date(1978, 1, 16))

    def test_a_month_only_date_is_left_unparsed_rather_than_guessing_a_day(self):
        # "1883-01" and "1891" are the precision the reporter actually gives;
        # inventing a day would assert something the source does not support.
        from apps.caselaw.importing import as_date

        self.assertIsNone(as_date("1883-01"))
        self.assertIsNone(as_date("1891"))

    def test_a_field_holding_two_hearing_dates_takes_the_first_and_keeps_both(self):
        # A document with two hearings produces "1991-08-12; 1991-08-20". The
        # column takes one date; the wording is preserved in the provenance row.
        from apps.caselaw.dates import record_date_provenance
        from apps.caselaw.importing import as_date

        decision = CaseLawDecision.objects.create(title="Two hearings", source_sha256="d" * 64)
        rows = record_date_provenance(
            decision,
            {"hearing_date": "1991-08-12; 1991-08-20"},
            text="The matter was heard August 12, 1991.",
        )

        self.assertEqual(as_date("1991-08-12; 1991-08-20"), date(1991, 8, 12))
        self.assertEqual(rows[0].value, date(1991, 8, 12))
        self.assertEqual(rows[0].raw_value, "1991-08-12; 1991-08-20")

    def test_provenance_records_whether_the_document_itself_shows_the_date(self):
        from apps.caselaw.dates import record_date_provenance

        decision = CaseLawDecision.objects.create(title="Provenance", source_sha256="e" * 64)
        rows = {row.field: row for row in record_date_provenance(
            decision,
            {"decision_date": "2005-03-09", "filed_date": "1996-02-01"},
            source_key="caselaw/metadata/abc.json",
            source_sha256="abc123",
            text="DATE: March 9, 2005 CASE NO.: 2004 CVG 28660",
        )}

        self.assertTrue(rows["decision_date"].corroborated)
        self.assertEqual(rows["decision_date"].matched_text, "March 9, 2005")
        self.assertEqual(rows["decision_date"].source_key, "caselaw/metadata/abc.json")
        self.assertEqual(rows["decision_date"].source_sha256, "abc123")
        self.assertIn("March 9, 2005", rows["decision_date"].snippet)
        # The filed date is in the sidecar but not in the text. It is still
        # recorded, marked as unconfirmed rather than dropped or asserted.
        self.assertFalse(rows["filed_date"].corroborated)
        self.assertEqual(rows["filed_date"].value, date(1996, 2, 1))
        self.assertEqual(rows["filed_date"].snippet, "")

    def test_re_recording_replaces_rows_rather_than_accumulating_them(self):
        from apps.caselaw.dates import record_date_provenance
        from apps.caselaw.models import CaseLawDateProvenance

        decision = CaseLawDecision.objects.create(title="Rerun", source_sha256="f" * 64)
        record_date_provenance(decision, {"decision_date": "2005-03-09"}, text="")
        record_date_provenance(decision, {"decision_date": "2006-04-26"}, text="")

        rows = CaseLawDateProvenance.objects.filter(decision=decision)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().value, date(2006, 4, 26))

    def test_the_recorded_passage_is_the_one_that_fits_the_field(self):
        # The same date can appear as a hearing mention and as the entry. The
        # snippet a reader is shown should be the supporting passage, not
        # whichever occurrence happened to come first in the scan.
        from apps.caselaw.dates import record_date_provenance

        decision = CaseLawDecision.objects.create(title="Two mentions", source_sha256="a1" * 32)
        rows = {row.field: row for row in record_date_provenance(
            decision,
            {"decision_date": "1989-03-06"},
            text=(
                "The hearing previously scheduled for Monday, March 6, 1989, was cancelled. "
                "This cause was decided March 6, 1989 upon the pleadings."
            ),
        )}

        self.assertEqual(rows["decision_date"].context_label, "decided")
        self.assertIn("decided", rows["decision_date"].snippet)


class CapCitationTests(TestCase):
    """Resolving a citation-only record against the Caselaw Access Project.

    A citation is not nothing -- it confirms a cited case exists -- but the
    opinion is what can be read and quoted. These cover the parsing and matching
    rules; the network is never touched.
    """

    def test_reporters_this_corpus_cites_map_to_the_right_bulk_directory(self):
        from apps.caselaw.cap import parse_citation

        self.assertEqual(parse_citation("104 Ohio St. 372"), {
            "citation": "104 Ohio St. 372", "reporter": "ohio-st", "volume": "104", "page": "372",
        })
        self.assertEqual(parse_citation("126 Ohio Misc.2d 84")["reporter"], "ohio-misc-2d")
        self.assertEqual(parse_citation("109 Ohio App.3d 401")["reporter"], "ohio-app-3d")
        self.assertEqual(parse_citation("87 B.R. 14")["reporter"], "br")
        self.assertEqual(parse_citation("701 F.2d 1093")["reporter"], "f2d")
        # Spacing varies in the corpus and must not change the reporter.
        self.assertEqual(parse_citation("62 Ohio St. 3d 24")["reporter"], "ohio-st-3d")

    def test_a_citation_that_cannot_be_resolved_says_so_rather_than_guessing(self):
        from apps.caselaw.cap import parse_citation

        # A reporter CAP does not publish must not be mapped to a near neighbour.
        self.assertIsNone(parse_citation("2019 WL 12345"))
        self.assertIsNone(parse_citation("No. 87-CVG-06464"))
        self.assertIsNone(parse_citation("123 Fictional Rep. 4"))
        self.assertIsNone(parse_citation(""))
        self.assertIsNone(parse_citation(None))

    def test_the_citation_decides_the_case_not_the_page_number(self):
        # Page matching alone picks the wrong case where a volume's numbering
        # restarts, so the citation is matched first.
        from apps.caselaw.cap import find_case

        cases = [
            {"first_page": 372, "citations": [{"cite": "104 Ohio St. 999"}], "file_name": "wrong"},
            {"first_page": 999, "citations": [{"cite": "104 Ohio St. 372"}], "file_name": "right"},
        ]
        parsed = {"citation": "104 Ohio St. 372", "page": "372", "reporter": "ohio-st", "volume": "104"}

        self.assertEqual(find_case(cases, parsed)["file_name"], "right")

    def test_the_first_page_still_matches_when_the_cite_is_written_differently(self):
        from apps.caselaw.cap import find_case

        cases = [{"first_page": 372, "citations": [{"cite": "104 OhioSt 372"}], "file_name": "spaced"}]
        parsed = {"citation": "104 Ohio St. 372", "page": "372", "reporter": "ohio-st", "volume": "104"}

        self.assertEqual(find_case(cases, parsed)["file_name"], "spaced")

    def test_the_opinion_text_keeps_the_head_matter_and_every_opinion(self):
        from apps.caselaw.cap import opinion_text

        text = opinion_text({"casebody": {
            "head_matter": "Ketcham v. Miller. Syllabus by the Court.",
            "opinions": [
                {"author": "Robinson, J.", "text": "The amended petition alleges title."},
                {"author": "Wanamaker, J.", "text": "I dissent."},
            ],
        }})

        self.assertIn("Syllabus by the Court", text)
        self.assertIn("Robinson, J.", text)
        self.assertIn("I dissent.", text)

    def test_a_fetched_case_carries_its_source_and_an_unchecked_treatment_note(self):
        from apps.caselaw.cap import case_metadata

        metadata = case_metadata(
            {
                "id": 12345,
                "name": "Ketcham v. Miller et al.",
                "name_abbreviation": "Ketcham v. Miller",
                "decision_date": "1922-04-11",
                "citations": [{"cite": "104 Ohio St. 372"}, {"cite": "135 N.E. 536"}],
                "court": {"name": "Supreme Court of Ohio"},
                "jurisdiction": {"name_long": "Ohio"},
                "casebody": {"judges": ["Robinson, J."]},
            },
            {"citation": "104 Ohio St. 372", "reporter": "ohio-st", "volume": "104", "page": "372"},
            source_url="https://static.case.law/ohio-st/104/cases/0372-01.json",
        )

        self.assertEqual(metadata["decision_date"], "1922-04-11")
        self.assertEqual(metadata["citation_string"], "104 Ohio St. 372")
        self.assertEqual(metadata["parallel_citations"], ["135 N.E. 536"])
        self.assertEqual(metadata["external_source_id"], "cap:12345")
        self.assertEqual(metadata["metadata_source"], "caselaw_access_project")
        self.assertIn("static.case.law", metadata["source_url"])
        # Nothing fetched here has had its currentness checked.
        self.assertEqual(metadata["treatment_status"], "unchecked")
        self.assertIn("not been checked", metadata["treatment_notes"])

    def test_resolution_reports_each_way_a_lookup_can_come_up_empty(self):
        from apps.caselaw.cap import CapClient

        volume = json.dumps([{"first_page": 372, "citations": [{"cite": "104 Ohio St. 372"}], "file_name": "0372-01"}]).encode()
        case = json.dumps({"id": 1, "name": "Ketcham v. Miller", "casebody": {"opinions": [{"text": "Opinion."}]}}).encode()

        def opener(url):
            if url.endswith("CasesMetadata.json"):
                return volume if "/104/" in url else None
            if url.endswith("cases/0372-01.json"):
                return case
            return None

        client = CapClient(opener=opener)
        self.assertEqual(client.resolve("104 Ohio St. 372")["status"], "found")
        self.assertEqual(client.resolve("999 Ohio St. 372")["status"], "volume_not_published")
        self.assertEqual(client.resolve("104 Ohio St. 5")["status"], "case_not_in_volume")
        self.assertEqual(client.resolve("2019 WL 1")["status"], "unparsed_citation")

    def test_a_volume_index_is_fetched_once_however_many_citations_need_it(self):
        from apps.caselaw.cap import CapClient

        calls = []
        volume = json.dumps([
            {"first_page": 372, "citations": [{"cite": "104 Ohio St. 372"}], "file_name": "0372-01"},
            {"first_page": 400, "citations": [{"cite": "104 Ohio St. 400"}], "file_name": "0400-01"},
        ]).encode()

        def opener(url):
            calls.append(url)
            if url.endswith("CasesMetadata.json"):
                return volume
            return json.dumps({"id": 1, "casebody": {"opinions": [{"text": "Opinion."}]}}).encode()

        client = CapClient(opener=opener)
        client.resolve("104 Ohio St. 372")
        client.resolve("104 Ohio St. 400")

        self.assertEqual(sum(1 for url in calls if url.endswith("CasesMetadata.json")), 1)


class CaselawMetadataEnrichmentTests(TestCase):
    """Summarizing a fetched opinion the way the rest of the corpus was summarized.

    One model drafts, a second checks it against the text, and a marker records
    that the second pass happened. What a reporter already stated is not up for
    revision by either of them.
    """

    def _sidecar(self):
        return {
            "title": "Ketcham v. Miller et al.",
            "citation_string": "104 Ohio St. 372",
            "decision_date": "1922-04-11",
            "court": "Supreme Court of Ohio",
            "external_source_id": "cap:12345",
            "source_url": "https://static.case.law/ohio-st/104/cases/0372-01.json",
            "key_facts": "",
        }

    def test_reporter_facts_are_offered_to_the_model_as_facts(self):
        from apps.caselaw.management.commands.enrich_caselaw_metadata import known_facts

        facts = known_facts(self._sidecar())

        self.assertEqual(facts["citation_string"], "104 Ohio St. 372")
        self.assertEqual(facts["decision_date"], "1922-04-11")
        # An empty field is not a fact to repeat.
        self.assertNotIn("key_facts", facts)

    def test_a_summarizer_cannot_overwrite_what_the_reporter_printed(self):
        from apps.caselaw.management.commands.enrich_caselaw_metadata import merge

        merged = merge(self._sidecar(), {
            "decision_date": "1922-04-12",
            "citation_string": "104 Ohio St. 999",
            "title": "Ketcham versus Miller",
            "key_facts": "The amended petition alleged execution of a lease.",
            "issues": ["Whether the petition sounds in contract or in tort."],
        })

        self.assertEqual(merged["decision_date"], "1922-04-11")
        self.assertEqual(merged["citation_string"], "104 Ohio St. 372")
        self.assertEqual(merged["title"], "Ketcham v. Miller et al.")
        # The analysis is exactly what the pipeline is for, and it is kept.
        self.assertIn("amended petition", merged["key_facts"])
        self.assertEqual(len(merged["issues"]), 1)

    def test_fields_outside_the_schema_are_not_smuggled_in(self):
        from apps.caselaw.management.commands.enrich_caselaw_metadata import merge

        merged = merge(self._sidecar(), {"approved_for_search": True, "source_sha256": "x" * 64})

        self.assertNotIn("approved_for_search", merged)
        self.assertNotIn("source_sha256", merged)

    def test_a_model_that_wraps_its_json_in_prose_or_fences_is_still_read(self):
        from apps.caselaw.management.commands.enrich_caselaw_metadata import _json_object

        self.assertEqual(_json_object('```json\n{"issues": ["a"]}\n```')["issues"], ["a"])
        self.assertEqual(_json_object('Here it is:\n{"issues": ["b"]}\nHope that helps.')["issues"], ["b"])
        with self.assertRaises(ValueError):
            _json_object("I could not determine the metadata.")
        with self.assertRaises(ValueError):
            _json_object('["not", "an", "object"]')

    def test_a_page_pincite_written_with_at_is_still_a_citation(self):
        # "175 Ohio St. at 130" is how a citation reads when it is quoted from
        # within a paragraph rather than typed as a standalone cite; "at" is
        # not part of the reporter name.
        from apps.caselaw.cap import parse_citation

        self.assertEqual(parse_citation("175 Ohio St. at 130"), parse_citation("175 Ohio St. 130"))
