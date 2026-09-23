from django.contrib import admin

from .models import (
    Assistant,
    AssistantAccess,
    Conversation,
    Message,
)


@admin.register(Assistant)
class AssistantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organisation",
        "slug",
        "is_active",
    )

    list_filter = (
        "organisation",
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
        "organisation__name",
    )


@admin.register(AssistantAccess)
class AssistantAccessAdmin(admin.ModelAdmin):
    list_display = (
        "membership",
        "assistant",
        "created_at",
    )

    list_filter = (
        "assistant",
    )

    search_fields = (
        "membership__user__username",
        "assistant__name",
    )

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "user",
        "organisation",
        "assistant",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "organisation",
        "assistant",
        "created_at",
    )

    search_fields = (
        "title",
        "user__username",
        "assistant__name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "role",
        "created_at",
    )

    list_filter = (
        "role",
        "created_at",
    )

    search_fields = (
        "conversation__title",
        "conversation__user__username",
        "content",
    )

    readonly_fields = (
        "created_at",
    )