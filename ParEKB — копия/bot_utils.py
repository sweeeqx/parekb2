import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)


BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv("BOT_TOKEN", "8563043264:AAELXPwWhlwHQqy0FFTk55jpuu7t7JzlGug")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1140430618"))
MANAGER = os.getenv("MANAGER", "@sweeeqx")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/+U82CidH7uzA2ZWYx")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003834386683"))

CATALOG_FILE = BASE_DIR / "catalog.json"
USERS_FILE = BASE_DIR / "users.json"
EMOJI_FILE = BASE_DIR / "emoji.json"
START_PHOTO_FILE = BASE_DIR / "photo_2026-07-23_14-37-18.jpg"
START_PHOTO = os.getenv("START_PHOTO")
ASSORTMENT_PHOTO_FILE = BASE_DIR / "assortiment-main-parekb-secondary.png"
ASSORTMENT_PHOTO = os.getenv("ASSORTMENT_PHOTO")


def load_json(file: Path) -> dict[str, Any]:
    if not file.exists():
        return {}

    try:
        with file.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def save_json(file: Path, data: dict[str, Any]) -> None:
    with file.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=4, ensure_ascii=False)


def manager_url(text: str | None = None) -> str:
    url = f"https://t.me/{MANAGER.removeprefix('@')}"
    if text is None:
        return url
    return f"{url}?text={quote(text)}"


def start_photo() -> str | FSInputFile | None:
    if START_PHOTO:
        return START_PHOTO
    if START_PHOTO_FILE.is_file():
        return FSInputFile(START_PHOTO_FILE)
    return None


def assortment_photo() -> str | FSInputFile | None:
    if ASSORTMENT_PHOTO:
        return ASSORTMENT_PHOTO
    if ASSORTMENT_PHOTO_FILE.is_file():
        return FSInputFile(ASSORTMENT_PHOTO_FILE)
    return None


def premium_emoji_id(name: str) -> str | None:
    emoji_id = str(load_json(EMOJI_FILE).get(name, "")).strip()
    return emoji_id if emoji_id.isdigit() else None


def premium_emoji(name: str, fallback: str) -> str:
    emoji_id = premium_emoji_id(name)
    if emoji_id is None:
        return fallback

    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def stored_emoji_id(value: Any) -> str | None:
    emoji_id = str(value or "").strip()
    return emoji_id if emoji_id.isdigit() else None


def first_product(
    products_by_brand: dict[str, Any],
    preferred_emoji_field: str | None = None,
) -> dict[str, Any] | None:
    fallback = None
    for products in products_by_brand.values():
        for product in products.values():
            if fallback is None:
                fallback = product
            if (
                preferred_emoji_field is not None
                and stored_emoji_id(product.get(preferred_emoji_field))
            ):
                return product
    return fallback


def preferred_product(
    products: dict[str, Any],
    emoji_field: str,
) -> dict[str, Any]:
    fallback = next(iter(products.values()), {})
    return next(
        (
            product
            for product in products.values()
            if stored_emoji_id(product.get(emoji_field))
        ),
        fallback,
    )


def emoji_button(
    label: str,
    emoji_name: str,
    fallback: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
) -> InlineKeyboardButton:
    emoji_id = premium_emoji_id(emoji_name)
    text = label if emoji_id else f"{fallback} {label}"

    return InlineKeyboardButton(
        text=text,
        icon_custom_emoji_id=emoji_id,
        callback_data=callback_data,
        url=url,
    )


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                emoji_button(
                    "Ассортимент",
                    "shop",
                    "🛍",
                    callback_data="menu_cat",
                )
            ],
            [
                emoji_button(
                    "Менеджер",
                    "manager",
                    "👤",
                    url=manager_url(),
                )
            ],
            [
                emoji_button(
                    "Канал",
                    "channel",
                    "📢",
                    url=CHANNEL_LINK,
                )
            ],
        ]
    )


def back(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                emoji_button(
                    "Назад",
                    "back",
                    "⬅️",
                    callback_data=callback_data,
                )
            ]
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [emoji_button("Добавить", "add", "➕", callback_data="add")],
            [emoji_button("Редактировать", "edit", "✏️", callback_data="edit")],
            [emoji_button("Удалить", "delete", "❌", callback_data="del")],
            [emoji_button("Новость", "news", "📢", callback_data="news")],
            [
                emoji_button(
                    "Пользователи",
                    "users",
                    "👥",
                    callback_data="users_count",
                )
            ],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                emoji_button(
                    "Отмена",
                    "cancel",
                    "✖️",
                    callback_data="cancel_action",
                )
            ]
        ]
    )


def news_photo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                emoji_button(
                    "Без фото",
                    "skip",
                    "⏭️",
                    callback_data="news_without_photo",
                )
            ],
            [
                emoji_button(
                    "Отмена",
                    "cancel",
                    "✖️",
                    callback_data="cancel_action",
                )
            ],
        ]
    )


def assortment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                emoji_button(
                    "Ассортимент",
                    "shop",
                    "🛍",
                    callback_data="menu_cat",
                )
            ]
        ]
    )


def subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                emoji_button(
                    "Подписаться на канал",
                    "channel",
                    "📢",
                    url=CHANNEL_LINK,
                )
            ],
            [
                emoji_button(
                    "Проверить подписку",
                    "success",
                    "✅",
                    callback_data="check_subscription",
                )
            ],
        ]
    )


def buy_keyboard(
    back_callback: str | None = None,
    order_text: str | None = None,
) -> InlineKeyboardMarkup:
    buy_button = emoji_button(
        "Купить",
        "cart",
        "🛒",
        url=manager_url(order_text),
    )
    row = [buy_button]

    if back_callback is not None:
        row.append(
            emoji_button(
                "Назад",
                "back",
                "⬅️",
                callback_data=back_callback,
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[row]
    )


def categories_keyboard(catalog: dict[str, Any]) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=str(
                    (
                        first_product(brands, "category_emoji_id")
                        or {}
                    ).get(
                        "category_button_text",
                        category,
                    )
                ),
                icon_custom_emoji_id=stored_emoji_id(
                    (
                        first_product(brands, "category_emoji_id")
                        or {}
                    ).get("category_emoji_id")
                ),
                callback_data=f"cat:{category}",
            )
        ]
        for category, brands in catalog.items()
    ]
    keyboard.append(
        [
            emoji_button(
                "Назад",
                "back",
                "⬅️",
                callback_data="back_main",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def brands_keyboard(
    category: str,
    brands: dict[str, Any],
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=str(
                    preferred_product(
                        products,
                        "brand_emoji_id",
                    ).get(
                        "brand_button_text",
                        brand,
                    )
                ),
                icon_custom_emoji_id=stored_emoji_id(
                    preferred_product(
                        products,
                        "brand_emoji_id",
                    ).get(
                        "brand_emoji_id"
                    )
                ),
                callback_data=f"brand:{category}:{brand}",
            )
        ]
        for brand, products in brands.items()
    ]
    keyboard.append(
        [
            emoji_button(
                "Назад",
                "back",
                "⬅️",
                callback_data="menu_cat",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def catalog_products_keyboard(
    products: dict[str, Any],
    back_callback: str,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=str(
                    product.get("name_button_text")
                    or product.get("name", "Без названия")
                ),
                icon_custom_emoji_id=stored_emoji_id(
                    product.get("name_emoji_id")
                ),
                callback_data=f"view:{product_id}",
            )
        ]
        for product_id, product in products.items()
    ]
    keyboard.append(
        [
            emoji_button(
                "Назад",
                "back",
                "⬅️",
                callback_data=back_callback,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def product_choice_keyboard(
    catalog: dict[str, Any],
    action: str,
) -> InlineKeyboardMarkup | None:
    keyboard = [
        [
            InlineKeyboardButton(
                text=str(
                    product.get("name_button_text")
                    or product.get("name", "Без названия")
                ),
                icon_custom_emoji_id=stored_emoji_id(
                    product.get("name_emoji_id")
                ),
                callback_data=f"{action}:{product_id}",
            )
        ]
        for brands in catalog.values()
        for products in brands.values()
        for product_id, product in products.items()
    ]
    if not keyboard:
        return None

    keyboard.append(
        [
            emoji_button(
                "Отмена",
                "cancel",
                "✖️",
                callback_data="cancel_action",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def edit_fields_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                emoji_button(
                    "Описание",
                    "description",
                    "📝",
                    callback_data="f:desc",
                )
            ],
            [
                emoji_button(
                    "Цена",
                    "money",
                    "💰",
                    callback_data="f:price",
                )
            ],
            [
                emoji_button(
                    "Отмена",
                    "cancel",
                    "✖️",
                    callback_data="cancel_action",
                )
            ],
        ]
    )


async def edit_menu_message(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    photo: str | FSInputFile | None = None,
) -> None:
    try:
        if message.photo:
            if photo is not None:
                await message.edit_media(
                    media=InputMediaPhoto(
                        media=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML,
                    ),
                    reply_markup=reply_markup,
                )
                return

            await message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            return

        if photo is not None:
            await message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            return

        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest as error:
        if "message is not modified" in str(error).lower():
            return
        raise


async def answer_admin_callback(call: CallbackQuery) -> bool:
    if call.from_user.id == ADMIN_ID:
        await call.answer()
        return True

    await call.answer("Недостаточно прав", show_alert=True)
    return False
