from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from config import SUPPORT_URL


def main_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="💳 Пополнить Steam"), KeyboardButton(text="❓ Ответы на вопросы")],
        [KeyboardButton(text="🆘 Поддержка")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Администрирование")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=False)


def answers() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✖️ Закрыть", callback_data="hidden")]]
    )


def contact_support() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Связаться с поддержкой", url=SUPPORT_URL)],
            [InlineKeyboardButton(text="✖️ Закрыть", callback_data="hidden")],
        ]
    )


def admin_statistics() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Назад в админ-панель", callback_data="back_to_admin_panel"
                )
            ]
        ]
    )


def admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_statistics")],
            [InlineKeyboardButton(text="✖️ Закрыть", callback_data="hidden")],
        ]
    )


def payment_options() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Банковская карта [РФ]", callback_data="initiate_payment"
                )
            ]
        ]
    )


def apply() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_payment")],
            [InlineKeyboardButton(text="🔄 Изменить", callback_data="change_payment")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment_pre")],
        ]
    )


def payment_actions(quickpay_url: str = None, payment_uuid: str = None) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🛒 Перейти к оплате", url=quickpay_url)],
        [
            InlineKeyboardButton(
                text="🔍 Проверить статус оплаты", callback_data=f"check_payment:{payment_uuid}"
            )
        ],
        [
            InlineKeyboardButton(
                text="✖️ Отменить оплату", callback_data=f"cancel_payment:{payment_uuid}"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order(payment_uuid: str = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять в работу", callback_data=f"order_apply:{payment_uuid}"
                )
            ],
        ]
    )
