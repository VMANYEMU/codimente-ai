"""
Text embedding service.

Two backends, selected with EMBEDDINGS_BACKEND:

- "api" (default): the Hugging Face Inference API. The web
  process never loads torch, which keeps the hosted demo
  far below its 512 MB memory limit and makes builds fast.
- "local": the original in-process sentence-transformers
  model, for on-premises and air-gapped installs. Requires
  `pip install sentence-transformers` on that machine.

Both produce 384-dimensional all-MiniLM-L6-v2 vectors, so
pgvector data is interchangeable between the backends.
"""

import os

import requests


class EmbeddingService:

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSIONS = 384

    API_TIMEOUT_SECONDS = 30

    @classmethod
    def _backend(cls):

        return os.getenv(
            "EMBEDDINGS_BACKEND",
            "api",
        ).strip().lower()

    # -----------------------------------------------------
    # API backend (default)
    # -----------------------------------------------------

    @classmethod
    def _api_url(cls):

        return os.getenv(
            "EMBEDDINGS_API_URL",
            (
                "https://router.huggingface.co/hf-inference"
                "/models/sentence-transformers"
                "/all-MiniLM-L6-v2/pipeline/feature-extraction"
            ),
        )

    @classmethod
    def _embed_via_api(cls, texts):

        token = os.getenv("HF_TOKEN")

        if not token:
            raise RuntimeError(
                "HF_TOKEN is not configured for the "
                "embeddings API backend."
            )

        response = requests.post(
            cls._api_url(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"inputs": texts},
            timeout=cls.API_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:

            raise RuntimeError(
                "Embeddings API returned "
                f"{response.status_code}: "
                f"{response.text[:200]}"
            )

        raw = response.json()

        return [
            cls._as_vector(item)
            for item in raw
        ]

    @classmethod
    def _as_vector(cls, item):

        # The API can answer with a pooled vector
        # [float, ...] or with per-token vectors
        # [[float, ...], ...]; the latter is mean-pooled.

        if item and isinstance(item[0], list):

            item = [
                sum(values) / len(values)
                for values in zip(*item)
            ]

        vector = [float(value) for value in item]

        if len(vector) != cls.DIMENSIONS:

            raise RuntimeError(
                "Embeddings API returned vectors of "
                f"dimension {len(vector)}, expected "
                f"{cls.DIMENSIONS}."
            )

        return vector

    # -----------------------------------------------------
    # Local backend (on-premises / air-gapped installs)
    # -----------------------------------------------------

    @classmethod
    def _embed_via_local(cls, texts):

        try:

            from sentence_transformers import (
                SentenceTransformer,
            )

        except ImportError:

            raise RuntimeError(
                "EMBEDDINGS_BACKEND=local requires the "
                "sentence-transformers package: "
                "pip install sentence-transformers"
            )

        if not hasattr(cls, "_local_model"):

            cls._local_model = SentenceTransformer(
                cls.MODEL_NAME
            )

        embeddings = cls._local_model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )

        return [
            [float(value) for value in vector]
            for vector in embeddings
        ]

    # -----------------------------------------------------
    # Public interface (unchanged for callers)
    # -----------------------------------------------------

    @classmethod
    def embed_text(cls, text):

        if not text or not text.strip():
            raise ValueError(
                "Cannot generate an embedding for empty "
                "text."
            )

        return cls.embed_texts([text])[0]

    @classmethod
    def embed_texts(cls, texts):

        clean_texts = [
            text for text in texts
            if text and text.strip()
        ]

        if not clean_texts:
            return []

        if cls._backend() == "local":
            return cls._embed_via_local(clean_texts)

        return cls._embed_via_api(clean_texts)
