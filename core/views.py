from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from ai.models import Assistant
from core.services import get_active_membership, record_audit


def home(request):
    return render(
        request,
        "core/home.html",
    )


@login_required
def chat(request, assistant_slug=None):

    # -----------------------------------------
    # 1. Find the logged-in user's organisation
    # -----------------------------------------

    membership = get_active_membership(request)

    if membership is None:
        raise PermissionDenied(
            "You do not have an active organisation membership."
        )

    # -----------------------------------------
    # 2. Find assistants this user can access
    # -----------------------------------------

    assistants = (
        Assistant.objects
        .filter(
            access_permissions__membership=membership,
            organisation=membership.organisation,
            is_active=True,
        )
        .distinct()
        .order_by("id")
    )

    if not assistants.exists():
        raise PermissionDenied(
            "You do not have access to any AI assistants."
        )

    # -----------------------------------------
    # 3. Determine which assistant to open
    # -----------------------------------------

    if assistant_slug is None:

        # /chat/
        # Open the first assistant the user is
        # authorised to access.

        active_assistant = assistants.first()

    else:

        # /chat/<assistant-slug>/
        # The requested assistant must also be
        # one of this user's authorised assistants.

        active_assistant = (
            assistants
            .filter(
                slug=assistant_slug,
            )
            .first()
        )

        if active_assistant is None:
            raise PermissionDenied(
                "You do not have access to this assistant."
            )

    # -----------------------------------------
    # 4. Find the user's recent conversations
    #    grouped per assistant, so the sidebar
    #    shows each assistant's own history.
    # -----------------------------------------

    recent_conversations = (
        request.user.ai_conversations
        .filter(
            organisation=membership.organisation,
        )
        .select_related("assistant")
        .order_by("-updated_at")
    )

    conversations_by_assistant = {
        assistant.id: []
        for assistant in assistants
    }

    for conversation in recent_conversations:

        bucket = conversations_by_assistant.get(
            conversation.assistant_id,
        )

        if bucket is not None and len(bucket) < 8:
            bucket.append(conversation)

    assistant_sections = [
        {
            "assistant": assistant,
            "conversations": conversations_by_assistant[
                assistant.id
            ],
        }
        for assistant in assistants
    ]

    # -----------------------------------------
    # 5. Other organisations the user belongs to,
    #    for the switcher in the sidebar.
    # -----------------------------------------

    other_memberships = (
        request.user.organisation_memberships
        .filter(
            is_active=True,
        )
        .exclude(
            id=membership.id,
        )
        .select_related("organisation")
    )

    # -----------------------------------------
    # 6. Render the authorised chat interface
    # -----------------------------------------

    return render(
        request,
        "core/chat.html",
        {
            "assistant_sections": assistant_sections,
            "active_assistant": active_assistant,
            "membership": membership,
            "other_memberships": other_memberships,
        },
    )


@login_required
def organisation_switch(request, membership_id):

    target_membership = get_object_or_404(
        request.user.organisation_memberships,
        id=membership_id,
        is_active=True,
    )

    request.session["active_organisation_id"] = (
        target_membership.id
    )

    record_audit(
        organisation=target_membership.organisation,
        actor=request.user,
        action="organisation.switched",
        object_type="organisation",
        object_id=target_membership.organisation_id,
        detail={
            "organisation_name": (
                target_membership.organisation.name
            )
        },
    )

    messages.success(
        request,
        "You are now working in "
        f"{target_membership.organisation.name}.",
    )

    return redirect("chat")