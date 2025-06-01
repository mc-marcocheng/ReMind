from typing import Literal, Optional

import gradio as gr
from bson import ObjectId

from remind.domain.models import Model


def model_selector(
        label: str,
        selected_id: Optional[ObjectId] = None,
        model_type: Literal[
            "language", "embedding", "speech_to_text", "text_to_speech"
        ] = "language",
        info: Optional[str] = None,
    ):
    models = Model.get_models_by_type(model_type)
    models.sort(key=lambda x: (x.provider, x.name))
    model_names = [f"{x.provider} - {x.name}" for x in models]
    if selected_id is None:
        index = 0
    else:
        model_ids = [m.id for m in models]
        index = model_ids.index(selected_id) if selected_id in model_ids else 0

    if not models:
        value = None
    else:
        value = model_names[index]

    return gr.Dropdown(
        choices=model_names,
        value=value,
        label=label,
        info=info,
    )


def get_model_from_key(
        model_key: str,
        model_type: Literal[
            "language", "embedding", "speech_to_text", "text_to_speech"
        ] = "language",
) -> Model:
    if not model_key:
        return None

    models = Model.get_models_by_type(model_type)
    if not models:
        return None
    model_keys = [f"{x.provider} - {x.name}" for x in models]
    index = model_keys.index(model_key) if model_key in model_keys else 0
    return models[index]
