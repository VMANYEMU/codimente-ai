from django.urls import path
from . import views


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
]