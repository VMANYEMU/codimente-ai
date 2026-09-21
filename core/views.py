from django.shortcuts import render, get_object_or_404

from ai.models import Assistant


def home(request):
    return render(request, "core/home.html")


def chat(request, assistant_slug="general"):

    assistants = Assistant.objects.filter(
        is_active=True
    ).order_by("id")

    active_assistant = get_object_or_404(
        Assistant,
        slug=assistant_slug,
        is_active=True,
    )

    context = {
        "assistants": assistants,
        "active_assistant": active_assistant,
    }

    return render(
        request,
        "core/chat.html",
        context,
    )