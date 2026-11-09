import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Message

import bot
import config
import init_env
import payment


def callback(data):
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
        message=Message(
            message_id=1, date=datetime.now(timezone.utc), chat=Chat(id=1, type="private")
        ),
    )


def test_required_configuration_does_not_expose_values(monkeypatch):
    monkeypatch.delenv("TOKEN")
    with pytest.raises(ValueError, match="TOKEN"):
        config.required("TOKEN")


def test_env_init_preserves_secret_and_permissions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path(".env.example").write_text("TOKEN=\nWEBHOOK_SECRET=\n")
    init_env.main()
    original = Path(".env").read_bytes()
    assert len(original.split(b"WEBHOOK_SECRET=")[1].strip()) >= 32
    assert Path(".env").stat().st_mode & 0o777 == 0o600
    init_env.main()
    assert Path(".env").read_bytes() == original


def test_decimal_calculation_has_no_binary_money():
    result = bot.calculate(100)
    assert result["total_payment"] == Decimal("105.75")
    assert result["after_aggregator"] == Decimal("102.58")
    assert result["after_steam"] == Decimal("92")
    assert all(isinstance(value, Decimal) for value in result.values())


def test_admin_callback_checks_permission(monkeypatch):
    monkeypatch.setattr(bot.db, "check_user_admin_status", AsyncMock(return_value=False))
    stats = AsyncMock()
    monkeypatch.setattr(bot.db, "get_user_statistics", stats)
    request = callback("admin_statistics")
    asyncio.run(bot.callback_query_handler(request, SimpleNamespace()))
    assert request.answer.await_args.args[0] == "Доступ запрещён"
    stats.assert_not_awaited()


def test_foreign_payment_never_reaches_provider(monkeypatch):
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(bot.db, "get_payment", lookup)
    provider = AsyncMock()
    monkeypatch.setattr(bot.YoomoneyAPI, "is_success_operation", provider)
    payment_id = "00000000-0000-4000-8000-000000000001"
    request = callback(f"check_payment:{payment_id}")
    asyncio.run(bot.callback_query_handler(request, SimpleNamespace()))
    lookup.assert_awaited_once_with(payment_id, 1)
    provider.assert_not_awaited()


def test_repeated_confirmation_does_not_repeat_order(monkeypatch):
    monkeypatch.setattr(bot.db, "get_payment", AsyncMock(return_value=(100, "login", "success")))
    send_order = AsyncMock()
    monkeypatch.setattr(bot, "new_order", send_order)
    request = callback("check_payment:00000000-0000-4000-8000-000000000001")
    asyncio.run(bot.callback_query_handler(request, SimpleNamespace()))
    send_order.assert_not_awaited()
    assert request.answer.await_args.args[0] == "Оплата уже подтверждена"


def test_cancel_race_does_not_report_success(monkeypatch):
    monkeypatch.setattr(bot.db, "get_payment", AsyncMock(return_value=(100, "login", "pending")))
    monkeypatch.setattr(bot.db, "transition_payment", AsyncMock(return_value=False))
    monkeypatch.setattr(bot.YoomoneyAPI, "is_success_operation", AsyncMock(return_value=True))
    send_order = AsyncMock()
    monkeypatch.setattr(bot, "new_order", send_order)
    request = callback("check_payment:00000000-0000-4000-8000-000000000001")
    asyncio.run(bot.callback_query_handler(request, SimpleNamespace()))
    send_order.assert_not_awaited()
    assert request.answer.await_args.args[0] == "Статус заявки уже изменился"


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({}, True),
        ({"direction": "out"}, False),
        ({"amount": 10.0}, False),
        ({"label": "another"}, False),
        ({"status": "in_progress"}, False),
        ({"amount": None}, False),
    ],
)
def test_provider_checks_label_direction_amount_and_status(monkeypatch, changes, expected):
    operation = SimpleNamespace(label="payment", status="success", direction="in", amount=102.58)
    for name, value in changes.items():
        setattr(operation, name, value)
    client = SimpleNamespace(
        operation_history=AsyncMock(return_value=SimpleNamespace(operations=[operation]))
    )
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(payment, "AsyncClient", lambda **_: context)
    assert (
        asyncio.run(payment.YoomoneyAPI().is_success_operation("payment", Decimal("102.58")))
        is expected
    )


def test_nontext_amount_is_rejected_without_changing_state():
    message = SimpleNamespace(text=None, answer=AsyncMock())
    state = SimpleNamespace(update_data=AsyncMock())
    asyncio.run(bot.process_amount(message, state))
    state.update_data.assert_not_awaited()
