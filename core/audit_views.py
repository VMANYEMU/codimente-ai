from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from core.services import get_active_membership


@login_required
def audit_log(request):

    membership = get_active_membership(request)

    if (
        membership is None
        or membership.role != "admin"
    ):
        raise PermissionDenied(
            "Only organisation admins can view the audit "
            "log."
        )

    events = (
        membership.organisation.audit_logs
        .select_related("actor")[:200]
    )

    return render(
        request,
        "core/audit_log.html",
        {
            "events": events,
            "membership": membership,
        },
    )
