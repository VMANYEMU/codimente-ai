import re

from pgvector.django import CosineDistance

from knowledge.models import DocumentChunk
from knowledge.services.embedding_service import EmbeddingService


STOP_WORDS = {
    "the", "a", "an", "is", "are", "of", "to", "for",
    "and", "in", "on", "this", "that", "what", "how",
    "can", "does", "do", "i", "my", "me",
}

MIN_HYBRID_SCORE = 0.25

def tokenize(text):
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

    return {
        word
        for word in words
        if word not in STOP_WORDS
    }



def calculate_keyword_score(query, content):
    """
    Return a simple lexical overlap score between 0 and 1.
    """

    query_words = tokenize(query)

    if not query_words:
        return 0.0

    content_words = tokenize(content)

    matches = query_words.intersection(content_words)

    return len(matches) / len(query_words)


def semantic_retrieve(assistant, query, limit=5):
    """
    Retrieve candidate chunks using pgvector, then attach
    semantic, keyword and hybrid scores.
    """

    query_embedding = EmbeddingService.embed_text(query)

    # Retrieve more candidates than ultimately required.
    candidate_limit = max(limit * 3, 10)

    candidates = list(
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
        .order_by("distance")[:candidate_limit]
    )

    for chunk in candidates:
        semantic_score = 1 - float(chunk.distance)

        keyword_score = calculate_keyword_score(
            query,
            chunk.content,
        )

        # Semantic meaning carries most of the weight.
        hybrid_score = (
            semantic_score * 0.75
            + keyword_score * 0.25
        )

        chunk.similarity = semantic_score
        chunk.keyword_score = keyword_score
        chunk.hybrid_score = hybrid_score

    candidates.sort(
        key=lambda chunk: chunk.hybrid_score,
        reverse=True,
    )

    relevant_candidates = [
        chunk
        for chunk in candidates
        if chunk.hybrid_score >= MIN_HYBRID_SCORE
    ]

    return relevant_candidates[:limit]


def keyword_retrieve(assistant, query, limit=5):
    """
    Fallback retrieval if semantic retrieval is unavailable.
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
    Main knowledge retrieval entry point.

    Semantic/hybrid retrieval is authoritative when
    embeddings are available. Keyword retrieval is used
    only if semantic retrieval fails technically.
    """

    try:
        return semantic_retrieve(
            assistant,
            query,
            limit,
        )

    except Exception as exc:
        print(
            f"Semantic retrieval failed: {exc}"
        )

        return keyword_retrieve(
            assistant,
            query,
            limit,
        )