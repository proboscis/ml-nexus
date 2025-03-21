import asyncio
from contextlib import asynccontextmanager
from typing import Dict


class KeyedLock:
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()  # Lock for managing the locks dict

    @asynccontextmanager
    async def lock(self, key: str):
        """
        Get a lock for the given key. If the lock doesn't exist, create it.
        Usage: async with keyed_lock.lock("my_key"): ...
        """
        try:
            # Safely get or create the lock for this key
            async with self._lock:
                if key not in self.locks:
                    self.locks[key] = asyncio.Lock()
                lock = self.locks[key]

            # Acquire the lock for this key
            await lock.acquire()
            yield
        finally:
            # Release the lock
            lock.release()

            # Clean up if no one is waiting
            async with self._lock:
                if not lock.locked() and key in self.locks:
                    del self.locks[key]