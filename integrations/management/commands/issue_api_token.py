"""
Issue an API token for an external system without using the
Django admin — for headless or automated deployments.

The raw key is printed exactly once and never stored (only
its SHA-256 hash is kept). Redirecting the output to a file
or secret manager is the intended way to hand it over.

Usage:

    python manage.py issue_api_token \
        --username svc-intranet \
        --organisation "Codimente Demo Organisation" \
        --name "Intranet portal" \
        [--expires-in-days 90]
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Organisation, OrganisationMembership
from core.services import record_audit

from integrations.models import ApiToken


class Command(BaseCommand):

    help = (
        "Create an API token for an external system and "
        "print the key once. The user must already hold an "
        "active membership in the named organisation."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--username",
            required=True,
            help="The user the token acts as.",
        )

        parser.add_argument(
            "--organisation",
            required=True,
            help=(
                "Name of the organisation the token is "
                "pinned to."
            ),
        )

        parser.add_argument(
            "--name",
            required=True,
            help=(
                "Token name describing what connects "
                "through it, e.g. 'Intranet portal'. "
                "Unique per organisation."
            ),
        )

        parser.add_argument(
            "--expires-in-days",
            type=int,
            default=None,
            help=(
                "Optional validity period in days from "
                "now. Omit for a token that stays valid "
                "until revoked."
            ),
        )

    def handle(self, *args, **options):

        username = options["username"]
        organisation_name = options["organisation"]

        user = User.objects.filter(
            username=username,
        ).first()

        if user is None:

            raise CommandError(
                f"User '{username}' does not exist. "
                f"Create it first (e.g. in /admin/ or via "
                f"seed_organisation --admin-username)."
            )

        organisation = Organisation.objects.filter(
            name=organisation_name,
        ).first()

        if organisation is None:

            raise CommandError(
                f"Organisation '{organisation_name}' does "
                f"not exist."
            )

        membership = OrganisationMembership.objects.filter(
            user=user,
            organisation=organisation,
            is_active=True,
        ).first()

        if membership is None:

            raise CommandError(
                f"User '{username}' has no active "
                f"membership in "
                f"'{organisation_name}'. Add one in "
                f"/admin/ -> Organisation memberships "
                f"first."
            )

        expires_at = None

        if options["expires_in_days"] is not None:

            if options["expires_in_days"] <= 0:

                raise CommandError(
                    "--expires-in-days must be a positive "
                    "number of days."
                )

            expires_at = timezone.now() + timedelta(
                days=options["expires_in_days"],
            )

        if (
            ApiToken.objects
            .filter(
                organisation=organisation,
                name=options["name"],
            )
            .exists()
        ):

            raise CommandError(
                f"A token named '{options['name']}' already "
                f"exists in '{organisation_name}'. Token "
                f"names are unique per organisation — "
                f"choose another name or revoke the "
                f"existing token first."
            )

        token, raw_key = ApiToken.issue(
            user=user,
            organisation=organisation,
            name=options["name"],
            expires_at=expires_at,
        )

        record_audit(
            organisation=organisation,
            actor=user,
            action="integration.token_created",
            object_type="api_token",
            object_id=token.pk,
            detail={
                "token_name": token.name,
                "username": username,
                "issued_via": "management_command",
            },
        )

        expiry_line = "never (until revoked)"

        if expires_at is not None:

            expiry_line = expires_at.isoformat()

        self.stdout.write(
            self.style.SUCCESS(
                "API token created. COPY THE KEY NOW — it "
                "is shown only once and cannot be "
                "recovered:"
            )
        )

        self.stdout.write(raw_key)

        self.stdout.write(
            f"user={username} "
            f"organisation='{organisation_name}' "
            f"name='{token.name}' "
            f"expires={expiry_line}"
        )

        self.stdout.write(
            "Verify with: curl "
            "https://YOUR-HOST/api/v1/whoami/ "
            "-H 'Authorization: Token " + token.prefix +
            "...'"
        )
