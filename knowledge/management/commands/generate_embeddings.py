from django.core.management.base import BaseCommand

from knowledge.models import DocumentChunk
from knowledge.services.embedding_service import EmbeddingService


class Command(BaseCommand):
    help = "Generate embeddings for document chunks."

    def handle(self, *args, **options):
        chunks = list(
            DocumentChunk.objects.filter(
                embedding__isnull=True
            ).order_by("id")
        )

        if not chunks:
            self.stdout.write(
                self.style.SUCCESS(
                    "No document chunks require embeddings."
                )
            )
            return

        self.stdout.write(
            f"Generating embeddings for {len(chunks)} chunks..."
        )

        texts = [chunk.content for chunk in chunks]

        embeddings = EmbeddingService.embed_texts(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        DocumentChunk.objects.bulk_update(
            chunks,
            ["embedding"],
            batch_size=100,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {len(embeddings)} embeddings successfully."
            )
        )