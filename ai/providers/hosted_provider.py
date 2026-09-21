import os

from openai import OpenAI

from .base import ModelProvider


class HostedProvider(ModelProvider):

    def __init__(self):

        self.token = os.getenv("HF_TOKEN")

        self.model = os.getenv(
            "AI_MODEL",
            "openai/gpt-oss-120b:cerebras"
        )

        if not self.token:
            raise ValueError(
                "HF_TOKEN is not configured."
            )

        self.client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=self.token,
        )


    def chat(
        self,
        message: str,
        system_prompt: str = "",
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

        response = self.client.chat.completions.create(

            model=self.model,

            messages=[
                {
                    "role": "system",
                    "content": codimente_prompt,
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],

            max_tokens=500,
        )

        return response.choices[0].message.content