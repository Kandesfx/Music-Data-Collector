"""
Music Data Collector - Concurrency & Lock Manager Module
Provides distributed (MongoDB) and in-memory (RLock) mutex locks with:
1. Global Pipeline Task Locking (Prevents overlapping crawl/download batch jobs)
2. Per-Track Atomic Download Locks (Prevents concurrent writes to the same audio file)
3. Hardware/CLI Execution Mutex (Serializes OS-level commands like WARP & Tailscale)
4. Self-Healing Deadlock Prevention (Automatic TTL lease expiration and stale lock reclamation)
"""

import time
import uuid
import threading
from typing import Dict, Any, Optional, Tuple, Callable
from datetime import datetime, timedelta

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LockManager:
    """Manages distributed and in-memory synchronization locks."""

    _mem_locks: Dict[str, threading.RLock] = {}
    _mem_meta: Dict[str, Dict[str, Any]] = {}
    _global_rlock = threading.RLock()

    def __init__(self, db_manager: Optional[Any] = None):
        self.db = db_manager

    def set_db_manager(self, db_manager: Any):
        """Set DB manager reference."""
        self.db = db_manager

    def _get_mem_lock(self, lock_name: str) -> threading.RLock:
        """Get or create in-memory lock."""
        with self._global_rlock:
            if lock_name not in self._mem_locks:
                self._mem_locks[lock_name] = threading.RLock()
            return self._mem_locks[lock_name]

    def acquire_lock(
        self,
        lock_name: str,
        owner: str = "system",
        ttl_seconds: int = 600,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Acquire a named lock with TTL lease expiration.
        Returns:
            (acquired: bool, existing_lock_info: Optional[Dict])
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)

        # 1. Check & update in MongoDB if connected
        if self.db and hasattr(self.db, "is_connected") and self.db.is_connected():
            try:
                coll = self.db.db.system_locks
                # Ensure unique index on lock_name
                coll.create_index("lock_name", unique=True)
                coll.create_index("expires_at", expireAfterSeconds=0)

                existing = coll.find_one({"lock_name": lock_name})
                if existing:
                    # Check if stale / expired
                    exp = existing.get("expires_at")
                    if isinstance(exp, str):
                        try:
                            exp = datetime.fromisoformat(exp)
                        except Exception:
                            exp = None

                    if exp and exp > now:
                        # Lock is currently active
                        return False, {
                            "lock_name": lock_name,
                            "owner": existing.get("owner", "unknown"),
                            "acquired_at": existing.get("acquired_at"),
                            "expires_at": existing.get("expires_at"),
                            "time_left_sec": int((exp - now).total_seconds()),
                            "metadata": existing.get("metadata", {}),
                        }
                    else:
                        # Stale lock: auto-reclaim
                        logger.warning(f"[Auto-Reclaim] Expired stale lock reclaimed: '{lock_name}' (owned by {existing.get('owner')})")

                # Insert or overwrite expired lock atomically
                doc = {
                    "lock_name": lock_name,
                    "owner": owner,
                    "acquired_at": now,
                    "expires_at": expires_at,
                    "metadata": metadata or {},
                    "updated_at": now,
                }
                coll.update_one({"lock_name": lock_name}, {"$set": doc}, upsert=True)
                return True, None
            except Exception as ex:
                logger.error(f"Error acquiring MongoDB lock '{lock_name}': {ex}")

        # 2. In-Memory fallback
        with self._global_rlock:
            existing_meta = self._mem_meta.get(lock_name)
            if existing_meta:
                exp = existing_meta.get("expires_at")
                if exp and exp > now:
                    return False, {
                        "lock_name": lock_name,
                        "owner": existing_meta.get("owner", "unknown"),
                        "time_left_sec": int((exp - now).total_seconds()),
                        "metadata": existing_meta.get("metadata", {}),
                    }

            self._mem_meta[lock_name] = {
                "lock_name": lock_name,
                "owner": owner,
                "acquired_at": now,
                "expires_at": expires_at,
                "metadata": metadata or {},
            }
            return True, None

    def release_lock(self, lock_name: str, owner: Optional[str] = None) -> bool:
        """Release a named lock."""
        # 1. Release in MongoDB
        if self.db and hasattr(self.db, "is_connected") and self.db.is_connected():
            try:
                coll = self.db.db.system_locks
                query: Dict[str, Any] = {"lock_name": lock_name}
                if owner:
                    query["owner"] = owner
                coll.delete_one(query)
            except Exception as ex:
                logger.error(f"Error releasing MongoDB lock '{lock_name}': {ex}")

        # 2. Release in Memory
        with self._global_rlock:
            if lock_name in self._mem_meta:
                if not owner or self._mem_meta[lock_name].get("owner") == owner:
                    del self._mem_meta[lock_name]
                    return True
        return True

    def get_lock_info(self, lock_name: str) -> Optional[Dict[str, Any]]:
        """Query status and owner of a lock."""
        now = datetime.utcnow()
        if self.db and hasattr(self.db, "is_connected") and self.db.is_connected():
            try:
                doc = self.db.db.system_locks.find_one({"lock_name": lock_name}, {"_id": 0})
                if doc:
                    exp = doc.get("expires_at")
                    if exp and exp > now:
                        doc["time_left_sec"] = int((exp - now).total_seconds())
                        return doc
            except Exception:
                pass

        with self._global_rlock:
            meta = self._mem_meta.get(lock_name)
            if meta:
                exp = meta.get("expires_at")
                if exp and exp > now:
                    meta["time_left_sec"] = int((exp - now).total_seconds())
                    return meta
        return None

    def acquire_track_download_lock(
        self,
        spotify_id: str,
        owner: str = "download_worker",
        ttl_seconds: int = 180,
    ) -> bool:
        """
        Atomically lock an individual track during download.
        Prevents multiple threads/processes from downloading the exact same track file concurrently.
        """
        lock_key = f"track_download_{spotify_id}"
        ok, _ = self.acquire_lock(
            lock_name=lock_key,
            owner=owner,
            ttl_seconds=ttl_seconds,
            metadata={"spotify_id": spotify_id}
        )
        return ok

    def release_track_download_lock(self, spotify_id: str, owner: Optional[str] = None) -> bool:
        """Release download lock for an individual track."""
        lock_key = f"track_download_{spotify_id}"
        return self.release_lock(lock_name=lock_key, owner=owner)

    def execute_with_cli_mutex(self, lock_name: str, func: Callable, *args, timeout_sec: int = 15, **kwargs) -> Any:
        """
        Execute OS CLI commands (WARP, Tailscale) inside a strictly serialized mutex
        to prevent OS-level process deadlocks and race conditions.
        """
        mem_lock = self._get_mem_lock(lock_name)
        acquired = mem_lock.acquire(timeout=timeout_sec)
        if not acquired:
            raise TimeoutError(f"Hệ thống đang bận thực thi tác vụ '{lock_name}'. Vui lòng thử lại sau vài giây!")

        try:
            return func(*args, **kwargs)
        finally:
            mem_lock.release()


# Global Singleton Instance
lock_manager = LockManager()
