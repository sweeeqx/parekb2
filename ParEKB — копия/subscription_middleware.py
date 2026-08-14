from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot_utils import (
    ADMIN_ID,
    CHANNEL_ID,
    subscription_keyboard,
)


class SubscriptionMiddleware(BaseMiddleware):
    """Globally blocks bot actions until the user joins the channel."""

    @staticmethod
    def is_subscribed(member: Any) -> bool:
        if member.status in {
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
        }:
            return True

        return (
            member.status == ChatMemberStatus.RESTRICTED
            and bool(getattr(member, "is_member", False))
        )

    async def show_subscription_required(
        self,
        event: Message | CallbackQuery,
        text: str,
    ) -> None:
        if isinstance(event, CallbackQuery):
            if event.data == "check_subscription":
                await event.answer(text, show_alert=True)
                return

            await event.answer()
            if event.message is not None:
                await event.message.answer(
                    text,
                    reply_markup=subscription_keyboard(),
                )
            return

        await event.answer(
            text,
            reply_markup=subscription_keyboard(),
        )

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        user = event.from_user
        if user is None or user.id == ADMIN_ID:
            return await handler(event, data)

        bot: Bot = data["bot"]
        try:
            member = await bot.get_chat_member(
                chat_id=CHANNEL_ID,
                user_id=user.id,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            await self.show_subscription_required(
                event,
                "Не удалось проверить подписку. Попробуйте позже.",
            )
            return None

        if self.is_subscribed(member):
            return await handler(event, data)

        await self.show_subscription_required(
            event,
            "Чтобы пользоваться ботом, подпишитесь на канал "
            "и нажмите «Проверить подписку».",
        )
        return None
