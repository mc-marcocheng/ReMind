"""
Classes for supporting different text to speech models
"""

import gc
import io
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

import numpy as np
import semchunk
import torch
from pydub import AudioSegment

from remind.models.chatterbox.tts import ChatterboxTTS


def numpy_to_mp3(audio_array: np.ndarray, sampling_rate: int) -> bytes:
    # Normalize audio_array if it's floating-point
    if np.issubdtype(audio_array.dtype, np.floating):
        max_val = np.max(np.abs(audio_array))
        audio_array = (audio_array / max_val) * 32767 # Normalize to 16-bit range
        audio_array = audio_array.astype(np.int16)

    # Create an audio segment from the numpy array
    audio_segment = AudioSegment(
        audio_array.tobytes(),
        frame_rate=sampling_rate,
        sample_width=audio_array.dtype.itemsize,
        channels=1
    )

    # Export the audio segment to MP3 bytes - use a high bitrate to maximise quality
    mp3_io = io.BytesIO()
    audio_segment.export(mp3_io, format="mp3", bitrate="320k")

    # Get the MP3 bytes
    mp3_bytes = mp3_io.getvalue()
    mp3_io.close()

    return mp3_bytes

@dataclass
class TextToSpeechModel(ABC):
    """
    Abstract base class for text to speech models.
    """

    model_name: Optional[str] = None

    @abstractmethod
    def to_audio(self, text: str) -> Generator[bytes, None, None]:
        """
        Convert text into (sample rate in Hz, audio data as numpy array)
        """
        raise NotImplementedError

@dataclass
class ChatterboxTextToSpeechModel(TextToSpeechModel):
    model_name: str

    def chunk_transcript(text: str, chunk_size: int) -> list[str]:
        chunker = semchunk.chunkerify("o200k_base", chunk_size=chunk_size) # 40 second speech limit
        chunks = chunker(text)
        return chunks

    def to_audio(self, text: str) -> Generator[bytes, None, None]:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ChatterboxTTS.from_pretrained(device=device)
            match self.model_name:
                case "female":
                    chunk_size = 120
                    model.prepare_conditionals(Path(__file__).parent / "chatterbox" / "audio_samples" / "female.mp3")
                case _:
                    chunk_size = 130
            sr = model.sr

            chunks = self.chunk_transcript(text, chunk_size)
            for chunk in chunks:
                wav = model.generate(chunk).squeeze(dim=0).cpu().numpy()
                yield numpy_to_mp3(wav, sr)

        del model
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()
