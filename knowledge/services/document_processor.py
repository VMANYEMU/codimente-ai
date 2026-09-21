from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from knowledge.models import DocumentChunk
from knowledge.services.embedding_service import EmbeddingService


def extract_pdf(file_path):
    reader = PdfReader(file_path)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            pages.append({
                "page": page_number,
                "text": text,
            })

    return pages


def extract_docx(file_path):
    document = DocxDocument(file_path)

    text = "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    )

    return [{
        "page": None,
        "text": text,
    }]


def extract_txt(file_path):
    with open(
        file_path,
        "r",
        encoding="utf-8",
    ) as file:
        text = file.read()

    return [{
        "page": None,
        "text": text,
    }]


def chunk_text(
    text,
    chunk_size=1200,
    overlap=200,
):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def process_document(document):
    file_path = document.file.path
    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        pages = extract_pdf(file_path)

    elif extension == ".docx":
        pages = extract_docx(file_path)

    elif extension == ".txt":
        pages = extract_txt(file_path)

    else:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    prepared_chunks = []
    chunk_index = 0

    for page in pages:
        chunks = chunk_text(page["text"])

        for content in chunks:
            prepared_chunks.append({
                "chunk_index": chunk_index,
                "content": content,
                "page_number": page["page"],
            })

            chunk_index += 1

    if not prepared_chunks:
        raise ValueError(
            "No readable text was found in the document."
        )

    # Generate embeddings in one batch.
    texts = [
        item["content"]
        for item in prepared_chunks
    ]

    embeddings = EmbeddingService.embed_texts(
        texts
    )

    if len(embeddings) != len(prepared_chunks):
        raise ValueError(
            "Embedding count does not match "
            "document chunk count."
        )

    # Only remove the old chunks after extraction
    # and embedding generation have succeeded.
    document.chunks.all().delete()

    document_chunks = []

    for item, embedding in zip(
        prepared_chunks,
        embeddings,
    ):
        document_chunks.append(
            DocumentChunk(
                document=document,
                chunk_index=item["chunk_index"],
                content=item["content"],
                page_number=item["page_number"],
                embedding=embedding,
            )
        )

    DocumentChunk.objects.bulk_create(
        document_chunks,
        batch_size=100,
    )

    document.is_processed = True
    document.save(
        update_fields=["is_processed"]
    )

    return len(document_chunks)