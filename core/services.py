"""
Central services for the core app: audit logging and
active-organisation resolution.
"""

from django.db import transaction

from core.models import AuditLog, OrganisationMembership


# ---------------------------------------------------------
# Audit logging
# ---------------------------------------------------------

def record_audit(
    organisation,
    actor,
    action,
    object_type="",
    object_id="",
    detail=None,
):
    """
    Persist an audit event. Never raises: auditing must
    not break the request that triggered it.
    """

    # The savepoint matters: if the insert fails inside a
    # larger atomic block, rolling back to the savepoint
    # keeps the surrounding transaction usable instead of
    # leaving it poisoned by the failed statement.

    try:

        with transaction.atomic():

            return AuditLog.objects.create(
                organisation=organisation,
                actor=actor if (
                    getattr(actor, "is_authenticated", False)
                ) else None,
                actor_username=(
                    getattr(actor, "username", "") or ""
                ),
                action=action,
                object_type=object_type,
                object_id=str(object_id) if object_id else "",
                detail=detail or {},
            )

    except Exception:

        return None


# ---------------------------------------------------------
# Active organisation
# ---------------------------------------------------------

def get_active_membership(request):
    """
    Return the user's active organisation membership.

    Resolution order:
      1. the membership id stored in the session
         (set by core.views.organisation_switch)
      2. the first active membership
    """

    memberships = (
        OrganisationMembership.objects
        .filter(
            user=request.user,
            is_active=True,
        )
        .select_related("organisation")
    )

    active_id = request.session.get(
        "active_organisation_id"
    )

    if active_id:

        membership = memberships.filter(
            id=active_id,
        ).first()

        if membership:
            return membership

        # The session pointed at a membership that no
        # longer exists or is inactive: fall through and
        # pick the default instead of failing.

    return memberships.first()
