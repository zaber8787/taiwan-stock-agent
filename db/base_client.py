# File: db/base_client.py

'''Abstract base class for database managers.'''
from abc import ABC, abstractmethod
from typing import Any


class BaseDBClient(ABC):
    '''Provides a common interface with connection lifecycle management.

    Subclasses MUST:
      ``connect(...)``  – open the underlying connection
      ``disconnect()``  – close / release resources
      ``is_connected()`` – return True if connected
    '''

    def __init__(self) -> None:
        self._is_connected: bool = False

    @abstractmethod
    def connect(self, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass
