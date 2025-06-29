from datetime import datetime
from pathlib import Path

import gradio as gr

from remind.domain.notes import Asset, Source
from remind.domain.transformation import Transformation
from remind.graphs.title import graph as title_graph
from remind.graphs.topics import graph as topics_graph
from remind.graphs.transformation import graph as transformation_graph
from remind.process_content.file_to_text import file_to_text
from remind.process_content.url_to_text import (firecrawl_url_to_text,
                                                is_firecrawl_available,
                                                url_to_text)
from remind.process_content.youtube_to_text import (
    retrieve_youtube_transcript, stt_youtube_audio)
from remind.webui.components.markdown_latex_render import \
    GR_MARKDOWN_LATEX_DELIMITERS


def update_file_path(file_path):
    file_name = Path(file_path).name
    return file_name, ""

def update_url(url):
    return "", url

def upload_tab(calendar_update):
    with gr.Tab("📤 Upload"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("1. Convert Note into Text")
                file_path = gr.State("")
                url = gr.State("")

                with gr.Tabs():
                    with gr.Tab("File"):
                        gr.Markdown("Supports PDF, DOCX, XLSX, PPTX, AsciiDoc, HTML, XHTML, CSV, video file.")
                        file = gr.File()
                        additional_files = gr.File(file_count="multiple", label="Additional Files", visible=False)
                        file.clear(lambda: ("", ""), outputs=[file_path, url])
                        file.change(lambda file: gr.File(None, visible=bool(file) and Path(file).suffix == ".md"), inputs=[file], outputs=[additional_files])
                        file_convert_button = gr.Button("Convert to Text")

                    with gr.Tab("YouTube"):
                        gr.Markdown("If Convert to Text does not work, use STT Convert.")
                        youtube_url = gr.Textbox(label="YouTube Video URL")
                        with gr.Row():
                            youtube_convert_button = gr.Button("Convert to Text")
                            youtube_stt_button = gr.Button("STT Convert")

                    with gr.Tab("Webpage"):
                        webpage_url = gr.Textbox(label="Webpage URL")
                        with gr.Row():
                            webpage_convert_button = gr.Button("Convert to Text")
                            if is_firecrawl_available():
                                webpage_firecrawl_convert_button = gr.Button("Firecrawl Convert")

                with gr.Accordion("Edit Note Content", open=False):
                    note_text = gr.TextArea(label="Note Content", interactive=True, container=False)
                note_markdown = gr.Markdown(show_label=False, latex_delimiters=GR_MARKDOWN_LATEX_DELIMITERS)
                note_text.change(lambda x: x, inputs=[note_text], outputs=[note_markdown], show_progress=False)

                file_convert_button.click(lambda: gr.Info("Converting file...", duration=2)).then(
                    file_to_text, inputs=[file, additional_files], outputs=[note_text]
                ).then(
                    update_file_path, inputs=[file], outputs=[file_path, url]
                )

                youtube_convert_button.click(lambda: gr.Info("Retrieving transcriptions...", duration=2)).then(
                    retrieve_youtube_transcript, inputs=[youtube_url], outputs=[note_text]
                ).then(
                    update_url, inputs=[youtube_url], outputs=[file_path, url]
                )

                youtube_stt_button.click(lambda: gr.Info("STT transcribing...", duration=5)).then(
                    stt_youtube_audio, inputs=[youtube_url], outputs=[note_text]
                ).then(
                    update_url, inputs=[youtube_url], outputs=[file_path, url]
                )

                webpage_convert_button.click(lambda: gr.Info("Downloading Webpage...", duration=2)).then(
                    url_to_text, inputs=[webpage_url], outputs=[note_text]
                ).then(
                    update_url, inputs=[webpage_url], outputs=[file_path, url]
                )

                if is_firecrawl_available():
                    webpage_firecrawl_convert_button.click(lambda: gr.Info("Firecrawl converting...", duration=2)).then(
                        firecrawl_url_to_text, inputs=[webpage_url], outputs=[note_text]
                    ).then(
                        update_url, inputs=[webpage_url], outputs=[file_path, url]
                    )

                gr.Markdown("2. Transform Note Content")
                note_transform_button = gr.Button("AI Transform")
                note_transform_button.click(lambda: gr.Info("Transforming...", duration=5))

            with gr.Column():
                @gr.render(inputs=[note_text, file_path, url], triggers=[note_transform_button.click])
                def transformed_note(input_text, file_path, url):
                    gr.Markdown("3. Save Note")
                    title = title_graph.invoke(dict(input_text=input_text))["output"]
                    note_title = gr.Textbox(title, label="Title", interactive=True)
                    all_transformations: list[Transformation] = Transformation.get_all()
                    all_transformation_textareas = []
                    for transformation in all_transformations:
                        transformation_output_text = transformation_graph.invoke(dict(
                            input_text=input_text,
                            transformation=transformation,
                        ))["output"]
                        transformation_output_textarea = gr.TextArea(transformation_output_text, label=transformation.name, interactive=True, info=transformation.description)
                        all_transformation_textareas.append(transformation_output_textarea)
                    topics = topics_graph.invoke(dict(input_text=input_text))["output"]
                    note_topics = gr.Dropdown(topics, value=topics, multiselect=True, label="Topics", interactive=True, allow_custom_value=True)

                    save_note_button = gr.Button("Save Note")

                    def save_note(title, topics, *transformation_texts):
                        source = Source(
                            asset=Asset(file_path=file_path, url=url),
                            title=title,
                            topics=topics,
                            full_text=input_text,
                        )
                        source.save()
                        source.vectorize()
                        for transformation, transformation_text in zip(all_transformations, transformation_texts):
                            source.add_insight(transformation.name, transformation_text)

                    save_note_button.click(lambda: gr.Info("Saving...", 2)).then(
                        save_note,
                        inputs=[note_title, note_topics, *all_transformation_textareas],
                    ).then(
                        lambda: datetime.now(), outputs=[calendar_update]
                    ).then(lambda: gr.Info("Note saved.", duration=2))
