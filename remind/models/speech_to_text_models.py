"""
Classes for supporting different transcription models
"""

import gc
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import torch


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

        # output = asr_model.transcribe(['2086-149220-0033.wav'])
        output = asr_model.transcribe([audio_file_path])
        del asr_model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return output[0].text
