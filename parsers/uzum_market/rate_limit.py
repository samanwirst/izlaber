import asyncio
import random


class RateLimiter:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds

    async def wait(self) -> None:
        if self.delay_seconds <= 0:
            return
        jitter = random.uniform(0, self.delay_seconds * 0.25)
        await asyncio.sleep(self.delay_seconds + jitter)
