"""
Audit signal handlers.

Events recorded here happen outside the ordinary view
flow, so they are captured with Django signals:

- successful logins
- failed login attempts
- logouts
- assistant access grants and revocations
"""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ai.models import AssistantAccess
from core.models import OrganisationMembership
from core.services import record_audit


def _primary_membership(user):
    """
    Best-effort organisation for user-level events.
    Userless or organisationless events are stored with
    a null organisation.
    """

    return (
        OrganisationMembership.objects
        .filter(
            user=user,
            is_active=True,
        )
        .select_related("organisation")
        .first()
    )


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):

    if user is None:
        return

    membership = _primary_membership(user)

    record_audit(
        organisation=(
            membership.organisation if membership else None
        ),
        actor=user,
        action="auth.login",
        object_type="user",
        object_id=user.pk,
        detail={"username": user.get_username()},
    )


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, **kwargs):

    record_audit(
        organisation=None,
        actor=None,
        action="auth.login_failed",
        object_type="user",
        object_id="",
        detail={
            "username": credentials.get("username", ""),
        },
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):

    if user is None or not getattr(
        user, "is_authenticated", False
    ):
        return

    membership = _primary_membership(user)

    record_audit(
        organisation=(
            membership.organisation if membership else None
        ),
        actor=user,
        action="auth.logout",
        object_type="user",
        object_id=user.pk,
        detail={"username": user.get_username()},
    )


@receiver(post_save, sender=AssistantAccess)
def audit_access_granted(
    sender, instance, created, **kwargs
):

    if not created:
        return

    record_audit(
        organisation=(
            instance.membership.organisation
        ),
        actor=None,
        action="assistant.access_granted",
        object_type="assistant_access",
        object_id=instance.pk,
        detail={
            "username": (
                instance.membership.user.get_username()
            ),
            "assistant": instance.assistant.slug,
        },
    )


@receiver(post_delete, sender=AssistantAccess)
def audit_access_revoked(sender, instance, **kwargs):

    record_audit(
        organisation=(
            instance.membership.organisation
        ),
        actor=None,
        action="assistant.access_revoked",
        object_type="assistant_access",
        object_id=instance.pk,
        detail={
            "username": (
                instance.membership.user.get_username()
            ),
            "assistant": instance.assistant.slug,
        },
    )
