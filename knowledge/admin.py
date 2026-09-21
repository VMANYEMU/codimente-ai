from django.contrib import admin

from .models import (
    KnowledgeBase,
    Document,
    DocumentChunk,
)


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organisation",
        "assistant",
    )


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "knowledge_base",
        "is_processed",
        "uploaded_at",
    )

    list_filter = (
        "is_processed",
        "knowledge_base",
    )

    actions = [
        "process_selected_documents"
    ]

    @admin.action(
        description="Process selected documents"
    )
    def process_selected_documents(
        self,
        request,
        queryset,
    ):

        from .services.document_processor import (
            process_document,
        )

        total_chunks = 0

        for document in queryset:

            total_chunks += process_document(
                document
            )

        self.message_user(
            request,
            (
                f"Documents processed successfully. "
                f"{total_chunks} chunks created."
            )
        )


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = (
        "document",
        "chunk_index",
        "page_number",
    )