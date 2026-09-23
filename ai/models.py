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

class Conversation(models.Model):
    organisation = models.ForeignKey(
        "core.Organisation",
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )

    assistant = models.ForeignKey(
        Assistant,
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    title = models.CharField(
        max_length=200,
        default="New conversation",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        super().clean()

        if (
            self.organisation_id
            and self.assistant_id
            and self.organisation_id
            != self.assistant.organisation_id
        ):
            raise ValidationError(
                {
                    "assistant": (
                        "The assistant must belong to the "
                        "conversation organisation."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.title}"
        )


class Message(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
    )

    content = models.TextField()

    sources = models.JSONField(
        default=list,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "created_at",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.conversation_id} - "
            f"{self.role}"
        )