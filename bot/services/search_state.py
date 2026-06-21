from dataclasses import dataclass


@dataclass(slots=True)
class SearchSession:
    query: str
    offset: int = 0


class SearchStateStore:
    def __init__(self) -> None:
        self._sessions: dict[tuple[int, int | None], SearchSession] = {}

    def set(self, *, chat_id: int, user_id: int | None, query: str, offset: int) -> None:
        self._sessions[(chat_id, user_id)] = SearchSession(query=query, offset=offset)

    def get(self, *, chat_id: int, user_id: int | None) -> SearchSession | None:
        return self._sessions.get((chat_id, user_id))

    def clear(self, *, chat_id: int, user_id: int | None) -> None:
        self._sessions.pop((chat_id, user_id), None)


search_state = SearchStateStore()
