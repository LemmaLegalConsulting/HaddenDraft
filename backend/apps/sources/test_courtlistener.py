from tempfile import TemporaryDirectory

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.caselaw.models import CaseLawDecision
from apps.sources.courtlistener import CourtListenerCitationFallback
from apps.sources.connectors.local_cases import LocalCaseIndexConnector
from apps.sources.models import CourtListenerCitationCache


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class Session:
    def __init__(self, lookup, opinion):
        self.lookup = lookup
        self.opinion = opinion
        self.posts = []
        self.gets = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.lookup

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self.opinion


@override_settings(
    COURTLISTENER_API_TOKEN="test-token",
    COURTLISTENER_API_BASE_URL="https://www.courtlistener.com/api/rest/v4/",
    COURTLISTENER_API_TIMEOUT_SECONDS=3,
    ARGUMENT_GYM_COURTLISTENER_MAX_CITATIONS=2,
)
class CourtListenerFallbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        settings_override = override_settings(DOCUMENT_STORAGE_ROOT=self.storage.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def test_batches_lookup_and_fetches_one_resolved_opinion(self):
        session = Session(
            Response(
                200,
                [{
                    "status": 200,
                    "normalized_citations": ["18 F.3d 337"],
                    "clusters": [{
                        "id": 7,
                        "case_name": "Michigan Protection v. Babin",
                        "absolute_url": "/opinion/7/example/",
                        "sub_opinions": ["https://www.courtlistener.com/api/rest/v4/opinions/9/"],
                    }],
                }],
            ),
            Response(200, {"id": 9, "html_with_citations": "<p>The statute reaches interference.</p>"}),
        )
        sources, trace = CourtListenerCitationFallback(session=session).resolve([
            {"targetId": "u1:authority1", "citation": "18 F.3d 337", "proposition": "The court held broadly."}
        ])
        self.assertEqual(len(session.posts), 1)
        self.assertEqual(len(session.gets), 1)
        self.assertEqual(sources[0].metadata["targetId"], "u1:authority1")
        self.assertIn("statute reaches interference", sources[0].snippet)
        self.assertEqual(trace["resolved"], 1)

    def test_resolved_opinion_is_promoted_and_reused_without_external_request(self):
        lookup = Response(
            200,
            [{
                "status": 200,
                "normalized_citations": ["18 F.3d 337"],
                "clusters": [{
                    "id": 7,
                    "case_name": "Michigan Protection v. Babin",
                    "absolute_url": "/opinion/7/example/",
                    "sub_opinions": [9],
                }],
            }],
        )
        target = {"targetId": "u1:authority1", "citation": "18 F.3d 337", "proposition": "The holding."}
        first_session = Session(lookup, Response(200, {"id": 9, "plain_text": "The durable holding."}))
        first, _trace = CourtListenerCitationFallback(session=first_session).resolve([target])

        second_session = Session(Response(500, {}), Response(500, {}))
        second, trace = CourtListenerCitationFallback(session=second_session).resolve([target])

        self.assertEqual(len(first), 1)
        self.assertEqual(CaseLawDecision.objects.count(), 1)
        self.assertEqual(CourtListenerCitationCache.objects.get().status, "resolved")
        self.assertEqual(second[0].source_kind, "local_cases")
        self.assertTrue(second[0].metadata["persistentCache"])
        self.assertEqual(trace["resolved"], 1)
        self.assertEqual(second_session.posts, [])
        self.assertEqual(second_session.gets, [])
        self.assertEqual(LocalCaseIndexConnector().search('"18 F.3d 337"')[0].title, "Michigan Protection v. Babin")

    def test_not_found_citation_is_cached_temporarily(self):
        target = {"targetId": "u1:authority1", "citation": "999 F.3d 999", "proposition": "The holding."}
        first_session = Session(
            Response(200, [{"citation": "999 F.3d 999", "status": 404, "clusters": []}]),
            Response(500, {}),
        )
        first, _trace = CourtListenerCitationFallback(session=first_session).resolve([target])
        second_session = Session(Response(500, {}), Response(500, {}))
        second, trace = CourtListenerCitationFallback(session=second_session).resolve([target])

        cached = CourtListenerCitationCache.objects.get()
        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertEqual(cached.status, "not_found")
        self.assertIsNotNone(cached.expires_at)
        self.assertEqual(trace["requested"], 0)
        self.assertEqual(trace["negativeCacheHits"], 1)
        self.assertEqual(second_session.posts, [])

    def test_rate_limit_is_not_retried_or_reported_as_no_authority(self):
        session = Session(Response(429, {"wait_until": "later"}), Response(200, {}))
        sources, trace = CourtListenerCitationFallback(session=session).resolve([
            {"targetId": "u1:authority1", "citation": "18 F.3d 337", "proposition": "The court held broadly."}
        ])
        self.assertEqual(sources, [])
        self.assertTrue(trace["rateLimited"])
        self.assertEqual(len(session.posts), 1)
        self.assertEqual(session.gets, [])

    def test_duplicate_citation_uses_one_lookup_and_one_opinion_fetch(self):
        session = Session(
            Response(
                200,
                [{
                    "status": 200,
                    "normalized_citations": ["18 F.3d 337"],
                    "clusters": [{
                        "id": 7,
                        "case_name": "Michigan Protection v. Babin",
                        "absolute_url": "/opinion/7/example/",
                        "sub_opinions": [9],
                    }],
                }],
            ),
            Response(200, {"id": 9, "plain_text": "The relevant holding."}),
        )
        sources, _trace = CourtListenerCitationFallback(session=session).resolve([
            {"targetId": "u1:authority1", "citation": "18 F.3d 337", "proposition": "First use."},
            {"targetId": "u8:authority1", "citation": "18 F.3d 337", "proposition": "Second use."},
        ])
        self.assertEqual(len(session.posts), 1)
        self.assertEqual(len(session.gets), 1)
        self.assertEqual({source.metadata["targetId"] for source in sources}, {"u1:authority1", "u8:authority1"})

    def test_parallel_reporter_resolves_target_when_official_reporter_is_ambiguous(self):
        session = Session(
            Response(
                200,
                [
                    {
                        "start_index": 0,
                        "status": 300,
                        "clusters": [{"id": 1}, {"id": 2}],
                    },
                    {
                        "start_index": 20,
                        "status": 200,
                        "normalized_citations": ["662 N.E.2d 264"],
                        "clusters": [{
                            "id": 7,
                            "case_name": "Dresher v. Burt",
                            "absolute_url": "/opinion/7/dresher/",
                            "sub_opinions": [9],
                        }],
                    },
                ],
            ),
            Response(200, {"id": 9, "plain_text": "The movant bears the initial burden."}),
        )

        sources, trace = CourtListenerCitationFallback(session=session).resolve([{
            "targetId": "u1:authority1",
            "citation": "75 Ohio St.3d 280, 662 N.E.2d 264",
            "proposition": "The movant bears the initial burden.",
        }])

        self.assertEqual(trace["resolved"], 1)
        self.assertEqual(sources[0].title, "Dresher v. Burt")
        self.assertEqual(len(session.posts), 1)
        self.assertEqual(len(session.gets), 1)
