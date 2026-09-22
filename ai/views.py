from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from knowledge.services.retriever import retrieve_knowledge
from core.models import OrganisationMembership
from .models import Assistant
from .providers.hosted_provider import HostedProvider


@api_view(["POST"])
def chat_api(request):

    # Get the user's question
    message = request.data.get(
        "message",
        ""
    ).strip()

    # Get the selected assistant
    assistant_slug = request.data.get(
        "assistant",
        "general"
    )
    if not request.user.is_authenticated:
        return Response(
            {
                "error": "Authentication is required."
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )


    membership = (
        OrganisationMembership.objects
        .filter(
            user=request.user,
            is_active=True,
        )
        .select_related("organisation")
        .first()
    )

    if membership is None:
        return Response(
            {
                "error": (
                    "No active organisation "
                    "membership was found."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Make sure a question was supplied
    if not message:

        return Response(
            {"error": "A message is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Find the selected assistant
    try:

        assistant = Assistant.objects.get(
            slug=assistant_slug,
            organisation=membership.organisation,
            is_active=True,
            access_permissions__membership=membership,
        )

    except Assistant.DoesNotExist:

        return Response(
            {
                "error": (
                    "You do not have access "
                    "to this assistant."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:

        # -----------------------------------------
        # RAG STEP 1:
        # Search this assistant's knowledge base
        # -----------------------------------------

        knowledge_chunks = retrieve_knowledge(
            assistant,
            message,
        )

        # -----------------------------------------
        # RAG STEP 2:
        # Combine retrieved chunks into context
        # -----------------------------------------

        knowledge_context = ""

        if knowledge_chunks:

            knowledge_context = "\n\n".join(
                chunk.content
                for chunk in knowledge_chunks
            )

        # -----------------------------------------
        # RAG STEP 3:
        # Build assistant instructions
        # -----------------------------------------

        rag_prompt = assistant.system_prompt

        if knowledge_context:

            rag_prompt += (
                "\n\n"
                "The following information was retrieved "
                "from the organisation's approved "
                "knowledge base:\n\n"
                f"{knowledge_context}\n\n"
                "Answer the user's question using this "
                "organisational information. "
                "Do not contradict or invent information "
                "that is not supported by the supplied "
                "organisational knowledge."
            )

        else:

            rag_prompt += (
                "\n\n"
                "No relevant organisational knowledge "
                "was retrieved for this question. "
                "Do not invent organisation-specific facts."
            )

        # -----------------------------------------
        # RAG STEP 4:
        # Send question + retrieved knowledge
        # to the LLM
        # -----------------------------------------

        provider = HostedProvider()

        answer = provider.chat(
            message=message,
            system_prompt=rag_prompt,
        )

        # -----------------------------------------
        # RAG STEP 5:
        # Return answer AND its sources
        # -----------------------------------------

        return Response(
            {
                "message": message,
                "answer": answer,
                "assistant": assistant.name,
                "provider": "huggingface",

                "sources": [
                {
                    "title": chunk.document.title,
                    "page": chunk.page_number,
                    "knowledge_base": chunk.document.knowledge_base.name,
                    "chunk_index": chunk.chunk_index,
                    "similarity": round(
                        getattr(chunk, "similarity", 0),
                        4,
                    ),
                }
                for chunk in knowledge_chunks
            ],
            }
        )

    except Exception as exc:

        print(f"AI Provider Error: {exc}")

        return Response(
            {
                "error": (
                    "Codimente AI could not obtain "
                    "a response from the AI provider."
                )
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )