import os
import secrets


# настройки только для изолированных тестов, внешние запросы не выполняются
os.environ.update(
    {
        "PG_DSN": "postgresql://localhost/paymentscloud_test",
        "REDIS_URL": "redis://localhost:6379/15",
        "TOKEN": f"123456:{secrets.token_urlsafe(32)}",
        "WEBHOOK_SECRET": secrets.token_urlsafe(32),
        "BASE_WEBHOOK_URL": "https://example.invalid",
        "YOOMONEY_TOKEN": secrets.token_urlsafe(32),
        "YOOMONEY_RECEIVER": "123456",
        "SUPPORT_URL": "https://example.invalid/support",
    }
)
