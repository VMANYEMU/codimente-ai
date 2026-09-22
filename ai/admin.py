from django.contrib import admin

from .models import (
    Assistant,
    AssistantAccess,
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