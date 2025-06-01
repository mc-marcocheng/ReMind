from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple

import semchunk
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from remind.database.mongodb import collection_delete, collection_query
from remind.exceptions import DatabaseOperationError, InvalidInputError

from .base import ObjectModel, PyObjectId

chunker = semchunk.chunkerify("o200k_base", chunk_size=1024)

def split_text(text: str) -> list[str]:
    chunks = chunker(text)
    return chunks

class Asset(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None


class SourceEmbedding(ObjectModel):
    table_name: ClassVar[str] = "source_embedding"
    content: str
    source_id: PyObjectId

    def needs_embedding(self) -> bool:
        return True

    def get_embedding_content(self) -> Optional[str]:
        return self.content

    @property
    def source(self) -> "Source":
        try:
            result = collection_query(Source.table_name, {"_id": self.source_id})
            if not result:
                raise DatabaseOperationError(f"Source with id {self.source_id} not found")
            return Source(**result[0])
        except Exception as e:
            logger.error(f"Error fetching source for embedding {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)


class SourceInsight(ObjectModel):
    table_name: ClassVar[str] = "source_insight"
    insight_type: str
    content: str
    source_id: PyObjectId

    def needs_embedding(self) -> bool:
        return True

    def get_embedding_content(self) -> Optional[str]:
        return self.content

    @property
    def source(self) -> "Source":
        try:
            result = collection_query(Source.table_name, {"_id": self.source_id})
            if not result:
                raise DatabaseOperationError(f"Source with id {self.source_id} not found")
            return Source(**result[0])
        except Exception as e:
            logger.error(f"Error fetching source for insight {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)


class Source(ObjectModel):
    table_name: ClassVar[str] = "source"
    asset: Optional[Asset] = None
    title: Optional[str] = None
    topics: Optional[List[str]] = Field(default_factory=list)
    full_text: Optional[str] = None

    def get_context(
        self, context_size: Literal["short", "long"] = "short"
    ) -> Dict[str, Any]:
        insights = [insight.model_dump() for insight in self.insights]
        if context_size == "long":
            return dict(
                id=self.id,
                title=self.title,
                insights=insights,
                full_text=self.full_text,
            )
        else:
            return dict(id=self.id, title=self.title, insights=insights)

    @property
    def embedded_chunks(self) -> int:
        try:
            result = collection_query(
                "source_embedding", {"source_id": self.id}
            )
            return len(result)
        except Exception as e:
            logger.error(f"Error fetching insights for source {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(f"Failed to count chunks for source: {str(e)}")

    @property
    def insights(self) -> List[SourceInsight]:
        try:
            result = collection_query(
                "source_insight", {"source_id": self.id}
            )
            return [SourceInsight(**insight) for insight in result]
        except Exception as e:
            logger.error(f"Error fetching insights for source {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError("Failed to fetch insights for source")

    def vectorize(self) -> None:
        logger.info(f"Starting vectorization for source {self.id}")

        try:
            if not self.full_text:
                logger.warning(f"No text to vectorize for source {self.id}")
                return

            chunks = split_text(self.full_text)
            chunk_count = len(chunks)
            logger.info(f"Split into {chunk_count} chunks for source {self.id}")

            if chunk_count == 0:
                logger.warning("No chunks created after splitting")
                return

            def process_chunk(source_embedding: SourceEmbedding):
                source_embedding.save()

            # Process chunks in parallel while preserving order
            logger.info("Starting parallel processing of chunks")
            with ThreadPoolExecutor(max_workers=8) as executor:
                chunk_tasks = [SourceEmbedding(content=chunk, source_id=self.id) for chunk in chunks]
                # Process all chunks in parallel and get results
                list(executor.map(process_chunk, chunk_tasks))
            logger.info(f"Vectorization complete for source {self.id}")

        except Exception as e:
            logger.error(f"Error vectorizing source {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    def add_insight(self, insight_type: str, content: str) -> Any:
        if not insight_type or not content:
            raise InvalidInputError("Insight type and content must be provided")
        try:
            SourceInsight(
                insight_type=insight_type,
                content=content,
                source_id=self.id,
            ).save()
        except Exception as e:
            logger.error(f"Error adding insight to source {self.id}: {str(e)}")
            raise  # DatabaseOperationError(e)

    def delete(self):
        collection_delete("source_embedding", {"source_id": self.id})
        collection_delete("source_insight", {"source_id": self.id})
        super().delete()
