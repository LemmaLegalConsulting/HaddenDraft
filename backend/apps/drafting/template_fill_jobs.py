"""Background preparation/export with durable status and stalled-job detection."""
import logging
import threading

from jinja2 import TemplateError
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.drafting.models import TemplateFillJob
from apps.drafting.template_fill import prepare_session, export_session

logger = logging.getLogger(__name__)


def execute(job_id):
    job = TemplateFillJob.objects.select_related("session__matter", "session__template", "created_by").get(pk=job_id)
    if job.status != "pending":
        return
    job.status = "running"
    job.save(update_fields=["status"])
    try:
        result = prepare_session(job.session, job.payload) if job.kind == "prepare" else export_session(job)
    except Exception as error:
        if not isinstance(error, (ValueError, TemplateError)):
            logger.exception("Template fill job %s failed", job.pk)
        TemplateFillJob.objects.filter(pk=job.pk, status="running").update(
            status="failed", error=str(error) if isinstance(error, (ValueError, TemplateError)) else "Template processing failed. Check its fields and supported expressions, then retry.", completed_at=timezone.now())
    else:
        TemplateFillJob.objects.filter(pk=job.pk, status="running").update(status="complete", result=result, completed_at=timezone.now())


def launch(job):
    def work():
        close_old_connections()
        try:
            execute(job.pk)
        finally:
            close_old_connections()
    if getattr(settings, "TEMPLATE_FILL_BACKGROUND", True):
        transaction.on_commit(lambda: threading.Thread(target=work, name=f"template-fill-{job.pk}", daemon=True).start())
    else:
        execute(job.pk)
    return job


def job_payload(job):
    if job.status in {"pending", "running"} and (timezone.now() - job.created_at).total_seconds() > 900:
        TemplateFillJob.objects.filter(pk=job.pk, status__in=["pending", "running"]).update(
            status="failed", error="Template processing stopped before completion. Please retry.", completed_at=timezone.now())
        job.refresh_from_db()
    return {"id": job.pk, "sessionId": job.session_id, "kind": job.kind, "status": job.status,
            "error": job.error, "result": {k: v for k, v in job.result.items() if k != "fileKey"}}
