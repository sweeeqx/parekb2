import asyncio
import uuid
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    Message,
    MessageEntity,
)

from bot_utils import (
    ADMIN_ID,
    CATALOG_FILE,
    TOKEN,
    USERS_FILE,
    admin_menu,
    answer_admin_callback,
    assortment_keyboard,
    assortment_photo,
    back,
    brands_keyboard,
    buy_keyboard,
    cancel_keyboard,
    catalog_products_keyboard,
    categories_keyboard,
    edit_fields_keyboard,
    edit_menu_message,
    load_json,
    main_menu,
    news_photo_keyboard,
    premium_emoji,
    product_choice_keyboard,
    save_json,
    start_photo,
)
from subscription_middleware import SubscriptionMiddleware

router = Router()
subscription_guard = SubscriptionMiddleware()
router.message.outer_middleware(subscription_guard)
router.callback_query.outer_middleware(subscription_guard)


# FSM
class Add(StatesGroup):
    cat = State()
    brand = State()
    name = State()
    desc = State()
    price = State()
    photo = State()


class Edit(StatesGroup):
    field = State()


class News(StatesGroup):
    text = State()
    photo = State()


def button_text_and_emoji(msg: Message) -> tuple[str, str | None]:
    custom_emoji_entities = [
        entity
        for entity in (msg.entities or [])
        if entity.custom_emoji_id
    ]
    if not custom_emoji_entities:
        return msg.text or "", None

    text_utf16 = bytearray((msg.text or "").encode("utf-16-le"))
    for entity in sorted(
        custom_emoji_entities,
        key=lambda item: item.offset,
        reverse=True,
    ):
        start = entity.offset * 2
        end = (entity.offset + entity.length) * 2
        del text_utf16[start:end]

    button_text = bytes(text_utf16).decode("utf-16-le").strip()
    return (
        button_text or "Без названия",
        custom_emoji_entities[0].custom_emoji_id,
    )


# START
@router.message(CommandStart())
async def start(msg: Message) -> None:
    if msg.from_user is not None:
        users = load_json(USERS_FILE)
        users[str(msg.from_user.id)] = True
        save_json(USERS_FILE, users)

    text = f"{premium_emoji('fire', '🔥')} <b>Добро пожаловать</b>"
    photo = start_photo()

    if photo is not None:
        await msg.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=main_menu(),
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.answer(
        text,
        reply_markup=main_menu(),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await msg.answer("Нет активного действия.")
        return

    await state.clear()
    await msg.answer(
        "Действие отменено.",
        reply_markup=(
            admin_menu()
            if msg.from_user is not None and msg.from_user.id == ADMIN_ID
            else None
        ),
    )


@router.callback_query(F.data == "cancel_action")
async def cancel_action(call: CallbackQuery, state: FSMContext) -> None:
    if not await answer_admin_callback(call):
        return

    await state.clear()
    await edit_menu_message(
        call.message,
        text=f"{premium_emoji('success', '✅')} Действие отменено",
        reply_markup=admin_menu(),
    )


# КАТЕГОРИИ
@router.callback_query(F.data == "menu_cat")
async def categories(call: CallbackQuery) -> None:
    await call.answer()
    catalog = load_json(CATALOG_FILE)

    if not catalog:
        await edit_menu_message(
            call.message,
            text=f"{premium_emoji('error', '❌')} <b>Каталог пуст</b>",
            reply_markup=back("back_main"),
            photo=assortment_photo(),
        )
        return

    await edit_menu_message(
        call.message,
        text=f"{premium_emoji('package', '📦')} <b>Категории</b>",
        reply_markup=categories_keyboard(catalog),
        photo=assortment_photo(),
    )


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery) -> None:
    await call.answer()
    await edit_menu_message(
        call.message,
        text=f"{premium_emoji('home', '🏠')} <b>Главное меню</b>",
        reply_markup=main_menu(),
        photo=start_photo(),
    )


# БРЕНДЫ
@router.callback_query(F.data.startswith("cat:"))
async def brands(call: CallbackQuery) -> None:
    await call.answer()
    category = call.data.split(":", maxsplit=1)[1]
    catalog = load_json(CATALOG_FILE)
    category_brands = catalog.get(category, {})
    sample_product = next(
        (
            product
            for products in category_brands.values()
            for product in products.values()
        ),
        {},
    )
    category_html = sample_product.get("category_html") or escape(category)

    await edit_menu_message(
        call.message,
        text=f"{premium_emoji('package', '📦')} {category_html}",
        reply_markup=brands_keyboard(category, category_brands),
        photo=assortment_photo(),
    )


# ТОВАРЫ
@router.callback_query(F.data.startswith("brand:"))
async def products(call: CallbackQuery) -> None:
    await call.answer()
    _, category, brand = call.data.split(":", maxsplit=2)

    catalog = load_json(CATALOG_FILE)
    items = catalog.get(category, {}).get(brand, {})

    if not items:
        await edit_menu_message(
            call.message,
            text=f"{premium_emoji('error', '❌')} Нет товаров",
            reply_markup=back(f"cat:{category}"),
            photo=assortment_photo(),
        )
        return

    sample_product = next(iter(items.values()))
    brand_html = sample_product.get("brand_html")
    if not brand_html:
        brand_html = f"<b>{escape(brand)}</b>"
    await edit_menu_message(
        call.message,
        text=(
            f"{premium_emoji('package', '📦')} "
            f"{brand_html}"
        ),
        reply_markup=catalog_products_keyboard(
            items,
            back_callback=f"cat:{category}",
        ),
        photo=assortment_photo(),
    )


@router.callback_query(F.data.startswith("view:"))
async def product_card(call: CallbackQuery) -> None:
    await call.answer()
    product_id = call.data.split(":", maxsplit=1)[1]
    catalog = load_json(CATALOG_FILE)

    selected: tuple[str, str, dict] | None = None
    for category, brands in catalog.items():
        for brand, products in brands.items():
            if product_id in products:
                selected = (category, brand, products[product_id])
                break
        if selected is not None:
            break

    if selected is None:
        await edit_menu_message(
            call.message,
            text=f"{premium_emoji('error', '❌')} Товар не найден",
            reply_markup=back("menu_cat"),
            photo=assortment_photo(),
        )
        return

    category, brand, item = selected
    name = item.get("name_html")
    if not name:
        name = (
            f"<b>{escape(str(item.get('name', 'Без названия')))}</b>"
        )
    description = item.get("desc_html") or escape(
        str(item.get("desc", ""))
    )
    price = item.get("price_html") or escape(
        str(item.get("price", "—"))
    )
    caption = (
        f"{premium_emoji('fire', '🔥')} {name}\n\n"
        f"{description}\n"
        f"{premium_emoji('money', '💰')} "
        f"{price} ₽"
    )
    order_text = (
        "Здравствуйте! Хочу купить товар:\n\n"
        f"Категория: {category}\n"
        f"Бренд: {brand}\n"
        f"Товар: {item.get('name', 'Без названия')}\n"
        f"Цена: {item.get('price', '—')} ₽\n"
        f"ID товара: {product_id}"
    )

    await edit_menu_message(
        call.message,
        text=caption,
        reply_markup=buy_keyboard(
            back_callback=f"brand:{category}:{brand}",
            order_text=order_text,
        ),
        photo=item.get("photo"),
    )


# АДМИНКА
@router.message(Command("admin"))
async def admin(msg: Message) -> None:
    if msg.from_user is None or msg.from_user.id != ADMIN_ID:
        return

    await msg.answer(
        f"{premium_emoji('settings', '⚙️')} Админка",
        reply_markup=admin_menu(),
    )


@router.message(Command("emoji_id"))
async def emoji_id(msg: Message) -> None:
    if msg.from_user is None or msg.from_user.id != ADMIN_ID:
        return

    source = msg.reply_to_message
    if source is None:
        await msg.answer(
            "Ответь командой /emoji_id на сообщение с premium emoji."
        )
        return

    entities = source.entities or source.caption_entities or []
    emoji_ids = list(
        dict.fromkeys(
            entity.custom_emoji_id
            for entity in entities
            if entity.custom_emoji_id
        )
    )

    if not emoji_ids:
        await msg.answer("В сообщении не найдены premium emoji.")
        return

    await msg.answer(
        "ID premium emoji:\n<code>"
        + "</code>\n<code>".join(emoji_ids)
        + "</code>"
    )


@router.callback_query(F.data == "check_subscription")
async def subscription_confirmed(call: CallbackQuery) -> None:
    await call.answer("Подписка подтверждена")

    users = load_json(USERS_FILE)
    users[str(call.from_user.id)] = True
    save_json(USERS_FILE, users)

    await edit_menu_message(
        call.message,
        text=(
            f"{premium_emoji('success', '✅')} "
            f"<b>Подписка подтверждена</b>"
        ),
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "users_count")
async def users_count(call: CallbackQuery) -> None:
    if not await answer_admin_callback(call):
        return

    users = load_json(USERS_FILE)
    await call.message.answer(
        f"{premium_emoji('users', '👥')} "
        f"Пользователей: <b>{len(users)}</b>"
    )


# ДОБАВЛЕНИЕ
@router.callback_query(F.data == "add")
async def add_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await answer_admin_callback(call):
        return

    await state.set_state(Add.cat)
    await call.message.answer(
        "Категория:",
        reply_markup=cancel_keyboard(),
    )


@router.message(Add.cat, F.text)
async def add_cat(msg: Message, state: FSMContext) -> None:
    button_text, emoji_id = button_text_and_emoji(msg)
    await state.update_data(
        cat=msg.text,
        category_html=msg.html_text,
        category_button_text=button_text,
        category_emoji_id=emoji_id,
    )
    await state.set_state(Add.brand)
    await msg.answer(
        "Бренд:",
        reply_markup=cancel_keyboard(),
    )


@router.message(Add.brand, F.text)
async def add_brand(msg: Message, state: FSMContext) -> None:
    button_text, emoji_id = button_text_and_emoji(msg)
    await state.update_data(
        brand=msg.text,
        brand_html=msg.html_text,
        brand_button_text=button_text,
        brand_emoji_id=emoji_id,
    )
    await state.set_state(Add.name)
    await msg.answer(
        "Название:",
        reply_markup=cancel_keyboard(),
    )


@router.message(Add.name, F.text)
async def add_name(msg: Message, state: FSMContext) -> None:
    button_text, emoji_id = button_text_and_emoji(msg)
    await state.update_data(
        name=msg.text,
        name_html=msg.html_text,
        name_button_text=button_text,
        name_emoji_id=emoji_id,
    )
    await state.set_state(Add.desc)
    await msg.answer(
        "Описание:",
        reply_markup=cancel_keyboard(),
    )


@router.message(Add.desc, F.text)
async def add_desc(msg: Message, state: FSMContext) -> None:
    await state.update_data(desc=msg.text, desc_html=msg.html_text)
    await state.set_state(Add.price)
    await msg.answer(
        "Цена:",
        reply_markup=cancel_keyboard(),
    )


@router.message(Add.price, F.text)
async def add_price(msg: Message, state: FSMContext) -> None:
    await state.update_data(
        price=msg.text,
        price_html=msg.html_text,
    )
    await state.set_state(Add.photo)
    await msg.answer(
        "Отправь фото:",
        reply_markup=cancel_keyboard(),
    )


@router.message(Add.photo, F.photo)
async def add_photo(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    catalog = load_json(CATALOG_FILE)

    product_id = uuid.uuid4().hex[:6]
    products = catalog.setdefault(data["cat"], {}).setdefault(data["brand"], {})
    products[product_id] = {
        "name": data["name"],
        "name_html": data["name_html"],
        "name_button_text": data["name_button_text"],
        "name_emoji_id": data["name_emoji_id"],
        "desc": data["desc"],
        "desc_html": data["desc_html"],
        "price": data["price"],
        "price_html": data["price_html"],
        "category_html": data["category_html"],
        "category_button_text": data["category_button_text"],
        "category_emoji_id": data["category_emoji_id"],
        "brand_html": data["brand_html"],
        "brand_button_text": data["brand_button_text"],
        "brand_emoji_id": data["brand_emoji_id"],
        "photo": msg.photo[-1].file_id,
    }

    save_json(CATALOG_FILE, catalog)
    await state.clear()
    await msg.answer(
        f"{premium_emoji('success', '✅')} Товар добавлен",
        reply_markup=admin_menu(),
    )


@router.message(Add.photo)
async def add_photo_invalid(msg: Message) -> None:
    await msg.answer(
        "Нужно отправить именно фотографию.",
        reply_markup=cancel_keyboard(),
    )


# УДАЛЕНИЕ
@router.callback_query(F.data == "del")
async def delete(call: CallbackQuery) -> None:
    if not await answer_admin_callback(call):
        return

    catalog = load_json(CATALOG_FILE)
    keyboard = product_choice_keyboard(catalog, "del")

    if not keyboard:
        await call.message.answer(
            f"{premium_emoji('error', '❌')} Каталог пуст"
        )
        return

    await call.message.answer(
        "Выбери товар:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("del:"))
async def delete_item(call: CallbackQuery) -> None:
    if not await answer_admin_callback(call):
        return

    product_id = call.data.split(":", maxsplit=1)[1]
    catalog = load_json(CATALOG_FILE)
    deleted = False

    for category in list(catalog):
        for brand in list(catalog[category]):
            if product_id not in catalog[category][brand]:
                continue

            del catalog[category][brand][product_id]
            deleted = True

            if not catalog[category][brand]:
                del catalog[category][brand]
            if not catalog[category]:
                del catalog[category]
            break

        if deleted:
            break

    if deleted:
        save_json(CATALOG_FILE, catalog)

    await call.message.delete()
    if deleted:
        text = f"{premium_emoji('success', '✅')} Товар удалён"
    else:
        text = f"{premium_emoji('error', '❌')} Ошибка удаления"
    await call.message.answer(text)


# РЕДАКТИРОВАНИЕ
@router.callback_query(F.data == "edit")
async def edit(call: CallbackQuery) -> None:
    if not await answer_admin_callback(call):
        return

    catalog = load_json(CATALOG_FILE)
    keyboard = product_choice_keyboard(catalog, "edit")

    if not keyboard:
        await call.message.answer(
            f"{premium_emoji('error', '❌')} Каталог пуст"
        )
        return

    await call.message.answer(
        "Выбери товар:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("edit:"))
async def edit_choose(call: CallbackQuery, state: FSMContext) -> None:
    if not await answer_admin_callback(call):
        return

    product_id = call.data.split(":", maxsplit=1)[1]
    await state.update_data(pid=product_id)
    await state.set_state(Edit.field)

    await call.message.answer(
        "Что изменить?",
        reply_markup=edit_fields_keyboard(),
    )


@router.callback_query(Edit.field, F.data.startswith("f:"))
async def edit_field(call: CallbackQuery, state: FSMContext) -> None:
    if not await answer_admin_callback(call):
        return

    field = call.data.split(":", maxsplit=1)[1]
    await state.update_data(field=field)
    await call.message.answer(
        "Новое значение:",
        reply_markup=cancel_keyboard(),
    )


@router.message(Edit.field, F.text)
async def edit_save(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get("pid")
    field = data.get("field")

    if field not in {"desc", "price"}:
        await msg.answer("Сначала выбери поле для изменения.")
        return

    catalog = load_json(CATALOG_FILE)
    updated = False

    for brands in catalog.values():
        for products in brands.values():
            if product_id in products:
                product = products[product_id]
                product[field] = msg.text
                if field == "desc":
                    product["desc_html"] = msg.html_text
                elif field == "price":
                    product["price_html"] = msg.html_text
                updated = True
                break
        if updated:
            break

    if updated:
        save_json(CATALOG_FILE, catalog)

    await state.clear()
    if updated:
        text = f"{premium_emoji('success', '✅')} Обновлено"
    else:
        text = f"{premium_emoji('error', '❌')} Товар не найден"
    await msg.answer(
        text,
        reply_markup=admin_menu(),
    )


# НОВОСТИ
def news_entities(data: dict) -> list[MessageEntity]:
    return [
        MessageEntity.model_validate(entity)
        for entity in data.get("entities", [])
    ]


async def broadcast_news(
    bot: Bot,
    data: dict,
    photo: str | None = None,
) -> tuple[int, int]:
    users = load_json(USERS_FILE)
    entities = news_entities(data)
    sent = 0
    failed = 0

    for user_id in users:
        try:
            if photo is not None:
                await bot.send_photo(
                    chat_id=int(user_id),
                    photo=photo,
                    caption=data["text"],
                    caption_entities=entities or None,
                    parse_mode=None,
                    reply_markup=assortment_keyboard(),
                )
            else:
                await bot.send_message(
                    chat_id=int(user_id),
                    text=data["text"],
                    entities=entities or None,
                    parse_mode=None,
                    reply_markup=assortment_keyboard(),
                )
            sent += 1
        except Exception:
            # Пользователь мог заблокировать бота или удалить аккаунт.
            failed += 1

    return sent, failed


def news_result_text(sent: int, failed: int) -> str:
    return (
        f"{premium_emoji('success', '✅')} "
        f"<b>Рассылка завершена</b>\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}"
    )


@router.callback_query(F.data == "news")
async def news_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await answer_admin_callback(call):
        return

    await state.clear()
    await state.set_state(News.text)
    await call.message.answer(
        "Отправь текст новости с нужным форматированием:",
        reply_markup=cancel_keyboard(),
    )


@router.message(News.text, F.text)
async def news_text(msg: Message, state: FSMContext) -> None:
    entities = [
        entity.model_dump(mode="json", exclude_none=True)
        for entity in (msg.entities or [])
    ]
    await state.update_data(text=msg.text, entities=entities)
    await state.set_state(News.photo)
    await msg.answer(
        "Отправь фотографию или выбери «Без фото»:",
        reply_markup=news_photo_keyboard(),
    )


@router.message(News.text)
async def news_text_invalid(msg: Message) -> None:
    await msg.answer(
        "Нужно отправить текст новости.",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(News.photo, F.data == "news_without_photo")
async def news_send_without_photo(
    call: CallbackQuery,
    state: FSMContext,
    bot: Bot,
) -> None:
    if not await answer_admin_callback(call):
        return

    data = await state.get_data()
    sent, failed = await broadcast_news(bot, data)
    await state.clear()
    await edit_menu_message(
        call.message,
        text=news_result_text(sent, failed),
        reply_markup=admin_menu(),
    )


@router.message(News.photo, F.photo)
async def news_send(msg: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    sent, failed = await broadcast_news(
        bot,
        data,
        photo=msg.photo[-1].file_id,
    )
    await state.clear()
    await msg.answer(
        news_result_text(sent, failed),
        reply_markup=admin_menu(),
    )


@router.message(News.photo)
async def news_photo_invalid(msg: Message) -> None:
    await msg.answer(
        "Нужно отправить фотографию или выбрать «Без фото».",
        reply_markup=news_photo_keyboard(),
    )


# ЗАПУСК
async def main() -> None:
    if not TOKEN:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    async with Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    ) as bot:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
