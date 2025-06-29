import os
from datetime import datetime
from functools import partial

import gradio as gr

from remind.domain.models import DefaultModels, Model, model_manager
from remind.models import MODEL_CLASS_MAP
from remind.webui.components.model_selector import (get_model_from_key,
                                                    model_selector)

provider_status = {}

model_types = [
    "language",
    "vision",
    "embedding",
    "text_to_speech",
    "speech_to_text",
]

provider_status["ollama"] = os.environ.get("OLLAMA_API_BASE") is not None
provider_status["openai"] = os.environ.get("OPENAI_API_KEY") is not None
provider_status["groq"] = os.environ.get("GROQ_API_KEY") is not None
provider_status["xai"] = os.environ.get("XAI_API_KEY") is not None
provider_status["vertexai"] = (
    os.environ.get("VERTEX_PROJECT") is not None
    and os.environ.get("VERTEX_LOCATION") is not None
    and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is not None
)
provider_status["vertexai-anthropic"] = (
    os.environ.get("VERTEX_PROJECT") is not None
    and os.environ.get("VERTEX_LOCATION") is not None
    and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is not None
)
provider_status["gemini"] = os.environ.get("GEMINI_API_KEY") is not None
provider_status["openrouter"] = (
    os.environ.get("OPENROUTER_API_KEY") is not None
    and os.environ.get("OPENAI_API_KEY") is not None
    and os.environ.get("OPENROUTER_BASE_URL") is not None
)
provider_status["anthropic"] = os.environ.get("ANTHROPIC_API_KEY") is not None
provider_status["elevenlabs"] = os.environ.get("ELEVENLABS_API_KEY") is not None
provider_status["litellm"] = (
    provider_status["ollama"]
    or provider_status["vertexai"]
    or provider_status["vertexai-anthropic"]
    or provider_status["anthropic"]
    or provider_status["openai"]
    or provider_status["gemini"]
)
provider_status["chatterbox"] = True
provider_status["parakeet"] = True

available_providers = [k for k, v in provider_status.items() if v]
unavailable_providers = [k for k, v in provider_status.items() if not v]

default_models = DefaultModels()

def delete_model(model: Model):
    if model.id in vars(default_models).values():
        for key, value in vars(default_models).items():
            if value == model.id:
                setattr(default_models, key, None)
        default_models.update()
        model_manager.refresh_defaults()
    model.delete()
    return datetime.now()

def save_default_models(
        langauge_model_key: str,
        transformation_model_key: str,
        tools_model_key: str,
        large_context_model_key: str,
        vision_model_key: str,
        text_to_speech_model_key: str,
        speech_to_text_model_key: str,
        embedding_model_key: str
):
    default_chat_model = get_model_from_key(langauge_model_key, "language")
    default_models.default_chat_model = default_chat_model.id if default_chat_model else None
    default_transformation_model = get_model_from_key(transformation_model_key, "language")
    default_models.default_transformation_model = default_transformation_model.id if default_transformation_model else None
    default_tools_model = get_model_from_key(tools_model_key, "language")
    default_models.default_tools_model = default_tools_model.id if default_tools_model else None
    default_large_context_model = get_model_from_key(large_context_model_key, "language")
    default_models.default_large_context_model = default_large_context_model.id if default_large_context_model else None
    default_vision_model = get_model_from_key(vision_model_key, "vision")
    default_models.default_vision_model = default_vision_model.id if default_vision_model else None
    default_text_to_speech_model = get_model_from_key(text_to_speech_model_key, "text_to_speech")
    default_models.default_text_to_speech_model = default_text_to_speech_model.id if default_text_to_speech_model else None
    default_speech_to_text_model = get_model_from_key(speech_to_text_model_key, "speech_to_text")
    default_models.default_speech_to_text_model = default_speech_to_text_model.id if default_speech_to_text_model else None
    default_embedding_model = get_model_from_key(embedding_model_key, "embedding")
    default_models.default_embedding_model = default_embedding_model.id if default_embedding_model else None
    default_models.update()
    model_manager.refresh_defaults()
    gr.Info("Default models updated.")

def models_tab(demo, all_models):
    with gr.Tab("🤖 Models"):
        all_models_update = gr.State()
        all_models_update.change(lambda: Model.get_all(), outputs=[all_models])
        demo.load(lambda: datetime.now(), outputs=[all_models_update])

        with gr.Tabs():
            with gr.Tab("Configured Models"):
                @gr.render(inputs=[all_models])
                def render_configured_models(all_models: list[Model]):
                    if not all_models:
                        gr.Markdown("No models configured. Create a new model in the 'New Model' tab.")
                    else:
                        for model in all_models:
                            with gr.Row():
                                gr.Markdown(f"**{model.name}** ({model.provider}, {model.type})")
                                delete_model_button = gr.Button("Delete", scale=0)
                                delete_model_button.click(
                                    lambda model=model: partial(delete_model, model)(),
                                    outputs=[all_models_update],
                                )

            with gr.Tab("Add Model"):
                provider = gr.Dropdown(
                    choices=available_providers,
                    label="Provider",
                )

                @gr.render(inputs=[provider])
                def add_model_form(provider: str):
                    available_model_types = []
                    for model_type in model_types:
                        if model_type in MODEL_CLASS_MAP and provider in MODEL_CLASS_MAP[model_type]:
                            available_model_types.append(model_type)
                    if not available_model_types:
                        gr.Markdown(f"No compatible model types available for provider: {provider}")
                    else:
                        model_type = gr.Dropdown(
                            choices=available_model_types,
                            label="Model Type",
                            info="Use language for text generation models, text_to_speech for TTS models for generating podcasts, etc.",
                        )
                        model_name = gr.Textbox(label="Model Name", placeholder="gpt-4o-mini, claude, gemini, llama3, etc")
                        model_add_button = gr.Button("Add")
                        model_add_button.click(
                            lambda model_name, model_type: Model(name=model_name, provider=provider, type=model_type).save(),
                            inputs=[model_name, model_type],
                        ).then(
                            lambda: datetime.now(),
                            outputs=[all_models_update],
                        ).then(lambda: gr.Info("Model added.", duration=2))

            with gr.Tab("Default Models"):
                gr.Markdown(
                    "You can select the default models to be used on the various content operations done by ReMind. Some of these can be overriden in the different modules."
                )

                @gr.render(triggers=[all_models.change])
                def default_model_form():
                    langauge_model_key = model_selector(
                        label="Default Chat Model",
                        selected_id=default_models.default_chat_model,
                        model_type="language",
                        info="This model will be used for chat.",
                    )
                    transformation_model_key = model_selector(
                        label="Default Transformation Model",
                        selected_id=default_models.default_transformation_model,
                        model_type="language",
                        info="This model will be used for text transformations such as summaries, insights, etc.",
                    )
                    tools_model_key = model_selector(
                        label="Default Tools Model",
                        selected_id=default_models.default_tools_model,
                        model_type="language",
                        info="This model will be used for calling tools.",
                    )
                    large_context_model_key = model_selector(
                        label="Default Large Context Model",
                        selected_id=default_models.default_large_context_model,
                        model_type="language",
                        info="This model will be used for larger context generation.",
                    )
                    vision_model_key = model_selector(
                        label="Default Vision Model",
                        selected_id=default_models.default_vision_model,
                        model_type="vision",
                        info="This model will be used for image annotation.",
                    )
                    text_to_speech_model_key = model_selector(
                        label="Default Text to Speech Model",
                        selected_id=default_models.default_text_to_speech_model,
                        model_type="text_to_speech",
                        info="This is the default model for converting text to speech (podcasts, etc).",
                    )
                    speech_to_text_model_key = model_selector(
                        label="Default Speech to Text Model",
                        selected_id=default_models.default_speech_to_text_model,
                        model_type="speech_to_text",
                        info="This is the default model for converting speech to text (audio transcriptions, etc).",
                    )
                    embedding_model_key = model_selector(
                        label="Default Embedding Model",
                        selected_id=default_models.default_embedding_model,
                        model_type="embedding",
                        info="This is the default model for embeddings (semantic search, etc)",
                    )

                    save_defaults_button = gr.Button("Save Defaults")
                    save_defaults_button.click(
                        save_default_models,
                        inputs=[
                            langauge_model_key,
                            transformation_model_key,
                            tools_model_key,
                            large_context_model_key,
                            vision_model_key,
                            text_to_speech_model_key,
                            speech_to_text_model_key,
                            embedding_model_key,
                        ],
                    )
