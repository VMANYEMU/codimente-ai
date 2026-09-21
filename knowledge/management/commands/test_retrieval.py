from django.core.management.base import BaseCommand

from ai.models import Assistant
from knowledge.services.retriever import semantic_retrieve


class Command(BaseCommand):
    help = "Test retrieval across departmental assistants."

    def handle(self, *args, **options):

        tests = [
            # HR
            {
                "assistant": "human-resources",
                "question": "How many annual leave days do employees receive?",
                "expected": "HR",
            },
            {
                "assistant": "human-resources",
                "question": "Can I carry unused leave into next year?",
                "expected": "HR",
            },
            {
                "assistant": "human-resources",
                "question": "What should I do if I am sick?",
                "expected": "HR",
            },

            # Procurement
            {
                "assistant": "procurement",
                "question": "What is the procurement threshold?",
                "expected": "Procurement",
            },
            {
                "assistant": "procurement",
                "question": "How many quotations are required for a P20,000 purchase?",
                "expected": "Procurement",
            },
            {
                "assistant": "procurement",
                "question": "What happens when a purchase exceeds P50,000?",
                "expected": "Procurement",
            },

            # Finance
            {
                "assistant": "finance",
                "question": "When must I submit an expense claim?",
                "expected": "Finance",
            },
            {
                "assistant": "finance",
                "question": "Who is responsible for monitoring departmental expenditure?",
                "expected": "Finance",
            },
            {
                "assistant": "finance",
                "question": "What happens if expenditure exceeds the approved budget?",
                "expected": "Finance",
            },

            # ICT
            {
                "assistant": "ict-support",
                "question": "What should I do if I forget my password?",
                "expected": "ICT",
            },
            {
                "assistant": "ict-support",
                "question": "Can I connect my own device to the internal network?",
                "expected": "ICT",
            },
            {
                "assistant": "ict-support",
                "question": "What should I do if I suspect a cybersecurity incident?",
                "expected": "ICT",
            },

            # Deliberately wrong department
            {
                "assistant": "human-resources",
                "question": "What is the procurement threshold?",
                "expected": "NO MATCH",
            },
            {
                "assistant": "finance",
                "question": "How many annual leave days do employees receive?",
                "expected": "NO MATCH",
            },
            {
                "assistant": "procurement",
                "question": "How do I reset my password?",
                "expected": "NO MATCH",
            },
            {
                "assistant": "ict-support",
                "question": "When must I submit an expense claim?",
                "expected": "NO MATCH",
            },

            # General unrelated questions
            {
                "assistant": "human-resources",
                "question": "What is the capital of Japan?",
                "expected": "NO MATCH",
            },
            {
                "assistant": "ict-support",
                "question": "Who won the football match yesterday?",
                "expected": "NO MATCH",
            },
        ]

        for test in tests:

            self.stdout.write(
                "\n" + "=" * 72
            )

            self.stdout.write(
                f"ASSISTANT: {test['assistant']}"
            )

            self.stdout.write(
                f"EXPECTED: {test['expected']}"
            )

            self.stdout.write(
                f"QUESTION: {test['question']}"
            )

            try:
                assistant = Assistant.objects.get(
                    slug=test["assistant"],
                    is_active=True,
                )

            except Assistant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        "Assistant not found."
                    )
                )
                continue

            results = semantic_retrieve(
                assistant,
                test["question"],
                limit=2,
            )

            if not results:
                self.stdout.write(
                    "No results."
                )
                continue

            for result in results:

                semantic = getattr(
                    result,
                    "similarity",
                    0,
                )

                keyword = getattr(
                    result,
                    "keyword_score",
                    0,
                )

                hybrid = getattr(
                    result,
                    "hybrid_score",
                    0,
                )

                self.stdout.write(
                    f"\nDocument: "
                    f"{result.document.title}"
                )

                self.stdout.write(
                    f"Knowledge Base: "
                    f"{result.document.knowledge_base.name}"
                )

                self.stdout.write(
                    f"Chunk: {result.chunk_index}"
                )

                self.stdout.write(
                    f"Semantic: {semantic:.4f}"
                )

                self.stdout.write(
                    f"Keyword:  {keyword:.4f}"
                )

                self.stdout.write(
                    f"Hybrid:   {hybrid:.4f}"
                )