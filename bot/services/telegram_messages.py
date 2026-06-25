from __future__ import annotations

from typing import Any

from aiogram.types import Message


def direct_messages_topic_id(message: Message) -> int | None:
    topic = getattr(message, "direct_messages_topic", None)
    topic_id = getattr(topic, "topic_id", None)
    return topic_id if isinstance(topic_id, int) else None


def direct_message_answer_kwargs(message: Message, kwargs: dict[str, Any]) -> dict[str, Any]:
    topic_id = direct_messages_topic_id(message)
    if topic_id is None or "direct_messages_topic_id" in kwargs:
        return kwargs
    return {**kwargs, "direct_messages_topic_id": topic_id}


async def answer_message(message: Message, text: str, **kwargs: Any) -> Message:
    return await message.answer(text, **direct_message_answer_kwargs(message, kwargs))
