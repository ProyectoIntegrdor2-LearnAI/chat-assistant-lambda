import os
from typing import Dict, Optional

from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection


class MongoCourseClient:
    def __init__(self) -> None:
        uri = os.getenv("ATLAS_URI")
        if not uri:
            raise ValueError("ATLAS_URI environment variable is required")

        self._database_name = os.getenv("DATABASE_NAME", "learnia_db")
        self._collection_name = os.getenv("COLLECTION_NAME", "courses")
        self._client = MongoClient(
            uri,
            connectTimeoutMS=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "10000")),
            serverSelectionTimeoutMS=int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "10000")),
        )
        self._collection: Collection = self._client[self._database_name][self._collection_name]

    def get_course(self, course_id: str) -> Optional[Dict]:
        if not course_id:
            return None
        query = {"_id": ObjectId(course_id)} if ObjectId.is_valid(course_id) else {"legacy_id": course_id}
        result = self._collection.find_one(
            query,
            {
                "_id": 1,
                "title": 1,
                "description": 1,
                "url": 1,
                "platform": 1,
                "duration": 1,
                "level": 1,
            },
        )
        if not result:
            return None
        result["course_id"] = str(result.pop("_id", course_id))
        return result


_client: Optional[MongoCourseClient] = None


def get_mongo_client() -> MongoCourseClient:
    global _client
    if _client is None:
        _client = MongoCourseClient()
    return _client
