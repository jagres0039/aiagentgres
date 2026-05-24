"""Base types untuk gateway abstraction.

`Gateway` adalah abstract interface yang setiap platform implementation harus
penuhi. Agent core gak peduli platform-nya apa — dia cuma terima
`IncomingMessage` dan emit `OutgoingMessage`.

Pattern ini mirror desain Hermes Agent: "gateways" lapisan input/output, dan
"agent" lapisan kognitif yang stateless terhadap transport.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Attachment:
    """File yang ikut ke pesan (foto, voice, dokumen)."""

    kind: str  # "photo" | "voice" | "audio" | "document" | "video"
    file_path: Path
    filename: str | None = None
    mime_type: str | None = None
    caption: str | None = None


@dataclass(frozen=True)
class Button:
    """Tombol inline (Approve/Skip pada approval flow, Yes/No pada trade, dll)."""

    label: str
    payload: str  # opaque callback data — gateway-specific encoding


@dataclass
class IncomingMessage:
    """Pesan masuk yang udah dinormalisasi dari platform native ke format internal."""

    platform: str  # "telegram", "discord", "email", ...
    platform_user_id: str  # chat_id, channel_id, email addr — gateway-specific
    user_id: int  # canonical user identifier (di Telegram = update.effective_user.id)
    username: str | None = None
    text: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    is_callback: bool = False
    callback_data: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    """Pesan keluar yang gateway harus translate balik ke format platform."""

    text: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    buttons: list[list[Button]] = field(default_factory=list)  # rows of buttons
    parse_mode: str | None = None  # "Markdown" | "HTML" | None
    reply_to_message_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


HandlerFn = Callable[[IncomingMessage], Awaitable[None]]


class Gateway(ABC):
    """Abstract platform gateway.

    Subclass harus implement:
      - `start()`: connect ke platform, register native handlers yang translate
        ke `IncomingMessage` lalu call `self._dispatch(msg)`.
      - `stop()`: clean shutdown.
      - `send(target, msg)`: kirim `OutgoingMessage` ke target (platform user id).
    """

    name: str = "abstract"

    def __init__(self) -> None:
        self._handler: HandlerFn | None = None

    def register_handler(self, handler: HandlerFn) -> None:
        """Pasang single async handler yang dipanggil tiap incoming message."""
        self._handler = handler

    async def _dispatch(self, msg: IncomingMessage) -> None:
        """Internal: panggil handler yang udah di-register."""
        if self._handler is None:
            raise RuntimeError(
                f"Gateway {self.name!r} dapet message tapi handler belum di-register."
            )
        await self._handler(msg)

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send(self, target: str, msg: OutgoingMessage) -> None: ...

    def run_forever(self) -> None:
        """Blocking entry-point. Default: start() lalu run sampai SIGINT.

        Subclass yang punya event-loop sendiri (kayak python-telegram-bot
        `run_polling()`) boleh override.
        """
        import asyncio

        async def _main() -> None:
            await self.start()
            try:
                # Idle forever — subclass yang override harus handle ini sendiri.
                while True:
                    await asyncio.sleep(3600)
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            finally:
                await self.stop()

        asyncio.run(_main())
