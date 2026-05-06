"""PayPal Orders API v2 provider (redirect flow)."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from ..base import BasePaymentProvider
from ..models import PaymentRequest, PaymentResult


@dataclass
class PayPalConfig:
    """Configuration for PayPalProvider."""

    client_id: str
    client_secret: str
    environment: Literal["sandbox", "live"] = "sandbox"


class PayPalProvider(BasePaymentProvider):
    """Payment provider for PayPal Orders API v2.

    Implements the *redirect* flow: ``create_payment`` returns a URL to which
    the user is redirected, and ``handle_redirect`` captures the order after
    the user approves it.
    """

    def __init__(self, config: PayPalConfig) -> None:
        self._config = config
        self._base_url = (
            "https://api-m.sandbox.paypal.com"
            if config.environment == "sandbox"
            else "https://api-m.paypal.com"
        )
        self._access_token: str | None = None

    # ------------------------------------------------------------------
    # BasePaymentProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "paypal"

    @property
    def flow(self) -> Literal["redirect"]:
        return "redirect"

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        credentials = base64.b64encode(
            f"{self._config.client_id}:{self._config.client_secret}".encode()
        ).decode()
        response = await client.post(
            f"{self._base_url}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        return response.json()["access_token"]

    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            token = await self._get_access_token(client)
            payload = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": request.order_id or "default",
                        "amount": {
                            "currency_code": request.currency,
                            "value": f"{request.amount:.2f}",
                        },
                        "description": request.description,
                    }
                ],
                "application_context": {
                    "return_url": request.return_url,
                    "cancel_url": request.cancel_url,
                },
            }
            response = await client.post(
                f"{self._base_url}/v2/checkout/orders",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        order_id: str = data["id"]
        redirect_url: str = next(
            (link["href"] for link in data.get("links", []) if link["rel"] == "approve"),
            "",
        )
        return PaymentResult(
            payment_id=order_id,
            status="pending",
            provider=self.name,
            amount=request.amount,
            currency=request.currency,
            redirect_url=redirect_url,
            raw=data,
        )

    async def execute_payment(
        self, payment_id: str, data: dict[str, Any]
    ) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            token = await self._get_access_token(client)
            response = await client.post(
                f"{self._base_url}/v2/checkout/orders/{payment_id}/capture",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={},
            )
            response.raise_for_status()
            result_data = response.json()

        status = result_data.get("status", "")
        return PaymentResult(
            payment_id=payment_id,
            status="completed" if status == "COMPLETED" else "pending",
            provider=self.name,
            raw=result_data,
        )

    async def get_payment(self, payment_id: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            token = await self._get_access_token(client)
            response = await client.get(
                f"{self._base_url}/v2/checkout/orders/{payment_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

        status_map = {
            "CREATED": "pending",
            "SAVED": "pending",
            "APPROVED": "pending",
            "VOIDED": "failed",
            "COMPLETED": "completed",
            "PAYER_ACTION_REQUIRED": "pending",
        }
        raw_status: str = data.get("status", "")
        return PaymentResult(
            payment_id=payment_id,
            status=status_map.get(raw_status, "pending"),  # type: ignore[arg-type]
            provider=self.name,
            raw=data,
        )

    async def refund_payment(
        self, payment_id: str, amount: float | None = None
    ) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            token = await self._get_access_token(client)
            # First, get the order to find the capture ID
            order_response = await client.get(
                f"{self._base_url}/v2/checkout/orders/{payment_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            order_response.raise_for_status()
            order_data = order_response.json()

            capture_id: str = ""
            for unit in order_data.get("purchase_units", []):
                for capture in unit.get("payments", {}).get("captures", []):
                    capture_id = capture["id"]
                    break

            if not capture_id:
                raise ValueError(f"No capture found for order '{payment_id}'.")

            refund_payload: dict[str, Any] = {}
            if amount is not None:
                currency: str = (
                    order_data.get("purchase_units", [{}])[0]
                    .get("amount", {})
                    .get("currency_code", "EUR")
                )
                refund_payload["amount"] = {
                    "value": f"{amount:.2f}",
                    "currency_code": currency,
                }

            response = await client.post(
                f"{self._base_url}/v2/payments/captures/{capture_id}/refund",
                json=refund_payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            refund_data = response.json()

        return PaymentResult(
            payment_id=payment_id,
            status="refunded",
            provider=self.name,
            raw=refund_data,
        )

    async def handle_webhook(
        self, body: Any, headers: dict[str, str]
    ) -> PaymentResult:
        # PayPal uses redirect flow; webhooks are informational.
        event_type: str = body.get("event_type", "") if isinstance(body, dict) else ""
        resource: dict[str, Any] = body.get("resource", {}) if isinstance(body, dict) else {}
        payment_id: str = resource.get("id", "")
        status = "completed" if "COMPLETED" in event_type else "pending"
        return PaymentResult(
            payment_id=payment_id,
            status=status,  # type: ignore[arg-type]
            provider=self.name,
            raw=body if isinstance(body, dict) else {},
        )

    async def handle_redirect(self, query: dict[str, str]) -> PaymentResult:
        token: str = query.get("token", "")
        payer_id: str = query.get("PayerID", "")
        if not token:
            return PaymentResult(
                payment_id="",
                status="failed",
                provider=self.name,
                raw={"error": "missing token"},
            )
        # Capture the order
        return await self.execute_payment(token, {"payer_id": payer_id})
