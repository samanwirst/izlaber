from dataclasses import dataclass
from time import time


@dataclass(frozen=True, slots=True)
class AIStatusEvent:
    kind: str
    reason: str


class AIRuntimeState:
    def __init__(self) -> None:
        self._quota_disabled = False
        self._reason = ""
        self._disabled_at: float | None = None
        self._events: list[AIStatusEvent] = []

    @property
    def quota_disabled(self) -> bool:
        return self._quota_disabled

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def disabled_at(self) -> float | None:
        return self._disabled_at

    def ai_allowed(self) -> bool:
        return not self._quota_disabled

    def mark_quota_exhausted(self, reason: str) -> None:
        self._reason = reason
        if self._quota_disabled:
            return
        self._quota_disabled = True
        self._disabled_at = time()
        self._events.append(AIStatusEvent(kind="disabled", reason=reason))

    def mark_available(self) -> None:
        if not self._quota_disabled:
            return
        self._quota_disabled = False
        self._reason = ""
        self._disabled_at = None
        self._events.append(AIStatusEvent(kind="enabled", reason="OpenAI API is available."))

    def consume_events(self) -> list[AIStatusEvent]:
        events = self._events[:]
        self._events.clear()
        return events

    def reset_for_tests(self) -> None:
        self._quota_disabled = False
        self._reason = ""
        self._disabled_at = None
        self._events.clear()


ai_runtime_state = AIRuntimeState()
