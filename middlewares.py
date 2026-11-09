from aiogram import BaseMiddleware
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Message, CallbackQuery

import db
from config import REDIS_URL


class Manage(BaseMiddleware):
    async def __call__(self, handler, event: Message | CallbackQuery, data: dict):
        if isinstance(event, Message) and (event.chat.type != "private" or event.from_user is None):
            return None
        user_id = event.from_user.id
        username = event.from_user.username
        first_name = event.from_user.first_name
        last_name = event.from_user.last_name

        await db.upsert_user(user_id, username, first_name, last_name)

        is_blocked = await db.check_if_user_blocked(user_id)
        if is_blocked:
            return await event.answer("<b>Доступ к профилю в боте ограничен</b>")

        return await handler(event, data)


class Throttling(BaseMiddleware):
    def __init__(self):
        self.storage = RedisStorage.from_url(
            REDIS_URL, connection_kwargs={"socket_timeout": 5, "socket_connect_timeout": 5}
        )

    async def __call__(self, handler, event: Message | CallbackQuery, data: dict):
        long_user_key = f"long_user_{event.from_user.id}"

        current_count_long = await self.storage.redis.incr(long_user_key)
        if current_count_long == 1:
            await self.storage.redis.expire(long_user_key, 5)

        if current_count_long > 10:
            await db.block_user_account(
                event.from_user.id, "СПАМ. Превышение 10 запросов за 5 секунд."
            )
            return await event.answer(
                "<b>Доступ к профилю заблокирован за чрезмерное количество запросов</b>"
            )

        if current_count_long > 5:
            return await event.answer("<b>Слишком много запросов. Повторите попытку позже</b>")

        return await handler(event, data)
