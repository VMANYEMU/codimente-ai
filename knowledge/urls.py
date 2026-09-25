from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.knowledge_home,
        name="knowledge-home",
    ),
    path(
        "upload/<slug:assistant_slug>/",
        views.document_upload,
        name="document-upload",
    ),
    path(
        "documents/<int:document_id>/reprocess/",
        views.document_reprocess,
        name="document-reprocess",
    ),
    path(
        "documents/<int:document_id>/delete/",
        views.document_delete,
        name="document-delete",
    ),
]
