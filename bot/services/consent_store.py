from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from bot.services.api_client import ServerAPIClient, ServerAPIError


@dataclass(slots=True)
class UserConsentStore:
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _active_user_ids: set[int] = field(default_factory=set, init=False, repr=False)

    def has_active(self, user_id: int | None) -> bool:
        if user_id is None:
            return False
        with self._lock:
            return user_id in self._active_user_ids

    def set_cached_active(self, user_id: int | None, active: bool) -> None:
        if user_id is None:
            return
        with self._lock:
            if active:
                self._active_user_ids.add(user_id)
            else:
                self._active_user_ids.discard(user_id)

    async def preload(self, client: ServerAPIClient, consent_version: str) -> None:
        try:
            active_user_ids = await client.load_active_user_consents(consent_version)
        except ServerAPIError:
            return

        with self._lock:
            self._active_user_ids = set(active_user_ids)

    async def set_consent(
        self,
        *,
        user_id: int | None,
        action: str,
        consent_version: str,
        language_code: str,
        client: ServerAPIClient,
    ) -> bool:
        if user_id is None:
            return False
        active = await client.set_user_consent(
            telegram_user_id=user_id,
            action=action,
            consent_version=consent_version,
            language_code=language_code,
        )
        self.set_cached_active(user_id, active)
        return active


user_consents = UserConsentStore()
