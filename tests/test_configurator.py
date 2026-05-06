"""Tests for CheckoutConfigurator."""

from __future__ import annotations

from typing import Any, Literal
from unittest.mock import AsyncMock

import pytest

from awesome_python_checkout import (
    BasePaymentProvider,
    CheckoutConfigurator,
    InMemoryTransactionStore,
    PaymentRequest,
    PaymentResult,
)


class _DummyProvider(BasePaymentProvider):
    """Minimal provider for testing the configurator."""

    def __init__(self, name: str = "dummy") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def flow(self) -> Literal["redirect"]:
        return "redirect"

    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            payment_id="pay-001",
            status="pending",
            provider=self.name,
            amount=request.amount,
            currency=request.currency,
            redirect_url="https://example.com/pay",
        )

    async def execute_payment(self, payment_id: str, data: dict[str, Any]) -> PaymentResult:
        return PaymentResult(
            payment_id=payment_id,
            status="completed",
            provider=self.name,
        )

    async def get_payment(self, payment_id: str) -> PaymentResult:
        return PaymentResult(
            payment_id=payment_id,
            status="completed",
            provider=self.name,
        )

    async def refund_payment(self, payment_id: str, amount: float | None = None) -> PaymentResult:
        return PaymentResult(
            payment_id=payment_id,
            status="refunded",
            provider=self.name,
        )

    async def handle_webhook(self, body: Any, headers: dict[str, str]) -> PaymentResult:
        return PaymentResult(
            payment_id="pay-001",
            status="completed",
            provider=self.name,
        )

    async def handle_redirect(self, query: dict[str, str]) -> PaymentResult:
        return PaymentResult(
            payment_id=query.get("token", ""),
            status="completed",
            provider=self.name,
        )


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


def test_register_provider_chainable():
    checkout = CheckoutConfigurator()
    result = checkout.register_provider(_DummyProvider())
    assert result is checkout


def test_get_unknown_provider_raises():
    checkout = CheckoutConfigurator()
    with pytest.raises(ValueError, match="not registered"):
        checkout._get_provider("unknown")


def test_register_multiple_providers():
    checkout = CheckoutConfigurator()
    checkout.register_provider(_DummyProvider("alpha"))
    checkout.register_provider(_DummyProvider("beta"))
    assert "alpha" in checkout._providers
    assert "beta" in checkout._providers


# ---------------------------------------------------------------------------
# Event system tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_subscription_and_emit():
    checkout = CheckoutConfigurator()
    received: list[Any] = []
    checkout.on("payment.created", lambda payload: received.append(payload))
    await checkout.emit("payment.created", {"provider": "dummy", "paymentId": "x"})
    assert len(received) == 1
    assert received[0]["paymentId"] == "x"


@pytest.mark.asyncio
async def test_event_on_chainable():
    checkout = CheckoutConfigurator()
    result = checkout.on("payment.created", lambda _: None)
    assert result is checkout


@pytest.mark.asyncio
async def test_create_payment_fires_event():
    checkout = CheckoutConfigurator()
    checkout.register_provider(_DummyProvider())
    events: list[str] = []
    checkout.on("payment.created", lambda _: events.append("created"))
    await checkout.create_payment("dummy", PaymentRequest(amount=10.0, currency="EUR"))
    assert "created" in events


@pytest.mark.asyncio
async def test_execute_payment_fires_completed_event():
    checkout = CheckoutConfigurator()
    checkout.register_provider(_DummyProvider())
    events: list[str] = []
    checkout.on("payment.completed", lambda _: events.append("completed"))
    await checkout.execute_payment("dummy", "pay-001", {})
    assert "completed" in events


@pytest.mark.asyncio
async def test_refund_payment_fires_event():
    checkout = CheckoutConfigurator()
    checkout.register_provider(_DummyProvider())
    events: list[str] = []
    checkout.on("payment.refunded", lambda _: events.append("refunded"))
    await checkout.refund_payment("dummy", "pay-001")
    assert "refunded" in events


@pytest.mark.asyncio
async def test_handle_webhook_fires_events():
    checkout = CheckoutConfigurator()
    checkout.register_provider(_DummyProvider())
    events: list[str] = []
    checkout.on("webhook.received", lambda _: events.append("webhook"))
    checkout.on("payment.completed", lambda _: events.append("completed"))
    await checkout.handle_webhook("dummy", {}, {})
    assert "webhook" in events
    assert "completed" in events


@pytest.mark.asyncio
async def test_handle_redirect_fires_completed_event():
    checkout = CheckoutConfigurator()
    checkout.register_provider(_DummyProvider())
    events: list[str] = []
    checkout.on("payment.completed", lambda _: events.append("completed"))
    await checkout.handle_redirect("dummy", {"token": "pay-001"})
    assert "completed" in events


# ---------------------------------------------------------------------------
# InMemoryTransactionStore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_store_save_get_delete():
    from awesome_python_checkout import TransactionData

    store = InMemoryTransactionStore()
    tx = TransactionData(
        payment_id="p1",
        order_id="o1",
        amount=9.99,
        currency="EUR",
        provider="dummy",
    )
    await store.save("key1", tx)
    retrieved = await store.get("key1")
    assert retrieved is not None
    assert retrieved.payment_id == "p1"

    await store.delete("key1")
    assert await store.get("key1") is None


@pytest.mark.asyncio
async def test_in_memory_store_missing_key_returns_none():
    store = InMemoryTransactionStore()
    assert await store.get("nonexistent") is None
