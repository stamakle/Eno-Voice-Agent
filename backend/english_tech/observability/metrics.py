from __future__ import annotations

import threading
from collections import defaultdict


class MetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.http_counts: dict[str, int] = defaultdict(int)
        self.http_duration_ms: dict[str, float] = defaultdict(float)
        self.ws_events: dict[str, int] = defaultdict(int)
        self.llm_calls: dict[str, int] = defaultdict(int)

    def record_http(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        bucket = f'{method} {path} {status_code}'
        with self._lock:
            self.http_counts[bucket] += 1
            self.http_duration_ms[bucket] += duration_ms

    def record_ws_event(self, *, channel: str, event_type: str) -> None:
        bucket = f'{channel}:{event_type}'
        with self._lock:
            self.ws_events[bucket] += 1

    def record_llm(self, *, surface: str, provider: str, success: bool) -> None:
        bucket = f'{surface}:{provider}:{"success" if success else "failure"}'
        with self._lock:
            self.llm_calls[bucket] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                'http_counts': dict(self.http_counts),
                'http_duration_ms': {key: round(value, 2) for key, value in self.http_duration_ms.items()},
                'ws_events': dict(self.ws_events),
                'llm_calls': dict(self.llm_calls),
            }


metrics_store = MetricsStore()
