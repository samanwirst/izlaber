from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from bot.locales import normalize_language_code
from bot.services.api_client import ServerAPIClient, ServerAPIError


@dataclass(slots=True)
class LanguagePreferenceStore:
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _preferences: dict[int, str] = field(default_factory=dict, init=False, repr=False)

    def get(self, user_id: int | None) -> str | None:
        if user_id is None:
            return None
        with self._lock:
            return self._preferences.get(user_id)

    def set_cached(self, user_id: int | None, language_code: str) -> str | None:
        if user_id is None:
            return None
        normalized = normalize_language_code(language_code)
        with self._lock:
            self._preferences[user_id] = normalized
        return normalized

    def clear_cached(self, user_id: int | None) -> None:
        if user_id is None:
            return
        with self._lock:
            self._preferences.pop(user_id, None)

    async def preload(self, client: ServerAPIClient) -> None:
        try:
            preferences = await client.load_language_preferences()
        except ServerAPIError:
            return

        with self._lock:
            self._preferences = {
                user_id: normalize_language_code(language_code)
                for user_id, language_code in preferences.items()
            }

    async def set(
        self,
        user_id: int | None,
        language_code: str,
        client: ServerAPIClient,
    ) -> str | None:
        if user_id is None:
            return None
        normalized = normalize_language_code(language_code)
        try:
            persisted = await client.set_language_preference(user_id, normalized)
        except ServerAPIError:
            persisted = normalized
        normalized = normalize_language_code(persisted)
        with self._lock:
            self._preferences[user_id] = normalized
        return normalized


language_preferences = LanguagePreferenceStore()
