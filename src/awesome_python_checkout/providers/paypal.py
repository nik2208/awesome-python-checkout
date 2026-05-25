"""PayPal Orders API v2 provider."""

from __future__ import annotations

from typing import Any, Literal, cast

import requests
from pydantic import BaseModel

from ..core.payment import PaymentRequest, PaymentResponse
from ..core.provider import Provider


class PayPalConfig(BaseModel):
    """Configuration for PayPal provider."""

    client_id: str
    client_secret: str
    environment: Literal["sandbox", "live"] = "sandbox"


class PayPalProvider(Provider):
    """PayPal redirect-flow provider."""

    def __init__(
        self, config: PayPalConfig, session: requests.Session | None = None
    ) -> None:
        super().__init__()
        self.config = config
        self.session = session or requests.Session()
        self.base_url = (
            "https://api-m.sandbox.paypal.com"
            if config.environment == "sandbox"
            else "https://api-m.paypal.com"
        )

    @property
    def name(self) -> str:
        return "paypal"

    @property
    def flow(self) -> Literal["redirect"]:
        return "redirect"

    def initiate(self, payment: PaymentRequest) -> PaymentResponse:
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": payment.order_id,
                    "amount": {
                        "currency_code": payment.currency,
                        "value": f"{payment.amount:.2f}",
                    },
                    "description": payment.description,
                }
            ],
            "application_context": {
                "return_url": payment.return_url,
                "cancel_url": payment.cancel_url,
            },
        }
        response = self.session.request(
            "POST", f"{self.base_url}/v2/checkout/orders", json=payload, timeout=30
        )
        response.raise_for_status()
        body = response.json()
        redirect_url = next(
            (
                link["href"]
                for link in body.get("links", [])
                if link.get("rel") == "approve"
            ),
            None,
        )
        return PaymentResponse(
            payment_id=body.get("id", payment.order_id),
            provider=self.name,
            status="pending",
            flow=self.flow,
            redirect_url=redirect_url,
            amount=payment.amount,
            currency=payment.currency,
            raw=body,
        )

    def verify(
        self, payment_id: str, payload: dict[str, Any] | None = None
    ) -> PaymentResponse:
        response = self.session.request(
            "GET", f"{self.base_url}/v2/checkout/orders/{payment_id}", timeout=30
        )
        response.raise_for_status()
        body = response.json()
        status_map = {
            "COMPLETED": "completed",
            "APPROVED": "pending",
            "CREATED": "pending",
            "VOIDED": "failed",
        }
        mapped_status = cast(
            Literal["pending", "completed", "failed", "refunded"],
            status_map.get(body.get("status", ""), "pending"),
        )
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status=mapped_status,
            flow=self.flow,
            raw=body,
        )

    def refund(self, payment_id: str, amount: float | None = None) -> PaymentResponse:
        payload: dict[str, Any] = {}
        if amount is not None:
            payload["amount"] = {"value": f"{amount:.2f}", "currency_code": "EUR"}
        response = self.session.request(
            "POST",
            f"{self.base_url}/v2/payments/captures/{payment_id}/refund",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status="refunded",
            flow=self.flow,
            raw=response.json(),
        )
