from django.urls import path

from .views import (
    chat_api,
    conversation_detail,
    conversation_list,
)


urlpatterns = [
    path(
        "chat/",
        chat_api,
        name="ai-chat",
    ),

    path(
        "conversations/",
        conversation_list,
        name="conversation-list",
    ),

    path(
        "conversations/<int:conversation_id>/",
        conversation_detail,
        name="conversation-detail",
    ),
]