from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type, TypeVar, cast

from bson import ObjectId
from loguru import logger
from pydantic import (BaseModel, Field, ValidationError, field_validator,
                      model_validator)
from pydantic_core import core_schema

from remind.database.mongodb import (
    collection_create, collection_create_vector_index_if_not_exists,
    collection_delete, collection_query, collection_update, collection_upsert)
from remind.exceptions import (DatabaseOperationError, InvalidInputError,
                               NotFoundError)

T = TypeVar("T", bound="ObjectModel")

class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(
            cls, _source_type: Any, _handler: Any
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x),
                when_used='json',
            ),
        )

    @classmethod
    def validate(cls, value) -> ObjectId:
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")

        return ObjectId(value)

class ObjectModel(BaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    table_name: ClassVar[str] = ""
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    @classmethod
    def get_all(cls: Type[T]) -> List[T]:
        try:
            # If called from a specific subclass, use its table_name
            if cls.table_name:
                target_class = cls
                table_name = cls.table_name
            else:
                # This path is taken if called directly from ObjectModel
                raise InvalidInputError(
                    "get_all() must be called from a specific model class"
                )

            result = collection_query(table_name, {})
            objects = []
            for obj in result:
                try:
                    objects.append(target_class(**obj))
                except Exception as e:
                    logger.critical(f"Error creating object: {str(e)}")

            return objects
        except Exception as e:
            logger.error(f"Error fetching all {cls.table_name}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    @classmethod
    def get(cls: Type[T], id: str | ObjectId) -> T:
        if not id:
            raise InvalidInputError("ID cannot be empty")
        try:
            # Get the table name from the ID (everything before the first colon)
            if isinstance(id, ObjectId):
                table_name = cls.table_name
            else:
                table_name = id.split(":")[0] if ":" in id else id

            # If we're calling from a specific subclass and IDs match, use that class
            if cls.table_name and cls.table_name == table_name:
                target_class: Type[T] = cls
            else:
                # Otherwise, find the appropriate subclass based on table_name
                found_class = cls._get_class_by_table_name(table_name)
                if not found_class:
                    raise InvalidInputError(f"No class found for table {table_name}")
                target_class = cast(Type[T], found_class)

            result = collection_query(table_name, {"_id": id})
            if result:
                return target_class(**result[0])
            else:
                raise NotFoundError(f"{table_name} with id {id} not found")
        except Exception as e:
            logger.error(f"Error fetching object with id {id}: {str(e)}")
            logger.exception(e)
            raise NotFoundError(f"Object with id {id} not found - {str(e)}")

    @classmethod
    def _get_class_by_table_name(cls, table_name: str) -> Optional[Type["ObjectModel"]]:
        """Find the appropriate subclass based on table_name."""

        def get_all_subclasses(c: Type["ObjectModel"]) -> List[Type["ObjectModel"]]:
            all_subclasses: List[Type["ObjectModel"]] = []
            for subclass in c.__subclasses__():
                all_subclasses.append(subclass)
                all_subclasses.extend(get_all_subclasses(subclass))
            return all_subclasses

        for subclass in get_all_subclasses(ObjectModel):
            if hasattr(subclass, "table_name") and subclass.table_name == table_name:
                return subclass
        return None

    def needs_embedding(self) -> bool:
        return False

    def get_embedding_content(self) -> Optional[str]:
        return None

    def save(self) -> None:
        from remind.domain.models import model_manager

        try:
            self.model_validate(self.model_dump(by_alias=True), strict=True)
            data = self._prepare_save_data()
            data["updated"] = datetime.now()

            if self.needs_embedding():
                embedding_content = self.get_embedding_content()
                if embedding_content:
                    EMBEDDING_MODEL = model_manager.embedding_model
                    if not EMBEDDING_MODEL:
                        logger.warning(
                            "No embedding model found. Content will not be searchable."
                        )
                    data["embedding"] = (
                        EMBEDDING_MODEL.embed(embedding_content)
                        if EMBEDDING_MODEL
                        else []
                    )
                    if EMBEDDING_MODEL:
                        collection_create_vector_index_if_not_exists(self.__class__.table_name, len(data["embedding"]))

            if self.id is None:
                data["created"] = datetime.now()
                self.id = collection_create(self.__class__.table_name, data)
            else:
                data["created"] = self.created
                logger.debug(f"Updating record with id {self.id}")
                collection_update(self.__class__.table_name, {"_id": self.id}, data)

            # Update the current instance with the result
            updated_document = collection_query(self.__class__.table_name, {"_id": self.id})
            if updated_document:
                for key, value in updated_document[0].items():
                    if hasattr(self, key):
                        if isinstance(getattr(self, key), BaseModel):
                            setattr(self, key, type(getattr(self, key))(**value))
                        else:
                            setattr(self, key, value)

        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error saving {self.__class__.table_name}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = self.model_dump(by_alias=True)
        return {key: value for key, value in data.items() if value is not None}

    def delete(self) -> bool:
        if self.id is None:
            raise InvalidInputError("Cannot delete object without an ID")
        try:
            logger.debug(f"Deleting record with id {self.id}")
            return collection_delete(self.__class__.table_name, {"_id": self.id})
        except Exception as e:
            logger.error(
                f"Error deleting {self.__class__.table_name} with id {self.id}: {str(e)}"
            )
            raise DatabaseOperationError(
                f"Failed to delete {self.__class__.table_name}"
            )

    @field_validator("created", "updated", mode="before")
    @classmethod
    def parse_datetime(cls, value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


class RecordModel(BaseModel):
    record_id: ClassVar[str]
    auto_save: ClassVar[bool] = (
        False  # Default to False, can be overridden in subclasses
    )
    _instances: ClassVar[Dict[str, "RecordModel"]] = {}  # Store instances by record_id

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True
        extra = "allow"
        from_attributes = True
        defer_build = True

    def __new__(cls, **kwargs):
        # If an instance already exists for this record_id, return it
        if cls.record_id in cls._instances:
            instance = cls._instances[cls.record_id]
            # Update instance with any new kwargs if provided
            if kwargs:
                for key, value in kwargs.items():
                    setattr(instance, key, value)
            return instance

        # If no instance exists, create a new one
        instance = super().__new__(cls)
        cls._instances[cls.record_id] = instance
        return instance

    def __init__(self, **kwargs):
        # Only initialize if this is a new instance
        if not hasattr(self, "_initialized"):
            object.__setattr__(self, "__dict__", {})
            # Load data from DB first
            result = collection_query("record", {"record_id": self.record_id})

            # Initialize with DB data and any overrides
            init_data = {}
            if result and result[0]:
                init_data.update(result[0])

            # Override with any provided kwargs
            if kwargs:
                init_data.update(kwargs)

            # Initialize base model first
            super().__init__(**init_data)

            # Mark as initialized
            object.__setattr__(self, "_initialized", True)

    @classmethod
    def get_instance(cls) -> "RecordModel":
        """Get or create the singleton instance"""
        return cls()

    @model_validator(mode="after")
    def auto_save_validator(self):
        if self.__class__.auto_save:
            self.update()
        return self

    def update(self):
        # Get all non-ClassVar fields and their values
        data = {
            field_name: getattr(self, field_name)
            for field_name, field_info in self.__class__.model_fields.items()
            if not str(field_info.annotation).startswith("typing.ClassVar")
        }

        collection_upsert("record", {"record_id": self.record_id}, data)

        result = collection_query("record", {"record_id": self.record_id})
        if result:
            for key, value in result[0].items():
                if hasattr(self, key):
                    object.__setattr__(
                        self, key, value
                    )  # Use object.__setattr__ to avoid triggering validation again

        return self

    @classmethod
    def clear_instance(cls):
        """Clear the singleton instance (useful for testing)"""
        if cls.record_id in cls._instances:
            del cls._instances[cls.record_id]

    def patch(self, model_dict: dict):
        """Update model attributes from dictionary and save"""
        for key, value in model_dict.items():
            setattr(self, key, value)
        self.update()
