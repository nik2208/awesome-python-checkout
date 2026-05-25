"""Satispay Business API v1 provider."""

from __future__ import annotations

from typing import Any, Literal, cast

import requests
from pydantic import BaseModel

from ..core.payment import PaymentRequest, PaymentResponse
from ..core.provider import Provider


class SatispayConfig(BaseModel):
    """Configuration for Satispay provider."""

    key_id: str
    private_key: str
    environment: Literal["sandbox", "live"] = "sandbox"


class SatispayProvider(Provider):
    """Satispay webhook-flow provider."""

    def __init__(
        self, config: SatispayConfig, session: requests.Session | None = None
    ) -> None:
        super().__init__()
        self.config = config
        self.session = session or requests.Session()
        self.base_url = (
            "https://staging.authservices.satispay.com"
            if config.environment == "sandbox"
            else "https://authservices.satispay.com"
        )

    @property
    def name(self) -> str:
        return "satispay"

    @property
    def flow(self) -> Literal["webhook"]:
        return "webhook"

    def initiate(self, payment: PaymentRequest) -> PaymentResponse:
        payload = {
            "amount_unit": int(round(payment.amount * 100)),
            "currency": payment.currency,
            "external_code": payment.order_id,
            "redirect_url": payment.return_url,
            "metadata": payment.metadata,
        }
        response = self.session.request(
            "POST", f"{self.base_url}/g_business/v1/payments", json=payload, timeout=30
        )
        response.raise_for_status()
        body = response.json()
        return PaymentResponse(
            payment_id=body.get("id", payment.order_id),
            provider=self.name,
            status="pending",
            flow=self.flow,
            redirect_url=body.get("redirect_url"),
            amount=payment.amount,
            currency=payment.currency,
            raw=body,
        )

    def verify(
        self, payment_id: str, payload: dict[str, Any] | None = None
    ) -> PaymentResponse:
        if payload is None:
            response = self.session.request(
                "GET",
                f"{self.base_url}/g_business/v1/payments/{payment_id}",
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        status_map = {
            "ACCEPTED": "completed",
            "PENDING": "pending",
            "CANCELED": "failed",
        }
        mapped_status = cast(
            Literal["pending", "completed", "failed", "refunded"],
            status_map.get(payload.get("status", "PENDING"), "pending"),
        )
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status=mapped_status,
            flow=self.flow,
            raw=payload,
        )

    def refund(self, payment_id: str, amount: float | None = None) -> PaymentResponse:
        payload: dict[str, Any] = {"payment_id": payment_id}
        if amount is not None:
            payload["amount_unit"] = int(round(amount * 100))
        response = self.session.request(
            "POST", f"{self.base_url}/g_business/v1/refunds", json=payload, timeout=30
        )
        response.raise_for_status()
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status="refunded",
            flow=self.flow,
            raw=response.json(),
        )
