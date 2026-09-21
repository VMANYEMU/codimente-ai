from sentence_transformers import SentenceTransformer


class EmbeddingService:
    _model = None

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSIONS = 384

    @classmethod
    def get_model(cls):
        if cls._model is None:
            cls._model = SentenceTransformer(cls.MODEL_NAME)
        return cls._model

    @classmethod
    def embed_text(cls, text):
        if not text or not text.strip():
            raise ValueError("Cannot generate an embedding for empty text.")

        model = cls.get_model()

        embedding = model.encode(
            text,
            normalize_embeddings=True,
        )

        return embedding.tolist()

    @classmethod
    def embed_texts(cls, texts):
        clean_texts = [
            text for text in texts
            if text and text.strip()
        ]

        if not clean_texts:
            return []

        model = cls.get_model()

        embeddings = model.encode(
            clean_texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )

        return embeddings.tolist()