import time
from collections import defaultdict
from contextlib import contextmanager


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.timers_total_ms: dict[str, float] = defaultdict(float)
        self.timers_count: dict[str, int] = defaultdict(int)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    @contextmanager
    def timer(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.timers_total_ms[name] += elapsed_ms
            self.timers_count[name] += 1

    def snapshot(self) -> dict[str, object]:
        averages = {
            key: (self.timers_total_ms[key] / self.timers_count[key]) if self.timers_count[key] else 0.0
            for key in self.timers_total_ms
        }
        return {
            "counters": dict(self.counters),
            "timers_avg_ms": averages,
        }


metrics = MetricsRegistry()
