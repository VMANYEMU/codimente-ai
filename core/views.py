from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from ai.models import Assistant
from core.models import OrganisationMembership


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

    membership = (
        OrganisationMembership.objects
        .filter(
            user=request.user,
            is_active=True,
        )
        .select_related("organisation")
        .first()
    )

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
    # 4. Render the authorised chat interface
    # -----------------------------------------

    return render(
        request,
        "core/chat.html",
        {
            "assistants": assistants,
            "active_assistant": active_assistant,
            "membership": membership,
        },
    )