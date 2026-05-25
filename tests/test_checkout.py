from __future__ import annotations

from typing import Any, Literal

import pytest

from awesome_python_checkout import (
    Checkout,
    PaymentRequest,
    PaymentResponse,
    Provider,
    ProviderNotRegisteredError,
)


class DummyProvider(Provider):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def flow(self) -> Literal["direct"]:
        return "direct"

    def initiate(self, payment: PaymentRequest) -> PaymentResponse:
        return PaymentResponse(
            payment_id="p-1", provider=self.name, status="pending", flow=self.flow
        )

    def verify(
        self, payment_id: str, payload: dict[str, Any] | None = None
    ) -> PaymentResponse:
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status="completed",
            flow=self.flow,
            raw=payload or {},
        )

    def refund(self, payment_id: str, amount: float | None = None) -> PaymentResponse:
        return PaymentResponse(
            payment_id=payment_id, provider=self.name, status="refunded", flow=self.flow
        )


def test_register_and_create_payment() -> None:
    checkout = Checkout().register_provider(DummyProvider())
    result = checkout.create_payment(
        "dummy", PaymentRequest(amount=10.0, order_id="o-1")
    )
    assert result.status == "pending"


def test_verify_emits_completed_event() -> None:
    checkout = Checkout().register_provider(DummyProvider())
    events: list[str] = []
    checkout.on("payment.completed", lambda _: events.append("completed"))
    checkout.verify_payment("dummy", "p-1")
    assert events == ["completed"]


def test_unknown_provider_error() -> None:
    checkout = Checkout()
    with pytest.raises(ProviderNotRegisteredError):
        checkout.get_provider("missing")
