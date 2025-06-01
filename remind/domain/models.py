from typing import ClassVar, Dict, Optional

from remind.database.mongodb import collection_query
from remind.domain.base import ObjectModel, PyObjectId, RecordModel
from remind.models import (MODEL_CLASS_MAP, EmbeddingModel, LanguageModel,
                           ModelType, SpeechToTextModel, TextToSpeechModel)


class Model(ObjectModel):
    table_name: ClassVar[str] = "model"
    name: str
    provider: str
    type: str

    @classmethod
    def get_models_by_type(cls, model_type):
        models = collection_query(cls.table_name, {"type": model_type})
        return [cls(**model) for model in models]


class DefaultModels(RecordModel):
    record_id: ClassVar[str] = "default_models"
    default_chat_model: Optional[PyObjectId] = None
    default_transformation_model: Optional[PyObjectId] = None
    default_large_context_model: Optional[PyObjectId] = None
    default_text_to_speech_model: Optional[PyObjectId] = None
    default_speech_to_text_model: Optional[PyObjectId] = None
    # default_vision_model: Optional[PyObjectId]
    default_embedding_model: Optional[PyObjectId] = None
    default_tools_model: Optional[PyObjectId] = None


class ModelManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._model_cache: Dict[str, ModelType] = {}
            self._default_models = None
            self.refresh_defaults()

    def get_model(self, model_id: str, **kwargs) -> Optional[ModelType]:
        if not model_id:
            return None

        cache_key = f"{model_id}:{str(kwargs)}"

        if cache_key in self._model_cache:
            cached_model = self._model_cache[cache_key]
            if not isinstance(
                cached_model,
                (LanguageModel, EmbeddingModel, SpeechToTextModel, TextToSpeechModel),
            ):
                raise TypeError(
                    f"Cached model is of unexpected type: {type(cached_model)}"
                )
            return cached_model

        model: Model = Model.get(model_id)

        if not model:
            raise ValueError(f"Model with ID {model_id} not found")

        if not model.type or model.type not in MODEL_CLASS_MAP:
            raise ValueError(f"Invalid model type: {model.type}")

        provider_map = MODEL_CLASS_MAP[model.type]
        if model.provider not in provider_map:
            raise ValueError(
                f"Provider {model.provider} not compatible with {model.type} models"
            )

        model_class = provider_map[model.provider]
        model_instance = model_class(model_name=model.name, **kwargs)
        self._model_cache[cache_key] = model_instance
        return model_instance

    def refresh_defaults(self):
        """Refresh the default models from the database"""
        self._default_models = DefaultModels()

    @property
    def defaults(self) -> DefaultModels:
        """Get the default models configuration"""
        if not self._default_models:
            self.refresh_defaults()
            if not self._default_models:
                raise RuntimeError("Failed to initialize default models configuration")
        return self._default_models

    @property
    def speech_to_text(self, **kwargs) -> Optional[SpeechToTextModel]:
        """Get the default speech-to-text model"""
        model_id = self.defaults.default_speech_to_text_model
        if not model_id:
            return None
        model = self.get_model(model_id, **kwargs)
        assert model is None or isinstance(
            model, SpeechToTextModel
        ), f"Expected SpeechToTextModel but got {type(model)}"
        return model

    @property
    def text_to_speech(self, **kwargs) -> Optional[TextToSpeechModel]:
        """Get the default text-to-speech model"""
        model_id = self.defaults.default_text_to_speech_model
        if not model_id:
            return None
        model = self.get_model(model_id, **kwargs)
        assert model is None or isinstance(
            model, TextToSpeechModel
        ), f"Expected TextToSpeechModel but got {type(model)}"
        return model

    @property
    def embedding_model(self, **kwargs) -> Optional[EmbeddingModel]:
        """Get the default embedding model"""
        model_id = self.defaults.default_embedding_model
        if not model_id:
            return None
        model = self.get_model(model_id, **kwargs)
        assert model is None or isinstance(
            model, EmbeddingModel
        ), f"Expected EmbeddingModel but got {type(model)}"
        return model

    def get_default_model(self, model_type: str, **kwargs) -> Optional[ModelType]:
        """
        Get the default model for a specific type.

        Args:
            model_type: The type of model to retrieve (e.g., 'chat', 'embedding', etc.)
            **kwargs: Additional arguments to pass to the model constructor
        """
        model_id = None

        if model_type == "chat":
            model_id = self.defaults.default_chat_model
        elif model_type == "transformation":
            model_id = (
                self.defaults.default_transformation_model
                or self.defaults.default_chat_model
            )
        elif model_type == "tools":
            model_id = (
                self.defaults.default_tools_model or self.defaults.default_chat_model
            )
        elif model_type == "embedding":
            model_id = self.defaults.default_embedding_model
        elif model_type == "text_to_speech":
            model_id = self.defaults.default_text_to_speech_model
        elif model_type == "speech_to_text":
            model_id = self.defaults.default_speech_to_text_model
        elif model_type == "large_context":
            model_id = self.defaults.large_context_model

        if not model_id:
            return None

        return self.get_model(model_id, **kwargs)

    def clear_cache(self):
        """Clear the model cache"""
        self._model_cache.clear()


model_manager = ModelManager()
