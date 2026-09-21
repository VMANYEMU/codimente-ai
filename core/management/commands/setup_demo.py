from django.core.management.base import BaseCommand

from core.models import Organisation
from ai.models import Assistant
from knowledge.models import KnowledgeBase


class Command(BaseCommand):

    help = "Create the Codimente Private AI demo organisation"

    def handle(self, *args, **options):

        organisation, created = Organisation.objects.get_or_create(
            name="Codimente Demo Organisation",
            defaults={
                "description": (
                    "Demonstration organisation for "
                    "Codimente Private AI."
                )
            },
        )

        assistants = [
            {
                "name": "General Assistant",
                "slug": "general",
                "description": "General organisational assistant.",
                "system_prompt": (
                    "You are the General Assistant for this organisation. "
                    "Provide professional and concise assistance. "
                    "Do not invent organisational facts."
                ),
            },
            {
                "name": "Human Resources",
                "slug": "human-resources",
                "description": "Human Resources assistant.",
                "system_prompt": (
                    "You are the Human Resources assistant. "
                    "Assist with HR policies, procedures and authorised "
                    "employee information. Do not invent HR policies or "
                    "employee information."
                ),
            },
            {
                "name": "Finance",
                "slug": "finance",
                "description": "Finance assistant.",
                "system_prompt": (
                    "You are the Finance assistant. "
                    "Assist with authorised financial information, "
                    "policies and analysis. Do not invent financial data."
                ),
            },
            {
                "name": "Procurement",
                "slug": "procurement",
                "description": "Procurement assistant.",
                "system_prompt": (
                    "You are the Procurement assistant. "
                    "Assist with procurement policies, procedures, "
                    "contracts and authorised procurement information."
                ),
            },
            {
                "name": "ICT Support",
                "slug": "ict-support",
                "description": "ICT support assistant.",
                "system_prompt": (
                    "You are the ICT Support assistant. "
                    "Assist with approved ICT documentation, procedures, "
                    "systems and troubleshooting information."
                ),
            },
        ]

        for item in assistants:

            assistant, assistant_created = Assistant.objects.update_or_create(
                organisation=organisation,
                slug=item["slug"],
                defaults={
                    "name": item["name"],
                    "description": item["description"],
                    "system_prompt": item["system_prompt"],
                    "is_active": True,
                },
            )

            KnowledgeBase.objects.get_or_create(
                organisation=organisation,
                assistant=assistant,
                defaults={
                    "name": f"{assistant.name} Knowledge Base",
                    "description": (
                        f"Knowledge used by the "
                        f"{assistant.name}."
                    ),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Codimente Private AI demo environment created."
            )
        )