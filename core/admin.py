from django.contrib import admin

from .models import (
    AuditLog,
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


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    # The audit trail is append-only: view it in the
    # admin, but never edit or delete history there.

    list_display = (
        "created_at",
        "actor_username",
        "action",
        "object_type",
        "object_id",
    )

    list_filter = (
        "action",
        "organisation",
    )

    search_fields = (
        "actor_username",
        "action",
        "object_type",
        "object_id",
    )

    date_hierarchy = "created_at"

    readonly_fields = (
        "created_at",
        "organisation",
        "actor",
        "actor_username",
        "action",
        "object_type",
        "object_id",
        "detail",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False