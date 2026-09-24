"""The research-mode API: a deterministic search, with AI as a labelled extra.

Two things are kept apart here on purpose.

The search itself runs in ``apps.sources.research``, which does not import
``apps.ai`` at all. Whatever happens to a model provider -- unconfigured,
rate-limited, timing out, switched off by policy -- a search still returns the
corpus's own answer, because nothing on that path can call one.

Reranking and synthesis sit on top of that finished result set, are off unless
asked for, and report what they did in the response's ``ai`` block whether they
ran or not. A reader should never have to infer from a missing field that
nothing generative happened, nor from a small icon that something did. When a
model was asked for and failed, that is reported too: the results below it are
still the library's, and saying so is the difference between a degraded answer
and a silently different one.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.http import JsonResponse

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import PromptRenderError, render_prompt
from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.core.views import default_jurisdiction_for_user
from apps.matters.services import matter_for_user
from apps.sources.ordinances import notice_snippet, pending_notices
from apps.sources.research import engine, expansion_status
from apps.sources.research.corpus import CORPORA, CORPUS_LABELS
from apps.sources.research.expansion import MODES
from apps.sources.research.facets import FILTER_ONLY_FIELDS, facet_fields
from apps.sources.research.index import corpus_fingerprint, peek_index, warm_index


# How many results a model is allowed to see when reordering. A rerank is a
# second opinion about the head of a list, not a second retrieval.
RERANK_WINDOW = 25
SYNTHESIS_WINDOW = 12

FILTERABLE = tuple(field["field"] for field in facet_fields()) + FILTER_ONLY_FIELDS


def _truthy(value):
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _as_values(value):
    """One filter's values, whether they arrived as a list or as a bare string.

    A string is not iterated as a list of characters: ``{"county": "Cuyahoga"}``
    is an obvious thing for a caller to send, and reading it character by
    character would narrow to eight impossible counties and return nothing.
    """
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _filters_from(source, getlist):
    filters = {}
    for field in FILTERABLE:
        values = [str(value) for value in _as_values(getlist(source, field)) if str(value).strip()]
        if values:
            filters[field] = values
    return filters


def _request_options(request):
    """Read one search request from either a GET query string or a JSON body.

    GET is supported so a search can be linked to and reopened, which is part of
    being a research tool rather than a chat.
    """
    if request.method == "GET":
        data = request.GET
        # A GET is supposed to be the shareable, repeatable form of a search, and
        # a link gets forwarded, crawled and prefetched. Honouring the AI flags
        # here meant that opening a URL someone sent you could spend money on a
        # model call and hand it the summary of whichever matter the link named.
        # The flags are read so the response can say they were refused rather
        # than silently ignored; generative work needs a POST.
        refused = [
            name for name, value in (("aiRerank", data.get("aiRerank")), ("aiSynthesis", data.get("aiSynthesis")))
            if _truthy(value)
        ]
        return {
            "query": data.get("q", "") or data.get("query", ""),
            "corpora": data.getlist("corpus"),
            "filters": _filters_from(data, lambda source, field: source.getlist(field)),
            "expansion": data.get("expansion", ""),
            "limit": data.get("limit"),
            "offset": data.get("offset"),
            "jurisdiction": data.get("jurisdiction", ""),
            "matter_id": data.get("matterId"),
            "rerank": False,
            "synthesize": False,
            "ai_refused": refused,
        }
    body = json_body(request)
    raw_filters = body.get("filters") if isinstance(body.get("filters"), dict) else {}
    return {
        "query": body.get("query", "") or body.get("q", ""),
        "corpora": _as_values(body.get("corpora")),
        "filters": _filters_from(raw_filters, lambda source, field: source.get(field)),
        "expansion": body.get("expansion", ""),
        "limit": body.get("limit"),
        "offset": body.get("offset"),
        "jurisdiction": body.get("jurisdiction", ""),
        "matter_id": body.get("matterId"),
        "rerank": _truthy(body.get("aiRerank")),
        "synthesize": _truthy(body.get("aiSynthesis")),
        "ai_refused": [],
    }


def _ai_unavailable_reason():
    if not settings.AI_DRAFTING_ENABLED:
        return "AI features are switched off for this deployment."
    return ""


def _page_phrase(payload, count):
    """"the first N results" is only true on page one; say which page otherwise."""
    offset = payload.get("offset") or 0
    if not offset:
        return f"the first {count} results"
    return f"results {offset + 1}\u2013{offset + count} on this page"


def _rerank(payload, *, query, jurisdiction):
    """Ask a model to reorder this page, reporting whether it did."""
    window = payload["results"][:RERANK_WINDOW]
    if not window:
        return {"requested": True, "applied": False, "reason": "There was nothing to reorder.", "window": 0}
    candidates = [
        {
            "id": result["id"],
            "title": result["title"],
            "citation": result["citation"],
            "source": result["corpusLabel"],
            "excerpt": result["snippet"][:400],
        }
        for result in window
    ]
    try:
        prompt = render_prompt(
            "research.rerank",
            query=query,
            jurisdiction=jurisdiction,
            candidates=json.dumps(candidates, ensure_ascii=False),
        )
        response = OpenAICompatibleClient().complete(
            system=prompt.system,
            user=prompt.user,
            temperature=0,
            model=prompt.default_model,
            reasoning_level=prompt.default_reasoning_level,
        )
        order = json.loads(response)
        identifiers = order.get("order", []) if isinstance(order, dict) else []
    except (OpenAIBackendError, PromptRenderError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            "requested": True, "applied": False, "window": len(window),
            "reason": f"The reranker could not be reached, so results are in deterministic order ({exc}).",
        }

    # Only ids the model was actually shown count. Without this an answer of
    # {"order": ["invented-id"]} was non-empty, changed nothing, and was
    # reported as a rerank that had been applied -- the one thing this block
    # exists to report honestly.
    candidates = {result["id"] for result in window}
    # Filter first, then rank. Enumerating before the filter left gaps, so an
    # invented id in front of a real one pushed the real one's rank past the
    # default given to everything the model did not mention, and the reorder
    # silently did nothing.
    named = [
        identifier for identifier in identifiers
        if isinstance(identifier, str) and identifier in candidates
    ]
    positions = {identifier: position for position, identifier in enumerate(dict.fromkeys(named))}
    if not positions:
        return {
            "requested": True, "applied": False, "window": len(window),
            "reason": (
                "The reranker named no result it was given, so results are in deterministic order."
                if identifiers else
                "The reranker returned no usable order, so results are in deterministic order."
            ),
        }
    # A result the model left out keeps its deterministic position behind the
    # ones it ranked, rather than disappearing: dropping a result is retrieval,
    # and reranking is not allowed to do retrieval.
    reordered = sorted(
        enumerate(window),
        key=lambda item: (positions.get(item[1]["id"], len(positions)), item[0]),
    )
    moved = sum(1 for new_position, (old_position, _result) in enumerate(reordered) if new_position != old_position)
    payload["results"] = [result for _old, result in reordered] + payload["results"][RERANK_WINDOW:]
    for position, result in enumerate(payload["results"][: len(window)]):
        result["rerankedTo"] = position
    where = _page_phrase(payload, len(window))
    return {
        "requested": True, "applied": True, "window": len(window), "moved": moved,
        "reason": f"A model reordered {where}; {moved} changed position. Everything else is in deterministic order.",
    }


def _synthesize(payload, *, query, jurisdiction, matter):
    window = payload["results"][:SYNTHESIS_WINDOW]
    if not window:
        return {"requested": True, "applied": False, "reason": "There were no results to summarize.", "answer": ""}
    sources = []
    for position, result in enumerate(window, start=1):
        citation = f" Citation: {result['citation']}." if result["citation"] else ""
        sources.append(f"[{position}] {result['title']} [{result['corpusLabel']}].{citation}\nExcerpt: {result['snippet']}")
    try:
        prompt = render_prompt(
            "research.answer",
            query=query,
            matter_summary=getattr(matter, "summary", "") if matter else "",
            jurisdiction=jurisdiction,
            conversation="- None",
            sources="\n".join(sources),
        )
        answer = OpenAICompatibleClient().complete(
            system=prompt.system,
            user=prompt.user,
            temperature=0.1,
            model=prompt.default_model,
            reasoning_level=prompt.default_reasoning_level,
        )
    except (OpenAIBackendError, PromptRenderError) as exc:
        return {
            "requested": True, "applied": False, "answer": "",
            "reason": f"The answer could not be generated ({exc}). The results below are unaffected.",
        }
    return {
        "requested": True, "applied": True, "answer": answer, "citedResults": len(window),
        "reason": (
            f"A model wrote the summary above from {_page_phrase(payload, len(window))}. "
            "It is not part of the corpus; read the sources."
        ),
    }


@api_login_required
def research_search(request):
    """Search the corpus. Deterministic unless a model is explicitly asked for."""
    if request.method not in {"GET", "POST"}:
        return method_not_allowed(["GET", "POST"])
    options = _request_options(request)

    matter = None
    if options["matter_id"]:
        matter = matter_for_user(request.user, options["matter_id"])
        if not matter:
            return JsonResponse({"error": "Case not found or not available to this user"}, status=404)

    jurisdiction = (
        getattr(matter, "jurisdiction", "").strip()
        or str(options["jurisdiction"] or "").strip()
        or default_jurisdiction_for_user(request.user)
    )
    expansion_mode = options["expansion"] if options["expansion"] in MODES else "thesaurus"

    payload = engine.search(
        options["query"],
        filters=options["filters"],
        corpora=options["corpora"],
        expansion_mode=expansion_mode,
        limit=options["limit"] or engine.DEFAULT_LIMIT,
        offset=options["offset"] or 0,
        jurisdiction=jurisdiction,
    )
    payload["jurisdiction"] = jurisdiction
    # Local law the corpus knows of but holds no text for -- a repealed chapter,
    # an ordinance not yet acquired. Such a record produces no chunk, so it can
    # never rank; without this, "Newburgh Heights pay to stay" led with the
    # treatise section describing a chapter the city repealed in 2024.
    payload["coverageNotices"] = [
        {**notice, "snippet": notice_snippet(notice)} for notice in pending_notices(options["query"])
    ]

    unavailable = _ai_unavailable_reason()
    rerank_report = None
    synthesis_report = None
    if options.get("ai_refused"):
        refused = {
            "requested": True, "applied": False,
            "reason": (
                "A link cannot start generative work. "
                f"{' and '.join(options['ai_refused'])} was ignored because this search arrived as a GET; "
                "send the same search as a POST to run it."
            ),
        }
        rerank_report = dict(refused) if "aiRerank" in options["ai_refused"] else None
        synthesis_report = {**refused, "answer": ""} if "aiSynthesis" in options["ai_refused"] else None
    if options["rerank"]:
        rerank_report = (
            {"requested": True, "applied": False, "reason": unavailable}
            if unavailable else _rerank(payload, query=options["query"], jurisdiction=jurisdiction)
        )
    if options["synthesize"]:
        synthesis_report = (
            {"requested": True, "applied": False, "answer": "", "reason": unavailable}
            if unavailable else _synthesize(payload, query=options["query"], jurisdiction=jurisdiction, matter=matter)
        )
    payload["ai"] = engine.ai_report(rerank=rerank_report, synthesis=synthesis_report)
    return JsonResponse(payload)


@api_login_required
def research_search_status(request):
    """What research mode can currently do, before anyone types a query.

    This is also what warms the index. The interface asks for it when the
    search view opens, several seconds before anyone has finished typing, so
    the build starts here and on a background thread -- the status of a library
    is not worth holding a request open for, and a worker killed mid-build
    returns no headers at all, which reaches the browser as a CORS failure
    rather than as a timeout.
    """
    if request.method != "GET":
        return method_not_allowed(["GET"])
    index = peek_index()
    building = warm_index() if index is None else False
    unavailable = _ai_unavailable_reason()
    return JsonResponse({
        "index": (
            index.status(current_fingerprint=corpus_fingerprint()) if index
            else {"building": building, "documentCount": 0, "documentsByCorpus": {}, "stale": False}
        ),
        "expansion": expansion_status(),
        "corpora": [{"id": corpus, "label": CORPUS_LABELS[corpus]} for corpus in CORPORA],
        "facetFields": facet_fields(),
        "querySyntax": [
            {"example": '"notice to leave the premises"', "description": "Exact phrase. Only text containing it is returned."},
            {"example": "R.C. 5321.04", "description": "Citation. The section itself ranks above sources discussing it."},
            {"example": "court:cleveland", "description": "Field filter. Also county, municipality, district, year, status, judge, title, source."},
            {"example": "-sublease", "description": "Exclude a word."},
        ],
        "ai": {
            "available": not unavailable,
            "reason": unavailable,
            "default": {"rerank": False, "synthesis": False},
            "note": "Search never calls a model. Reranking and synthesis are opt-in per search and are reported in every response.",
        },
    })
