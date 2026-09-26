from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView


urlpatterns = [
    path("admin/", admin.site.urls),

    # Search engines are not welcome on this private
    # deployment; point them at a blanket disallow.

    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
        name="robots",
    ),

    # Django authentication
    path("accounts/", include("django.contrib.auth.urls")),

    path("", include("core.urls")),
    path("knowledge/", include("knowledge.urls")),
    path("api/v1/", include("ai.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )