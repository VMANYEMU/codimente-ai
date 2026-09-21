from abc import ABC, abstractmethod


class ModelProvider(ABC):
    """
    Base interface for all Codimente AI model providers.
    """

    @abstractmethod
    def chat(self, message: str) -> str:
        pass