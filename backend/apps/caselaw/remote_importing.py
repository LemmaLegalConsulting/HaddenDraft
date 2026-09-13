"""Promote remotely retrieved public opinions into the searchable local corpus."""

import hashlib
import re

from django.db import transaction

from apps.caselaw.importing import as_date, rebuild_search_documents
from apps.caselaw.models import CaseLawArtifact, CaseLawDecision, CaseLawPage
from apps.caselaw.storage import caselaw_prefix, get_caselaw_storage


def import_public_opinion(
    *, title, external_id, text, citations, source_url, metadata_source,
    decision_date="", publication_status="published", storage_slug="remote",
):
    """Idempotently promote a public remote opinion into the local corpus."""
    content = text.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    title = str(title or citations[0])[:500]
    citation_values = list(dict.fromkeys(str(value) for value in citations if value))
    source_key = f"{caselaw_prefix()}/{storage_slug}/{digest}.txt"
    storage = get_caselaw_storage()
    stored = storage.put_bytes(content=content, key=source_key, content_type="text/plain")

    with transaction.atomic():
        decision = CaseLawDecision.objects.filter(external_source_id=external_id).first()
        if decision is None:
            decision = CaseLawDecision.objects.filter(source_sha256=digest).first()
        defaults = {
            "title": title,
            "short_title": title,
            "normalized_title": re.sub(r"\s+", " ", title.casefold()).strip(),
            "external_source_id": external_id,
            "decision_date": as_date(decision_date),
            "publication_status": str(publication_status or "unknown")[:80],
            "precedential_status": str(publication_status or "")[:120],
            "citation_string": citation_values[0] if citation_values else "",
            "parallel_citations": citation_values[1:],
            "source_sha256": digest,
            "file_size_bytes": len(content),
            "mime_type": "text/plain",
            "has_embedded_text": True,
            "has_ocr_layer": False,
            "metadata_source": metadata_source,
            "metadata_verified": False,
            "approved_for_search": True,
            "approved_for_drafting": False,
            "is_unpublished": str(publication_status or "").casefold() != "published",
            "is_persuasive_only": True,
            "original_filename": f"{storage_slug}-{external_id.rsplit(':', 1)[-1]}.txt",
        }
        if decision is None:
            decision = CaseLawDecision.objects.create(**defaults)
        else:
            for field, value in defaults.items():
                setattr(decision, field, value)
            decision.save()
        CaseLawArtifact.objects.update_or_create(
            decision=decision,
            artifact_type="opinion_text",
            storage_key=source_key,
            defaults={
                "original_filename": defaults["original_filename"],
                "storage_backend": storage.backend_name,
                "content_type": "text/plain",
                "size_bytes": stored["size"],
                "sha256": stored["sha256"],
            },
        )
        decision.pages.all().delete()
        CaseLawPage.objects.create(decision=decision, page_number=1, text=text)
        rebuild_search_documents(decision, text)
    return decision


def import_courtlistener_opinion(*, cluster, opinion, text, citations, source_url):
    """Idempotently store a CourtListener opinion and return its decision row."""
    cluster_id = str(cluster.get("id") or "")
    opinion_id = str(opinion.get("id") or "")
    return import_public_opinion(
        title=cluster.get("case_name") or cluster.get("case_name_full") or citations[0],
        external_id=f"courtlistener:{cluster_id}:{opinion_id}", text=text,
        citations=citations, source_url=source_url,
        metadata_source="courtlistener_v4", decision_date=cluster.get("date_filed"),
        publication_status=cluster.get("precedential_status") or "unknown",
        storage_slug="courtlistener",
    )
