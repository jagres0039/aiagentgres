"""Tests untuk gateway abstraction."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from gateways.base import (
    Attachment,
    Button,
    Gateway,
    IncomingMessage,
    OutgoingMessage,
)
from gateways.stub import StubGateway


def test_attachment_dataclass():
    a = Attachment(kind="photo", file_path=Path("/tmp/x.jpg"))
    assert a.kind == "photo"
    assert a.file_path == Path("/tmp/x.jpg")


def test_outgoing_message_defaults():
    o = OutgoingMessage(text="halo")
    assert o.text == "halo"
    assert o.attachments == []
    assert o.buttons == []


def test_incoming_message_defaults():
    m = IncomingMessage(platform="x", platform_user_id="1", user_id=1)
    assert m.text == ""
    assert m.attachments == []
    assert m.is_callback is False


@pytest.mark.asyncio
async def test_stub_gateway_lifecycle():
    gw = StubGateway()
    assert gw._started is False
    await gw.start()
    assert gw._started is True
    await gw.stop()
    assert gw._stopped is True


@pytest.mark.asyncio
async def test_stub_gateway_send():
    gw = StubGateway()
    msg = OutgoingMessage(text="halo bro")
    await gw.send("42", msg)
    assert len(gw.sent) == 1
    assert gw.sent[0] == ("42", msg)


@pytest.mark.asyncio
async def test_stub_gateway_dispatch():
    gw = StubGateway()
    received: list[IncomingMessage] = []

    async def handler(msg: IncomingMessage) -> None:
        received.append(msg)

    gw.register_handler(handler)
    incoming = IncomingMessage(
        platform="stub", platform_user_id="42", user_id=42, text="halo"
    )
    await gw.feed(incoming)
    assert len(received) == 1
    assert received[0].text == "halo"


@pytest.mark.asyncio
async def test_dispatch_without_handler_raises():
    gw = StubGateway()
    incoming = IncomingMessage(platform="stub", platform_user_id="42", user_id=42)
    with pytest.raises(RuntimeError):
        await gw.feed(incoming)


def test_gateway_is_abstract():
    """Gak bisa instantiate Gateway langsung."""
    with pytest.raises(TypeError):
        Gateway()  # type: ignore[abstract]


def test_button_dataclass():
    b = Button(label="OK", payload="ok_payload")
    assert b.label == "OK"
    assert b.payload == "ok_payload"


@pytest.mark.asyncio
async def test_stub_multiple_messages():
    gw = StubGateway()
    for i in range(5):
        await gw.send(str(i), OutgoingMessage(text=f"msg {i}"))
    assert len(gw.sent) == 5
    assert gw.sent[3][0] == "3"
    assert gw.sent[3][1].text == "msg 3"
