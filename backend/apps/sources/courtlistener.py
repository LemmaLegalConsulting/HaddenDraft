"""Rate-bounded CourtListener fallback for unresolved case citations."""

from dataclasses import replace
import hashlib
from html import unescape
import re
from urllib.parse import urljoin, urlsplit

from django.conf import settings
from django.core.cache import cache
from django.utils.html import strip_tags
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
        for target in ranked:
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
            "requested": len(selected_groups),
            "resolved": len(results),
            "rateLimited": False,
        }
        if not pending:
            return results, trace
        try:
            response = self.session.post(
                urljoin(self.base_url, "citation-lookup/"),
                headers=self._headers(),
                data={"text": "\n".join(target["citation"] for target, _key, _group in pending)},
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
        for (target, key, group), lookup in zip(pending, lookups):
            combined_target = {
                **target,
                "proposition": "\n".join(item.get("proposition", "") for item in group),
            }
            source = self._resolved_source(combined_target, lookup)
            if source is None:
                continue
            cached = {**source.__dict__, "metadata": {**source.metadata, "targetId": ""}}
            cache.set(key, cached, 604800)
            results.extend(
                replace(source, metadata={**source.metadata, "targetId": item["targetId"]})
                for item in group
            )
        trace["resolved"] = len(results)
        return results, trace

    def _resolved_source(self, target, lookup):
        clusters = lookup.get("clusters") or []
        if lookup.get("status") != 200 or len(clusters) != 1:
            return None
        cluster = clusters[0]
        opinions = cluster.get("sub_opinions") or cluster.get("opinions") or []
        opinion_url = _opinion_url(opinions[0] if opinions else "", self.base_url)
        if not opinion_url:
            return None
        try:
            response = self.session.get(
                opinion_url,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        try:
            opinion = response.json()
        except ValueError:
            return None
        raw = next((opinion.get(field) for field in TEXT_FIELDS if opinion.get(field)), "")
        text = re.sub(r"\s+", " ", unescape(strip_tags(str(raw)))).strip()
        if not text:
            return None
        cluster_id = str(cluster.get("id") or "")
        return SourceResult(
            id=f"courtlistener:{cluster_id}:{opinion.get('id', '')}",
            title=cluster.get("case_name") or cluster.get("case_name_full") or target["citation"],
            citation=(lookup.get("normalized_citations") or [target["citation"]])[0],
            snippet=_relevant_excerpt(text, target.get("proposition")),
            source_kind="courtlistener",
            source_label="CourtListener (Free Law Project)",
            url=urljoin("https://www.courtlistener.com/", str(cluster.get("absolute_url") or "")),
            metadata={
                "provider": "Free Law Project",
                "clusterId": cluster_id,
                "opinionId": opinion.get("id"),
                "targetId": target["targetId"],
                "cacheHit": False,
            },
        )
