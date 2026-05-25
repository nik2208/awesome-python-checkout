from __future__ import annotations

from typing import Any, Literal

from awesome_python_checkout import (
    Checkout,
    PaymentRequest,
    PaymentResponse,
    Provider,
    WebhookHandler,
    WebhookPayload,
)


class WebhookProvider(Provider):
    @property
    def name(self) -> str:
        return "webhook"

    @property
    def flow(self) -> Literal["webhook"]:
        return "webhook"

    def initiate(self, payment: PaymentRequest) -> PaymentResponse:
        return PaymentResponse(
            payment_id="w-1", provider=self.name, status="pending", flow=self.flow
        )

    def verify(
        self, payment_id: str, payload: dict[str, Any] | None = None
    ) -> PaymentResponse:
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status="completed",
            flow=self.flow,
        )

    def refund(self, payment_id: str, amount: float | None = None) -> PaymentResponse:
        return PaymentResponse(
            payment_id=payment_id, provider=self.name, status="refunded", flow=self.flow
        )


def test_webhook_handler_process() -> None:
    checkout = Checkout().register_provider(WebhookProvider())
    handler = WebhookHandler(checkout)
    payload = WebhookPayload(
        event="payment.completed",
        payment_id="w-1",
        provider="webhook",
        status="completed",
    )
    result = handler.process("webhook", payload)
    assert result.payment_id == "w-1"
