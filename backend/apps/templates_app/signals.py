import logging
import threading

from django.core.signals import request_started
from django.db import OperationalError, ProgrammingError
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from apps.templates_app.content_library import sync_prepared_templates


logger = logging.getLogger(__name__)
_lock = threading.Lock()
_initial_sync_done = False


def _sync_once():
    global _initial_sync_done
    if _initial_sync_done:
        return
    with _lock:
        if _initial_sync_done:
            return
        try:
            sync_prepared_templates()
        except (OperationalError, ProgrammingError):
            # The first process import can occur before migrations. post_migrate
            # or the first request after migration will retry.
            return
        _initial_sync_done = True


@receiver(request_started, dispatch_uid="templates_app.sync_prepared_templates_on_start")
def sync_on_first_request(**_kwargs):
    _sync_once()


@receiver(post_migrate, dispatch_uid="templates_app.sync_prepared_templates_after_migrate")
def sync_after_migrate(sender, **_kwargs):
    if sender.name == "apps.templates_app":
        _sync_once()
