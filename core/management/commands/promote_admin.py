"""
Grant Django /admin/ access to portal users.

The organisation portal and the Django admin are two separate
permission layers:

- The portal sidebar links ("Manage knowledge", "Audit log")
  require an organisation membership with role "admin".
- The Django admin (/admin/) requires is_staff=True on the
  Django user itself — organisation rights do not grant it.

This command promotes portal users into Django admins
idempotently (safe to run repeatedly). There is intentionally
no demote action here: revoking staff status is a manual,
deliberate decision in /admin/ itself.

Usage:

    python manage.py promote_admin                  # all org admins
    python manage.py promote_admin --username guest # one user
    python manage.py promote_admin --username a --username b
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.models import OrganisationMembership


class Command(BaseCommand):

    help = (
        "Grant Django admin (staff + superuser) status to "
        "portal users. Without --username, every active "
        "organisation admin is promoted. Idempotent."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--username",
            action="append",
            default=[],
            help=(
                "Username to promote. Repeatable. Without any "
                "--username, all active organisation admins "
                "are promoted."
            ),
        )

    def handle(self, *args, **options):

        usernames = options["username"]

        if usernames:

            users = []

            for username in usernames:

                user = User.objects.filter(
                    username=username,
                ).first()

                if user is None:

                    raise CommandError(
                        f"User '{username}' does not exist."
                    )

                users.append(user)

        else:

            users = list(
                User.objects.filter(
                    organisation_memberships__role="admin",
                    organisation_memberships__is_active=True,
                )
                .distinct()
                .order_by("username")
            )

            if not users:

                self.stdout.write(
                    "No active organisation admins found; "
                    "nothing to promote."
                )

                return

        for user in users:

            was_active = user.is_active

            if (
                user.is_staff
                and user.is_superuser
                and was_active
            ):

                self.stdout.write(
                    f"'{user.username}' already has Django "
                    f"admin access."
                )

                continue

            # is_active=False also produces 403 on
            # /admin/, so promotion reactivates the
            # account as well.

            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()

            if was_active:

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Granted Django admin access to "
                        f"'{user.username}'. They can now "
                        f"sign in at /admin/."
                    )
                )

            else:

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Reactivated '{user.username}' "
                        f"and granted Django admin access."
                    )
                )
