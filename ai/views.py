from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.services import get_active_membership
from knowledge.services.retriever import retrieve_knowledge

from .models import Assistant, Conversation, Message
from .providers.hosted_provider import HostedProvider


def get_authorised_assistant(membership, assistant_slug):
    """
    Return the requested assistant when the membership
    is authorised to use it, otherwise None.
    """
    if not assistant_slug:
        return None

    return (
        Assistant.objects
        .filter(
            slug=assistant_slug,
            organisation=membership.organisation,
            is_active=True,
            access_permissions__membership=membership,
        )
        .distinct()
        .first()
    )


@api_view(["POST"])
def chat_api(request):

    # -----------------------------------------
    # 1. Require authentication
    # -----------------------------------------

    if not request.user.is_authenticated:
        return Response(
            {
                "error": "Authentication is required."
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # -----------------------------------------
    # 2. Find active organisation membership
    # -----------------------------------------

    membership = get_active_membership(request)

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
    # 3. Validate the request data
    # -----------------------------------------

    message = (request.data.get("message") or "").strip()

    assistant_slug = (
        request.data.get("assistant") or "general"
    )

    conversation_id = request.data.get("conversation_id")

    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "error": (
                        "The conversation id must be "
                        "a whole number."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    if not message:
        return Response(
            {
                "error": "A message is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # -----------------------------------------
    # 4. Authorize selected assistant
    # -----------------------------------------

    assistant = get_authorised_assistant(
        membership,
        assistant_slug,
    )

    if assistant is None:
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
    # 5. Validate an existing conversation
    #
    # The security chain is enforced here:
    #   the conversation must belong to the
    #   logged-in user, their organisation,
    #   and an assistant they may use.
    # -----------------------------------------

    conversation = None

    if conversation_id:

        conversation = (
            Conversation.objects
            .filter(
                id=conversation_id,
                user=request.user,
                organisation=membership.organisation,
                assistant=assistant,
            )
            .first()
        )

        if conversation is None:
            return Response(
                {
                    "error": (
                        "Conversation not found or "
                        "access is not permitted."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    # -----------------------------------------
    # 6. Load PREVIOUS conversation history
    #
    # Done BEFORE saving the new message so
    # history and the current message stay
    # clearly separated.
    # -----------------------------------------

    conversation_history = []

    if conversation:

        conversation_history = list(
            conversation.messages
            .order_by("-created_at", "-id")[:10]
        )

        # The database returned newest first.
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

    try:

        # -----------------------------------------
        # 8. Retrieve organisational knowledge
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
        # 9. Build knowledge context
        # -----------------------------------------

        knowledge_context = ""

        if knowledge_chunks:

            knowledge_context = "\n\n".join(
                chunk.content
                for chunk in knowledge_chunks
            )

        # -----------------------------------------
        # 10. Build grounded RAG instructions
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
        # 11. Ask AI provider
        # -----------------------------------------

        provider = HostedProvider()

        answer = provider.chat(
            message=message,
            system_prompt=rag_prompt,
            conversation_history=conversation_history,
        )

        # -----------------------------------------
        # 12. Prepare source information
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
        # 13. Persist everything atomically
        #
        # The conversation, the user message and
        # the assistant answer are stored only once
        # a successful answer exists. A failed AI
        # call leaves no orphan data and the user
        # can safely retry.
        # -----------------------------------------

        with transaction.atomic():

            if conversation is None:

                conversation = Conversation.objects.create(
                    organisation=membership.organisation,
                    user=request.user,
                    assistant=assistant,
                    title=message[:80],
                )

            Message.objects.create(
                conversation=conversation,
                role="user",
                content=message,
            )

            Message.objects.create(
                conversation=conversation,
                role="assistant",
                content=answer,
                sources=sources,
            )

        # -----------------------------------------
        # 14. Return response
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
@api_view(["GET"])
def conversation_list(request):

    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    membership = get_active_membership(request)

    if membership is None:
        return Response(
            {"error": "No active organisation membership."},
            status=status.HTTP_403_FORBIDDEN,
        )

    assistant_slug = request.query_params.get("assistant")

    conversations = (
        Conversation.objects
        .filter(
            user=request.user,
            organisation=membership.organisation,
        )
        .select_related("assistant")
    )

    if assistant_slug:

        assistant = get_authorised_assistant(
            membership,
            assistant_slug,
        )

        if assistant is None:
            return Response(
                {
                    "error": (
                        "You do not have access "
                        "to this assistant."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        conversations = conversations.filter(
            assistant=assistant,
        )

    conversations = conversations.order_by(
        "-updated_at",
    )[:20]

    return Response(
        {
            "conversations": [
                {
                    "id": conversation.id,
                    "title": conversation.title,
                    "assistant": conversation.assistant.slug,
                    "updated_at": (
                        conversation.updated_at.isoformat()
                    ),
                }
                for conversation in conversations
            ],
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
def conversation_detail(request, conversation_id):

    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    membership = get_active_membership(request)

    if membership is None:
        return Response(
            {"error": "No active organisation membership."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # The security chain:
    #   conversation belongs to the logged-in user,
    #   to the user's organisation, and to an
    #   assistant the user is authorised to use.

    conversation = (
        Conversation.objects
        .filter(
            id=conversation_id,
            user=request.user,
            organisation=membership.organisation,
            assistant__is_active=True,
            assistant__access_permissions__membership=membership,
        )
        .select_related("assistant")
        .distinct()
        .first()
    )

    if conversation is None:
        return Response(
            {"error": "Conversation not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    messages = conversation.messages.order_by(
        "created_at",
        "id",
    )

    return Response(
        {
            "conversation_id": conversation.id,
            "title": conversation.title,
            "assistant": {
                "id": conversation.assistant.id,
                "name": conversation.assistant.name,
                "slug": conversation.assistant.slug,
            },
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "sources": message.sources,
                    "created_at": message.created_at.isoformat(),
                }
                for message in messages
            ],
        },
        status=status.HTTP_200_OK,
    )