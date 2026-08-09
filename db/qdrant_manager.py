# File: db/qdrant_manager.py

'''Qdrant vector DB manager (loads settings from .env).'''
from __future__ import annotations
import os
import uuid
from typing import Any
from db.base_client import BaseDBClient

try:
    import numpy as np
except ImportError:
    np = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from qdrant_client import QdrantClient as _QClient
    from qdrant_client.models import Distance, VectorParams
    from qdrant_client.http import models as _http_model
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False
    _QClient = None
    _http_model = None

_VECTOR_SIZE = int(os.getenv('QDRANT_VECTOR_SIZE', '768'))
_DISTANCE = Distance.COSINE if HAS_QDRANT else 'COSINE'
_COLLECTION_NAME = os.getenv('QDRANT_COLLECTION_NAME', 'news_vectors')
_QDRANT_URI = os.getenv('QDRANT_URI', 'http://localhost:6333')
_qdrant_instance: QdrantManager | None = None


class QdrantManager(BaseDBClient):
    '''Manages a running Qdrant instance.'''

    def __init__(self, uri: str | None = None) -> None:
        super().__init__()
        self._uri = uri or _QDRANT_URI
        self._client: Any | None = None
        self._collection_name = _COLLECTION_NAME

    def connect(self, *args, **kwargs) -> None:
        if not HAS_QDRANT:
            raise RuntimeError('qdrant-client is not installed')
        if self.is_connected():
            return
        self._client = _QClient(url=self._uri, timeout=3.0)
        self._ensure_collection()
        self._is_connected = True

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._client is not None

    def _ensure_collection(self) -> None:
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

    def upsert_news(self, articles: list[dict], embeddings: Any) -> None:
        if not self._client:
            return
        points = []
        for i, article in enumerate(articles):
            doc_id = article.get('id') or str(uuid.uuid4())
            payload = {k: v for k, v in article.items() if k != 'id'}
            vec = embeddings[i].tolist() if hasattr(embeddings[i], 'tolist') else list(embeddings[i]) if embeddings else [0.0]*_VECTOR_SIZE
            points.append(_http_model.PointStruct(id=doc_id, vector=vec, payload=payload))
        
        self._client.upsert(collection_name=_COLLECTION_NAME, points=points, wait=True)

    def search(self, query_vector: list[float] | Any, top_k: int = 5, filter_: dict | None = None) -> list[dict]:
        if not self._client:
            return []
        if hasattr(query_vector, 'tolist'):
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
        if not self._client:
            return None
        results = self._client.retrieve(
            collection_name=_COLLECTION_NAME,
            ids=[str(id_)],
            with_payload=True
        )
        if results:
            return {'id': results[0].id, 'payload': results[0].payload}
        return None

    def search_news_by_ticker(self, ticker: str, top_k: int = 10) -> list[dict]:
        '''Search news related to a specific ticker.'''
        if not self._client:
            return []
        
        from qdrant_client.http import models as http_model
        filter_ = http_model.Filter(
            must=[http_model.FieldCondition(key='ticker', match=http_model.MatchValue(value=ticker))]
        )
        
        results = self._client.search(
            collection_name=_COLLECTION_NAME,
            query_vector=[0.0] * _VECTOR_SIZE,
            limit=top_k,
            query_filter=filter_,
            with_payload=True
        )
        return [{'id': hit.id, 'score': hit.score, 'payload': hit.payload} for hit in results]

    def search_news_by_industry(self, industry: str, top_k: int = 10) -> list[dict]:
        '''Search news related to a specific industry.'''
        if not self._client:
            return []
        
        from qdrant_client.http import models as http_model
        filter_ = http_model.Filter(
            must=[http_model.FieldCondition(key='industry', match=http_model.MatchValue(value=industry))]
        )
        
        results = self._client.search(
            collection_name=_COLLECTION_NAME,
            query_vector=[0.0] * _VECTOR_SIZE,
            limit=top_k,
            query_filter=filter_,
            with_payload=True
        )
        return [{'id': hit.id, 'score': hit.score, 'payload': hit.payload} for hit in results]

    def upsert_news_with_metadata(
        self, 
        articles: list[dict], 
        embeddings: Any,
        include_industry: bool = True
    ) -> None:
        '''Upsert news articles with optional industry metadata.'''
        if not self._client:
            return
        
        # Import industry mapping
        try:
            from crawlers.industry_graph import TAG_TO_COMPANIES
            ticker_to_industry = {}
            for tag, companies in TAG_TO_COMPANIES.items():
                for company_info in companies:
                    if isinstance(company_info, dict):
                        ticker = company_info.get('code', '')
                        if ticker:
                            ticker_to_industry[ticker] = tag
        except Exception:
            ticker_to_industry = {}

        points = []
        for i, article in enumerate(articles):
            doc_id = article.get('id') or str(uuid.uuid4())
            payload = {k: v for k, v in article.items() if k != 'id'}
            
            # Add industry metadata if available
            if include_industry:
                ticker = article.get('ticker', '')
                if ticker:
                    payload['industry'] = ticker_to_industry.get(ticker, 'Unknown')
            
            vec = embeddings[i].tolist() if hasattr(embeddings[i], 'tolist') else list(embeddings[i]) if embeddings else [0.0]*_VECTOR_SIZE
            points.append(_http_model.PointStruct(id=doc_id, vector=vec, payload=payload))
        
        self._client.upsert(collection_name=_COLLECTION_NAME, points=points, wait=True)


def get_qdrant_manager() -> QdrantManager:
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = QdrantManager()
    return _qdrant_instance


def check_qdrant_status() -> dict[str, Any]:
    '''Helper to test Qdrant connection status on startup.'''
    if not HAS_QDRANT:
        return {'connected': False, 'uri': _QDRANT_URI, 'collection': _COLLECTION_NAME, 'reason': 'qdrant-client not installed'}
    qm = get_qdrant_manager()
    try:
        qm.connect()
        return {'connected': True, 'uri': _QDRANT_URI, 'collection': _COLLECTION_NAME, 'reason': 'OK'}
    except Exception as e:
        return {'connected': False, 'uri': _QDRANT_URI, 'collection': _COLLECTION_NAME, 'reason': str(e)}
