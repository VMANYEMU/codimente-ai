from django.contrib import admin

from core.services import record_audit

from .models import ApiToken, generate_api_key, hash_api_key


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "organisation",
        "user",
        "prefix",
        "is_active",
        "expires_at",
        "last_used_at",
        "created_at",
    )

    list_filter = (
        "organisation",
        "is_active",
    )

    search_fields = (
        "name",
        "user__username",
        "organisation__name",
    )

    readonly_fields = (
        "prefix",
        "key_hash",
        "last_used_at",
        "created_at",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "user",
                    "organisation",
                    "expires_at",
                    "is_active",
                )
            },
        ),
        (
            "Automatic (read-only)",
            {
                "fields": (
                    "prefix",
                    "key_hash",
                    "last_used_at",
                    "created_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):

        if not change:

            # Issue the secret here so the row is created
            # with its hash in one save. The raw key exists
            # only in the response message — it is never
            # stored — so this is the one chance to copy it.

            raw_key = generate_api_key()

            obj.key_hash = hash_api_key(raw_key)
            obj.prefix = raw_key[:10]

            super().save_model(
                request,
                obj,
                form,
                change,
            )

            self.message_user(
                request,
                "API token created. COPY THE KEY NOW — it is "
                "shown only once and cannot be recovered: "
                + raw_key,
            )

            record_audit(
                organisation=obj.organisation,
                actor=request.user,
                action="integration.token_created",
                object_type="api_token",
                object_id=obj.pk,
                detail={
                    "token_name": obj.name,
                    "username": obj.user.username,
                },
            )

            return

        was_active = (
            ApiToken.objects.get(pk=obj.pk).is_active
        )

        super().save_model(
            request,
            obj,
            form,
            change,
        )

        if was_active and not obj.is_active:

            record_audit(
                organisation=obj.organisation,
                actor=request.user,
                action="integration.token_revoked",
                object_type="api_token",
                object_id=obj.pk,
                detail={
                    "token_name": obj.name,
                    "username": obj.user.username,
                },
            )

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):

        # Prefer deactivating over deleting so the audit
        # trail keeps its references intact.

        return False
