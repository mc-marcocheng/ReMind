"""
Classes for supporting different transcription models
"""

import gc
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import torch
from pydub import AudioSegment


@dataclass
class SpeechToTextModel(ABC):
    """
    Abstract base class for speech to text models.
    """

    model_name: Optional[str] = None

    @abstractmethod
    def transcribe(self, audio_file_path: str) -> str:
        """
        Generates a text transcription from audio
        """
        raise NotImplementedError


@dataclass
class OpenAISpeechToTextModel(SpeechToTextModel):
    model_name: str

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribes an audio file into text
        """
        from openai import OpenAI

        # todo: make this Singleton
        client = OpenAI()
        with open(audio_file_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                model=self.model_name, file=audio
            )
            return transcription.text


@dataclass
class GroqSpeechToTextModel(SpeechToTextModel):
    model_name: str

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribes an audio file into text
        """
        from groq import Groq

        # todo: make this Singleton
        client = Groq()
        with open(audio_file_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                model=self.model_name, file=audio
            )
            return transcription.text


@dataclass
class ParakeetSpeechToTextModel(SpeechToTextModel):
    model_name: str

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribes an audio file into text
        """
        import nemo.collections.asr as nemo_asr
        asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v2")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Split the audio file into segments as the audio file maybe too long
            audio = AudioSegment.from_file(audio_file_path)
            segment_length = 450000  # 450 seconds in milliseconds
            segment_files = []

            for i, segment in enumerate(audio[::segment_length]):
                segment_file_path = f"{tmp_dir}/segment_{i}.mp3"
                segment.export(segment_file_path, format="mp3")
                segment_files.append(segment_file_path)

            all_transcripts = []
            for segment_file in segment_files:
                output = asr_model.transcribe([segment_file])
                all_transcripts.append(output[0].text)

        del asr_model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return " ".join(all_transcripts)
