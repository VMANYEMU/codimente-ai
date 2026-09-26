from django.conf import settings
from django.db import models


class Organisation(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class OrganisationMembership(models.Model):
    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("user", "User"),
    ]

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organisation_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="user",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organisation",
                    "user",
                ],
                name="unique_organisation_membership",
            )
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.organisation.name}"
        )


class AuditLog(models.Model):
    """
    Organisation-scoped audit trail for security-relevant
    events: logins, assistant permission changes, knowledge
    document lifecycle and denied access attempts.
    """

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )

    # Kept separately so the trail survives user deletion.

    actor_username = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    action = models.CharField(max_length=100)

    object_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    object_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    detail = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.created_at:%Y-%m-%d %H:%M} "
            f"{self.actor_username or 'system'} "
            f"{self.action}"
        )

