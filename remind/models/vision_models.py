"""
Classes for supporting different vision models
"""

import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import litellm
import ollama
from docling.datamodel.pipeline_options import (PictureDescriptionApiOptions,
                                                PictureDescriptionBaseOptions)
from docling_litellm_picture_description.datamodel.pipeline_options import \
    PictureDescriptionLiteLLMOptions

from remind.prompter import Prompter


@dataclass
class VisionModel(ABC):
    """
    Abstract base class for speech to text models.
    """

    model_name: Optional[str] = None

    @staticmethod
    def image_to_base64(image_path: str) -> str:
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()

        # Convert image to base64
        return base64.b64encode(img_data).decode()

    @abstractmethod
    def picture_description_options(self) -> PictureDescriptionBaseOptions:
        """
        Returns the docling picture_description options for PdfPipelineOptions.
        """
        raise NotImplementedError

    @abstractmethod
    def picture_description(self, image_path: str) -> str:
        """
        Generates a text transcription of an image in image_path.
        """
        raise NotImplementedError


@dataclass
class OllamaVisionModel(VisionModel):
    """
    Vision model that uses Ollama chat service.
    """

    model_name: str
    base_url: str = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")

    def picture_description_options(self) -> PictureDescriptionApiOptions:
        return PictureDescriptionApiOptions(
            url=self.base_url.rstrip("/") + "/v1/chat/completions",
            params={"model": self.model_name},
            prompt=Prompter(prompt_template="image_description").render(data={}),
            scale=1.0,
            timeout=120,
        )

    def picture_description(self, image_path: str) -> str:
        image_data = self.image_to_base64(image_path)
        response = ollama.generate(
            model=self.model_name,
            prompt=Prompter(prompt_template="image_description").render(data={}),
            images=[image_data],    # Pass base64 encoded image data at top level
        )

        # Extract the caption from the response
        caption = response["response"].strip()
        return caption


@dataclass
class LiteLLMVisionModel(VisionModel):
    """
    Vision model that uses LiteLLM chat interface.
    """

    model_name: str

    def picture_description_options(self) -> PictureDescriptionLiteLLMOptions:
        return PictureDescriptionLiteLLMOptions(
            model=self.model_name,
            prompt=Prompter(prompt_template="image_description").render(data={}),
            scale=1.0,
            timeout=120,
        )

    def picture_description(self, image_path: str) -> str:
        image_data = self.image_to_base64(image_path)
        response = litellm.completion(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": Prompter(prompt_template="image_description").render(data={}),
                        },
                        {
                            "type": "image_url",
                            "image_url": f"data:image/jpeg;base64,{image_data}",
                        },
                    ],
                },
            ],
            timeout=120,
        )
        return response["choices"][0]["message"]["content"].strip()
