# File: db/mongo_client.py

'''MongoDB manager singleton. Connected to localhost:27017, database stock_agent.'''
from __future__ import annotations
from pymongo import MongoClient as _PyMongoClient
from pymongo.collection import Collection
from db.base_client import BaseDBClient

_MONGO_URI = 'mongodb://localhost:27017'
_DB_NAME = 'stock_agent'
_instance: MongoClient | None = None


class MongoClient(BaseDBClient):
    def __init__(self, uri: str = _MONGO_URI, db_name: str = _DB_NAME) -> None:
        super().__init__()
        self._uri = uri
        self._db_name = db_name
        self._client: _PyMongoClient | None = None
        self._is_connected: bool = False

    def connect(self, *args, **kwargs) -> None:
        '''Establish a client connection to MongoDB.'''
        if self.is_connected():
            return
        self._client = _PyMongoClient(self._uri, serverSelectionTimeoutMS=5000)
        self._client.admin.command('ping')
        self._is_connected = True

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
        self._is_connected = False

    def is_connected(self) -> bool:
        return bool(self._is_connected and self._client)

    @property
    def database(self):
        if not self._client:
            raise RuntimeError('MongoClient not connected. Call connect() first.')
        return self._client[self._db_name]

    def get_collection(self, name: str) -> Collection:
        return self.database[name]

    def insert_one(self, collection_name: str, doc: dict) -> None:
        coll = self.get_collection(collection_name)
        coll.insert_one(doc)

    def find_one(self, collection_name: str, filter_: dict) -> dict | None:
        coll = self.get_collection(collection_name)
        return coll.find_one(filter_)

    def update_one(self, collection_name: str, filter_: dict, update_: dict, upsert: bool = False) -> None:
        coll = self.get_collection(collection_name)
        coll.update_one(filter_, update_, upsert=upsert)

    def delete_many(self, collection_name: str, filter_: dict) -> None:
        coll = self.get_collection(collection_name)
        coll.delete_many(filter_)

    def bulk_insert(self, collection_name: str, docs_list: list[dict]) -> int:
        '''Efficient batch insert with acknowledged write concern.'''
        if not docs_list:
            return 0
        coll = self.get_collection(collection_name)
        result = coll.insert_many(docs_list, ordered=False)
        return len(result.inserted_ids)


def get_mongo_client() -> MongoClient:
    '''Return the global/first MongoClient instance (connects on-demand).'''
    global _instance
    if _instance is None:
        _instance = MongoClient()
    return _instance
