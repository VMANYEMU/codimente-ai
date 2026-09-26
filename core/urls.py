from django.urls import path
from . import views
from . import audit_views


urlpatterns = [
    path("", views.home, name="home"),

    path(
        "chat/",
        views.chat,
        name="chat",
    ),

    path(
        "chat/<slug:assistant_slug>/",
        views.chat,
        name="assistant-chat",
    ),

    path(
        "organisations/<int:membership_id>/switch/",
        views.organisation_switch,
        name="organisation-switch",
    ),

    path(
        "audit/",
        audit_views.audit_log,
        name="audit-log",
    ),
]