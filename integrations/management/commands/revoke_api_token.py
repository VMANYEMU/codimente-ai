"""
Revoke an API token by name (and organisation) — the CLI
counterpart to unticking Active in /admin/. The token row is
kept for the audit trail; only its active flag flips.

Usage:

    python manage.py revoke_api_token \
        --name "Intranet portal" \
        --organisation "Codimente Demo Organisation"
"""

from django.core.management.base import BaseCommand, CommandError

from core.models import Organisation
from core.services import record_audit

from integrations.models import ApiToken


class Command(BaseCommand):

    help = (
        "Deactivate an API token so its key stops working "
        "immediately. The token record is kept for the "
        "audit trail."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--name",
            required=True,
            help="Name of the token to revoke.",
        )

        parser.add_argument(
            "--organisation",
            required=True,
            help=(
                "Name of the organisation the token "
                "belongs to."
            ),
        )

    def handle(self, *args, **options):

        organisation = Organisation.objects.filter(
            name=options["organisation"],
        ).first()

        if organisation is None:

            raise CommandError(
                f"Organisation "
                f"'{options['organisation']}' does not "
                f"exist."
            )

        token = ApiToken.objects.filter(
            organisation=organisation,
            name=options["name"],
        ).first()

        if token is None:

            raise CommandError(
                f"No token named '{options['name']}' "
                f"exists in "
                f"'{options['organisation']}'."
            )

        if not token.is_active:

            self.stdout.write(
                f"Token '{token.name}' "
                f"({token.prefix}...) is already "
                f"revoked."
            )

            return

        token.is_active = False
        token.save()

        record_audit(
            organisation=organisation,
            actor=token.user,
            action="integration.token_revoked",
            object_type="api_token",
            object_id=token.pk,
            detail={
                "token_name": token.name,
                "username": token.user.username,
                "revoked_via": "management_command",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Token '{token.name}' ({token.prefix}...) "
                f"revoked. Requests with its key now "
                f"receive 401."
            )
        )
