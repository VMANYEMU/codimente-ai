from django.core.exceptions import ValidationError
from django.db import models

from core.models import Organisation

class Assistant(models.Model):

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="assistants",
    )

    name = models.CharField(max_length=100)

    slug = models.SlugField(max_length=100)

    description = models.TextField(blank=True)

    system_prompt = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "organisation",
            "slug",
        )

    def __str__(self):
        return f"{self.organisation.name} - {self.name}"
        
       
class AssistantAccess(models.Model):
    membership = models.ForeignKey(
        "core.OrganisationMembership",
        on_delete=models.CASCADE,
        related_name="assistant_access",
    )

    assistant = models.ForeignKey(
        Assistant,
        on_delete=models.CASCADE,
        related_name="access_permissions",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "membership",
                    "assistant",
                ],
                name="unique_assistant_access",
            )
        ]

    def clean(self):
        super().clean()

        if (
            self.membership_id
            and self.assistant_id
            and self.membership.organisation_id
            != self.assistant.organisation_id
        ):
            raise ValidationError(
                {
                    "assistant": (
                        "The assistant must belong to the "
                        "same organisation as the membership."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.membership.user.username} - "
            f"{self.assistant.name}"
        )