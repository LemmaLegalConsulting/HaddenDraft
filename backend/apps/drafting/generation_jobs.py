"""Generate a plan's drafts on a background thread, with a row to poll.

The same shape as the argument gym's runs (apps.argument_gym.pipeline): the
request that asks for work returns a row at once, a daemon thread does the
work, and the client polls the row. A request held open for the whole
generation reached the browser as a CORS-less 504 when it outlived nginx, and
the advocate who clicked Generate again got two drafts.
"""

import logging
import threading

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from apps.drafting.models import DraftGenerationJob

logger = logging.getLogger(__name__)


def job_to_dict(job):
    return {
        "id": job.id,
        "sessionId": job.session_id,
        "status": job.status,
        "error": job.error,
        "draftIds": job.draft_ids or [],
        "createdAt": job.created_at.isoformat() if job.created_at else "",
        "completedAt": job.completed_at.isoformat() if job.completed_at else "",
    }


def active_job(session):
    """A job for this session still pending or running, after stall detection."""
    for job in session.generation_jobs.filter(status__in=[DraftGenerationJob.PENDING, DraftGenerationJob.RUNNING]):
        if fail_if_stalled(job).status in {DraftGenerationJob.PENDING, DraftGenerationJob.RUNNING}:
            return job
    return None


def _execute(job, *, user):
    from apps.drafting.services import create_drafts_from_plan

    job.status = DraftGenerationJob.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])
    try:
        drafts = create_drafts_from_plan(job.session, user=user, request=None)
    except ValueError as error:
        job.status = DraftGenerationJob.FAILED
        job.error = str(error)
    except Exception as error:  # noqa: BLE001 - recorded for the advocate, logged for us
        logger.exception("Draft generation job %s failed", job.id)
        job.status = DraftGenerationJob.FAILED
        job.error = f"The draft could not be generated: {error}"
    else:
        job.status = DraftGenerationJob.COMPLETE
        job.draft_ids = [draft.id for draft in drafts]
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "error", "draft_ids", "completed_at"])
    return job


def start_job(session, *, user):
    """Start generating, or return the generation already under way."""
    existing = active_job(session)
    if existing:
        # A second click on Generate while the first is running waits on the
        # first rather than making a second set of drafts.
        return existing
    job = DraftGenerationJob.objects.create(session=session, created_by=user)
    if not getattr(settings, "DRAFT_GENERATION_BACKGROUND", True):
        return _execute(job, user=user)

    def work():
        # The request's connection belongs to the request; a thread uses its own
        # and hands it back.
        close_old_connections()
        try:
            _execute(job, user=user)
        except Exception:  # noqa: BLE001 - _execute records failure; this is the last resort
            logger.exception("Draft generation job %s died outside its own error handling", job.id)
        finally:
            close_old_connections()

    threading.Thread(target=work, name=f"draft-generation-{job.id}", daemon=True).start()
    return job


def fail_if_stalled(job):
    """Report a job whose worker died instead of one that claims to run forever."""
    if job.status not in {DraftGenerationJob.PENDING, DraftGenerationJob.RUNNING}:
        return job
    limit = getattr(settings, "DRAFT_GENERATION_TIMEOUT_SECONDS", 900)
    age = (timezone.now() - job.created_at).total_seconds()
    if age < limit:
        return job
    job.status = DraftGenerationJob.FAILED
    job.error = (
        f"Generation stopped reporting progress after {int(age // 60)} minutes and was most likely "
        "interrupted by a restart. Generate the draft again."
    )
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "error", "completed_at"])
    return job
