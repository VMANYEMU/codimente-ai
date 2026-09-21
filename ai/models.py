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