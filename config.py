"""Настройки из переменных окружения, без секретов в исходниках."""

import os
import re
from decimal import Decimal
from urllib.parse import urlsplit

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


def required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"Не задана обязательная переменная {name}")
    return value.strip()


def url(name: str, schemes: set[str]) -> str:
    value = required(name)
    parsed = urlsplit(value)
    if parsed.scheme not in schemes or not parsed.hostname:
        raise ValueError(f"Некорректный адрес в {name}")
    return value


PG_DSN = url("PG_DSN", {"postgresql", "postgres"})
REDIS_URL = url("REDIS_URL", {"redis", "rediss"})
TOKEN = required("TOKEN")
WEBHOOK_SECRET = required("WEBHOOK_SECRET")
if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", WEBHOOK_SECRET):
    raise ValueError("WEBHOOK_SECRET: нужны 32–256 символов A-Z, a-z, 0-9, _ или -")
BASE_WEBHOOK_URL = url("BASE_WEBHOOK_URL", {"https"}).rstrip("/")
if urlsplit(BASE_WEBHOOK_URL).path or urlsplit(BASE_WEBHOOK_URL).query:
    raise ValueError("BASE_WEBHOOK_URL должен содержать только HTTPS origin")
WEBHOOK_PATH = "/webhook"
WEB_SERVER_HOST = "127.0.0.1"
WEB_SERVER_PORT = 8083
YOOMONEY_TOKEN = required("YOOMONEY_TOKEN")
YOOMONEY_RECEIVER = required("YOOMONEY_RECEIVER")
if not YOOMONEY_RECEIVER.isascii() or not YOOMONEY_RECEIVER.isdigit():
    raise ValueError("YOOMONEY_RECEIVER должен содержать номер кошелька")
SUPPORT_URL = url("SUPPORT_URL", {"https"})

MINIMUM_AMOUNT = 100
MAXIMUM_AMOUNT = 14999
PAYMENT_COOLDOWN = 60
AGGREGATOR_RATE = Decimal("0.03")
SERVICE_RATE = Decimal("0.0251")
STEAM_RATE = Decimal("0.08")

BOT = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
