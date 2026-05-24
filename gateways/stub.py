"""Stub gateway buat testing — gak connect kemana-mana, in-memory only.

Useful buat unit tests, debugging, atau dry-run agent tanpa real Telegram.
"""

from __future__ import annotations

from gateways.base import Gateway, IncomingMessage, OutgoingMessage


class StubGateway(Gateway):
    """In-memory gateway. Sent messages di-record ke `self.sent` buat assert di test."""

    name = "stub"

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[str, OutgoingMessage]] = []
        self._started = False
        self._stopped = False

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._stopped = True

    async def send(self, target: str, msg: OutgoingMessage) -> None:
        self.sent.append((target, msg))

    async def feed(self, msg: IncomingMessage) -> None:
        """Inject incoming message — dispatch ke handler yang udah register."""
        await self._dispatch(msg)
