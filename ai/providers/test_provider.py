from .base import ModelProvider


class TestProvider(ModelProvider):

    def chat(self, message: str) -> str:

        return (
            "Codimente AI received your question: "
            f"'{message}'. "
            "The AI communication pipeline is working successfully."
        )