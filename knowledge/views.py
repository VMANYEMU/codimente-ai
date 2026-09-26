from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ai.models import Assistant, AssistantAccess
from core.services import get_active_membership, record_audit
from knowledge.forms import DocumentUploadForm
from knowledge.models import Document, KnowledgeBase


def get_admin_membership(request):
    """
    Return the user's active membership only when they are
    an organisation admin. Knowledge management is an
    administrative function, so ordinary members cannot
    upload, reprocess or delete documents.
    """
    membership = get_active_membership(request)

    if membership is None or membership.role != "admin":
        return None

    return membership


def _document_status_payload(document):

    return {
        "document_id": document.id,
        "status": document.status,
        "is_processed": document.is_processed,
        "chunk_count": document.chunks.count(),
    }


@login_required
def knowledge_home(request):

    membership = get_admin_membership(request)

    if membership is None:
        raise PermissionDenied(
            "Only organisation admins can manage knowledge."
        )

    # Assistants this admin may manage knowledge for.

    assistants = (
        Assistant.objects
        .filter(
            organisation=membership.organisation,
            is_active=True,
        )
        .prefetch_related("knowledge_bases")
        .order_by("id")
    )

    sections = []

    for assistant in assistants:

        knowledge_base = assistant.knowledge_bases.first()

        documents = []

        if knowledge_base:

            documents = (
                knowledge_base.documents
                .order_by("-uploaded_at")
            )

        sections.append(
            {
                "assistant": assistant,
                "knowledge_base": knowledge_base,
                "documents": documents,
            }
        )

    return render(
        request,
        "knowledge/knowledge_home.html",
        {
            "sections": sections,
            "membership": membership,
        },
    )


@login_required
def document_upload(request, assistant_slug):

    membership = get_admin_membership(request)

    if membership is None:
        raise PermissionDenied(
            "Only organisation admins can upload documents."
        )

    assistant = get_object_or_404(
        Assistant,
        slug=assistant_slug,
        organisation=membership.organisation,
        is_active=True,
    )

    knowledge_base = assistant.knowledge_bases.first()

    if knowledge_base is None:

        # Self-heal: every assistant should have a knowledge
        # base (the seed command creates them). Create one
        # on demand so uploads never dead-end.

        knowledge_base = KnowledgeBase.objects.create(
            organisation=membership.organisation,
            assistant=assistant,
            name=f"{assistant.name} Knowledge",
        )

    if request.method == "POST":

        form = DocumentUploadForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            document = form.save(commit=False)
            document.knowledge_base = knowledge_base
            document.status = "pending"
            document.save()

            # -----------------------------------------
            # Process in the background so the upload
            # returns immediately. The worker thread
            # owns the status transitions:
            #   pending -> processing -> processed/failed
            #
            # (Render's single web service runs this as a
            # daemon thread; swap for a real task queue
            # without changing the status flow.)
            # -----------------------------------------

            transaction.on_commit(
                lambda: _spawn_processing(document.id)
            )

            record_audit(
                organisation=membership.organisation,
                actor=request.user,
                action="document.uploaded",
                object_type="document",
                object_id=document.id,
                detail={
                    "title": document.title,
                    "assistant": assistant.slug,
                },
            )

            messages.success(
                request,
                f"'{document.title}' was uploaded and is "
                "being processed.",
            )

            return redirect("knowledge-home")

    else:

        form = DocumentUploadForm()

    return render(
        request,
        "knowledge/document_upload.html",
        {
            "form": form,
            "assistant": assistant,
            "knowledge_base": knowledge_base,
        },
    )


def _spawn_processing(document_id):

    """
    Start background processing for a committed document
    row. Import inside the function so management commands
    and migrations are not affected by circular imports.
    """

    from knowledge.services.processing_worker import (
        spawn_document_processing,
    )

    spawn_document_processing(document_id)


@login_required
def document_status(request, document_id):

    membership = get_admin_membership(request)

    if membership is None:
        return JsonResponse(
            {"error": "Forbidden."},
            status=403,
        )

    document = get_object_or_404(
        Document,
        id=document_id,
        knowledge_base__organisation=membership.organisation,
    )

    return JsonResponse(
        _document_status_payload(document)
    )


@login_required
@require_POST
def document_reprocess(request, document_id):

    membership = get_admin_membership(request)

    if membership is None:
        raise PermissionDenied(
            "Only organisation admins can reprocess documents."
        )

    document = get_object_or_404(
        Document,
        id=document_id,
        knowledge_base__organisation=membership.organisation,
    )

    document.status = "pending"
    document.save(update_fields=["status"])

    transaction.on_commit(
        lambda: _spawn_processing(document.id)
    )

    record_audit(
        organisation=membership.organisation,
        actor=request.user,
        action="document.reprocess_requested",
        object_type="document",
        object_id=document.id,
        detail={"title": document.title},
    )

    messages.success(
        request,
        f"'{document.title}' is being reprocessed.",
    )

    return redirect("knowledge-home")


@login_required
@require_POST
def document_delete(request, document_id):

    membership = get_admin_membership(request)

    if membership is None:
        raise PermissionDenied(
            "Only organisation admins can delete documents."
        )

    document = get_object_or_404(
        Document,
        id=document_id,
        knowledge_base__organisation=membership.organisation,
    )

    if request.method == "POST":

        title = document.title

        record_audit(
            organisation=membership.organisation,
            actor=request.user,
            action="document.deleted",
            object_type="document",
            object_id=document.id,
            detail={"title": title},
        )

        document.delete()

        messages.success(
            request,
            f"'{title}' and its knowledge chunks were "
            "removed.",
        )

    return redirect("knowledge-home")
