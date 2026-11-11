[![Русский](https://img.shields.io/badge/%D0%A0%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-181717?style=for-the-badge)](README.ru.md)

# PaymentsCloud

A Telegram bot for Steam wallet top-up requests. Users enter an amount and Steam login, pay through YooMoney, and check the transfer status. An administrator receives the paid order and claims it for processing. Steam top-ups are fulfilled manually.

## Features

- Requests for RUB 100–14,999 with fee calculation.
- Bank card payments through YooMoney, with checks for the transfer owner, label, amount, direction, and status.
- PostgreSQL storage for users and requests, with duplicate confirmation protection.
- Administrator statistics and order claiming by a single operator.
- Support, rate limiting, and user blocking through Redis.

## Installation and startup

Requires Python 3.14, [uv](https://docs.astral.sh/uv/), PostgreSQL, Redis, and a public HTTPS address for the Telegram webhook. Exact versions are pinned in [.python-version](.python-version) and [uv.lock](uv.lock).

```bash
uv sync --frozen
uv run --frozen python init_env.py
```

Fill in the generated `.env` using an editor. `init_env.py` generates `WEBHOOK_SECRET` once, sets permissions to `0600`, and preserves an existing file on subsequent runs. The remaining values come from external services. All settings in [.env.example](.env.example) are required:

| Setting             | Purpose                                               |
| ------------------- | ----------------------------------------------------- |
| `TOKEN`             | Telegram bot token                                    |
| `PG_DSN`            | PostgreSQL DSN for a dedicated project database        |
| `REDIS_URL`         | Address of a dedicated Redis database                 |
| `WEBHOOK_SECRET`    | Secret for validating the Telegram webhook            |
| `BASE_WEBHOOK_URL`  | Public HTTPS origin without a path                    |
| `YOOMONEY_TOKEN`    | Wallet token with `operation-history` permission       |
| `YOOMONEY_RECEIVER` | Wallet number for incoming transfers                  |
| `SUPPORT_URL`       | HTTPS support link                                    |

Use TLS with certificate verification for remote PostgreSQL and Redis connections. Keep secrets out of commands and terminal history.

```bash
uv run --frozen --env-file .env python main.py
```

The application listens on `127.0.0.1:8083`. The reverse proxy must forward HTTPS requests from `/webhook` to this address. Startup creates missing tables, checks Redis, and registers the webhook. Existing tables and requests are preserved.

## Usage

After the first `/start`, assign an administrator through a trusted SQL client, passing their Telegram ID as a query parameter:

```sql
UPDATE public.paymentscloud_users SET admin = TRUE WHERE user_id = :user_id;
```

The user creates a request, pays for it, and starts the transfer check. The administrator claims the paid order and manually tops up the Steam wallet.

## Checks

```bash
uv run --frozen python check.py
uv run --frozen pip-audit
gitleaks git --redact
```

`check.py` runs formatting checks, static analysis, and isolated regression tests with warnings treated as errors. Tests do not access Telegram, YooMoney, or production databases.

To check concurrency and data preservation, prepare a clean local PostgreSQL instance with a `paymentscloud_test` database. Set its DSN as `PAYMENTSCLOUD_TEST_DSN` in a separate `.env.integration` file:

```bash
uv run --frozen --env-file .env.integration python -m pytest -W error tests/integration_db.py
```

The integration test changes only the dedicated database and accepts only `localhost` or `127.0.0.1`. Concurrency, idempotency, status transitions, and record preservation on repeated initialization have been tested on PostgreSQL 16.

## Limitations

Real transfers, the webhook, and Redis connectivity require testing with your own credentials. Before accepting real payments, notification delivery recovery after failures and reconciliation of unfinished transfers still need to be implemented: payments received after local cancellation are handled through support, and a failure after a successful status update may leave the administrator without a notification.

The input form is held in memory and resets on restart. There are no automatic Steam top-ups or refunds. Card fee calculation is based on the [YooMoney documentation](https://yoomoney.ru/docs/payment-buttons/using-api/forms); verify integration requirements and rates before use.
