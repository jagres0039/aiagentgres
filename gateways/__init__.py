"""Gateway abstraction package.

Tujuan: pisahin "platform messaging" dari "agent core". Telegram dulu, terus
nanti Discord, Email, Slack, Matrix, dll. Cukup tambahin `gateways/<nama>.py`
yang inherit `Gateway` ABC.
"""

from gateways.base import (
    Attachment,
    Button,
    Gateway,
    IncomingMessage,
    OutgoingMessage,
)

__all__ = [
    "Attachment",
    "Button",
    "Gateway",
    "IncomingMessage",
    "OutgoingMessage",
]
