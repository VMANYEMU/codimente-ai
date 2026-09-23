import os

from openai import OpenAI

from .base import ModelProvider


class HostedProvider(ModelProvider):

    def __init__(self):

        self.token = os.getenv("HF_TOKEN")

        self.model = os.getenv(
            "AI_MODEL",
            "openai/gpt-oss-120b:cerebras",
        )

        if not self.token:
            raise ValueError(
                "HF_TOKEN is not configured."
            )

        self.client = OpenAI(
            base_url=(
                "https://router.huggingface.co/v1"
            ),
            api_key=self.token,
        )

    def chat(
        self,
        message: str,
        system_prompt: str = "",
        conversation_history=None,
    ) -> str:

        codimente_prompt = (
            "You are Codimente Private AI, an enterprise "
            "AI assistant provided by Codimente Systems. "
            "Be accurate, professional and concise. "
            "Do not claim to know private organisational "
            "information unless that information has "
            "actually been supplied to you."
        )

        if system_prompt:
            codimente_prompt += (
                "\n\nAssistant instructions:\n"
                + system_prompt
            )

        messages = [
            {
                "role": "system",
                "content": codimente_prompt,
            }
        ]

        # Add previous conversation messages.
        if conversation_history:

            for history_message in conversation_history:

                if history_message.role in (
                    "user",
                    "assistant",
                ):
                    messages.append(
                        {
                            "role": history_message.role,
                            "content": history_message.content,
                        }
                    )

        # Add the current question last.
        messages.append(
            {
                "role": "user",
                "content": message,
            }
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=500,
        )

        return response.choices[0].message.content