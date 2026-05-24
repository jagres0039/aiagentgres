"""Telegram gateway implementation.

Translate antara `python-telegram-bot` Updates dan format gateway-neutral.

**Status di Phase 1 PR1**: skeleton + outbound (`send`) functional. Inbound
handler registration sengaja minimal — `main.py` masih punya semua handler
existing-nya (start/clear/memory/handle_message/dll.) dan akan migrate
bertahap ke gateway pattern di Phase 1 PR berikutnya.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from logging_setup import get_logger

if TYPE_CHECKING:
    from telegram import Bot, Update

from gateways.base import (
    Attachment,
    Button,
    Gateway,
    IncomingMessage,
    OutgoingMessage,
)

logger = get_logger(__name__)


def telegram_update_to_incoming(update: Update) -> IncomingMessage | None:
    """Convert python-telegram-bot Update jadi IncomingMessage.

    Return None kalau update bukan jenis yang kita handle (e.g. edited message,
    chat_member update, dll).
    """
    user = update.effective_user
    if user is None:
        return None

    if update.callback_query is not None:
        cb = update.callback_query
        return IncomingMessage(
            platform="telegram",
            platform_user_id=str(cb.message.chat.id) if cb.message else str(user.id),
            user_id=user.id,
            username=user.username,
            text="",
            is_callback=True,
            callback_data=cb.data,
            metadata={"callback_query_id": cb.id},
        )

    msg = update.message
    if msg is None:
        return None

    attachments: list[Attachment] = []
    # Note: we don't auto-download attachments here. Caller decides — gateway
    # bisa expose helper `download(attachment)` di future revision. Untuk
    # sekarang, kita cuma populate metadata-nya.
    if msg.photo:
        attachments.append(
            Attachment(
                kind="photo",
                file_path=__import__("pathlib").Path("/dev/null"),  # placeholder
                filename=None,
                mime_type="image/jpeg",
                caption=msg.caption,
            )
        )
    if msg.voice:
        attachments.append(
            Attachment(
                kind="voice",
                file_path=__import__("pathlib").Path("/dev/null"),
                filename=None,
                mime_type=msg.voice.mime_type,
            )
        )
    if msg.document:
        attachments.append(
            Attachment(
                kind="document",
                file_path=__import__("pathlib").Path("/dev/null"),
                filename=msg.document.file_name,
                mime_type=msg.document.mime_type,
                caption=msg.caption,
            )
        )

    return IncomingMessage(
        platform="telegram",
        platform_user_id=str(msg.chat.id),
        user_id=user.id,
        username=user.username,
        text=msg.text or msg.caption or "",
        attachments=attachments,
        metadata={
            "message_id": msg.message_id,
            "chat_type": msg.chat.type,
        },
    )


class TelegramGateway(Gateway):
    """Telegram gateway. Wrap python-telegram-bot Bot.

    Di PR ini cuma `send()` yang functional — buat outbound message dari
    agent. `start()/stop()` ada tapi gak bikin Application baru; legacy
    handler registration di `main.py` masih jalan.

    Untuk pakai outbound: `TelegramGateway.from_bot(bot)` lalu
    `await gateway.send(chat_id, OutgoingMessage(...))`.
    """

    name = "telegram"

    def __init__(self, token: str | None = None) -> None:
        super().__init__()
        self.token = token
        self._bot: Bot | None = None
        self._app = None

    @classmethod
    def from_bot(cls, bot: Bot) -> TelegramGateway:
        """Adopt existing python-telegram-bot Bot (e.g. dari Application.bot)."""
        gw = cls(token=None)
        gw._bot = bot
        return gw

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            raise RuntimeError(
                "TelegramGateway belum punya Bot — panggil from_bot(app.bot) "
                "atau start() dulu."
            )
        return self._bot

    async def start(self) -> None:
        """Build python-telegram-bot Application kalau token disediakan."""
        if self._bot is not None:
            return  # already adopted
        if self.token is None:
            raise RuntimeError("TelegramGateway perlu token atau Bot pre-built")
        from telegram.ext import ApplicationBuilder

        self._app = ApplicationBuilder().token(self.token).build()
        self._bot = self._app.bot
        await self._app.initialize()
        await self._app.start()
        if self._app.updater:
            await self._app.updater.start_polling()
        logger.info("TelegramGateway started (polling).")

    async def stop(self) -> None:
        if self._app is not None:
            if self._app.updater:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("TelegramGateway stopped.")

    async def send(self, target: str, msg: OutgoingMessage) -> None:
        """Send OutgoingMessage ke chat_id `target`."""
        bot = self.bot
        chat_id = int(target)

        keyboard = _buttons_to_inline_keyboard(msg.buttons) if msg.buttons else None

        # Kirim attachments dulu (kalau ada), lalu text.
        for att in msg.attachments:
            await _send_attachment(bot, chat_id, att, parse_mode=msg.parse_mode)

        if msg.text:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=msg.text,
                    parse_mode=msg.parse_mode,
                    reply_markup=keyboard,
                    reply_to_message_id=msg.reply_to_message_id,
                )
            except Exception:
                logger.exception("Failed to send_message chat_id=%s", chat_id)


def _buttons_to_inline_keyboard(rows: list[list[Button]]):
    """Convert generic buttons ke telegram InlineKeyboardMarkup."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    kb = [
        [InlineKeyboardButton(b.label, callback_data=b.payload) for b in row]
        for row in rows
    ]
    return InlineKeyboardMarkup(kb)


async def _send_attachment(bot: Bot, chat_id: int, att: Attachment, parse_mode: str | None):
    """Helper buat kirim 1 attachment via Bot API."""
    path = str(att.file_path)
    if att.kind == "photo":
        with open(path, "rb") as f:
            await bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption=att.caption,
                parse_mode=parse_mode,
            )
    elif att.kind in ("voice", "audio"):
        with open(path, "rb") as f:
            await bot.send_voice(chat_id=chat_id, voice=f, caption=att.caption)
    elif att.kind == "video":
        with open(path, "rb") as f:
            await bot.send_video(chat_id=chat_id, video=f, caption=att.caption)
    else:  # document fallback
        with open(path, "rb") as f:
            await bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=att.filename,
                caption=att.caption,
            )
