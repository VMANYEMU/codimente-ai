import re

from pgvector.django import CosineDistance

from knowledge.models import DocumentChunk
from knowledge.services.embedding_service import EmbeddingService


STOP_WORDS = {
    "the", "a", "an", "is", "are", "of", "to", "for",
    "and", "in", "on", "this", "that", "what", "how",
    "can", "does", "do",
}


def tokenize(text):
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return {
        word for word in words
        if word not in STOP_WORDS
    }


def semantic_retrieve(assistant, query, limit=5):
    """
    Retrieve document chunks using semantic similarity.
    """

    query_embedding = EmbeddingService.embed_text(query)

    return list(
        DocumentChunk.objects.filter(
            document__knowledge_base__assistant=assistant,
            document__is_processed=True,
            embedding__isnull=False,
        )
        .select_related(
            "document",
            "document__knowledge_base",
        )
        .annotate(
            distance=CosineDistance(
                "embedding",
                query_embedding,
            )
        )
        .order_by("distance")[:limit]
    )


def keyword_retrieve(assistant, query, limit=5):
    """
    Fallback keyword retrieval for chunks without embeddings
    or if semantic retrieval fails.
    """

    query_words = tokenize(query)

    chunks = DocumentChunk.objects.filter(
        document__knowledge_base__assistant=assistant,
        document__is_processed=True,
    ).select_related(
        "document",
        "document__knowledge_base",
    )

    scored_chunks = []

    for chunk in chunks:
        chunk_words = tokenize(chunk.content)

        score = len(
            query_words.intersection(chunk_words)
        )

        if score > 0:
            scored_chunks.append(
                (score, chunk)
            )

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        chunk
        for score, chunk
        in scored_chunks[:limit]
    ]


def retrieve_knowledge(assistant, query, limit=5):
    """
    Main retrieval entry point.

    Semantic retrieval is preferred.
    Keyword retrieval remains available as a fallback.
    """

    try:
        semantic_results = semantic_retrieve(
            assistant,
            query,
            limit,
        )

        if semantic_results:
            return semantic_results

    except Exception as exc:
        print(
            f"Semantic retrieval failed: {exc}"
        )

    return keyword_retrieve(
        assistant,
        query,
        limit,
    )