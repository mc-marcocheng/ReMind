import os
from contextlib import contextmanager
from typing import Any, Dict

from loguru import logger
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel


@contextmanager
def db_connection():
    connection = MongoClient(
        host=os.environ["MONGO_HOST"],
    )
    try:
        yield connection[os.environ["MONGO_DATABASE"]]
    finally:
        connection.close()


def collection_query(collection_name: str, filter: Dict[str, Any]):
    with db_connection() as db:
        try:
            collection = db[collection_name]
            result = collection.find(filter)
            return list(result)
        except Exception as e:
            logger.critical(f"Query filter: {filter}")
            logger.exception(e)
            raise


def collection_create(collection_name: str, data: Dict[str, Any]):
    with db_connection() as db:
        collection = db[collection_name]
        result = collection.insert_one(data)
        return result.inserted_id


def collection_upsert(collection_name: str, filter: Dict[str, Any], data: Dict[str, Any]):
    with db_connection() as db:
        collection = db[collection_name]
        result = collection.update_one(filter, {"$set": data}, upsert=True)
        return result.upserted_id


def collection_update(collection_name: str, filter: Dict[str, Any], data: Dict[str, Any]):
    with db_connection() as db:
        collection = db[collection_name]
        result = collection.update_one(filter, {"$set": data})
        return result.modified_count


def collection_delete(collection_name: str, filter: Dict[str, Any]):
    with db_connection() as db:
        collection = db[collection_name]
        result = collection.delete_one(filter)
        return result.deleted_count


def collection_create_vector_index_if_not_exists(collection_name: str, embedding_dim: int):
    """ Ensure a vector index called vector_knn_index in collection_name has been created. """
    with db_connection() as db:
        collection = db[collection_name]
        index_name = "vector_knn_index"
        indexes = collection.list_search_indexes().to_list(length=None)
        for index in indexes:
            if index["name"] == index_name:
                return
        search_index_model = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "numDimensions": embedding_dim,
                        "path": "embedding",
                        "similarity": "cosine",  # Options: euclidean, cosine, dotProduct
                    }
                ]
            },
            name=index_name,
            type="vectorSearch",
        )

        collection.create_search_index(search_index_model)
        logger.info(f"Created vector index for collection {collection_name}")
