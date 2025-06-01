from typing import ClassVar

from .base import ObjectModel, PyObjectId


class Quizzed(ObjectModel):
    table_name: ClassVar[str] = "quiz"
    quizzed: list[PyObjectId]
