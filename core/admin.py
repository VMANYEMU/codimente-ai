from django.contrib import admin

from .models import (
    Organisation,
    OrganisationMembership,
)


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "created_at",
    )

    search_fields = (
        "name",
    )


@admin.register(OrganisationMembership)
class OrganisationMembershipAdmin(
    admin.ModelAdmin
):
    list_display = (
        "user",
        "organisation",
        "role",
        "is_active",
        "created_at",
    )

    list_filter = (
        "organisation",
        "role",
        "is_active",
    )

    search_fields = (
        "user__username",
        "user__email",
        "organisation__name",
    )