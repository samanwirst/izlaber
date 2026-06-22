from dataclasses import dataclass

from bot.services.api_client import ProductDTO


@dataclass(slots=True)
class SearchSession:
    query: str
    products: list[ProductDTO]
    offset: int = 0
    candidate_offset: int = 0


class SearchStateStore:
    def __init__(self) -> None:
        self._sessions: dict[tuple[int, int | None], SearchSession] = {}

    def set(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        query: str,
        products: list[ProductDTO],
        offset: int,
        candidate_offset: int,
    ) -> None:
        self._sessions[(chat_id, user_id)] = SearchSession(
            query=query,
            products=products,
            offset=offset,
            candidate_offset=candidate_offset,
        )

    def get(self, *, chat_id: int, user_id: int | None) -> SearchSession | None:
        return self._sessions.get((chat_id, user_id))

    def clear(self, *, chat_id: int, user_id: int | None) -> None:
        self._sessions.pop((chat_id, user_id), None)


search_state = SearchStateStore()
