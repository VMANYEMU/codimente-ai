from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from knowledge.services.retriever import retrieve_knowledge
from core.models import OrganisationMembership

from .models import (
    Assistant,
    Conversation,
    Message,
)

from .providers.hosted_provider import HostedProvider


@api_view(["POST"])
def chat_api(request):

    # -----------------------------------------
    # 1. Get request data
    # -----------------------------------------

    message = request.data.get(
        "message",
        ""
    ).strip()

    assistant_slug = request.data.get(
        "assistant",
        "general"
    )

    conversation_id = request.data.get(
        "conversation_id"
    )

    # -----------------------------------------
    # 2. Require authentication
    # -----------------------------------------

    if not request.user.is_authenticated:
        return Response(
            {
                "error": "Authentication is required."
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # -----------------------------------------
    # 3. Find active organisation membership
    # -----------------------------------------

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

    # -----------------------------------------
    # 4. Validate the question
    # -----------------------------------------

    if not message:
        return Response(
            {
                "error": "A message is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # -----------------------------------------
    # 5. Authorize selected assistant
    # -----------------------------------------

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

    # -----------------------------------------
    # 6. Find or create conversation
    # -----------------------------------------

    if conversation_id:

        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                user=request.user,
                organisation=membership.organisation,
                assistant=assistant,
            )

        except Conversation.DoesNotExist:
            return Response(
                {
                    "error": (
                        "Conversation not found or "
                        "access is not permitted."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    else:

        conversation = Conversation.objects.create(
            organisation=membership.organisation,
            user=request.user,
            assistant=assistant,
            title=message[:80],
        )

    # -----------------------------------------
    # 7. Load PREVIOUS conversation history
    #
    # Do this BEFORE saving the new message.
    # This makes it clear which messages are
    # history and which message is current.
    # -----------------------------------------

    conversation_history = list(
        conversation.messages
        .order_by(
            "-created_at",
            "-id",
        )[:10]
    )

    # Database query returned newest first.
    # The LLM needs oldest -> newest.
    conversation_history.reverse()

    # -----------------------------------------
    # 8. Build contextual retrieval query
    #
    # The vector search must understand vague
    # follow-ups such as:
    #
    # "What happens to the rest?"
    # "What about the limit?"
    # "And after that?"
    #
    # We therefore give retrieval a small amount
    # of recent conversational context.
    # -----------------------------------------

    retrieval_parts = []

    # Use only the most recent four previous
    # messages for retrieval context.
    for history_message in conversation_history[-4:]:

        if history_message.role == "user":
            retrieval_parts.append(
                "Previous user question: "
                + history_message.content
            )

        elif history_message.role == "assistant":
            retrieval_parts.append(
                "Previous assistant answer: "
                + history_message.content
            )

    retrieval_parts.append(
        "Current user question: "
        + message
    )

    retrieval_query = "\n".join(
        retrieval_parts
    )

    # -----------------------------------------
    # 9. Save current user's message
    # -----------------------------------------

    Message.objects.create(
        conversation=conversation,
        role="user",
        content=message,
    )

    try:

        # -----------------------------------------
        # 10. Retrieve organisational knowledge
        #
        # IMPORTANT:
        # Search using contextual retrieval_query,
        # not only the latest short question.
        # -----------------------------------------

        knowledge_chunks = retrieve_knowledge(
            assistant,
            retrieval_query,
        )

        # -----------------------------------------
        # 11. Build knowledge context
        # -----------------------------------------

        knowledge_context = ""

        if knowledge_chunks:

            knowledge_context = "\n\n".join(
                chunk.content
                for chunk in knowledge_chunks
            )

        # -----------------------------------------
        # 12. Build grounded RAG instructions
        # -----------------------------------------

        rag_prompt = assistant.system_prompt

        if knowledge_context:

            rag_prompt += (
                "\n\n"
                "IMPORTANT GROUNDING RULES:\n\n"

                "Below is information retrieved from the "
                "organisation's approved knowledge base.\n\n"

                "----- BEGIN APPROVED ORGANISATIONAL KNOWLEDGE -----\n"
                f"{knowledge_context}\n"
                "----- END APPROVED ORGANISATIONAL KNOWLEDGE -----\n\n"

                "For organisation-specific facts, policies, "
                "procedures, rules, thresholds, entitlements, "
                "exceptions, consequences, approvals, deadlines, "
                "systems, finances, employees, or operations, "
                "the approved organisational knowledge above "
                "is your authoritative source.\n\n"

                "Conversation history may be used to understand "
                "references and follow-up questions, but it is "
                "not an authoritative source for new "
                "organisational facts.\n\n"

                "Do NOT supplement organisational policy answers "
                "with general knowledge, common industry practice, "
                "assumptions, typical HR practice, external law, "
                "or information learned during model training.\n\n"

                "Do NOT invent consequences, exceptions, examples, "
                "payout rules, forfeiture rules, approval routes, "
                "thresholds, deadlines, or procedures that are not "
                "supported by the approved organisational knowledge.\n\n"

                "If the approved organisational knowledge answers "
                "only part of the question, answer that part and "
                "clearly state that the available organisational "
                "knowledge does not specify the remaining point.\n\n"

                "If conversation history conflicts with the approved "
                "organisational knowledge, follow the approved "
                "organisational knowledge."
            )

        else:

            rag_prompt += (
                "\n\n"
                "IMPORTANT GROUNDING RULES:\n\n"

                "No sufficiently relevant information was retrieved "
                "from the organisation's approved knowledge base.\n\n"

                "If the user is asking about the organisation, its "
                "policies, procedures, employees, finances, systems, "
                "rules, entitlements, or operations, do not answer "
                "using assumptions or general model knowledge.\n\n"

                "State clearly that the available organisational "
                "knowledge does not provide enough information "
                "to answer the question."
            )

        # -----------------------------------------
        # 13. Ask AI provider
        # -----------------------------------------

        provider = HostedProvider()

        answer = provider.chat(
            message=message,
            system_prompt=rag_prompt,
            conversation_history=conversation_history,
        )

        # -----------------------------------------
        # 14. Prepare source information
        # -----------------------------------------

        sources = [
            {
                "title": chunk.document.title,
                "page": chunk.page_number,
                "knowledge_base": (
                    chunk.document.knowledge_base.name
                ),
                "chunk_index": chunk.chunk_index,
                "similarity": round(
                    getattr(
                        chunk,
                        "similarity",
                        0,
                    ),
                    4,
                ),
            }
            for chunk in knowledge_chunks
        ]

        # -----------------------------------------
        # 15. Save assistant response
        # -----------------------------------------

        Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=answer,
            sources=sources,
        )

        # -----------------------------------------
        # 16. Return response
        # -----------------------------------------

        return Response(
            {
                "message": message,
                "answer": answer,
                "assistant": assistant.name,
                "provider": "huggingface",
                "conversation_id": conversation.id,
                "sources": sources,
            }
        )

    except Exception as exc:

        print(
            f"AI Provider Error: {exc}"
        )

        return Response(
            {
                "error": (
                    "Codimente AI could not obtain "
                    "a response from the AI provider."
                )
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )