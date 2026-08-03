# File: db/qdrant_manager.py

'''Qdrant vector DB manager (cosine distance, 768-dim embeddings).'''
from __future__ import annotations
import numpy as np
import uuid
from qdrant_client import QdrantClient as _QClient
from qdrant_client.models import (
    CollectionConfig,
    Distance,
    VectorParams,
    PayloadSchemaType
)
from qdrant_client.http import models as _http_model
from db.base_client import BaseDBClient

_VECTOR_SIZE = 768
_DISTANCE = Distance.COSINE
_COLLECTION_NAME = 'news_vectors'
_QDRANT_URI = 'http://localhost:6333'
_qdrant_instance: QdrantManager | None = None


class QdrantManager(BaseDBClient):
    '''Manages a running Qdrant instance at localhost:6333.'''

    def __init__(self, uri: str = _QDRANT_URI) -> None:
        super().__init__()
        self._uri = uri
        self._client: _QClient | None = None
        self._collection_name = _COLLECTION_NAME

    def connect(self, *args, **kwargs) -> None:
        if self.is_connected():
            return
        self._client = _QClient(url=self._uri)
        self._ensure_collection()
        self._is_connected = True

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._client is not None

    def _ensure_collection() -> None:
        '''Ensure the news_vectors collection exists with proper schema. Idempotent.'''
        if not self._client:
            raise RuntimeError('QdrantClient not connected')
        try:
            self._client.get_collection(_COLLECTION_NAME)
        except Exception:
            self._client.create_collection(
                collection_name=_COLLECTION_NAME,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=_DISTANCE)
            )

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def upsert_news(self, articles: list[dict], embeddings: np.ndarray) -> None:
        '''Bulk upsert articles with their precomputed embeddings (768-dim vectors).'''
        if not self._client:
            raise RuntimeError('QdrantClient not connected')
        if embeddings.shape[1] != _VECTOR_SIZE or len(articles) != embeddings.shape[0]:
            raise ValueError(f'embeddings shape mismatch: expected ({len(articles)}, {_VECTOR_SIZE}), got {embeddings.shape}')
        
        points = []
        for i, article in enumerate(articles):
            doc_id = article.get('id') or str(uuid.uuid4())
            payload = {k: v for k, v in article.items() if k != 'id'}
            points.append(_http_model.PointStruct(id=doc_id, vector=embeddings[i].tolist(), payload=payload))
        
        self._client.upsert(collection_name=_COLLECTION_NAME, points=points, wait=True)

    def search(self, query_vector: list[float] | np.ndarray, top_k: int = 5, filter_: dict | None = None) -> list[dict]:
        '''Search by a query embedding vector. Returns list of dicts with id, score, payload.'''
        if not self._client:
            raise RuntimeError('QdrantClient not connected')
        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()
        hits = self._client.search(
            collection_name=_COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filter_,
            with_payload=True
        )
        return [{'id': hit.id, 'score': hit.score, 'payload': hit.payload} for hit in hits]

    def get_news_by_id(self, id_: str) -> dict | None:
        '''Retrieve a single news document from Qdrant by its point id.'''
        if not self._client:
            raise RuntimeError('QdrantClient not connected')
        results = self._client.retrieve(
            collection_name=_COLLECTION_NAME,
            ids=[str(id_)],
            with_payload=True
        )
        if results:
            return {'id': results[0].id, 'payload': results[0].payload}
        return None


def get_qdrant_manager() -> QdrantManager:
    '''Return the global/first QdrantManager instance (connects on-demand).'''
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = QdrantManager()
    return _qdrant_instance
