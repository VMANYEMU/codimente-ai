"""
Background document processing.

On a single Render web service this runs as a daemon
thread started after the upload transaction commits. The
status flow owned here:

    pending -> processing -> processed | failed

If Codimente later moves to a real task queue (Celery,
RQ, Render Background Workers), only this module changes —
views and templates keep the same status contract.
"""

import threading
import traceback

from django.db import close_old_connections, transaction

from core.services import record_audit
from knowledge.models import Document


def _process_in_thread(document_id):

    close_old_connections()

    document = None

    try:

        document = Document.objects.select_related(
            "knowledge_base__organisation",
        ).get(id=document_id)

        document.status = "processing"
        document.save(update_fields=["status"])

        with transaction.atomic():

            chunk_count = process_document(document)

        document.status = "processed"
        document.save(update_fields=["status"])

        record_audit(
            organisation=(
                document.knowledge_base.organisation
            ),
            actor=None,
            action="document.processed",
            object_type="document",
            object_id=document.id,
            detail={
                "title": document.title,
                "chunks": chunk_count,
            },
        )

    except Exception:

        if document is not None:

            Document.objects.filter(
                id=document.id,
            ).update(status="failed")

            record_audit(
                organisation=(
                    document.knowledge_base.organisation
                ),
                actor=None,
                action="document.failed",
                object_type="document",
                object_id=document.id,
                detail={
                    "title": document.title,
                    "error": (
                        traceback.format_exc()[-500:]
                    ),
                },
            )

    finally:

        close_old_connections()


def spawn_document_processing(document_id):
    """
    Start processing in a daemon thread and return
    immediately.
    """

    thread = threading.Thread(
        target=_process_in_thread,
        args=(document_id,),
        daemon=True,
        name=f"document-processing-{document_id}",
    )

    thread.start()


# Imported late so the worker module itself can be loaded
# by management commands without heavy service imports.

from knowledge.services.document_processor import (
    process_document,  # noqa: E402
)
