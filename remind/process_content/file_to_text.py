import subprocess
import tempfile
from pathlib import Path

import gradio as gr
from docling.document_converter import DocumentConverter

from remind.domain.models import model_manager

VIDEO_EXTENSIONS = set(('webm', 'mkv', 'flv', 'vob', 'ogv', 'ogg', 'rrc', 'gifv', 'mng', 'mov', 'avi', 'qt', 'wmv', 'yuv', 'rm', 'asf', 'amv', 'mp4', 'm4p', 'm4v', 'mpg', 'mp2', 'mpeg', 'mpe', 'mpv', 'm4v', 'svi', '3gp', '3g2', 'mxf', 'roq', 'nsv', 'flv', 'f4v', 'f4p', 'f4a', 'f4b', 'mod'))

converter = DocumentConverter()

def file_to_text(file) -> str:
    """ Convert file to markdown. """
    if Path(file).suffix.lstrip(".") in VIDEO_EXTENSIONS:
        return video_to_text(file)
    result = converter.convert(file)
    return result.document.export_to_markdown()

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
