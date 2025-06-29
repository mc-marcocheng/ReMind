from typing import Dict, Type, Union

from remind.models.embedding_models import (EmbeddingModel,
                                            GeminiEmbeddingModel,
                                            OllamaEmbeddingModel,
                                            OpenAIEmbeddingModel,
                                            VertexEmbeddingModel)
from remind.models.llms import (AnthropicLanguageModel, GeminiLanguageModel,
                                GroqLanguageModel, LanguageModel,
                                LiteLLMLanguageModel, OllamaLanguageModel,
                                OpenAILanguageModel, OpenRouterLanguageModel,
                                VertexAILanguageModel,
                                VertexAnthropicLanguageModel, XAILanguageModel)
from remind.models.speech_to_text_models import (GroqSpeechToTextModel,
                                                 OpenAISpeechToTextModel,
                                                 ParakeetSpeechToTextModel,
                                                 SpeechToTextModel)
from remind.models.text_to_speech_models import (ChatterboxTextToSpeechModel,
                                                 TextToSpeechModel)
from remind.models.vision_models import OllamaVisionModel, VisionModel

ModelType = Union[LanguageModel, VisionModel, EmbeddingModel, SpeechToTextModel, TextToSpeechModel]


ProviderMap = Dict[str, Type[ModelType]]

MODEL_CLASS_MAP: Dict[str, ProviderMap] = {
    "language": {
        "ollama": OllamaLanguageModel,
        "openrouter": OpenRouterLanguageModel,
        "vertexai-anthropic": VertexAnthropicLanguageModel,
        "litellm": LiteLLMLanguageModel,
        "vertexai": VertexAILanguageModel,
        "anthropic": AnthropicLanguageModel,
        "openai": OpenAILanguageModel,
        "gemini": GeminiLanguageModel,
        "xai": XAILanguageModel,
        "groq": GroqLanguageModel,
    },
    "vision": {
        "ollama": OllamaVisionModel,
    },
    "embedding": {
        "openai": OpenAIEmbeddingModel,
        "gemini": GeminiEmbeddingModel,
        "vertexai": VertexEmbeddingModel,
        "ollama": OllamaEmbeddingModel,
    },
    "speech_to_text": {
        "openai": OpenAISpeechToTextModel,
        "groq": GroqSpeechToTextModel,
        "parakeet": ParakeetSpeechToTextModel,
    },
    "text_to_speech": {
        "chatterbox": ChatterboxTextToSpeechModel,
    },
}

__all__ = [
    "MODEL_CLASS_MAP",
    "LanguageModel",
    "VisionModel",
    "EmbeddingModel",
    "SpeechToTextModel",
    "TextToSpeechModel",
    "ModelType",
]
