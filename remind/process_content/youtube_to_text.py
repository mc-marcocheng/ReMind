import os
import tempfile
import uuid
from contextlib import suppress
from urllib.parse import parse_qs, urlparse

import gradio as gr
import yt_dlp
from youtube_transcript_api import FetchedTranscript, YouTubeTranscriptApi
from youtube_transcript_api.formatters import Formatter

from remind.domain.models import model_manager


def get_youtube_id(url: str, ignore_playlist: bool = False) -> str:
    """ Extract YouTube video ID from url.
    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com', 'music.youtube.com'}:
        if not ignore_playlist:
        # use case: get playlist id not current video in playlist
            with suppress(KeyError):
                return parse_qs(query.query)['list'][0]
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/watch/': return query.path.split('/')[2]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
    return url


class TranscriptFormatter(Formatter):
    def format_transcript(self, transcript: FetchedTranscript, **kwargs) -> str:
        formatted_texts = ""
        for snippet in transcript.snippets:
            text = snippet.text.strip()
            if not text:
                continue
            if text.startswith("[") and text.endswith("]"):
                continue
            text = text.replace("\n", " ")
            formatted_texts += text + "\n"
        return formatted_texts.strip()


def retrieve_youtube_transcript(url: str) -> str:
    # Retrieve YouTube transcript using YouTubeTranscriptApi
    ytt_api = YouTubeTranscriptApi()
    video_id = get_youtube_id(url)
    transcript = ytt_api.fetch(video_id)
    text = TranscriptFormatter().format_transcript(transcript)
    return text


def stt_youtube_audio(url: str) -> str:
    """ Download YouTube Audio and transcribe it with speech to text model. """
    STT_MODEL = model_manager.speech_to_text
    if STT_MODEL is None:
        raise gr.Error("Please set up a Speech to Text Model in Models tab.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_name = f"{uuid.uuid4()}"
        tmp_file_path = os.path.join(tmp_dir, file_name)

        # Define yt-dlp options
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': tmp_file_path,  # Save file to temporary path
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '0',
                'nopostoverwrites': False,
            }],
            # Add postprocessor arguments at global level
            'postprocessor_args': [
                '-ac', '1'  # Convert to mono
            ],
        }

        # Use yt-dlp to download and process video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        transcript = STT_MODEL.transcribe(tmp_file_path + ".mp3")
    return transcript
