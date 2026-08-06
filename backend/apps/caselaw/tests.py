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

    @override_settings(
        CASELAW_STORAGE_BACKEND="filesystem",
        CASELAW_IMPORT_APPROVE_VERIFIED_FOR_SEARCH=True,
        CASELAW_IMPORT_APPROVE_UNVERIFIED_FOR_SEARCH=False,
    )
    def test_ingestion_prefers_verified_metadata_and_copies_artifacts(self):
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
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
        self.assertTrue((self.storage / "caselaw" / "originals").exists())

    @override_settings(CASELAW_STORAGE_BACKEND="filesystem")
    def test_ingestion_is_idempotent_and_updates_verified_json(self):
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)
            verified = self.corpus / "sample-case.verified.json"
            payload = json.loads(verified.read_text(encoding="utf-8"))
            payload["judge"] = "Updated Judge"
            verified.write_text(json.dumps(payload), encoding="utf-8")
            ingest_caselaw_directory(self.corpus)

        self.assertEqual(CaseLawDecision.objects.count(), 1)
        self.assertEqual(CaseLawDecision.objects.get().judge, "Updated Judge")
        self.assertEqual(CaseLawArtifact.objects.filter(artifact_type="verified_metadata_json").count(), 1)

    @override_settings(CASELAW_STORAGE_BACKEND="filesystem")
    def test_missing_pdf_can_be_allowed(self):
        (self.corpus / "sample-case.pdf").unlink()
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
            report = ingest_caselaw_directory(self.corpus, allow_missing_pdf=True)

        self.assertEqual(len(report["imported"]), 1)
        self.assertEqual(CaseLawDecision.objects.count(), 1)
        self.assertIn("missing_pdf", report["imported"][0]["incomplete"])

    @override_settings(CASELAW_STORAGE_BACKEND="filesystem")
    def test_missing_text_creates_metadata_only_case_when_allowed(self):
        (self.corpus / "sample-case.pdf.txt").unlink()
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
            report = ingest_caselaw_directory(self.corpus, allow_missing_text=True)

        self.assertEqual(len(report["imported"]), 1)
        decision = CaseLawDecision.objects.get()
        self.assertEqual(decision.pages.count(), 0)
        self.assertTrue(decision.search_documents.exclude(document_type="ocr_chunk").exists())

    @override_settings(CASELAW_STORAGE_BACKEND="filesystem")
    def test_connector_returns_real_database_cases_with_metadata_and_jurisdiction_filter(self):
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
            ingest_caselaw_directory(self.corpus)

        results = LocalCaseIndexConnector().search("habitability repair", jurisdiction="Ohio")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Tenant v. Landlord")
        self.assertEqual(results[0].metadata["court"], "Cleveland Municipal Court Housing Division")
        self.assertEqual(results[0].metadata["treatmentStatus"], "unchecked")
        self.assertTrue(results[0].metadata["metadataVerified"])
        self.assertIn("warning", results[0].metadata)
        self.assertEqual(LocalCaseIndexConnector().search("habitability repair", jurisdiction="Michigan"), [])

    @override_settings(CASELAW_STORAGE_BACKEND="filesystem")
    def test_search_keywords_metadata_is_ingested_and_retrievable(self):
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
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

    @override_settings(CASELAW_STORAGE_BACKEND="filesystem")
    def test_decision_detail_and_artifacts_endpoints_return_json(self):
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
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

    @override_settings(CASELAW_STORAGE_BACKEND="filesystem")
    def test_case_browse_returns_facets_and_source_results(self):
        with override_settings(CASELAW_STORAGE_ROOT=self.storage):
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


class LocalCaseJurisdictionFilterTests(TestCase):
    """The matter and the corpus punctuate the same court differently.

    A matter created from LegalServer carries a jurisdiction a person typed;
    the corpus carries what the publisher wrote. Before punctuation was
    normalized, the mismatch removed local case law from the results entirely
    while the treatise -- which applies no such filter -- still returned hits,
    so a search looked like it had worked.
    """

    def setUp(self):
        decision = CaseLawDecision.objects.create(
            title="Tenant v. Landlord",
            court="Cleveland Municipal Court, Housing Division",
            county="Cuyahoga",
            jurisdiction="Ohio Municipal Court, Cuyahoga County",
            source_sha256="b" * 64,
            approved_for_search=True,
        )
        CaseLawSearchDocument.objects.create(
            decision=decision,
            document_type="holdings",
            title=decision.title,
            search_text="Rent abatement was allowed where habitability repairs went unmade.",
        )

    def _titles(self, jurisdiction):
        return [
            result.title
            for result in LocalCaseIndexConnector().search("habitability repairs", jurisdiction=jurisdiction)
        ]

    def test_court_name_punctuated_differently_still_matches(self):
        self.assertEqual(self._titles("Cleveland Municipal Court - Housing Division"), ["Tenant v. Landlord"])
        self.assertEqual(self._titles("Cleveland Municipal Court, Housing Division"), ["Tenant v. Landlord"])
        self.assertEqual(self._titles("cleveland municipal court housing division"), ["Tenant v. Landlord"])

    def test_state_and_county_forms_still_match(self):
        self.assertEqual(self._titles("Ohio"), ["Tenant v. Landlord"])
        self.assertEqual(self._titles("Cuyahoga"), ["Tenant v. Landlord"])

    def test_a_different_jurisdiction_still_excludes_the_case(self):
        self.assertEqual(self._titles("Michigan"), [])
        self.assertEqual(self._titles("Franklin County"), [])

    def test_no_jurisdiction_searches_everywhere(self):
        self.assertEqual(self._titles(""), ["Tenant v. Landlord"])
        self.assertEqual(self._titles("  -,  "), ["Tenant v. Landlord"])
