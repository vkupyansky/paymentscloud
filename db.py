import psycopg
from config import PG_DSN


async def get_db_connection():
    return await psycopg.AsyncConnection.connect(PG_DSN, connect_timeout=10)


async def initialize_database():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS public.paymentscloud_users (
                    unique_id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    latest_activity TIMESTAMP,
                    user_id BIGINT UNIQUE,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    admin BOOLEAN DEFAULT false,
                    blocked BOOLEAN DEFAULT false,
                    block_reason VARCHAR(255)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS public.paymentscloud_payments (
                    unique_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES public.paymentscloud_users(user_id),
                    amount INT,
                    steam VARCHAR(255),
                    picked BIGINT REFERENCES public.paymentscloud_users(user_id),
                    payment_uuid VARCHAR(255) UNIQUE,
                    status VARCHAR(255),
                    quickpay_urls JSONB,
                    datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)


async def create_payment(user_id, amount, steam, payment_uuid, quickpay_urls):
    async with await get_db_connection() as conn:
        await conn.execute(
            "INSERT INTO public.paymentscloud_payments "
            "(user_id, amount, steam, payment_uuid, status, quickpay_urls) "
            "VALUES (%s, %s, %s, %s, 'pending', %s) ON CONFLICT (payment_uuid) DO NOTHING",
            (user_id, amount, steam, payment_uuid, quickpay_urls),
        )


async def get_payment(payment_uuid, user_id):
    async with await get_db_connection() as conn:
        if user_id is None:
            result = await conn.execute(
                "SELECT amount, steam, status FROM public.paymentscloud_payments WHERE payment_uuid = %s",
                (payment_uuid,),
            )
        else:
            result = await conn.execute(
                "SELECT amount, steam, status FROM public.paymentscloud_payments "
                "WHERE payment_uuid = %s AND user_id = %s",
                (payment_uuid, user_id),
            )
        return await result.fetchone()


async def transition_payment(payment_uuid, user_id, status):
    if status not in {"success", "cancel"}:
        raise ValueError("Недопустимый статус платежа")
    async with await get_db_connection() as conn:
        result = await conn.execute(
            "UPDATE public.paymentscloud_payments SET status = %s "
            "WHERE payment_uuid = %s AND user_id = %s AND status = 'pending' RETURNING payment_uuid",
            (status, payment_uuid, user_id),
        )
        return await result.fetchone() is not None


async def picked_payment(picked, payment_uuid):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE public.paymentscloud_payments
                SET picked = %s
                WHERE payment_uuid = %s AND picked IS NULL AND status = 'success'
            """,
                (picked, payment_uuid),
            )
            return cur.rowcount > 0


async def get_amount_payment():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT SUM(amount) FROM public.paymentscloud_payments WHERE status = 'success'"
            )
            row = await cur.fetchone()
            return row[0] if row and row[0] is not None else 0


async def upsert_user(user_id, username, first_name, last_name):
    async with await get_db_connection() as conn:
        await conn.execute(
            "INSERT INTO public.paymentscloud_users "
            "(user_id, username, first_name, last_name, latest_activity) VALUES (%s, %s, %s, %s, NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username, "
            "first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name, latest_activity = NOW()",
            (user_id, username, first_name, last_name),
        )


async def get_admins():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT user_id FROM public.paymentscloud_users WHERE admin = TRUE")
            rows = await cur.fetchall()
            return [row[0] for row in rows]


async def check_user_admin_status(user_id):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT admin FROM public.paymentscloud_users WHERE user_id = %s", (user_id,)
            )
            row = await cur.fetchone()
            return row[0] if row else False


async def check_if_user_blocked(user_id):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT blocked FROM public.paymentscloud_users WHERE user_id = %s", (user_id,)
            )
            row = await cur.fetchone()
            return row[0] if row else False


async def block_user_account(user_id, reason):
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE public.paymentscloud_users
                SET blocked = true, block_reason = %s
                WHERE user_id = %s
            """,
                (reason, user_id),
            )


async def get_user_statistics():
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    COUNT(*) AS total_users,
                    COUNT(*) FILTER (WHERE blocked) AS total_blocked_users,
                    COUNT(*) FILTER (WHERE latest_activity >= NOW() - INTERVAL '1 day') AS active_24h,
                    COUNT(*) FILTER (WHERE latest_activity >= NOW() - INTERVAL '7 days') AS active_7d,
                    COUNT(*) FILTER (WHERE latest_activity >= NOW() - INTERVAL '30 days') AS active_30d
                FROM public.paymentscloud_users
            """)
            row = await cur.fetchone()
            return row[0], row[1], row[2], row[3], row[4]
