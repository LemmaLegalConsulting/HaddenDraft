import json
import shutil
import tempfile
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
