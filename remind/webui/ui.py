import gradio as gr

from .tabs.ask import ask_tab
from .tabs.calendar import calendar_tab
from .tabs.models import models_tab
from .tabs.quiz import quiz_tab
from .tabs.transformations import transformations_tab
from .tabs.upload import upload_tab


def get_ui():
    with gr.Blocks(title="ReMind", analytics_enabled=False, css="footer {visibility: hidden}") as demo:
        all_models = gr.State([])
        calendar_update = gr.State()

        with gr.Tabs():
            calendar_tab(demo, calendar_update)
            upload_tab(calendar_update)
            ask_tab(all_models)
            quiz_tab()
            transformations_tab(demo, all_models)
            models_tab(demo, all_models)
    return demo
