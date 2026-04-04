from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

import streamlit as st


JobFn = Callable[..., Dict[str, Any]]


@st.cache_resource
def get_background_job_manager() -> "_BackgroundJobManager":
    return _BackgroundJobManager()


class _BackgroundJobManager:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="livestorm-bg")
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def submit(self, job_type: str, fn: JobFn, *, context: Optional[Dict[str, Any]] = None, **kwargs: Any) -> str:
        job_id = uuid.uuid4().hex
        future = self._executor.submit(fn, **kwargs)
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "type": job_type,
                "future": future,
                "context": context or {},
            }
        return job_id

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            future: Future = record["future"]
            snapshot: Dict[str, Any] = {
                "id": record["id"],
                "type": record["type"],
                "context": dict(record.get("context") or {}),
                "done": future.done(),
                "cancelled": future.cancelled(),
            }
        if snapshot["done"] and not snapshot["cancelled"]:
            try:
                snapshot["result"] = future.result()
            except Exception as exc:  # pragma: no cover
                snapshot["exception"] = exc
        return snapshot

    def discard(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)
