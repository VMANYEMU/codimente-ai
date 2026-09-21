from django.db import models
from pgvector.django import VectorField
from core.models import Organisation
from ai.models import Assistant


class KnowledgeBase(models.Model):

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="knowledge_bases",
    )

    assistant = models.ForeignKey(
        Assistant,
        on_delete=models.CASCADE,
        related_name="knowledge_bases",
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Document(models.Model):

    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    title = models.CharField(max_length=255)

    file = models.FileField(
        upload_to="knowledge/documents/"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    is_processed = models.BooleanField(
        default=False
    )

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()

    page_number = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]

    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_index}"