import re
import subprocess
import tempfile
from pathlib import Path

import gradio as gr
from docling.datamodel.base_models import FormatToExtensions, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import PictureDescriptionData
from PIL import Image

from remind.domain.models import model_manager

from .upload_image import upload_image

VIDEO_EXTENSIONS = set(('webm', 'mkv', 'flv', 'vob', 'ogv', 'ogg', 'rrc', 'gifv', 'mng', 'mov', 'avi', 'qt', 'wmv', 'yuv', 'rm', 'asf', 'amv', 'mp4', 'm4p', 'm4v', 'mpg', 'mp2', 'mpeg', 'mpe', 'mpv', 'm4v', 'svi', '3gp', '3g2', 'mxf', 'roq', 'nsv', 'flv', 'f4v', 'f4p', 'f4a', 'f4b', 'mod'))
IMAGE_EXTENSIONS = set(FormatToExtensions[InputFormat.IMAGE])

def file_to_text(file, additional_files) -> str:
    """ Convert file to markdown. """
    # Markdown file
    if Path(file).suffix == ".md":
        with open(file, "r", encoding="utf-8") as f:
            markdown_text = f.read()
        if additional_files:
            for additional_file in additional_files:
                obsidian_link = f"![[{Path(additional_file).name}]]"
                if obsidian_link in markdown_text:
                    markdown_text = markdown_text.replace(obsidian_link, file_to_text(additional_file, []))
                else:
                    markdown_text += f"\n\n`{Path(additional_file).name}`:\n{file_to_text(additional_file, [])}"
        return markdown_text
    # Video file
    if Path(file).suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
        return video_to_text(file)
    # GIF or AVIF file
    if Path(file).suffix.lstrip(".").lower() in ("gif", "avif"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_png_path = f"{tmp_dir}/tmp.png"
            img = Image.open(file)
            img.convert("RGB").save(tmp_png_path)
            return file_to_text(tmp_png_path, [])
    # Others
    pipeline_options = PdfPipelineOptions(
        enable_remote_services=True,
        allow_external_plugins=True,
        do_picture_description=True,
        picture_description_options=model_manager.vision_model.picture_description_options(),
        generate_picture_images=True,
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.IMAGE: PdfFormatOption(
                pipeline_options=pipeline_options,
            ),
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )
    doc = converter.convert(file).document
    markdown_text = doc.export_to_markdown()
    for pic in doc.pictures:
        annotation_text = []
        for annotation in pic.annotations:
            if not isinstance(annotation, PictureDescriptionData):
                continue
            annotation_text.append(annotation.text)
        annotation_text = "\n".join(annotation_text)
        annotation_text = re.sub(r"\n+", "\n", annotation_text)
        image_link = upload_image(pic.image.pil_image)
        markdown_text = markdown_text.replace("<!-- image -->", f"![{annotation_text}]({image_link})", 1)

    # If the file is an image and OCR has failed, fallback to using vision model picture description.
    if not markdown_text and Path(file).suffix.lstrip(".").lower() in IMAGE_EXTENSIONS:
        caption = model_manager.vision_model.picture_description(file)
        caption = re.sub(r"\n+", "\n", caption)
        image_link = upload_image(file)
        markdown_text = f"![{caption}]({image_link})"

    return markdown_text

def video_to_text(video_file):
    """ Transcribe video to text. """
    STT_MODEL = model_manager.speech_to_text
    if STT_MODEL is None:
        raise gr.Error("Please set up a Speech to Text Model in Models tab.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file_path = f"{tmp_dir}/temp_audio"
        ffmpeg_command = f"ffmpeg -i {video_file} -vn -ac 1 -acodec libmp3lame {tmp_file_path}.mp3"
        process = subprocess.run(ffmpeg_command, shell=True, check=True)

        transcript = STT_MODEL.transcribe(tmp_file_path + ".mp3")
    return transcript
