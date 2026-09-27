"""
Seed the default organisation data.

Creates (idempotently — safe to run on every deploy):

- the demo organisation
- one Knowledge Base per assistant
- the standard departmental assistants
- an organisation admin user with access to every assistant

The admin username can be overridden with --admin-username
(default: "admin"). The password is taken from --admin-password
or the SEED_ADMIN_PASSWORD environment variable; when neither is
given and the user must be created, a random password is
generated and printed once.

If the admin user already exists (for example a staff account
created by hand in the Django admin), it is left untouched
including its password, but the admin membership and every
assistant access are (re-)applied for it: portal access comes
from memberships and access rows, not from Django flags.
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.crypto import get_random_string

from ai.models import Assistant, AssistantAccess
from core.models import Organisation, OrganisationMembership
from knowledge.models import KnowledgeBase


DEFAULT_ORGANISATION_NAME = "Codimente Demo Organisation"

DEFAULT_ASSISTANTS = [
    {
        "slug": "human-resources",
        "name": "Human Resources",
        "description": (
            "Policies and procedures for leave, benefits, "
            "conduct and employee relations."
        ),
        "system_prompt": (
            "You are the Human Resources assistant. Answer "
            "employee questions strictly from the "
            "organisation's approved HR knowledge."
        ),
    },
    {
        "slug": "finance",
        "name": "Finance",
        "description": (
            "Budgets, invoices, payments and financial policy."
        ),
        "system_prompt": (
            "You are the Finance assistant. Answer questions "
            "strictly from the organisation's approved "
            "finance knowledge."
        ),
    },
    {
        "slug": "procurement",
        "name": "Procurement",
        "description": (
            "Suppliers, purchasing and tender procedures."
        ),
        "system_prompt": (
            "You are the Procurement assistant. Answer "
            "questions strictly from the organisation's "
            "approved procurement knowledge."
        ),
    },
    {
        "slug": "ict-support",
        "name": "ICT Support",
        "description": (
            "Systems, accounts, hardware and IT procedures."
        ),
        "system_prompt": (
            "You are the ICT Support assistant. Answer "
            "questions strictly from the organisation's "
            "approved ICT knowledge."
        ),
    },
    {
        "slug": "general",
        "name": "General Assistant",
        "description": (
            "General organisational questions across all "
            "departments."
        ),
        "system_prompt": (
            "You are the General assistant. Answer questions "
            "strictly from the organisation's approved "
            "knowledge."
        ),
    },
]


class Command(BaseCommand):
    help = (
        "Create the default organisation, assistants, "
        "knowledge bases and an organisation admin user. "
        "Safe to run repeatedly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--organisation",
            default=DEFAULT_ORGANISATION_NAME,
            help="Name of the organisation to seed.",
        )
        parser.add_argument(
            "--admin-username",
            default="admin",
            help="Username for the organisation admin.",
        )
        parser.add_argument(
            "--admin-password",
            default=None,
            help=(
                "Password for the organisation admin. Falls "
                "back to the SEED_ADMIN_PASSWORD environment "
                "variable."
            ),
        )
        parser.add_argument(
            "--admin-email",
            default="",
            help="Email address for the organisation admin.",
        )
        parser.add_argument(
            "--django-admin",
            action="store_true",
            help=(
                "Also grant the admin user Django staff and "
                "superuser status (access to /admin/)."
            ),
        )

    def handle(self, *args, **options):

        # ---------------------------------------------
        # 1. Organisation
        # ---------------------------------------------

        organisation, organisation_created = (
            Organisation.objects.get_or_create(
                name=options["organisation"],
                defaults={
                    "description": (
                        "Default organisation created "
                        "during deployment."
                    )
                },
            )
        )

        self._report(
            organisation_created,
            f"Organisation '{organisation.name}'",
        )

        # ---------------------------------------------
        # 2. Assistants and their knowledge bases
        # ---------------------------------------------

        assistants = []

        for assistant_data in DEFAULT_ASSISTANTS:

            assistant, assistant_created = (
                Assistant.objects.get_or_create(
                    organisation=organisation,
                    slug=assistant_data["slug"],
                    defaults={
                        "name": assistant_data["name"],
                        "description": (
                            assistant_data["description"]
                        ),
                        "system_prompt": (
                            assistant_data["system_prompt"]
                        ),
                        "is_active": True,
                    },
                )
            )

            self._report(
                assistant_created,
                f"Assistant '{assistant.name}'",
            )

            knowledge_base, kb_created = (
                KnowledgeBase.objects.get_or_create(
                    organisation=organisation,
                    assistant=assistant,
                    name=f"{assistant.name} Knowledge",
                    defaults={
                        "description": (
                            "Approved documents for the "
                            f"{assistant.name} assistant."
                        )
                    },
                )
            )

            self._report(
                kb_created,
                f"Knowledge base '{knowledge_base.name}'",
            )

            assistants.append(assistant)

        # ---------------------------------------------
        # 3. Organisation admin user
        # ---------------------------------------------

        admin_username = options["admin_username"]

        admin_user, user_created = User.objects.get_or_create(
            username=admin_username,
            defaults={"email": options["admin_email"]},
        )

        if user_created:

            admin_password = (
                options["admin_password"]
                or os.getenv("SEED_ADMIN_PASSWORD")
            )

            if not admin_password:

                admin_password = get_random_string(
                    length=16,
                )

                self.stdout.write(
                    self.style.WARNING(
                        "No --admin-password or "
                        "SEED_ADMIN_PASSWORD was given, so a "
                        "random password was generated for "
                        f"'{admin_username}': {admin_password}"
                    )
                )

                self.stdout.write(
                    self.style.WARNING(
                        "Sign in and change this password "
                        "immediately."
                    )
                )

            admin_user.set_password(admin_password)
            admin_user.save()

            self.stdout.write(
                f"Created organisation admin "
                f"'{admin_username}'."
            )

        else:

            self.stdout.write(
                f"User '{admin_username}' already exists; "
                f"ensuring organisation membership and "
                f"assistant access."
            )

        # ---------------------------------------------
        # 4. Admin membership
        #
        # Idempotent and applied to existing users too:
        # an account created by hand (for example a
        # superuser added in the Django admin) ends up
        # fully usable in the portal after the next
        # seeding run. Portal access comes from the
        # membership and AssistantAccess rows — Django
        # superuser status plays no part in it.
        # ---------------------------------------------

        membership, membership_created = (
            OrganisationMembership.objects.get_or_create(
                organisation=organisation,
                user=admin_user,
                defaults={"role": "admin", "is_active": True},
            )
        )

        self._report(
            membership_created,
            f"Admin membership for '{admin_username}'",
        )

        # ---------------------------------------------
        # 5. Assistant access for the admin
        # ---------------------------------------------

        for assistant in assistants:

            access, access_created = (
                AssistantAccess.objects.get_or_create(
                    membership=membership,
                    assistant=assistant,
                )
            )

            self._report(
                access_created,
                f"Access '{admin_username}' -> "
                f"{assistant.name}",
            )

        # ---------------------------------------------
        # 6. Optional Django admin status
        # ---------------------------------------------

        if options["django_admin"]:

            if (
                not admin_user.is_staff
                or not admin_user.is_superuser
            ):

                admin_user.is_staff = True
                admin_user.is_superuser = True
                admin_user.save()

                self.stdout.write(
                    f"Granted Django admin status to "
                    f"'{admin_username}'."
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Organisation seeding complete."
            )
        )

    def _report(self, created, description):

        if created:
            self.stdout.write(
                f"Created {description}."
            )
        else:
            self.stdout.write(
                f"{description} already exists."
            )
