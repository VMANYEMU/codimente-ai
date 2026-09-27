"""
Authentication for external systems connecting through API
tokens.

Integration requests authenticate with:

    Authorization: Token codai_xxxxxxxx...

and are then treated as the token's user acting inside the
token's organisation — the same user -> organisation ->
assistant security chain as an interactive login, but without
sessions or CSRF (header-based, not cookie-based).
"""

from django.utils import timezone

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiToken, hash_api_key


def extract_raw_key(request):
    """
    Return the raw key from the Authorization header, or None
    when the request carries no token credential.

    "Token <key>" and "Bearer <key>" are accepted
    (case-insensitive scheme). Anything else — including no
    header — returns None, so DRF falls through to the next
    authenticator (the session) exactly as intended.
    """

    header = request.META.get(
        "HTTP_AUTHORIZATION",
        "",
    )

    if not header:
        return None

    scheme, _, credentials = header.partition(" ")

    if scheme.lower() not in ("token", "bearer"):
        return None

    if not credentials:
        return None

    return credentials.strip()


class ApiTokenAuthentication(BaseAuthentication):
    """
    DRF authentication backend for Codimente integration
    tokens.
    """

    keyword = "Token"

    def authenticate(self, request):

        raw_key = extract_raw_key(request)

        if raw_key is None:

            # Not a token request: let other
            # authenticators (session) handle it.

            return None

        key_hash = hash_api_key(raw_key)

        token = ApiToken.objects.filter(
            key_hash=key_hash,
        ).first()

        if token is None:

            raise AuthenticationFailed(
                "Invalid API token."
            )

        if not token.is_active:

            raise AuthenticationFailed(
                "This API token has been deactivated."
            )

        if (
            token.expires_at is not None
            and token.expires_at <= timezone.now()
        ):

            raise AuthenticationFailed(
                "This API token has expired."
            )

        if not token.user.is_active:

            raise AuthenticationFailed(
                "The user behind this API token is "
                "deactivated."
            )

        # Touch last_used_at without touching updated
        # behaviour elsewhere: a single cheap UPDATE per
        # authenticated request.

        ApiToken.objects.filter(
            pk=token.pk,
        ).update(
            last_used_at=timezone.now(),
        )

        # request.user is the token's user; request.auth is
        # the token itself, so views can scope to
        # token.organisation.

        return (
            token.user,
            token,
        )

    def authenticate_header(self, request):

        return self.keyword
