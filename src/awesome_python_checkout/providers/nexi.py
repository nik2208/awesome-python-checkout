"""Nexi eCommerce DispatcherServlet provider."""

from __future__ import annotations

import hashlib
import urllib.parse
from typing import Any, Literal, cast

from pydantic import BaseModel

from ..core.payment import PaymentRequest, PaymentResponse
from ..core.provider import Provider


class NexiConfig(BaseModel):
    """Configuration for Nexi provider."""

    merchant_id: str
    mac_key: str
    environment: Literal["sandbox", "live"] = "sandbox"


class NexiProvider(Provider):
    """Nexi redirect-flow provider using DispatcherServlet integration."""

    sandbox_url = "https://int-ecommerce.nexi.it/ecomm/ecomm/DispatcherServlet"
    live_url = "https://ecommerce.nexi.it/ecomm/ecomm/DispatcherServlet"

    def __init__(self, config: NexiConfig) -> None:
        super().__init__()
        self.config = config
        self.base_url = (
            self.sandbox_url if config.environment == "sandbox" else self.live_url
        )

    @property
    def name(self) -> str:
        return "nexi"

    @property
    def flow(self) -> Literal["redirect"]:
        return "redirect"

    def initiate(self, payment: PaymentRequest) -> PaymentResponse:
        amount_cents = str(int(round(payment.amount * 100)))
        params = {
            "alias": self.config.merchant_id,
            "importo": amount_cents,
            "divisa": payment.currency,
            "codTrans": payment.order_id,
            "url": payment.return_url,
            "url_back": payment.cancel_url,
            "descrizione": payment.description,
        }
        mac_src = (
            f"codTrans={params['codTrans']}"
            f"divisa={params['divisa']}"
            f"importo={params['importo']}"
            f"{self.config.mac_key}"
        )
        params["mac"] = hashlib.sha1(mac_src.encode()).hexdigest()
        return PaymentResponse(
            payment_id=payment.order_id,
            provider=self.name,
            status="pending",
            flow=self.flow,
            redirect_url=f"{self.base_url}?{urllib.parse.urlencode(params)}",
            amount=payment.amount,
            currency=payment.currency,
            raw=params,
        )

    def verify(
        self, payment_id: str, payload: dict[str, Any] | None = None
    ) -> PaymentResponse:
        payload = payload or {}
        esito = payload.get("esito", "")
        status = cast(
            Literal["pending", "completed", "failed", "refunded"],
            "completed" if esito == "OK" else "failed",
        )
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status=status,
            flow=self.flow,
            raw=payload,
        )

    def refund(self, payment_id: str, amount: float | None = None) -> PaymentResponse:
        return PaymentResponse(
            payment_id=payment_id,
            provider=self.name,
            status="refunded",
            flow=self.flow,
            raw={"amount": amount, "note": "Refund managed through Nexi back-office"},
        )
