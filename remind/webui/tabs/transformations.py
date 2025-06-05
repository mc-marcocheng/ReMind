from datetime import datetime
from functools import partial

import gradio as gr

from remind.domain.transformation import DefaultPrompts, Transformation
from remind.graphs.transformation import graph as transformation_graph
from remind.webui.components.model_selector import (get_model_from_key,
                                                    model_selector)


def create_transformation():
    Transformation(
        name="",
        description="",
        prompt="",
    ).save()
    return datetime.now()

def update_transformation(
        transformation: Transformation,
        name: str,
        description: str,
        prompt: str,
    ):
    transformation.name = name
    transformation.description = description
    transformation.prompt = prompt
    transformation.save()
    return datetime.now()

def delete_transformation(transformation: Transformation):
    transformation.delete()
    return datetime.now()

def set_transformation_open_state(index: int, transformation_open_state: list, state: bool):
    while len(transformation_open_state) <= index:
        transformation_open_state.append(False)
    transformation_open_state[index] = state
    return transformation_open_state

def run_transformation(transformation_name: str, model_key: str, input_text: str):
    transformation_list = Transformation.get_all()
    transformation = next(filter(lambda t: t.name == transformation_name, transformation_list), None)
    model = get_model_from_key(model_key, "language")
    output = transformation_graph.invoke(
        dict(
            input_text=input_text,
            transformation=transformation,
        ),
        config=dict(configurable={"model_id": model.id}),
    )
    return output["output"]

def transformations_tab(demo, all_models: gr.State):
    with gr.Tab("🧩 Transformations"):
        transformations = gr.State([])
        transformations_update = gr.State()
        transformations_update.change(lambda: Transformation.get_all(), outputs=transformations)
        demo.load(lambda: datetime.now(), outputs=[transformations_update])
        transformation_open_states = gr.State([])

        with gr.Tabs():
            with gr.Tab("Create"):
                gr.Markdown("Transformations are prompts that will be used by the LLM to process a source and extract insights, summaries, etc.")

                @gr.render(inputs=[transformations, transformation_open_states], triggers=[transformations.change])
                def transformation_accordions(transformation_list: list[Transformation], open_states: list[bool]):
                    for idx, transformation in enumerate(transformation_list):
                        open_state = open_states[idx] if len(open_states) > idx else False
                        with gr.Accordion(label=transformation.name, open=open_state) as accordion:
                            accordion.expand(lambda: set_transformation_open_state(idx, open_states, True), outputs=transformation_open_states)
                            accordion.collapse(lambda: set_transformation_open_state(idx, open_states, False), outputs=transformation_open_states)

                            name = gr.Textbox(transformation.name, label="Name")
                            description = gr.Textbox(
                                transformation.description, label="Description",
                                placeholder="Displayed as a hint in the UI so you know what you are selecting.",
                            )
                            prompt = gr.TextArea(
                                transformation.prompt, label="Prompt",
                                placeholder="You can use the prompt to summarize, expand, extract insights and much more. Example: `Translate this text to French`.\nFor inspiration, check out https://github.com/danielmiessler/fabric/tree/main/patterns.",
                            )
                            with gr.Row():
                                save_button = gr.Button("Save")
                                save_button.click(
                                    lambda name, description, prompt, transformation=transformation: \
                                        partial(update_transformation, transformation)(name, description, prompt),
                                    inputs=[name, description, prompt],
                                    outputs=[transformations_update],
                                ).then(lambda: gr.Info("Transformation saved.", duration=2))
                                delete_button = gr.Button("Delete")
                                delete_button.click(lambda: set_transformation_open_state(idx, open_states, False), outputs=transformation_open_states).then(
                                    lambda transformation=transformation: partial(delete_transformation, transformation)(),
                                    outputs=[transformations_update],
                                )

                create_new_button = gr.Button("Create New")
                create_new_button.click(
                    lambda: partial(create_transformation)(),
                    outputs=[transformations_update],
                )

            with gr.Tab("Playground"):
                @gr.render(inputs=[transformations], triggers=[all_models.change, transformations.change])
                def render_playground(transformation_list: list[Transformation]):
                    transformation_name = gr.Dropdown(
                        choices=[transformation.name for transformation in transformation_list],
                        label="Pick a transformation",
                        value=transformation_list[0].name if transformation_list else None,
                    )
                    model_key = model_selector(
                        label="Pick a model",
                        model_type="language",
                        info="This is the model that will be used to run the transformation",
                    )
                    input_text = gr.TextArea(label="Enter some text", placeholder="Enter text here")
                    run_button = gr.Button("Run")
                    output_text = gr.Markdown()
                    run_button.click(lambda: gr.Info("Transforming...", 2)).then(
                        run_transformation,
                        inputs=[transformation_name, model_key, input_text],
                        outputs=output_text,
                    )
