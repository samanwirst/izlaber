import json
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from parsers.wildberries.config import ParserConfig


class CheckpointStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.path = state_dir / "checkpoint.json"

    @staticmethod
    def empty_state() -> dict[str, Any]:
        return {
            "completed": False,
            "completed_status": None,
            "mode": None,
            "processed_category_ids": [],
            "processed_segment_keys": [],
            "segment_next_pages": {},
            "failed_segment_keys": [],
            "crawl_run_id": None,
        }

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.empty_state()
        payload = json.loads(self.path.read_text())
        state = self.empty_state()
        state.update(payload)
        return state

    def save(self, state: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        tmp_path.replace(self.path)


class ServerStorage:
    def __init__(self, config: ParserConfig, dry_run: bool = False) -> None:
        self.config = config
        self.dry_run = dry_run
        self.headers = {
            "X-Internal-API-Key": config.parser_api_key,
            "Content-Type": "application/json",
        }

    async def start_crawl_run(self, mode: str, metadata: dict[str, Any]) -> int | None:
        if self.dry_run:
            return None
        data = await self._post(
            "/internal/crawl-runs/start/",
            {
                "marketplace": self.config.marketplace_code,
                "run_type": mode,
                "metadata": metadata,
            },
        )
        return data["id"]

    async def get_product_states(self, source_product_ids: list[str]) -> dict[str, dict[str, Any]]:
        if self.dry_run or not source_product_ids:
            return {}
        data = await self._post(
            "/internal/products/hash-batch/",
            {
                "marketplace": self.config.marketplace_code,
                "source_product_ids": source_product_ids,
            },
        )
        states = data.get("products")
        return states if isinstance(states, dict) else {}

    async def record_seen_product_ids(
        self,
        crawl_run_id: int | None,
        source_product_ids: list[str],
    ) -> dict[str, Any]:
        if self.dry_run or crawl_run_id is None or not source_product_ids:
            return {"seen_count": len(source_product_ids), "dry_run": True}
        return await self._post(
            f"/internal/crawl-runs/{crawl_run_id}/seen-products/",
            {"source_product_ids": source_product_ids},
        )

    async def upsert_products(
        self,
        products: list[dict[str, Any]],
        crawl_run_id: int | None,
    ) -> dict[str, Any]:
        if self.dry_run:
            return {
                "created_count": 0,
                "updated_count": 0,
                "unchanged_count": len(products),
                "reactivated_count": 0,
                "dry_run": True,
            }
        return await self._post(
            "/internal/products/upsert-batch/",
            {
                "marketplace": self.config.marketplace_code,
                "crawl_run_id": crawl_run_id,
                "products": products,
            },
        )

    async def finish_crawl_run(
        self,
        crawl_run_id: int | None,
        *,
        status: str,
        deactivate_unseen: bool,
        metadata: dict[str, Any],
    ) -> None:
        if self.dry_run or crawl_run_id is None:
            return
        await self._post(
            f"/internal/crawl-runs/{crawl_run_id}/finish/",
            {
                "status": status,
                "deactivate_unseen": deactivate_unseen,
                "metadata": metadata,
            },
        )

    async def create_event(
        self,
        crawl_run_id: int | None,
        level: str,
        event_type: str,
        message: str,
        **extra,
    ) -> None:
        if self.dry_run or crawl_run_id is None:
            return
        await self._post(
            "/internal/crawl-events/",
            {
                "crawl_run": crawl_run_id,
                "level": level,
                "event_type": event_type,
                "message": message,
                **extra,
            },
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.server_api_base_url}{path}"
        async with ClientSession(
            timeout=ClientTimeout(total=self.config.request_timeout),
            headers=self.headers,
        ) as session:
            async with session.post(url, json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"Server API {response.status} for {url}: {body[:500]}")
                return json.loads(body) if body else {}
