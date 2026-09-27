"""
API tokens for connecting external systems to Codimente
Private AI.

A token belongs to exactly one user, and therefore to the
organisation memberships that user holds. Every request made
with a token is authorised through the same security chain as
an interactive login: user -> organisation -> assistant.

Only a SHA-256 hash of each key is stored; the full key is
shown exactly once, when the token is created.
"""

import hashlib
import secrets

from django.conf import settings
from django.db import models

from core.models import Organisation


def generate_api_key():

    # 32 url-safe bytes ~ 256 bits of entropy. The
    # codai_ prefix makes leaked keys recognisable in
    # secret scanners and support requests.

    return "codai_" + secrets.token_urlsafe(32)


def hash_api_key(raw_key):

    return hashlib.sha256(
        raw_key.encode("utf-8"),
    ).hexdigest()


class ApiToken(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="api_tokens",
        help_text=(
            "The organisation this token acts within. "
            "Requests with this token see only that "
            "organisation's assistants and knowledge."
        ),
    )

    name = models.CharField(
        max_length=100,
        help_text=(
            "What connects through this token, for example "
            "'Intranet portal' or 'Teams bot'."
        ),
    )

    key_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )

    prefix = models.CharField(
        max_length=12,
        editable=False,
        help_text=(
            "First characters of the key, so tokens can be "
            "recognised without knowing the full secret."
        ),
    )

    is_active = models.BooleanField(
        default=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Optional expiry. Empty means the token is valid "
            "until it is deactivated."
        ),
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:

        verbose_name = "API token"

        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="unique_api_token_name_per_organisation",
            )
        ]

    def __str__(self):

        return (
            f"{self.name} ({self.prefix}...) "
            f"for {self.user.username} in "
            f"{self.organisation.name}"
        )

    # -----------------------------------------------------
    # Creation
    # -----------------------------------------------------

    @classmethod
    def issue(cls, user, organisation, name, expires_at=None):

        """
        Create a token and return (token, raw_key). The raw
        key is never stored: only its SHA-256 hash is kept,
        so it must be handed to the integrator exactly once.
        """

        raw_key = generate_api_key()

        token = cls.objects.create(
            user=user,
            organisation=organisation,
            name=name,
            key_hash=hash_api_key(raw_key),
            prefix=raw_key[:10],
            expires_at=expires_at,
        )

        return token, raw_key

    # -----------------------------------------------------
    # Verification
    # -----------------------------------------------------

    def matches(self, raw_key):

        return secrets.compare_digest(
            self.key_hash,
            hash_api_key(raw_key),
        )
