from django.contrib import admin

from .models import Assistant


@admin.register(Assistant)
class AssistantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organisation",
        "is_active",
    )

    list_filter = (
        "organisation",
        "is_active",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }