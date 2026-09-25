from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from ai.models import Assistant, AssistantAccess
from core.models import OrganisationMembership
from knowledge.forms import DocumentUploadForm
from knowledge.models import Document, KnowledgeBase
from knowledge.services.document_processor import process_document


def get_admin_membership(request):
    """
    Return the user's active membership only when they are
    an organisation admin. Knowledge management is an
    administrative function, so ordinary members cannot
    upload, reprocess or delete documents.
    """
    return (
        OrganisationMembership.objects
        .filter(
            user=request.user,
            is_active=True,
            role="admin",
        )
        .select_related("organisation")
        .first()
    )


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
            document.save()

            try:

                with transaction.atomic():

                    chunk_count = process_document(document)

                messages.success(
                    request,
                    f"'{document.title}' was processed: "
                    f"{chunk_count} chunks embedded.",
                )

            except Exception:

                # Extraction or embedding failed. Remove the
                # stored file record so the admin can retry
                # cleanly; the file itself is left on disk.

                document.delete()

                messages.error(
                    request,
                    "The document could not be processed. "
                    "Check that it contains readable text "
                    "and is a valid PDF, DOCX or TXT file.",
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


@login_required
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

    try:

        with transaction.atomic():

            chunk_count = process_document(document)

        messages.success(
            request,
            f"'{document.title}' was reprocessed: "
            f"{chunk_count} chunks embedded.",
        )

    except Exception:

        messages.error(
            request,
            f"'{document.title}' could not be reprocessed. "
            "The previous chunks were kept unchanged.",
        )

    return redirect("knowledge-home")


@login_required
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

        document.delete()

        messages.success(
            request,
            f"'{title}' and its knowledge chunks were "
            "removed.",
        )

    return redirect("knowledge-home")
