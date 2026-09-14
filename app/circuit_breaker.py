from dataclasses import dataclass
import time


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


class CircuitBreaker:
    """Small process-local breaker; Redis can replace this state later."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._states: dict[str, CircuitState] = {}

    def allow(self, provider: str) -> bool:
        state = self._states.get(provider)
        if not state or state.opened_at is None:
            return True
        if time.monotonic() - state.opened_at >= self.cooldown_seconds:
            state.opened_at = None
            state.failures = 0
            return True
        return False

    def record_success(self, provider: str) -> None:
        self._states.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        state = self._states.setdefault(provider, CircuitState())
        state.failures += 1
        if state.failures >= self.failure_threshold:
            state.opened_at = time.monotonic()

    def snapshot(self) -> dict[str, dict[str, float | int | None]]:
        return {
            name: {"failures": state.failures, "opened_at": state.opened_at}
            for name, state in self._states.items()
        }
