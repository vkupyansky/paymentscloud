"""Явный интеграционный запуск против отдельной локальной тестовой базы."""

import asyncio
import os
from urllib.parse import urlsplit

import db


def test_payment_ownership_and_atomic_status(monkeypatch):
    dsn = os.environ["PAYMENTSCLOUD_TEST_DSN"]
    parsed = urlsplit(dsn)
    assert parsed.hostname in {"localhost", "127.0.0.1"}
    assert parsed.path == "/paymentscloud_test"
    monkeypatch.setattr(db, "PG_DSN", dsn)

    async def scenario():
        await db.initialize_database()
        await db.upsert_user(1, "owner", None, None)
        await db.upsert_user(2, "another", None, None)
        payment_id = "00000000-0000-4000-8000-000000000001"
        await db.create_payment(1, 100, "login", payment_id, "{}")
        await db.create_payment(1, 200, "replay", payment_id, "{}")
        assert await db.get_payment(payment_id, 2) is None
        assert await db.get_payment(payment_id, 1) == (100, "login", "pending")
        assert not await db.transition_payment(payment_id, 2, "cancel")
        confirmed = await asyncio.gather(
            *(db.transition_payment(payment_id, 1, "success") for _ in range(8))
        )
        assert confirmed.count(True) == 1
        assert not await db.transition_payment(payment_id, 1, "cancel")
        picked = await asyncio.gather(
            *(db.picked_payment(user_id, payment_id) for user_id in (1, 2))
        )
        assert picked.count(True) == 1
        await db.initialize_database()
        assert await db.get_payment(payment_id, 1) == (100, "login", "success")

    asyncio.run(scenario())
