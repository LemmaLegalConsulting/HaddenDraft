"""Rate-bounded CourtListener fallback for unresolved case citations."""

from dataclasses import replace
from datetime import timedelta
import hashlib
from html import unescape
import re
from urllib.parse import urljoin, urlsplit

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone
from django.utils.html import strip_tags
from eyecite import get_citations
import requests

from apps.sources.connectors.base import SourceResult


TEXT_FIELDS = (
    "plain_text",
    "html_with_citations",
    "html_lawbox",
    "html",
    "html_columbia",
    "xml_harvard",
)
MAX_CLUSTER_OPINIONS = 4


def _canonical_citations(value):
    citations = []
    for citation in get_citations(str(value or "")):
        corrected = getattr(citation, "corrected_citation", lambda: "")()
        if corrected:
            citations.append(corrected)
    return list(dict.fromkeys(citations))


def _citation_key(value):
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _case_priority(target):
    proposition = str(target.get("proposition") or "").casefold()
    material = bool(re.search(r"\b(?:hold|held|found|require|establish|provide|rule|standard)\w*\b", proposition))
    reporter = bool(re.search(r"\b\d+\s+[A-Z][A-Za-z.\d ]+\s+\d+", str(target.get("citation") or "")))
    return (material, reporter, -len(proposition), target.get("targetId", ""))


def _opinion_url(value, base_url):
    if isinstance(value, dict):
        value = value.get("resource_uri") or value.get("url") or value.get("id")
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        value = f"opinions/{value}/"
    if not value:
        return ""
    url = urljoin(base_url, str(value))
    return url if urlsplit(url).hostname == urlsplit(base_url).hostname else ""


def _source_from_cache(value, target_id):
    metadata = {**value.get("metadata", {}), "cacheHit": True, "targetId": target_id}
    return SourceResult(**{**value, "metadata": metadata})


def _relevant_excerpt(text, proposition, limit=12000):
    if len(text) <= limit:
        return text
    terms = {
        term.casefold()
        for term in re.findall(r"[A-Za-z]{6,}", str(proposition or ""))
        if term.casefold() not in {"plaintiff", "defendant", "appellant", "appellee", "court", "statute"}
    }
    lowered = text.casefold()
    starts = [0]
    for term in sorted(terms, key=len, reverse=True):
        position = lowered.find(term)
        if position >= 0 and all(abs(position - prior) > 1200 for prior in starts):
            starts.append(max(0, position - 800))
        if len(starts) >= 7:
            break
    chunks = [text[start : start + 1700] for start in starts]
    return " … ".join(chunks)[:limit]


class CourtListenerCitationFallback:
    """Resolve a prioritized batch only after local lookup misses."""

    def __init__(self, *, session=None):
        self.session = session or requests.Session()
        self.base_url = settings.COURTLISTENER_API_BASE_URL.rstrip("/") + "/"
        self.token = settings.COURTLISTENER_API_TOKEN
        self.limit = settings.ARGUMENT_GYM_COURTLISTENER_MAX_CITATIONS
        self.timeout = settings.COURTLISTENER_API_TIMEOUT_SECONDS

    @property
    def enabled(self):
        return bool(self.token and self.limit > 0)

    def _headers(self):
        return {"Authorization": f"Token {self.token}"}

    def resolve(self, targets):
        if not self.enabled:
            return [], {"method": "off", "requested": 0, "resolved": 0}
        grouped = {}
        for target in sorted(targets, key=_case_priority, reverse=True):
            grouped.setdefault(target["citation"].casefold(), []).append(target)
        selected_groups = list(grouped.values())[: self.limit]
        ranked = [target for group in selected_groups for target in group]
        results, pending_by_key = [], {}
        persistent_hits = 0
        negative_cache_hits = 0
        for target in ranked:
            persistent, complete = self._persistent_result(target)
            if persistent:
                results.append(persistent)
                persistent_hits += 1
                continue
            if complete:
                negative_cache_hits += 1
                continue
            digest = hashlib.sha256(target["citation"].casefold().encode("utf-8")).hexdigest()
            key = f"argument-gym:courtlistener:{digest}"
            cached = cache.get(key)
            if cached:
                results.append(_source_from_cache(cached, target["targetId"]))
            else:
                pending_by_key.setdefault(key, []).append(target)
        pending = [(group[0], key, group) for key, group in pending_by_key.items()]
        trace = {
            "method": "courtlistener_v4",
            "considered": len(selected_groups),
            "requested": len(pending),
            "resolved": len(results),
            "persistentHits": persistent_hits,
            "negativeCacheHits": negative_cache_hits,
            "rateLimited": False,
        }
        if not pending:
            return results, trace
        lookup_text = "\n".join(target["citation"] for target, _key, _group in pending)
        try:
            response = self.session.post(
                urljoin(self.base_url, "citation-lookup/"),
                headers=self._headers(),
                data={"text": lookup_text},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            trace["error"] = type(exc).__name__
            return results, trace
        if response.status_code == 429:
            trace["rateLimited"] = True
            return results, trace
        if response.status_code != 200:
            trace["error"] = f"http_{response.status_code}"
            return results, trace
        try:
            lookups = response.json()
        except ValueError:
            trace["error"] = "invalid_json"
            return results, trace
        lookups_by_target = self._associate_lookups(pending, lookups)
        for (target, key, group), target_lookups in zip(pending, lookups_by_target):
            combined_target = {
                **target,
                "proposition": "\n".join(item.get("proposition", "") for item in group),
            }
            source = self._resolved_source(combined_target, target_lookups)
            if source is None:
                self._remember_unresolved(combined_target, target_lookups)
                continue
            cached = {**source.__dict__, "metadata": {**source.metadata, "targetId": ""}}
            cache.set(key, cached, 604800)
            results.extend(
                replace(source, metadata={**source.metadata, "targetId": item["targetId"]})
                for item in group
            )
        trace["resolved"] = len(results)
        return results, trace

    def _persistent_result(self, target):
        aliases = _canonical_citations(target.get("citation"))
        if not aliases:
            return None, False
        try:
            from apps.sources.models import CourtListenerCitationCache

            rows = list(
                CourtListenerCitationCache.objects.select_related("decision").filter(
                    citation_key__in=[_citation_key(alias) for alias in aliases]
                )
            )
        except DatabaseError:
            return None, False
        now = timezone.now()
        for row in rows:
            if row.status != "resolved" or not row.decision_id:
                continue
            # Early cache entries stored only the first sub-opinion and cannot
            # support majority/dissent attribution. Refresh them once; current
            # entries record the complete bounded opinion-id list.
            if "opinionIds" not in (row.provider_payload or {}):
                continue
            text = "\n".join(row.decision.pages.values_list("text", flat=True))
            if not text:
                text = "\n".join(row.decision.chunks.values_list("text", flat=True))
            if not text:
                continue
            return SourceResult(
                id=f"local-case:{row.decision_id}",
                title=row.decision.title,
                citation=row.decision.citation_string or row.citation,
                snippet=_relevant_excerpt(text, target.get("proposition")),
                source_kind="local_cases",
                source_label="Local case law (originally CourtListener)",
                url=f"/api/caselaw/decisions/{row.decision_id}/",
                metadata={
                    "provider": "Free Law Project",
                    "decisionId": row.decision_id,
                    "targetId": target["targetId"],
                    "persistentCache": True,
                },
            ), True
        current = {
            row.citation_key
            for row in rows
            if row.status in {"not_found", "ambiguous"} and row.expires_at and row.expires_at > now
        }
        return None, all(_citation_key(alias) in current for alias in aliases)

    def _remember_unresolved(self, target, lookups):
        aliases = _canonical_citations(target.get("citation"))
        by_citation = {
            canonical: lookup
            for lookup in lookups
            for canonical in _canonical_citations(lookup.get("citation") or "")
        }
        try:
            from apps.sources.models import CourtListenerCitationCache

            for alias in aliases:
                lookup = by_citation.get(alias, {})
                status = "ambiguous" if lookup.get("status") == 300 else "not_found"
                days = (
                    settings.COURTLISTENER_AMBIGUOUS_CACHE_DAYS
                    if status == "ambiguous"
                    else settings.COURTLISTENER_NOT_FOUND_CACHE_DAYS
                )
                CourtListenerCitationCache.objects.update_or_create(
                    citation_key=_citation_key(alias),
                    defaults={
                        "citation": alias,
                        "status": status,
                        "decision": None,
                        "provider_payload": {
                            "status": lookup.get("status"),
                            "error_message": lookup.get("error_message", ""),
                            "cluster_ids": [item.get("id") for item in lookup.get("clusters") or []],
                        },
                        "expires_at": timezone.now() + timedelta(days=days),
                    },
                )
        except DatabaseError:
            return

    @staticmethod
    def _associate_lookups(pending, lookups):
        """Map parsed citations back to their input line, including parallels."""
        spans = []
        cursor = 0
        for target, _key, _group in pending:
            end = cursor + len(target["citation"])
            spans.append((cursor, end))
            cursor = end + 1
        associated = [[] for _item in pending]
        positioned = all(isinstance(item, dict) and isinstance(item.get("start_index"), int) for item in lookups)
        if positioned:
            for lookup in lookups:
                position = lookup["start_index"]
                for index, (start, end) in enumerate(spans):
                    if start <= position <= end:
                        associated[index].append(lookup)
                        break
            return associated
        # Compatibility for older/fake API responses that omitted offsets.
        for index, lookup in enumerate(lookups[: len(associated)]):
            associated[index].append(lookup)
        return associated

    def _resolved_source(self, target, lookups):
        # A full citation can yield an ambiguous official reporter row followed
        # by a uniquely resolved parallel reporter row. Prefer the latter.
        lookup = next(
            (
                item
                for item in lookups
                if item.get("status") == 200 and len(item.get("clusters") or []) == 1
            ),
            None,
        )
        if lookup is None:
            return None
        clusters = lookup.get("clusters") or []
        cluster = clusters[0]
        opinions = (cluster.get("sub_opinions") or cluster.get("opinions") or [])[:MAX_CLUSTER_OPINIONS]
        opinion_payloads = []
        opinion_texts = []
        for opinion_ref in opinions:
            opinion_url = _opinion_url(opinion_ref, self.base_url)
            if not opinion_url:
                continue
            try:
                response = self.session.get(
                    opinion_url, headers=self._headers(), timeout=self.timeout,
                )
            except requests.RequestException:
                continue
            # Do not retry or spend more of the low request budget after a rate
            # limit. Any already fetched opinion remains cacheable.
            if response.status_code == 429:
                break
            if response.status_code != 200:
                continue
            try:
                opinion = response.json()
            except ValueError:
                continue
            raw = next((opinion.get(field) for field in TEXT_FIELDS if opinion.get(field)), "")
            text = re.sub(r"\s+", " ", unescape(strip_tags(str(raw)))).strip()
            if text:
                opinion_payloads.append(opinion)
                opinion_texts.append(text)
        if not opinion_texts:
            return None
        opinion = opinion_payloads[0]
        text = "\n\n".join(opinion_texts)
        cluster_id = str(cluster.get("id") or "")
        normalized = list(dict.fromkeys([
            *(lookup.get("normalized_citations") or []),
            *_canonical_citations(target.get("citation")),
        ]))
        source_url = urljoin("https://www.courtlistener.com/", str(cluster.get("absolute_url") or ""))
        decision = None
        try:
            from apps.caselaw.remote_importing import import_courtlistener_opinion
            from apps.sources.models import CourtListenerCitationCache

            decision = import_courtlistener_opinion(
                cluster=cluster,
                opinion=opinion,
                text=text,
                citations=normalized or [target["citation"]],
                source_url=source_url,
            )
            payload = {
                "status": lookup.get("status"),
                "clusterId": cluster_id,
                "opinionId": opinion.get("id"),
                "opinionIds": [item.get("id") for item in opinion_payloads],
            }
            for alias in normalized:
                CourtListenerCitationCache.objects.update_or_create(
                    citation_key=_citation_key(alias),
                    defaults={
                        "citation": alias,
                        "status": "resolved",
                        "decision": decision,
                        "source_url": source_url,
                        "provider_payload": payload,
                        "expires_at": None,
                    },
                )
        except (DatabaseError, OSError):
            decision = None
        return SourceResult(
            id=f"courtlistener:{cluster_id}:{opinion.get('id', '')}",
            title=cluster.get("case_name") or cluster.get("case_name_full") or target["citation"],
            citation=(normalized or [target["citation"]])[0],
            snippet=_relevant_excerpt(text, target.get("proposition")),
            source_kind="courtlistener",
            source_label="CourtListener (Free Law Project)",
            url=source_url,
            metadata={
                "provider": "Free Law Project",
                "clusterId": cluster_id,
                "opinionId": opinion.get("id"),
                "opinionIds": [item.get("id") for item in opinion_payloads],
                "targetId": target["targetId"],
                "cacheHit": False,
                "promotedDecisionId": decision.id if decision else None,
            },
        )
