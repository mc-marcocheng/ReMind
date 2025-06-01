from typing import ClassVar, Optional

from pydantic import Field

from remind.domain.base import ObjectModel, RecordModel


class Transformation(ObjectModel):
    table_name: ClassVar[str] = "transformation"
    name: str
    description: str
    prompt: str


class DefaultPrompts(RecordModel):
    record_id: ClassVar[str] = "default_prompts"
    transformation_instructions: Optional[str] = Field(
        None, description="Instructions for executing a transformation"
    )
