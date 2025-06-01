import unicodedata

from remind.domain.models import model_manager
from remind.graphs.note_to_transcript import graph as note_to_transcript_graph


def sanitize_text(text: str) -> str:
    sanitized = unicodedata.normalize("NFKC", text)
    # Replace problematic character sequences that might cause tokenization issues
    replacements = {
        "…": "...",
        "–": "-",
        "—": "-",
        "\u200b": "",  # Zero-width space
        "\u200c": "",  # Zero-width non-joiner
        "\u200d": "",  # Zero-width joiner
        "\ufeff": "",  # Byte order mark
        "\xa0": " ",  # Non-breaking space
    }

    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)
    sanitized = sanitized.strip()
    return sanitized

def note_to_transcript(text: str) -> str:
    transcript = note_to_transcript_graph.invoke({"content": text})["output"]
    return transcript

def generate_audio_from_transcript(text: str):
    text = note_to_transcript(text)
    text = sanitize_text(text)
    TTS_MODEL = model_manager.text_to_speech
    yield from TTS_MODEL.to_audio(text)
