from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView


urlpatterns = [
    path("admin/", admin.site.urls),

    # The public landing page is indexed (the product is for
    # sale); chat, login and the API stay out of search.

    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
        name="robots",
    ),
    path(
        "sitemap.xml",
        TemplateView.as_view(
            template_name="sitemap.xml",
            content_type="application/xml",
        ),
        name="sitemap",
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