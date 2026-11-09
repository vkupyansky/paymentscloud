import asyncio
import json
import uuid
from decimal import Decimal, ROUND_HALF_UP
from html import escape

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from httpx import HTTPError
from yoomoney.exceptions import YooMoneyError

import config
import db
import keyboards
import messages
from middlewares import Manage, Throttling
from payment import YoomoneyAPI

router = Router()
throttling = Throttling()
router.message.middleware(Manage())
router.message.middleware(throttling)
router.callback_query.middleware(Manage())
router.callback_query.middleware(throttling)


class PaymentStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_login = State()
    waiting_for_confirmation = State()


def calculate(target_amount: int) -> dict[str, Decimal]:
    amount = Decimal(target_amount)
    leftover = (1 - config.AGGREGATOR_RATE) * (1 - config.SERVICE_RATE)
    payment = (amount / leftover).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    aggregator = (payment * config.AGGREGATOR_RATE).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    after_aggregator = payment - aggregator
    service = (after_aggregator * config.SERVICE_RATE).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    after_service = after_aggregator - service
    steam = (after_service * config.STEAM_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {
        "total_rate_percent": ((1 - leftover * (1 - config.STEAM_RATE)) * 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ),
        "total_payment": payment,
        "aggregator_fee": aggregator,
        "after_aggregator": after_aggregator,
        "service_fee": service,
        "after_service": after_service,
        "steam_fee": steam,
        "after_steam": (after_service - steam).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
    }


async def safe_edit_text(message, text, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in error.message:
            raise


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    is_admin = await db.check_user_admin_status(message.from_user.id)
    await message.answer(
        messages.WELCOME_TEXT.format(name=escape(message.from_user.full_name)),
        reply_markup=keyboards.main_menu(is_admin),
    )


@router.message(PaymentStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isascii() or not message.text.isdigit():
        await message.answer(messages.INVALID_AMOUNT_TEXT)
        return
    if (
        len(message.text) > 5
        or not config.MINIMUM_AMOUNT <= int(message.text) <= config.MAXIMUM_AMOUNT
    ):
        await message.answer(
            messages.AMOUNT_OUT_OF_RANGE_TEXT.format(
                minimum_amount=config.MINIMUM_AMOUNT, maximum_amount=config.MAXIMUM_AMOUNT
            )
        )
        return
    await state.update_data(amount=int(message.text))
    await state.set_state(PaymentStates.waiting_for_login)
    await message.answer(messages.ENTER_STEAM_LOGIN_TEXT)


@router.message(PaymentStates.waiting_for_login)
async def process_login(message: Message, state: FSMContext) -> None:
    login = (message.text or "").strip()
    if not login or len(login) > 255:
        await message.answer(messages.LOGIN_EMPTY)
        return
    data = await state.get_data()
    if "amount" not in data:
        await state.clear()
        await message.answer(messages.DATA_MISSING_MESSAGE)
        return
    await state.update_data(steam_login=login)
    result = calculate(data["amount"])
    await message.answer(
        messages.SUMMARY_MESSAGE.format(
            amount=data["amount"],
            steam_login=escape(login),
            total_payment=result["total_payment"],
            after_steam_fee=result["after_steam"],
        ),
        reply_markup=keyboards.apply(),
    )
    await state.set_state(PaymentStates.waiting_for_confirmation)


@router.message()
async def echo_handler(message: Message, state: FSMContext) -> None:
    if await state.get_state() == PaymentStates.waiting_for_confirmation.state:
        await message.answer(messages.USE_BUTTONS_MESSAGE)
    elif message.text == "💳 Пополнить Steam":
        await message.answer(
            messages.POPUP_STEAM_TEXT.format(
                minimum_amount=config.MINIMUM_AMOUNT,
                maximum_amount=config.MAXIMUM_AMOUNT,
                total_fee=calculate(config.MINIMUM_AMOUNT)["total_rate_percent"],
            ),
            reply_markup=keyboards.payment_options(),
        )
    elif message.text == "❓ Ответы на вопросы":
        await message.answer(messages.ANSWERS_TEXT, reply_markup=keyboards.answers())
    elif message.text == "🆘 Поддержка":
        await message.answer(messages.SUPPORT_MESSAGE, reply_markup=keyboards.contact_support())
    elif message.text == "⚙️ Администрирование" and await db.check_user_admin_status(
        message.from_user.id
    ):
        await message.answer(messages.ADMIN_PANEL_PROMPT, reply_markup=keyboards.admin_panel())


@router.callback_query()
async def callback_query_handler(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    data = callback.data or ""
    if not isinstance(callback.message, Message) or callback.message.chat.type != "private":
        await callback.answer("Откройте личный чат с ботом", show_alert=True)
        return
    if data in {"admin_statistics", "back_to_admin_panel"} or data.startswith("order_apply:"):
        if not await db.check_user_admin_status(user_id):
            await callback.answer("Доступ запрещён", show_alert=True)
            return
    if data == "hidden":
        await callback.message.delete()
    elif data == "back_to_admin_panel":
        await safe_edit_text(
            callback.message, messages.ADMIN_PANEL_PROMPT, reply_markup=keyboards.admin_panel()
        )
    elif data == "admin_statistics":
        stats = await db.get_user_statistics()
        result = calculate(await db.get_amount_payment())
        await safe_edit_text(
            callback.message,
            messages.ADMIN_STATISTICS_MESSAGE.format(
                total_users=stats[0],
                total_blocked_users=stats[1],
                active_24h=stats[2],
                active_7d=stats[3],
                active_30d=stats[4],
                **result,
            ),
            reply_markup=keyboards.admin_statistics(),
        )
    elif data == "initiate_payment":
        if not await throttling.storage.redis.set(
            f"payment_cooldown:{user_id}", "1", nx=True, ex=config.PAYMENT_COOLDOWN
        ):
            await callback.answer("Подождите минуту перед новой заявкой", show_alert=True)
            return
        await state.clear()
        await state.set_state(PaymentStates.waiting_for_amount)
        await safe_edit_text(
            callback.message,
            messages.INITIATE_PAYMENT_TEXT.format(
                minimum_amount=config.MINIMUM_AMOUNT, maximum_amount=config.MAXIMUM_AMOUNT
            ),
        )
    elif data in {"change_payment", "cancel_payment_pre", "confirm_payment"}:
        if await state.get_state() != PaymentStates.waiting_for_confirmation.state:
            await callback.answer(messages.DATA_MISSING_MESSAGE, show_alert=True)
            return
        if data == "cancel_payment_pre":
            await state.clear()
            await safe_edit_text(callback.message, messages.CANCEL_PAYMENT_MESSAGE)
        elif data == "change_payment":
            await state.set_state(PaymentStates.waiting_for_amount)
            await safe_edit_text(
                callback.message,
                messages.INITIATE_PAYMENT_TEXT.format(
                    minimum_amount=config.MINIMUM_AMOUNT, maximum_amount=config.MAXIMUM_AMOUNT
                ),
            )
        else:
            values = await state.get_data()
            if "amount" not in values or "steam_login" not in values:
                await callback.answer(messages.DATA_MISSING_MESSAGE, show_alert=True)
                return
            payment_id = values.get("payment_id") or str(uuid.uuid4())
            await state.update_data(payment_id=payment_id)
            try:
                urls = await asyncio.to_thread(
                    YoomoneyAPI().create_quickpay_url,
                    calculate(values["amount"])["total_payment"],
                    payment_id,
                )
            except HTTPError, YooMoneyError, TimeoutError:
                await callback.answer(messages.PAYMENT_CONNECTION_ERROR, show_alert=True)
                return
            await db.create_payment(
                user_id, values["amount"], values["steam_login"], payment_id, json.dumps(urls)
            )
            await state.clear()
            await safe_edit_text(
                callback.message,
                messages.PAYMENT_MESSAGE,
                reply_markup=keyboards.payment_actions(urls["redirected_url"], payment_id),
            )
    elif data.startswith(("check_payment:", "cancel_payment:", "order_apply:")):
        action, raw_id = data.split(":", 1)
        try:
            payment_id = str(uuid.UUID(raw_id))
        except ValueError:
            await callback.answer("Некорректная заявка", show_alert=True)
            return
        payment = await db.get_payment(payment_id, None if action == "order_apply" else user_id)
        if payment is None:
            await callback.answer("Заявка недоступна", show_alert=True)
            return
        amount, steam, status = payment
        if action == "order_apply":
            if status != "success" or not await db.picked_payment(user_id, payment_id):
                await callback.answer("Заявка уже принята или не оплачена", show_alert=True)
                return
            await safe_edit_text(
                callback.message,
                messages.ORDER_ACCEPTED_TEXT.format(
                    amount=amount, steam=escape(steam), payment_uuid=payment_id, **calculate(amount)
                ),
            )
        elif action == "cancel_payment":
            if not await db.transition_payment(payment_id, user_id, "cancel"):
                await callback.answer("Статус заявки уже изменился", show_alert=True)
                return
            await safe_edit_text(callback.message, messages.CANCEL_PAYMENT_MESSAGE)
        elif status == "success":
            await callback.answer("Оплата уже подтверждена", show_alert=True)
            return
        elif status != "pending":
            await callback.answer(
                "Заявка отменена. По переводу обратитесь в поддержку", show_alert=True
            )
            return
        else:
            try:
                paid = await YoomoneyAPI().is_success_operation(
                    payment_id, calculate(amount)["after_aggregator"]
                )
            except HTTPError, YooMoneyError, TimeoutError:
                await callback.answer(messages.PAYMENT_CONNECTION_ERROR, show_alert=True)
                return
            if not paid:
                await callback.answer(messages.PAYMENT_NOT_FOUND_MESSAGE, show_alert=True)
                return
            if not await db.transition_payment(payment_id, user_id, "success"):
                await callback.answer("Статус заявки уже изменился", show_alert=True)
                return
            await new_order(user_id, amount, steam, payment_id)
            await safe_edit_text(
                callback.message,
                messages.CONFIRM_PAYMENT_MESSAGE.format(
                    price=amount, steam_login=escape(steam), uuid=payment_id
                ),
            )
    await callback.answer()


async def new_order(user_id, amount, steam, payment_uuid):
    for admin in await db.get_admins():
        await config.BOT.send_message(
            chat_id=admin,
            text=messages.NEW_ORDER_TEXT.format(
                user_id=user_id,
                amount=amount,
                steam=escape(steam),
                payment_uuid=payment_uuid,
                **calculate(amount),
            ),
            reply_markup=keyboards.order(payment_uuid),
        )
